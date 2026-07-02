"""Strategy A — TrendBreak: structure breaks with the trend.

From the build plan's "Identify a Down-Trend / Trade Explanation" chart,
long side (spot — shorts disabled): in a 4h uptrend (EMA50 > EMA200), enter
when price breaks above the previous 20-bar swing high on >=1.5x average
volume. The breakout must be a fresh cross, not a market already drifting
above the level — mid-range noise never qualifies.

Exits: fixed 2xATR initial stop (on-exchange), take-profit at 1:2 RR, and
the stop starts trailing at 2xATR under the close once the trade is 1R in
profit.

Signal math lives in module-level pure functions (pandas only) so
tests/test_strategies.py can exercise it without freqtrade installed.
"""

from datetime import datetime
from typing import Optional

from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, merge_informative_pair, stoploss_from_absolute

SWING_BARS = 20        # lookback defining the prior swing high
VOL_MULT = 1.5         # breakout volume vs 20-bar mean
ATR_PERIOD = 14
ATR_STOP_MULT = 2.0    # initial + trailing stop distance
RISK_PER_TRADE = 0.01  # 1% of account per trade
RR_TARGET = 2.0        # take profit at 2x initial risk
TRAIL_AFTER_R = 1.0    # start trailing once profit >= 1x initial risk


def add_features(df: DataFrame) -> DataFrame:
    """Swing levels, volume mean and ATR. Needs: close, high, low, volume."""
    df["swing_high"] = df["high"].shift(1).rolling(SWING_BARS).max()
    df["swing_low"] = df["low"].shift(1).rolling(SWING_BARS).min()
    df["vol_mean20"] = df["volume"].rolling(20).mean()

    prev_close = df["close"].shift(1)
    tr = (df["high"] - df["low"]).combine((df["high"] - prev_close).abs(), max)
    tr = tr.combine((df["low"] - prev_close).abs(), max)
    df["atr"] = tr.rolling(ATR_PERIOD).mean()
    return df


def entry_signal(df: DataFrame) -> "DataFrame":
    """Fresh close above the prior swing high, volume confirm, 4h uptrend."""
    breakout = (df["close"] > df["swing_high"]) & (
        df["close"].shift(1) <= df["swing_high"].shift(1)
    )
    return (
        breakout
        & (df["volume"] > VOL_MULT * df["vol_mean20"])
        & (df["trend_up_4h"] > 0)
    )


def exit_signal(df: DataFrame) -> "DataFrame":
    """Structure failure: close back below the prior swing low."""
    return (df["close"] < df["swing_low"]) & (
        df["close"].shift(1) >= df["swing_low"].shift(1)
    )


class TrendBreakStrategy(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False  # spot
    process_only_new_candles = True
    startup_candle_count = 60

    # Disaster backstop; the working stop is custom_stoploss.
    stoploss = -0.08
    use_custom_stoploss = True
    minimal_roi = {}

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": True,
    }

    @property
    def protections(self):
        return [
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 24,
                "trade_limit": 3,
                "stop_duration_candles": 24,
                "max_allowed_drawdown": 0.03,
            },
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 24,
                "trade_limit": 2,
                "stop_duration_candles": 12,
                "only_per_pair": True,
            },
            {"method": "CooldownPeriod", "stop_duration_candles": 2},
        ]

    def informative_pairs(self):
        if not self.dp:
            return []
        return [(pair, "4h") for pair in self.dp.current_whitelist()]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        inf = self.dp.get_pair_dataframe(metadata["pair"], "4h")
        inf["ema50"] = inf["close"].ewm(span=50, adjust=False).mean()
        inf["ema200"] = inf["close"].ewm(span=200, adjust=False).mean()
        inf["trend_up"] = (inf["ema50"] > inf["ema200"]).astype(int)
        dataframe = merge_informative_pair(
            dataframe, inf[["date", "trend_up"]], self.timeframe, "4h", ffill=True
        )
        return add_features(dataframe)

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[entry_signal(dataframe), ["enter_long", "enter_tag"]] = (1, "swing_break")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[exit_signal(dataframe), ["exit_long", "exit_tag"]] = (1, "structure_failed")
        return dataframe

    # --- Risk management -------------------------------------------------

    def custom_stake_amount(self, pair: str, current_time: datetime,
                            current_rate: float, proposed_stake: float,
                            min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str],
                            side: str, **kwargs) -> float:
        """Size so a 2xATR stop costs ~1% of the account."""
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df.empty or not df["atr"].notna().any():
            return proposed_stake
        stop_fraction = ATR_STOP_MULT * df["atr"].iloc[-1] / current_rate
        if stop_fraction <= 0:
            return proposed_stake
        stake = (self.wallets.get_total_stake_amount() * RISK_PER_TRADE) / stop_fraction
        stake = min(stake, max_stake)
        if min_stake:
            stake = max(stake, min_stake)
        return stake

    def order_filled(self, pair: str, trade: Trade, order, current_time, **kwargs):
        """Pin ATR at entry: fixes the initial stop and the 1R/2R levels."""
        if order.ft_order_side == trade.entry_side and trade.get_custom_data("entry_atr") is None:
            df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if not df.empty and df["atr"].notna().any():
                trade.set_custom_data("entry_atr", float(df["atr"].iloc[-1]))

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool, **kwargs) -> Optional[float]:
        """Fixed 2xATR stop from entry; trails under close after +1R."""
        entry_atr = trade.get_custom_data("entry_atr")
        if not entry_atr:
            return None
        initial_risk = ATR_STOP_MULT * entry_atr / trade.open_rate

        if current_profit >= TRAIL_AFTER_R * initial_risk:
            df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if not df.empty and df["atr"].notna().any():
                last = df.iloc[-1]
                return stoploss_from_absolute(
                    last["close"] - ATR_STOP_MULT * last["atr"],
                    current_rate, is_short=trade.is_short, leverage=trade.leverage,
                )

        return stoploss_from_absolute(
            trade.open_rate - ATR_STOP_MULT * entry_atr,
            current_rate, is_short=trade.is_short, leverage=trade.leverage,
        )

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs):
        """Take profit at RR_TARGET x initial risk."""
        entry_atr = trade.get_custom_data("entry_atr")
        if entry_atr:
            initial_risk = ATR_STOP_MULT * entry_atr / trade.open_rate
            if current_profit >= RR_TARGET * initial_risk:
                return "rr_2_to_1"
        return None

"""Cross-asset lead-lag strategy: BTC + ETH momentum predicts SOL.

Majors move first, high-beta alts catch up. Enter SOL long when BTC and ETH
have both pumped over the last few hours while SOL still lags their average
move, in a 4h uptrend, with volume confirmation. Exit on 1:2 risk-reward,
a 2x ATR trailing stop, or a hard momentum flip in the majors.

Signal math lives in module-level pure functions (pandas only, no TA-Lib)
so tests/test_strategies.py can exercise it without a running bot.
"""

from datetime import datetime
from typing import Optional

from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, merge_informative_pair, stoploss_from_absolute

BTC_RET_MIN = 0.010   # BTC 4-bar return to call it a pump
ETH_RET_MIN = 0.010   # ETH 4-bar return
LAG_MIN = 0.005       # SOL must trail the majors' avg move by this much
VOL_MULT = 1.2        # volume vs 20-bar mean
MOM_BARS = 4          # lookback bars for momentum
ATR_PERIOD = 14
ATR_STOP_MULT = 2.0   # stop distance = 2 x ATR
RISK_PER_TRADE = 0.01 # 1% of account per trade
RR_TARGET = 2.0       # take profit at 2x initial risk


def add_features(df: DataFrame) -> DataFrame:
    """Momentum, lag, volume and ATR features. Needs columns: close, high,
    low, volume, btc_close, eth_close."""
    df["btc_ret"] = df["btc_close"].pct_change(MOM_BARS)
    df["eth_ret"] = df["eth_close"].pct_change(MOM_BARS)
    df["sol_ret"] = df["close"].pct_change(MOM_BARS)
    df["lag_gap"] = (df["btc_ret"] + df["eth_ret"]) / 2 - df["sol_ret"]
    df["vol_mean20"] = df["volume"].rolling(20).mean()

    prev_close = df["close"].shift(1)
    tr = (df["high"] - df["low"]).combine((df["high"] - prev_close).abs(), max)
    tr = tr.combine((df["low"] - prev_close).abs(), max)
    df["atr"] = tr.rolling(ATR_PERIOD).mean()
    return df


def entry_signal(df: DataFrame) -> "DataFrame":
    """Boolean Series: majors pumping, SOL lagging, uptrend, volume confirm."""
    return (
        (df["btc_ret"] > BTC_RET_MIN)
        & (df["eth_ret"] > ETH_RET_MIN)
        & (df["lag_gap"] > LAG_MIN)
        & (df["trend_up_4h"] > 0)
        & (df["volume"] > VOL_MULT * df["vol_mean20"])
    )


def exit_signal(df: DataFrame) -> "DataFrame":
    """Bail out when both majors flip hard negative — the lag thesis is dead."""
    return (df["btc_ret"] < -BTC_RET_MIN) & (df["eth_ret"] < -ETH_RET_MIN)


class SolCrossSignalStrategy(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False
    process_only_new_candles = True
    startup_candle_count = 60  # 4h EMAs are computed on the 4h informative df

    # Disaster backstop only — the working stop is custom_stoploss (2x ATR).
    stoploss = -0.08
    use_custom_stoploss = True
    minimal_roi = {}  # exits: RR target, ATR trail, momentum flip

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": True,
    }

    @property
    def protections(self):
        return [
            # Daily kill switch: stop after -3% drawdown across recent trades.
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 24,
                "trade_limit": 3,
                "stop_duration_candles": 24,
                "max_allowed_drawdown": 0.03,
            },
            # Pair cooldown after 2 stoplosses in a day.
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
        return [("BTC/USD", "1h"), ("ETH/USD", "1h"), ("SOL/USD", "4h")]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Majors, same timeframe: plain date-merge is candle-aligned.
        for pair, col in (("BTC/USD", "btc_close"), ("ETH/USD", "eth_close")):
            inf = self.dp.get_pair_dataframe(pair, self.timeframe)
            inf = inf[["date", "close"]].rename(columns={"close": col})
            dataframe = dataframe.merge(inf, on="date", how="left")

        # 4h trend filter, shifted properly by merge_informative_pair.
        sol4h = self.dp.get_pair_dataframe("SOL/USD", "4h")
        sol4h["ema50"] = sol4h["close"].ewm(span=50, adjust=False).mean()
        sol4h["ema200"] = sol4h["close"].ewm(span=200, adjust=False).mean()
        sol4h["trend_up"] = (sol4h["ema50"] > sol4h["ema200"]).astype(int)
        dataframe = merge_informative_pair(
            dataframe, sol4h[["date", "trend_up"]], self.timeframe, "4h", ffill=True
        )

        return add_features(dataframe)

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[entry_signal(dataframe), ["enter_long", "enter_tag"]] = (1, "btc_eth_lead_lag")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[exit_signal(dataframe), ["exit_long", "exit_tag"]] = (1, "majors_flipped")
        return dataframe

    # --- Risk management -------------------------------------------------

    def custom_stake_amount(self, pair: str, current_time: datetime,
                            current_rate: float, proposed_stake: float,
                            min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str],
                            side: str, **kwargs) -> float:
        """Size so that a 2xATR stop loses ~1% of the account."""
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df.empty or not df["atr"].notna().any():
            return proposed_stake
        atr = df["atr"].iloc[-1]
        stop_fraction = ATR_STOP_MULT * atr / current_rate
        if stop_fraction <= 0:
            return proposed_stake
        account = self.wallets.get_total_stake_amount()
        stake = (account * RISK_PER_TRADE) / stop_fraction
        stake = min(stake, max_stake)
        if min_stake:
            stake = max(stake, min_stake)
        return stake

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool, **kwargs) -> Optional[float]:
        """Trailing 2xATR stop below the latest close."""
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df.empty:
            return None
        last = df.iloc[-1]
        if not last.notna().get("atr", False):
            return None
        return stoploss_from_absolute(
            last["close"] - ATR_STOP_MULT * last["atr"],
            current_rate, is_short=trade.is_short, leverage=trade.leverage,
        )

    def order_filled(self, pair: str, trade: Trade, order, current_time, **kwargs):
        """Pin the ATR at entry so the RR target stays fixed for the trade."""
        if order.ft_order_side == trade.entry_side and trade.get_custom_data("entry_atr") is None:
            df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if not df.empty and df["atr"].notna().any():
                trade.set_custom_data("entry_atr", float(df["atr"].iloc[-1]))

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs):
        """Take profit at RR_TARGET x the initial (2xATR) risk."""
        entry_atr = trade.get_custom_data("entry_atr")
        if entry_atr:
            initial_risk = ATR_STOP_MULT * entry_atr / trade.open_rate
            if current_profit >= RR_TARGET * initial_risk:
                return "rr_2_to_1"
        return None

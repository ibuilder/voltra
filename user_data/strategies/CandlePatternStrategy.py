"""Strategy B — CandlePattern: reversal candles at meaningful levels.

From the candlestick cheat-sheet pin, with the plan's core discipline:
patterns mid-range are noise. A bullish reversal candle (hammer, bullish
engulfing, or morning star) only counts if it prints inside the 38.2–61.8%
Fibonacci retracement zone of the last swing (or at its support low), in a
4h uptrend, and the NEXT candle must confirm by closing above the pattern
candle's high. Entry happens on the confirmation candle — no lookahead.

Long-only (spot). Exits: same ATR/RR framework as the other strategies.

Signal math is module-level pure pandas so tests run without freqtrade.
"""

from datetime import datetime
from typing import Optional

from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import (
    DecimalParameter,
    IStrategy,
    merge_informative_pair,
    stoploss_from_absolute,
)

SWING_BARS = 40        # lookback defining the swing for the fib zone
FIB_LOW, FIB_HIGH = 0.382, 0.618
ZONE_TOLERANCE = 0.005  # fib zone widened by 0.5% each side
ATR_PERIOD = 14
ATR_STOP_MULT = 2.0
RISK_PER_TRADE = 0.01
RR_TARGET = 2.0
TRAIL_AFTER_R = 1.0


def _body(df: DataFrame):
    return (df["close"] - df["open"]).abs()


def hammer(df: DataFrame) -> "DataFrame":
    """Small body at the top, lower wick >= 2x body, little upper wick."""
    body = _body(df)
    lower_wick = df[["open", "close"]].min(axis=1) - df["low"]
    upper_wick = df["high"] - df[["open", "close"]].max(axis=1)
    rng = (df["high"] - df["low"]).replace(0, float("nan"))
    return (lower_wick >= 2 * body) & (upper_wick <= 0.3 * body + 0.1 * rng)


def bullish_engulfing(df: DataFrame) -> "DataFrame":
    prev_red = df["close"].shift(1) < df["open"].shift(1)
    green = df["close"] > df["open"]
    engulfs = (df["close"] >= df["open"].shift(1)) & (df["open"] <= df["close"].shift(1))
    return prev_red & green & engulfs & (_body(df) > _body(df).shift(1))


def morning_star(df: DataFrame) -> "DataFrame":
    """Red candle, small-body gap-ish middle, green close into first body."""
    first_red = df["close"].shift(2) < df["open"].shift(2)
    small_mid = _body(df).shift(1) < 0.5 * _body(df).shift(2)
    third_green = df["close"] > df["open"]
    recovers = df["close"] > (df["open"].shift(2) + df["close"].shift(2)) / 2
    return first_red & small_mid & third_green & recovers


def add_features(df: DataFrame) -> DataFrame:
    """Fib zone of the last swing, patterns, ATR.
    Needs: open, high, low, close, volume."""
    df["swing_high"] = df["high"].shift(1).rolling(SWING_BARS).max()
    df["swing_low"] = df["low"].shift(1).rolling(SWING_BARS).min()

    swing_range = df["swing_high"] - df["swing_low"]
    df["fib_zone_top"] = df["swing_high"] - FIB_LOW * swing_range
    df["fib_zone_bottom"] = df["swing_high"] - FIB_HIGH * swing_range

    df["pattern"] = (hammer(df) | bullish_engulfing(df) | morning_star(df)).astype(int)
    df["pattern_high"] = df["high"]  # confirmation reference for the next bar

    prev_close = df["close"].shift(1)
    tr = (df["high"] - df["low"]).combine((df["high"] - prev_close).abs(), max)
    tr = tr.combine((df["low"] - prev_close).abs(), max)
    df["atr"] = tr.rolling(ATR_PERIOD).mean()
    return df


def entry_signal(df: DataFrame, zone_tolerance: float = ZONE_TOLERANCE) -> "DataFrame":
    """Pattern on the previous candle inside the fib zone, confirmed by this
    candle closing above the pattern candle's high, in a 4h uptrend."""
    pattern_prev = df["pattern"].shift(1) == 1
    low_prev = df["low"].shift(1)
    in_zone = (
        low_prev <= df["fib_zone_top"].shift(1) * (1 + zone_tolerance)
    ) & (
        low_prev >= df["fib_zone_bottom"].shift(1) * (1 - zone_tolerance)
    )
    confirmed = df["close"] > df["pattern_high"].shift(1)
    return pattern_prev & in_zone & confirmed & (df["trend_up_4h"] > 0)


def exit_signal(df: DataFrame) -> "DataFrame":
    """Bearish engulfing after the fact = reversal thesis is done."""
    prev_green = df["close"].shift(1) > df["open"].shift(1)
    red = df["close"] < df["open"]
    engulfs = (df["close"] <= df["open"].shift(1)) & (df["open"] >= df["close"].shift(1))
    return prev_green & red & engulfs & (_body(df) > _body(df).shift(1))


class CandlePatternStrategy(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False  # spot
    process_only_new_candles = True
    startup_candle_count = 60

    stoploss = -0.08
    use_custom_stoploss = True
    minimal_roi = {}

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": True,
    }

    # Hyperopt spaces (1:2 min RR hard floor, per plan).
    zone_tolerance = DecimalParameter(0.0, 0.02, default=ZONE_TOLERANCE, decimals=3, space="buy")
    atr_stop_mult = DecimalParameter(1.5, 4.0, default=ATR_STOP_MULT, decimals=1, space="sell")
    rr_target = DecimalParameter(2.0, 4.0, default=RR_TARGET, decimals=1, space="sell")
    trail_after_r = DecimalParameter(0.5, 2.0, default=TRAIL_AFTER_R, decimals=1, space="sell")

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
        signal = entry_signal(dataframe, zone_tolerance=self.zone_tolerance.value)
        dataframe.loc[signal, ["enter_long", "enter_tag"]] = (1, "pattern_at_fib")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[exit_signal(dataframe), ["exit_long", "exit_tag"]] = (1, "bearish_engulf")
        return dataframe

    # --- Risk management (same framework as the other strategies) --------

    def custom_stake_amount(self, pair: str, current_time: datetime,
                            current_rate: float, proposed_stake: float,
                            min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str],
                            side: str, **kwargs) -> float:
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df.empty or not df["atr"].notna().any():
            return proposed_stake
        stop_fraction = self.atr_stop_mult.value * df["atr"].iloc[-1] / current_rate
        if stop_fraction <= 0:
            return proposed_stake
        stake = (self.wallets.get_total_stake_amount() * RISK_PER_TRADE) / stop_fraction
        stake = min(stake, max_stake)
        if min_stake:
            stake = max(stake, min_stake)
        return stake

    def order_filled(self, pair: str, trade: Trade, order, current_time, **kwargs):
        if order.ft_order_side == trade.entry_side and trade.get_custom_data("entry_atr") is None:
            df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if not df.empty and df["atr"].notna().any():
                trade.set_custom_data("entry_atr", float(df["atr"].iloc[-1]))

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool, **kwargs) -> Optional[float]:
        entry_atr = trade.get_custom_data("entry_atr")
        if not entry_atr:
            return None
        initial_risk = self.atr_stop_mult.value * entry_atr / trade.open_rate

        if current_profit >= self.trail_after_r.value * initial_risk:
            df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if not df.empty and df["atr"].notna().any():
                last = df.iloc[-1]
                return stoploss_from_absolute(
                    last["close"] - self.atr_stop_mult.value * last["atr"],
                    current_rate, is_short=trade.is_short, leverage=trade.leverage,
                )

        return stoploss_from_absolute(
            trade.open_rate - self.atr_stop_mult.value * entry_atr,
            current_rate, is_short=trade.is_short, leverage=trade.leverage,
        )

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs):
        entry_atr = trade.get_custom_data("entry_atr")
        if entry_atr:
            initial_risk = self.atr_stop_mult.value * entry_atr / trade.open_rate
            if current_profit >= self.rr_target.value * initial_risk:
                return "rr_target"
        return None

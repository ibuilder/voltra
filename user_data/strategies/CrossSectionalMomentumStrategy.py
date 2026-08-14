"""CrossSectionalMomentumStrategy — the project's first validated edge lead.

Each weekly rebalance, hold the top-N coins of the 16-pair basket by trailing
14-day return; drop coins that fall out of the top-N. Validated in
research/systematic/ (excess Sharpe ~1.4 over buy-and-hold, P(excess>0)=99.5%,
fee-robust to 0.50%/side, beats hold 3/4 years) — see docs/xsmom-lead-report.md.

This is a PORTFOLIO-REBALANCE strategy — a third category alongside active
(round-trip signal) and DCA. Its risk control is a **drawdown circuit-breaker**
(MaxDrawdown protection) plus a catastrophe stop, NOT a 1:2 RR target: a fixed
profit target would cut momentum winners short and destroy the very edge. Deep
drawdowns (~60%) are inherent to crypto momentum — this is an active *sleeve*, not
a passive core.

Look-ahead discipline: momentum uses only closed-bar data; the cross-pair ranking
compares each bar's backward-looking momentum, and Freqtrade enters on the next
candle. The ranking math is a module-level pure function so tests can verify it
without freqtrade.
"""

from datetime import datetime
from typing import Optional

import pandas as pd
from pandas import DataFrame

from freqtrade.strategy import IStrategy

LOOKBACK_DAYS = 14
TOP_N = 3
TIMEFRAME = "1h"
LOOKBACK_BARS = LOOKBACK_DAYS * 24        # 14 days of 1h candles


def momentum(close: "pd.Series", lookback_bars: int = LOOKBACK_BARS) -> "pd.Series":
    """Trailing return over `lookback_bars`, using only closed bars."""
    return close / close.shift(lookback_bars) - 1.0


def top_n_mask(mom_panel: DataFrame, n: int = TOP_N) -> DataFrame:
    """Given a date-indexed momentum panel (columns = pairs), return a boolean
    panel marking, per row, the n highest-momentum pairs. Ties broken by rank."""
    ranks = mom_panel.rank(axis=1, ascending=False, method="first")
    return ranks <= n


def is_rebalance(dt_series: "pd.Series") -> "pd.Series":
    """Weekly rebalance anchor: Monday 00:00 UTC."""
    return (dt_series.dt.dayofweek == 0) & (dt_series.dt.hour == 0)


class CrossSectionalMomentumStrategy(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = TIMEFRAME
    can_short = False
    process_only_new_candles = True
    startup_candle_count = LOOKBACK_BARS + 5

    top_n = TOP_N

    # Rank-driven exits; no ROI/trailing target (would cut momentum winners short).
    minimal_roi = {}
    stoploss = -0.30                 # per-position catastrophe backstop only
    use_custom_stoploss = False
    trailing_stop = False

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": True,
    }

    @property
    def protections(self):
        # The drawdown circuit-breaker the strategy needs: halt new entries after a
        # sharp basket drawdown (momentum's known crash risk), plus a cooldown.
        return [
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 24 * 14,
                "trade_limit": 4,
                "stop_duration_candles": 24 * 3,
                "max_allowed_drawdown": 0.25,
            },
            {"method": "CooldownPeriod", "stop_duration_candles": 2},
        ]

    def _mom_panel(self) -> Optional[DataFrame]:
        """Build a date-indexed momentum panel across the whole whitelist."""
        if not self.dp:
            return None
        cols = {}
        for p in self.dp.current_whitelist():
            d = self.dp.get_pair_dataframe(p, self.timeframe)
            if d is not None and len(d) > LOOKBACK_BARS:
                m = momentum(d["close"])
                m.index = d["date"]
                cols[p] = m
        return DataFrame(cols) if cols else None

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        panel = self._mom_panel()
        if panel is not None and pair in panel.columns:
            top = top_n_mask(panel, self.top_n)[pair]
            dataframe["is_top"] = dataframe["date"].map(top).fillna(False).astype(int)
        else:
            dataframe["is_top"] = 0
        dataframe["is_rebal"] = is_rebalance(dataframe["date"]).astype(int)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        enter = (dataframe["is_top"] == 1) & (dataframe["is_rebal"] == 1)
        dataframe.loc[enter, ["enter_long", "enter_tag"]] = (1, "xsmom_top")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit at a rebalance if this coin has fallen out of the top-N.
        exit_ = (dataframe["is_top"] == 0) & (dataframe["is_rebal"] == 1)
        dataframe.loc[exit_, ["exit_long", "exit_tag"]] = (1, "dropped_rank")
        return dataframe

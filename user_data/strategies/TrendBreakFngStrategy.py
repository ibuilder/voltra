"""EXPERIMENT: TrendBreak + Fear & Greed sentiment gate.

Identical to TrendBreakStrategy except entries are blocked while the crypto
Fear & Greed index printed Extreme Greed (>= 80) on the previous day —
pre-committed hypothesis: euphoric breakouts are late breakouts.

Uses yesterday's index value only (no lookahead). Data:
user_data/data/external/fear_greed_daily.feather.

VERDICT (2026-07-08): REJECTED — worse in 2021 (PF 1.45->1.35) and 2024
(1.07->1.06), never better; the blocked Extreme-Greed entries were net
winners. Kept only as a documented experiment. DO NOT DEPLOY.
See docs/walkforward-report-2026-07-02.md addendum 5.
"""

from pathlib import Path

import pandas as pd
from pandas import DataFrame

from TrendBreakStrategy import TrendBreakStrategy

FNG_FILE = Path(__file__).resolve().parents[1] / "data" / "external" / "fear_greed_daily.feather"
FNG_BLOCK_AT = 80  # Extreme Greed


class TrendBreakFngStrategy(TrendBreakStrategy):

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)
        fng = pd.read_feather(FNG_FILE)[["date", "fng"]].sort_values("date")
        # Shift one day: during day D we only know day D-1's print.
        fng["date"] = fng["date"] + pd.Timedelta(days=1)
        fng["date"] = fng["date"].astype(dataframe["date"].dtype)
        dataframe = pd.merge_asof(
            dataframe.sort_values("date"), fng, on="date", direction="backward"
        )
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_entry_trend(dataframe, metadata)
        dataframe.loc[dataframe["fng"] >= FNG_BLOCK_AT, "enter_long"] = 0
        return dataframe

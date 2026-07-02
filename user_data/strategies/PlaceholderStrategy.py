"""Phase 0 sanity-check strategy.

Exists only so `docker compose up` boots cleanly before Phase 2 delivers
TrendBreakStrategy. It never enters a trade. Delete once real strategies land.
"""

from pandas import DataFrame

from freqtrade.strategy import IStrategy


class PlaceholderStrategy(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False
    process_only_new_candles = True
    startup_candle_count = 0

    # Inert values — this strategy never opens a position.
    minimal_roi = {"0": 100}
    stoploss = -0.10

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        return dataframe

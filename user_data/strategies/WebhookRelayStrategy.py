"""Risk wrapper for externally-signalled (TradingView) trades.

Generates NO entry signals of its own — entries arrive only via the REST
/forceenter endpoint driven by the webhook relay. It exists so that even an
external TradingView signal is wrapped in Voltra's risk discipline:
1% ATR-based position sizing, a 2xATR on-exchange stoploss, and the same
MaxDrawdown / StoplossGuard / Cooldown protections as the validated bots.

Profit-taking is left to TradingView (send a 'close' alert); the ATR stop is
kept as a hard crash-safety so a trade is never left unprotected if the
external close signal never arrives.

Inherits all risk machinery from TrendBreakStrategy; only the signal-producing
methods are neutralized.
"""

from pandas import DataFrame

from TrendBreakStrategy import TrendBreakStrategy


class WebhookRelayStrategy(TrendBreakStrategy):

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0  # entries come only from /forceenter
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0  # exits come from /forceexit (TV close) or the ATR stop
        return dataframe

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        # No automatic profit target — TradingView owns the exit decision.
        # The inherited custom_stoploss (2xATR) still protects every trade.
        return None

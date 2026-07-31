"""Conservative mode — DCA (dollar-cost averaging) accumulation.

The hands-off, not-a-day-trader strategy: buy a small FIXED amount of each coin
on a schedule and HOLD. No market timing, no take-profit, no drawdown-halt — it
rides out dips (and keeps buying them), which is the entire point of DCA.

This is deliberately NOT an active strategy. Per CLAUDE.md, DCA is a separate
lower-risk category: small fixed per-buy stake, a far catastrophe-only backstop,
spot only, dry-run by default. Its honesty check is the vs-buy-and-hold report
(docs/dca-report.md) — DCA does not beat lump-sum in a rising market; its value
is lower risk, no timing, and steady accumulation of ongoing savings.

Mechanics: enter each pair once, then Freqtrade position-adjustment adds one more
fixed buy every `DCA_INTERVAL_HOURS`. The schedule math is a module-level pure
function so tests/test_strategies.py can exercise it without freqtrade.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy

DCA_BUY_USD = 25.0          # fixed stake per buy (small: <=1% of a 5k wallet)
DCA_INTERVAL_HOURS = 168    # add one buy per week (classic DCA cadence)
CATASTROPHE_STOP = -0.50    # backstop only — NOT a trading stop; DCA holds dips


def dca_buys_due(open_date: datetime, now: datetime, n_entries: int,
                 interval_hours: int = DCA_INTERVAL_HOURS) -> int:
    """How many scheduled buys are still owed for a held position.

    Expected buys = 1 (the initial entry) + one per fully-elapsed interval since
    the position opened. Returns expected - already-done (0 when none are due).
    Pure + deterministic so it's unit-testable without freqtrade.
    """
    if now < open_date:
        return 0
    elapsed = int((now - open_date).total_seconds() // (interval_hours * 3600))
    expected = 1 + elapsed
    return max(0, expected - n_entries)


class DcaAccumulateStrategy(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False                 # spot only
    process_only_new_candles = True
    startup_candle_count = 0

    # Hold forever: no ROI target, only a far catastrophe backstop. There is no
    # active stop and no drawdown protection — by design (see CLAUDE.md DCA rule).
    minimal_roi = {"0": 100.0}        # +10000% => effectively never sells on ROI
    stoploss = CATASTROPHE_STOP
    trailing_stop = False
    use_custom_stoploss = False

    # DCA engine: keep adding to the same position over time.
    position_adjustment_enable = True
    max_entry_position_adjustment = -1  # unlimited scheduled buys

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": True,
    }

    # No StoplossGuard / MaxDrawdown here on purpose — those halt buying in a
    # downturn, which is exactly when DCA should keep buying. Only a gentle
    # cooldown so a filled add doesn't immediately retrigger.
    @property
    def protections(self):
        return [{"method": "CooldownPeriod", "stop_duration_candles": 1}]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Always "want in": Freqtrade opens one position per pair (max_open_trades
        # = number of pairs) and won't double-open, so this just seeds each coin.
        dataframe.loc[:, ["enter_long", "enter_tag"]] = (1, "dca_seed")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe  # never sell on signal — hold and accumulate

    def custom_stake_amount(self, pair: str, current_time: datetime,
                            current_rate: float, proposed_stake: float,
                            min_stake: Optional[float], max_stake: float,
                            leverage: float, entry_tag: Optional[str],
                            side: str, **kwargs) -> float:
        """Every buy — initial and scheduled — is the same small fixed size."""
        stake = DCA_BUY_USD
        if min_stake:
            stake = max(stake, min_stake)
        return min(stake, max_stake)

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: Optional[float], max_stake: float,
                              **kwargs) -> Optional[float]:
        """Add one fixed buy each time the weekly schedule comes due."""
        if dca_buys_due(trade.open_date_utc, current_time,
                        trade.nr_of_successful_entries, DCA_INTERVAL_HOURS) <= 0:
            return None
        stake = DCA_BUY_USD
        if min_stake:
            stake = max(stake, min_stake)
        return min(stake, max_stake)

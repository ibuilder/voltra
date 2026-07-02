"""Signal-logic tests for SolCrossSignalStrategy.

The strategy keeps its math in module-level pure functions (add_features,
entry_signal, exit_signal) so these tests run with plain pandas — no
freqtrade install, docker, or network needed.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "user_data" / "strategies"))

# Import just the pure functions; the IStrategy class needs freqtrade, so the
# module import is done piecemeal via exec of the top portion.
STRATEGY_FILE = Path(__file__).parent.parent / "user_data" / "strategies" / "SolCrossSignalStrategy.py"


def _load_pure_functions():
    """Execute the strategy module up to (not including) the freqtrade imports."""
    source = STRATEGY_FILE.read_text(encoding="utf-8")
    # Everything before the IStrategy class is dependency-free except the
    # freqtrade imports, which we strip.
    lines = [
        line for line in source.split("class SolCrossSignalStrategy")[0].splitlines()
        if not line.startswith(("from freqtrade", "import freqtrade"))
    ]
    namespace = {}
    exec("\n".join(lines), namespace)
    return namespace


ns = _load_pure_functions()
add_features = ns["add_features"]
entry_signal = ns["entry_signal"]
exit_signal = ns["exit_signal"]


def make_candles(n=60, price=100.0, volume=1000.0):
    """Flat, boring market: SOL at `price`, BTC 60000, ETH 3000."""
    return pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC"),
        "open": price, "high": price * 1.001, "low": price * 0.999,
        "close": np.full(n, price, dtype=float),
        "volume": np.full(n, volume, dtype=float),
        "btc_close": np.full(n, 60000.0),
        "eth_close": np.full(n, 3000.0),
        "trend_up_4h": 1,
    })


def pump_majors(df, btc_pct=0.02, eth_pct=0.018, sol_pct=0.002, bars=4):
    """Ramp the last `bars` candles: majors pump, SOL (mostly) lags."""
    idx = df.index[-bars:]
    ramp = np.linspace(1, 1 + btc_pct, bars)
    df.loc[idx, "btc_close"] = 60000.0 * ramp
    df.loc[idx, "eth_close"] = 3000.0 * np.linspace(1, 1 + eth_pct, bars)
    df.loc[idx, "close"] = 100.0 * np.linspace(1, 1 + sol_pct, bars)
    df.loc[df.index[-1], "volume"] = 2500.0  # volume spike vs 1000 mean
    return df


def test_entry_fires_on_lead_lag_setup():
    df = add_features(pump_majors(make_candles()))
    assert entry_signal(df).iloc[-1], "majors pumped, SOL lagged, uptrend + volume -> should enter"


def test_no_entry_in_flat_market():
    df = add_features(make_candles())
    assert not entry_signal(df).any(), "flat mid-range market must produce zero entries"


def test_no_entry_when_sol_already_moved():
    df = add_features(pump_majors(make_candles(), sol_pct=0.025))
    assert not entry_signal(df).iloc[-1], "no lag gap -> no catch-up edge -> no entry"


def test_no_entry_in_downtrend():
    candles = pump_majors(make_candles())
    candles["trend_up_4h"] = 0
    df = add_features(candles)
    assert not entry_signal(df).iloc[-1], "4h downtrend filter must block longs"


def test_no_entry_without_volume_confirmation():
    candles = pump_majors(make_candles())
    candles.loc[candles.index[-1], "volume"] = 1000.0  # no spike
    df = add_features(candles)
    assert not entry_signal(df).iloc[-1], "no volume confirmation -> no entry"


def test_exit_fires_when_majors_flip():
    candles = make_candles()
    idx = candles.index[-4:]
    candles.loc[idx, "btc_close"] = 60000.0 * np.linspace(1, 0.975, 4)
    candles.loc[idx, "eth_close"] = 3000.0 * np.linspace(1, 0.97, 4)
    df = add_features(candles)
    assert exit_signal(df).iloc[-1], "both majors dumping >1% must trigger the bail-out exit"


def test_exit_quiet_in_flat_market():
    df = add_features(make_candles())
    assert not exit_signal(df).any()


def test_atr_positive_and_finite():
    df = add_features(make_candles())
    atr_tail = df["atr"].iloc[20:]
    assert (atr_tail > 0).all() and np.isfinite(atr_tail).all()

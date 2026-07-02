"""Signal-logic tests for SolCrossSignalStrategy and TrendBreakStrategy.

The strategies keep their math in module-level pure functions (add_features,
entry_signal, exit_signal) so these tests run with plain pandas — no
freqtrade install, docker, or network needed.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

STRATEGY_DIR = Path(__file__).parent.parent / "user_data" / "strategies"


def _load_pure_functions(strategy_file: str, class_name: str) -> dict:
    """Execute a strategy module up to its IStrategy class, skipping the
    freqtrade imports — leaves only stdlib/pandas-dependent code."""
    source = (STRATEGY_DIR / strategy_file).read_text(encoding="utf-8")
    lines, skipping = [], False
    for line in source.split(f"class {class_name}")[0].splitlines():
        if line.startswith(("from freqtrade", "import freqtrade")):
            skipping = line.rstrip().endswith("(")  # multi-line import block
            continue
        if skipping:
            skipping = line.strip() != ")"
            continue
        lines.append(line)
    namespace = {}
    exec("\n".join(lines), namespace)
    return namespace


ns = _load_pure_functions("SolCrossSignalStrategy.py", "SolCrossSignalStrategy")
add_features = ns["add_features"]
entry_signal = ns["entry_signal"]
exit_signal = ns["exit_signal"]

tb = _load_pure_functions("TrendBreakStrategy.py", "TrendBreakStrategy")
tb_add_features = tb["add_features"]
tb_entry_signal = tb["entry_signal"]
tb_exit_signal = tb["exit_signal"]


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


# --- TrendBreakStrategy ----------------------------------------------------


def make_range_market(n=60, volume=1000.0):
    """Price oscillating in a 98..102 box — prior swing high sits at 102."""
    closes = 100 + 2 * np.sin(np.arange(n) * 0.8)
    return pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC"),
        "open": closes,
        "high": closes + 0.5,
        "low": closes - 0.5,
        "close": closes,
        "volume": np.full(n, volume, dtype=float),
        "trend_up_4h": 1,
    })


def breakout_last_candle(df, close=104.0, vol=3000.0):
    """Final candle punches through the box top on heavy volume."""
    last = df.index[-1]
    df.loc[last, ["open", "close"]] = (102.0, close)
    df.loc[last, "high"] = close + 0.2
    df.loc[last, "low"] = 101.5
    df.loc[last, "volume"] = vol
    return df


def test_tb_entry_fires_on_swing_break():
    df = tb_add_features(breakout_last_candle(make_range_market()))
    assert tb_entry_signal(df).iloc[-1], "fresh break of 20-bar swing high on 3x volume in uptrend"


def test_tb_no_entry_mid_range():
    df = tb_add_features(make_range_market())
    assert not tb_entry_signal(df).any(), "oscillating mid-range must never signal"


def test_tb_no_entry_without_volume():
    df = tb_add_features(breakout_last_candle(make_range_market(), vol=1100.0))
    assert not tb_entry_signal(df).iloc[-1], "breakout on weak volume is not confirmed"


def test_tb_no_entry_in_downtrend():
    candles = breakout_last_candle(make_range_market())
    candles["trend_up_4h"] = 0
    df = tb_add_features(candles)
    assert not tb_entry_signal(df).iloc[-1], "4h downtrend filter must block longs"


def test_tb_no_reentry_while_drifting_above():
    """Only the crossing candle signals — not every candle above the level."""
    candles = make_range_market(n=64)
    idx = candles.index[-4:]
    candles.loc[idx, ["open", "close"]] = 104.0
    candles.loc[idx, "high"] = 104.5
    candles.loc[idx, "low"] = 103.5
    candles.loc[idx, "volume"] = 3000.0
    df = tb_add_features(candles)
    assert not tb_entry_signal(df).iloc[-1], "already above the level for 4 bars -> stale, no fresh cross"


def test_tb_exit_on_structure_failure():
    candles = make_range_market()
    last = candles.index[-1]
    candles.loc[last, ["open", "close"]] = (98.5, 96.0)  # crash through box bottom
    candles.loc[last, "high"] = 99.0
    candles.loc[last, "low"] = 95.8
    df = tb_add_features(candles)
    assert tb_exit_signal(df).iloc[-1], "close below prior swing low must exit"

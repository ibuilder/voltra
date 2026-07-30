"""Alpha101 fee-surviving-edge test on our Kraken basket (research spike).

The decisive question, same as the Kronos test: do any of WorldQuant's published
formulaic alphas produce a real, fee-surviving edge on OUR data (BTC/ETH/SOL/XRP),
or are they — like most public factors after costs — indistinguishable from noise?

Method (honest, no look-ahead):
  - Load 1h Kraken candles, resample to DAILY (Alpha101's native horizon; hourly
    turnover would be eaten alive by fees).
  - Build a cross-sectional panel across the 4 coins.
  - Each alpha scores the coins daily. Spot-only strategy: hold next day the ONE
    coin the alpha likes most (long-only top-1). Fees charged on switches.
  - Bootstrap the mean daily net return -> P(mean>0). Gate: >=95% for a real edge.
  - Benchmark: equal-weight daily-rebalanced hold, and buy-&-hold BTC.

Caveat baked into the verdict: Alpha101 are CROSS-SECTIONAL EQUITY alphas assuming
a universe of thousands. rank() over 4 coins has almost no breadth, so a weak
result here is expected and does not condemn the alphas in their native setting —
it just means they don't transfer to a 4-coin crypto basket.

Usage:  python research/alpha-zoo/alpha_test.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from alpha_ops import (  # noqa: E402
    rank, delay, delta, ts_rank, ts_argmax, stddev, correlation, sma,
)

ROOT = Path(__file__).resolve().parents[2]
PAIRS = ["BTC_USD", "ETH_USD", "SOL_USD", "XRP_USD"]
FEE_ONE_WAY = 0.00105  # 0.16% RT taker + 0.05% slippage, per side
RNG = np.random.default_rng(42)


def load_daily() -> dict:
    """Return dict of daily panels: open/high/low/close/volume/returns/vwap/adv20."""
    frames = {}
    for p in PAIRS:
        df = pd.read_feather(ROOT / "user_data" / "data" / "kraken" / f"{p}-1h.feather")
        df = df.set_index("date").sort_index()
        d = pd.DataFrame({
            "open": df["open"].resample("1D").first(),
            "high": df["high"].resample("1D").max(),
            "low": df["low"].resample("1D").min(),
            "close": df["close"].resample("1D").last(),
            "volume": df["volume"].resample("1D").sum(),
        }).dropna()
        frames[p] = d
    # align on common dates
    common = None
    for d in frames.values():
        common = d.index if common is None else common.intersection(d.index)
    panel = {}
    for field in ["open", "high", "low", "close", "volume"]:
        panel[field] = pd.DataFrame({p: frames[p].loc[common, field] for p in PAIRS})
    panel["returns"] = panel["close"].pct_change()
    panel["vwap"] = (panel["high"] + panel["low"] + panel["close"]) / 3.0  # daily proxy
    panel["adv20"] = sma(panel["close"] * panel["volume"], 20)
    panel["logvol"] = np.log(panel["volume"].replace(0, np.nan))
    return panel


def alphas(P: dict) -> dict:
    """A curated, faithfully-transcribed subset of Kakushadze (2015).
    Higher value = more bullish (the sign is baked into each formula)."""
    o, h, l, c = P["open"], P["high"], P["low"], P["close"]
    v, ret, vwap = P["volume"], P["returns"], P["vwap"]
    A = {}
    A["alpha001"] = rank(ts_argmax(np.sign(ret) * (stddev(ret, 20).where(ret < 0, c) ** 2), 5)) - 0.5
    A["alpha002"] = -1 * correlation(rank(delta(P["logvol"], 2)), rank((c - o) / o), 6)
    A["alpha003"] = -1 * correlation(rank(o), rank(v), 10)
    A["alpha004"] = -1 * ts_rank(rank(l), 9)
    A["alpha006"] = -1 * correlation(o, v, 10)
    A["alpha012"] = np.sign(delta(v, 1)) * (-1 * delta(c, 1))
    A["alpha033"] = rank(-1 * (1 - (o / c)))
    A["alpha041"] = ((h * l) ** 0.5) - vwap
    A["alpha054"] = (-1 * (l - c) * (o ** 5)) / ((l - h) * (c ** 5))
    A["alpha101"] = (c - o) / ((h - l) + 0.001)
    return A


def evaluate(alpha: pd.DataFrame, fwd: pd.DataFrame, bench: pd.Series) -> dict:
    """Long-only top-1: each day hold the coin with the highest alpha score,
    earn its next-day return, pay fees when the held coin changes.

    The edge is measured as EXCESS return over the equal-weight basket, so a
    rising market (which lifts any long-only strategy) can't masquerade as skill.
    P(mean EXCESS > 0) >= 95% is the real gate."""
    a = alpha.replace([np.inf, -np.inf], np.nan)
    valid = a.dropna(how="all")
    pick = a.reindex(valid.index).idxmax(axis=1).dropna()  # coin chosen each day
    nxt = fwd.reindex(pick.index)
    gross = np.array([nxt.loc[d, pick.loc[d]] for d in pick.index], dtype=float)
    switched = pick.values[1:] != pick.values[:-1]
    fee = np.zeros(len(gross))
    fee[1:] = np.where(switched, 2 * FEE_ONE_WAY, 0.0)
    net = pd.Series(gross - fee, index=pick.index)
    excess = (net - bench.reindex(pick.index)).dropna()
    net = net.reindex(excess.index)
    if len(excess) < 50:
        return {"n": len(excess), "cum": np.nan, "exmean": np.nan, "p": np.nan, "beats_bh": None}
    means = np.array([RNG.choice(excess.values, len(excess), replace=True).mean() for _ in range(5000)])
    strat_cum = float(np.prod(1 + net.values) - 1)
    bench_cum = float(np.prod(1 + bench.reindex(excess.index).values) - 1)
    return {
        "n": len(excess),
        "cum": strat_cum,
        "exmean": float(excess.mean()),
        "p": float(np.mean(means > 0)),          # P(mean excess return > 0)
        "beats_bh": strat_cum > bench_cum,
    }


def main() -> int:
    P = load_daily()
    fwd = P["close"].pct_change().shift(-1)  # next-day return per coin
    n_days = len(P["close"])
    print(f"basket: {PAIRS}")
    print(f"daily bars: {n_days}  ({P['close'].index[0].date()} -> {P['close'].index[-1].date()})\n")

    # benchmark = hold the equal-weight basket (the bar the alpha must beat)
    bench = fwd.mean(axis=1)  # equal-weight next-day return
    bh_btc = float((P["close"]["BTC_USD"].iloc[-1] / P["close"]["BTC_USD"].iloc[0]) - 1)
    eqw_cum = float(np.prod(1 + bench.dropna()) - 1)
    print(f"benchmark buy&hold BTC (whole window): {bh_btc:+.1%}")
    print(f"benchmark equal-weight basket:         {eqw_cum:+.1%}  <- the bar to beat\n")

    rows = [(name, evaluate(a, fwd, bench)) for name, a in alphas(P).items()]
    rows.sort(key=lambda x: (x[1]["p"] if not np.isnan(x[1]["p"]) else -1), reverse=True)

    print(f"{'alpha':<10} {'n':>5} {'strat cum':>10} {'excess/day':>11} {'beats hold':>11} {'P(excess>0)':>12}")
    print("-" * 64)
    for name, r in rows:
        if np.isnan(r["p"]):
            print(f"{name:<10} {r['n']:>5}  (insufficient data)")
            continue
        edge = r["p"] >= 0.95 and r["beats_bh"]
        print(f"{name:<10} {r['n']:>5} {r['cum']:>+9.1%} {r['exmean']:>+10.3%} {str(bool(r['beats_bh'])):>11} {r['p']:>11.1%}{'  <-- EDGE' if edge else ''}")

    passed = [n for n, r in rows if not np.isnan(r["p"]) and r["p"] >= 0.95 and r["beats_bh"]]
    print("\n=== VERDICT ===")
    if passed:
        print(f"{len(passed)} alpha(s) BEAT buy-and-hold AND clear P(excess>0)>=95%: {passed}")
        print("-> worth a Phase-2 walk-forward + Monte Carlo before trusting. Import candidate(s).")
    else:
        beats = [n for n, r in rows if r.get("beats_bh")]
        print("No alpha both beats the equal-weight basket AND clears P(excess>0)>=95% after fees.")
        print(f"   ({len(beats)} even beat buy-and-hold at all: {beats or 'none'}.)")
        print("-> REJECT for the 4-coin basket (joins Kronos/CandlePattern/regime/FnG).")
        print("   Alpha101 are cross-sectional equity alphas; rank() over 4 coins has no breadth.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

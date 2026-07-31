"""Mean-reversion test on the Kraken basket (awesome-systematic-trading review).

The awesome-systematic-trading repo is a curated *reading list*, not code — its
only actionable content is strategy CATEGORIES. We already run trend-following
(TrendBreak); the one untested category is mean-reversion. So, same discipline as
the Alpha-Zoo/Kronos spikes: test it honestly on our own data before believing it.

Signal (classic cross-sectional reversion): each day, go long the coin that is
MOST oversold (lowest trailing k-day return), expecting a bounce; hold 1 day.
Edge is measured as EXCESS return over the equal-weight basket (a rising market
can't masquerade as skill), bootstrapped. Fees charged on switches.

Usage:  python research/systematic/meanrev_test.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PAIRS = ["BTC_USD", "ETH_USD", "SOL_USD", "XRP_USD"]
FEE_ONE_WAY = 0.00105
LOOKBACKS = [1, 3, 5, 10]      # k-day trailing return used to rank "oversold"
RNG = np.random.default_rng(42)


def daily_close() -> pd.DataFrame:
    cols = {}
    for p in PAIRS:
        d = pd.read_feather(ROOT / "user_data" / "data" / "kraken" / f"{p}-1h.feather")
        d = d.set_index("date").sort_index()["close"].resample("1D").last()
        cols[p] = d
    return pd.DataFrame(cols).dropna()


def evaluate(signal: pd.DataFrame, fwd: pd.DataFrame, bench: pd.Series) -> dict:
    """Long the top-ranked coin each day (highest signal = most bullish call)."""
    pick = signal.replace([np.inf, -np.inf], np.nan).dropna(how="all").idxmax(axis=1).dropna()
    nxt = fwd.reindex(pick.index)
    gross = np.array([nxt.loc[d, pick.loc[d]] for d in pick.index], dtype=float)
    fee = np.zeros(len(gross))
    fee[1:] = np.where(pick.values[1:] != pick.values[:-1], 2 * FEE_ONE_WAY, 0.0)
    net = pd.Series(gross - fee, index=pick.index)
    excess = (net - bench.reindex(pick.index)).dropna()
    if len(excess) < 50:
        return {"n": len(excess), "cum": np.nan, "p": np.nan, "beats": None}
    means = np.array([RNG.choice(excess.values, len(excess), replace=True).mean() for _ in range(5000)])
    strat_cum = float(np.prod(1 + net.reindex(excess.index).values) - 1)
    bench_cum = float(np.prod(1 + bench.reindex(excess.index).values) - 1)
    return {"n": len(excess), "cum": strat_cum, "p": float(np.mean(means > 0)),
            "beats": strat_cum > bench_cum}


def main() -> int:
    close = daily_close()
    fwd = close.pct_change().shift(-1)
    bench = fwd.mean(axis=1)
    print(f"basket {PAIRS}  |  {len(close)} daily bars "
          f"({close.index[0].date()} -> {close.index[-1].date()})")
    print(f"equal-weight basket cum: {float(np.prod(1+bench.dropna())-1):+.0%}  <- bar to beat\n")

    print(f"{'lookback':>9} {'strat cum':>10} {'beats hold':>11} {'P(excess>0)':>12}")
    print("-" * 46)
    passed = []
    for k in LOOKBACKS:
        # most oversold = lowest trailing k-day return -> negate so argmax picks it
        signal = -(close / close.shift(k) - 1.0)
        r = evaluate(signal, fwd, bench)
        if np.isnan(r["p"]):
            print(f"{k:>8}d  (insufficient)"); continue
        edge = r["p"] >= 0.95 and r["beats"]
        if edge:
            passed.append(k)
        print(f"{k:>8}d {r['cum']:>+9.0%} {str(bool(r['beats'])):>11} {r['p']:>11.1%}{'  <-- EDGE' if edge else ''}")

    print("\n=== VERDICT ===")
    if passed:
        print(f"mean-reversion lookbacks {passed} beat buy-and-hold AND clear 95% — worth Phase 2.")
    else:
        print("No mean-reversion lookback beats buy-and-hold AND clears the 95% gate.")
        print("-> REJECT (joins Kronos / Alpha101 / CandlePattern / regime / FnG).")
        print("   Buying the most-oversold coin in a trending 4-coin basket = catching knives.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

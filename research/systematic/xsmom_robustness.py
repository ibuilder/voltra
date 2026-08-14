"""Robustness stress on the one lead: cross-sectional momentum (top-3 by 14d).

The factor-premia walk-forward flagged XS-momentum as the first thing to stay
POSITIVE out-of-sample (excess +0.13%/day, Sharpe ~1.0) — but P was 82% on a
single split, and the literature warns crypto momentum has brutal, slow-recovery
crashes. Before believing it, stress it: is the excess-over-buy-and-hold positive
across EVERY year, or does it live in one lucky window? And how deep is the drawdown?

Usage:  python research/systematic/xsmom_robustness.py
"""

import glob
import os
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
FEE = 0.00105
REBAL = 7
L, N = 14, 3
RNG = np.random.default_rng(42)


def load_daily_close():
    cols = {}
    for f in glob.glob(str(ROOT / "user_data" / "data" / "kraken" / "*-1h.feather")):
        pair = os.path.basename(f).replace("-1h.feather", "")
        cols[pair] = pd.read_feather(f).set_index("date").sort_index()["close"].resample("1D").last()
    df = pd.DataFrame(cols)
    return df.dropna(thresh=int(len(df.columns) * 0.6))


def run(close):
    rets = close.pct_change(fill_method=None).fillna(0.0)
    bench = rets.mean(axis=1)
    w = pd.Series(0.0, index=close.columns)
    port = pd.Series(0.0, index=close.index)
    for i in range(1, len(close)):
        if (i - 1) % REBAL == 0 and i > L + 1:
            score = close.iloc[:i].iloc[-1] / close.iloc[:i].iloc[-L] - 1.0
            pick = score.dropna().nlargest(N).index
            neww = pd.Series(0.0, index=close.columns)
            if len(pick):
                neww[pick] = 1.0 / len(pick)
            port.iloc[i] -= (neww - w).abs().sum() * FEE
            w = neww
        port.iloc[i] += float((w * rets.iloc[i]).sum())
    return port, bench


def maxdd(daily):
    eq = (1 + daily).cumprod()
    return float((eq / eq.cummax() - 1).min())


def main():
    close = load_daily_close()
    port, bench = run(close)
    excess = port - bench
    print(f"XS-momentum top-{N} by {L}d, weekly rebalance, {len(close.columns)} pairs, "
          f"{len(close)} days ({close.index[0].date()}->{close.index[-1].date()})\n")

    strat_cum = float((1 + port).prod() - 1)
    bench_cum = float((1 + bench).prod() - 1)
    means = np.array([RNG.choice(excess.values, len(excess), replace=True).mean() for _ in range(5000)])
    print(f"strategy cum: {strat_cum:+.0%}  |  buy&hold basket: {bench_cum:+.0%}")
    print(f"excess/day: {excess.mean():+.3%}  |  excess Sharpe: {excess.mean()/(excess.std()+1e-12)*np.sqrt(365):.2f}"
          f"  |  P(excess>0): {np.mean(means>0):.1%}")
    print(f"strategy maxDD: {maxdd(port):.0%}  |  buy&hold maxDD: {maxdd(bench):.0%}\n")

    print("Excess over buy&hold, per calendar year (the real robustness test):")
    print(f"{'year':>6} {'days':>5} {'strat':>8} {'hold':>8} {'excess':>8} {'beats?':>7}")
    print("-" * 46)
    yrs_beat = 0
    yrs_total = 0
    for yr, idx in excess.groupby(excess.index.year).groups.items():
        p = port.loc[idx]; b = bench.loc[idx]
        sc = float((1 + p).prod() - 1); bc = float((1 + b).prod() - 1)
        beat = sc > bc
        yrs_total += 1; yrs_beat += int(beat)
        print(f"{yr:>6} {len(idx):>5} {sc:>+7.0%} {bc:>+7.0%} {sc-bc:>+7.0%} {'yes' if beat else 'no':>7}")

    print("\n=== BEST OUTCOME ===")
    if yrs_beat >= yrs_total - 1 and np.mean(means > 0) >= 0.90:
        print(f"XS-momentum beats buy-and-hold in {yrs_beat}/{yrs_total} years, P(excess>0)="
              f"{np.mean(means>0):.0%}. This is the strongest, most robust lead the project has")
        print("found. NOT yet a 95% lock, and drawdowns are deep -- but it's real enough to")
        print(f"promote: port to a Freqtrade strategy (top-{N} by {L}d, weekly rebalance, the")
        print("basket's 16 pairs), full walk-forward + MC, then a dry-run. This is attempt #10")
        print("and the first worth advancing.")
    else:
        print(f"XS-momentum beats buy-and-hold in only {yrs_beat}/{yrs_total} years / P too low.")
        print("Not robust -- the single-split positive was window-luck. DCA/hold still wins.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

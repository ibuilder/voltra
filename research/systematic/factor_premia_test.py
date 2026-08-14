"""Test the documented crypto factor premia — walk-forward, honest gate.

Research (Liu 2020, Yang 2019, JFQA trend factor, 2025 reviews) says the premia
that exist in crypto are momentum (XS + TS) and low-vol/defensive; carry needs
perps (we're spot) and value needs fundamentals (we lack). We now have 16 pairs
= the breadth the Alpha101 test lacked. So test the testable ones properly:

  - XS momentum : each week hold the top-N coins by trailing-L-day return.
  - TS momentum : each week hold every coin with positive trailing-L return (else cash).
  - Low-vol     : each week hold the N lowest-volatility coins.

Method that refuses to fool itself:
  * weekly rebalance, fees charged on turnover (0.105%/side).
  * metric = EXCESS daily return over the equal-weight-16 basket (a bull market
    can't masquerade as skill); bootstrap P(mean excess > 0).
  * WALK-FORWARD: choose each premium's best (L,N) on TRAIN, validate on unseen TEST.

Usage:  python research/systematic/factor_premia_test.py
"""

import glob
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FEE = 0.00105                  # per side
SPLIT = pd.Timestamp("2025-06-01", tz="UTC")
REBAL = 7                      # days between rebalances
RNG = np.random.default_rng(42)


def load_daily_close():
    cols = {}
    for f in glob.glob(str(ROOT / "user_data" / "data" / "kraken" / "*-1h.feather")):
        pair = os.path.basename(f).replace("-1h.feather", "")
        s = pd.read_feather(f).set_index("date").sort_index()["close"].resample("1D").last()
        cols[pair] = s
    return pd.DataFrame(cols).dropna(how="all")


def weights_for(kind, hist, L, N):
    """Return a weight vector (sums to 1, long-only) given history up to today."""
    if len(hist) < L + 2:
        return None
    if kind == "xsmom":
        score = hist.iloc[-1] / hist.iloc[-L] - 1.0
        pick = score.dropna().nlargest(N).index
    elif kind == "tsmom":
        score = hist.iloc[-1] / hist.iloc[-L] - 1.0
        pick = score[score > 0].dropna().index
    elif kind == "lowvol":
        vol = hist.pct_change().iloc[-L:].std()
        pick = vol.dropna().nsmallest(N).index
    else:
        return None
    if len(pick) == 0:
        return pd.Series(0.0, index=hist.columns)
    w = pd.Series(0.0, index=hist.columns)
    w[pick] = 1.0 / len(pick)
    return w


def run(kind, close, L, N):
    """Weekly-rebalanced long-only portfolio; returns daily net returns + excess."""
    rets = close.pct_change().fillna(0.0)
    bench = rets.mean(axis=1)                      # equal-weight-16 buy&hold-ish
    dates = close.index
    w = pd.Series(0.0, index=close.columns)
    port = pd.Series(0.0, index=dates)
    for i in range(1, len(dates)):
        if (i - 1) % REBAL == 0:
            neww = weights_for(kind, close.iloc[:i], L, N)
            if neww is not None:
                cost = (neww - w).abs().sum() * FEE
                port.iloc[i] -= cost
                w = neww
        port.iloc[i] += float((w * rets.iloc[i]).sum())
    excess = (port - bench).dropna()
    return port, bench, excess


def score(excess):
    if len(excess) < 40:
        return None
    means = np.array([RNG.choice(excess.values, len(excess), replace=True).mean() for _ in range(3000)])
    return {"n": len(excess), "exmean": float(excess.mean()),
            "p": float(np.mean(means > 0)),
            "sharpe": float(excess.mean() / (excess.std() + 1e-12) * np.sqrt(365))}


def main():
    close = load_daily_close()
    close = close.dropna(thresh=int(len(close.columns) * 0.6))
    train = close[close.index < SPLIT]
    print(f"{len(close.columns)} pairs | {len(close)} daily bars | train<{SPLIT.date()}<=test\n")

    GRID = {
        "xsmom":  [(L, N) for L in (14, 30, 60, 90) for N in (3, 5, 8)],
        "tsmom":  [(L, 0) for L in (14, 30, 60, 90)],
        "lowvol": [(L, N) for L in (30, 60) for N in (3, 5, 8)],
    }
    results = []
    for kind, grid in GRID.items():
        # pick best (L,N) on TRAIN by excess Sharpe
        best = None
        for L, N in grid:
            _, _, ex = run(kind, train, L, N)
            s = score(ex)
            if s and (best is None or s["sharpe"] > best[1]["sharpe"]):
                best = ((L, N), s)
        if not best:
            continue
        (L, N), tr = best
        # validate that choice on the FULL series' test segment
        _, _, ex_full = run(kind, close, L, N)
        te = score(ex_full[ex_full.index >= SPLIT])
        results.append((kind, L, N, tr, te))

    print(f"{'premium':<8} {'L':>3} {'N':>3} {'train exSharpe':>14} {'TEST exmean':>12} {'TEST P':>8} {'TEST exSharpe':>14}")
    print("-" * 66)
    winner = None
    for kind, L, N, tr, te in results:
        if te is None:
            print(f"{kind:<8} {L:>3} {N:>3} {tr['sharpe']:>13.2f}  (insufficient test)"); continue
        ok = te["p"] >= 0.95 and te["exmean"] > 0
        if ok and (winner is None or te["sharpe"] > winner[-1]["sharpe"]):
            winner = (kind, L, N, te)
        print(f"{kind:<8} {L:>3} {N:>3} {tr['sharpe']:>13.2f} {te['exmean']:>+11.3%} {te['p']:>7.0%} {te['sharpe']:>13.2f}{'  <-- survives OOS' if ok else ''}")

    print("\n=== BEST OUTCOME ===")
    if winner:
        k, L, N, te = winner
        print(f"{k} (L={L}, N={N}) BEATS buy-and-hold out-of-sample: excess {te['exmean']:+.3%}/day,")
        print(f"P={te['p']:.0%}, excess Sharpe {te['sharpe']:.2f}. First survivor -> port to Freqtrade,")
        print("full walk-forward + MC, then a dry-run. Genuinely worth pursuing.")
    else:
        print("No documented premium beats buy-and-hold out-of-sample after fees on our")
        print("16-coin spot basket. Even with breadth, XS/TS momentum and low-vol don't")
        print("clear the honest gate OOS. Attempt #10-#12. The best outcome for a passive")
        print("user remains DCA/hold: it IS the equal-weight basket, which nothing beat.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

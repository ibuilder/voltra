"""Survivorship / new-listing stress on the XS-momentum lead.

The edge was measured on 16 pairs that survived to today. Momentum backtests are
especially flattered by (a) survivors and (b) newly-listed coins that pump on debut
— WLD (2025-03), CELO (2025-04), BNB (2025-04), SUI (2023-05) only appear partway
through the window. If the +1607% leans on catching those, it's not a robust edge.

We can't resurrect delisted coins, but we can isolate the concern: re-run the exact
strategy on universes that remove the selection bias:
  - full16      : the original basket (baseline).
  - fullwindow12: only coins present from the 2023-01-01 window start (drops the
                  late-listers WLD/CELO/BNB/SUI).
  - majors9     : established liquid names only.

If the excess-over-buy-and-hold edge holds on fullwindow12 / majors9, survivorship
and new-listing pumps are not what's driving it.

Usage:  python research/systematic/xsmom_survivorship.py
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
REBAL, L, N = 7, 14, 3
RNG = np.random.default_rng(42)

LATE = {"WLD_USD", "CELO_USD", "BNB_USD", "SUI_USD"}          # listed mid-window
MAJORS = ["BTC_USD", "ETH_USD", "SOL_USD", "XRP_USD", "ADA_USD",
          "DOGE_USD", "LTC_USD", "TRX_USD", "XLM_USD"]


def load_daily_close():
    cols = {}
    for f in glob.glob(str(ROOT / "user_data" / "data" / "kraken" / "*-1h.feather")):
        pair = os.path.basename(f).replace("-1h.feather", "")
        cols[pair] = pd.read_feather(f).set_index("date").sort_index()["close"].resample("1D").last()
    return pd.DataFrame(cols)


def run(close):
    rets = close.pct_change(fill_method=None).fillna(0.0)
    bench = rets.mean(axis=1)
    w = pd.Series(0.0, index=close.columns)
    port = pd.Series(0.0, index=close.index)
    for i in range(1, len(close)):
        if (i - 1) % REBAL == 0 and i > L + 1:
            sc = close.iloc[:i].iloc[-1] / close.iloc[:i].iloc[-L] - 1.0
            pick = sc.dropna().nlargest(N).index
            neww = pd.Series(0.0, index=close.columns)
            if len(pick):
                neww[pick] = 1.0 / len(pick)
            port.iloc[i] -= (neww - w).abs().sum() * FEE
            w = neww
        port.iloc[i] += float((w * rets.iloc[i]).sum())
    return port, bench


def evaluate(close, universe):
    sub = close[[c for c in universe if c in close.columns]]
    # restrict to the window where at least half the universe has data
    sub = sub.dropna(how="all")
    sub = sub[sub.notna().sum(axis=1) >= max(4, len(universe) // 2)]
    if len(sub) < 200:
        return None
    port, bench = run(sub)
    ex = (port - bench).dropna()
    means = np.array([RNG.choice(ex.values, len(ex), replace=True).mean() for _ in range(5000)])
    return {"n_pairs": sub.shape[1], "days": len(sub),
            "strat_cum": float((1 + port).prod() - 1),
            "hold_cum": float((1 + bench).prod() - 1),
            "exmean": float(ex.mean()), "p": float(np.mean(means > 0)),
            "sharpe": float(ex.mean() / (ex.std() + 1e-12) * np.sqrt(365))}


def main():
    close = load_daily_close()
    full16 = list(close.columns)
    fullwindow12 = [c for c in full16 if c not in LATE]
    universes = {"full16": full16, "fullwindow12": fullwindow12, "majors9": MAJORS}

    print(f"{'universe':<14}{'pairs':>6}{'days':>6}{'strat':>9}{'hold':>8}{'excess/d':>10}{'exSharpe':>10}{'P':>7}")
    print("-" * 71)
    verdict = []
    for name, u in universes.items():
        r = evaluate(close, u)
        if not r:
            print(f"{name:<14} insufficient"); continue
        beats = r["strat_cum"] > r["hold_cum"]
        strong = r["p"] >= 0.90 and beats
        verdict.append((name, strong, r))
        print(f"{name:<14}{r['n_pairs']:>6}{r['days']:>6}{r['strat_cum']:>+8.0%}{r['hold_cum']:>+7.0%}"
              f"{r['exmean']:>+9.3%}{r['sharpe']:>10.2f}{r['p']:>6.0%}")

    print("\n=== SURVIVORSHIP VERDICT ===")
    core = [v for v in verdict if v[0] in ("fullwindow12", "majors9")]
    if core and all(v[1] for v in core):
        print("Edge SURVIVES on the full-window and majors universes (P>=90%, beats hold).")
        print("-> not driven by new-listing pumps or survivor selection. The lead holds up.")
    elif any(v[1] for v in core):
        print("Edge survives on one survivorship-safer universe but not both -> partly real,")
        print("partly new-listing/selection. Treat magnitude with caution; keep dry-running.")
    else:
        print("Edge COLLAPSES once late-listers/survivors are removed -> it was largely a")
        print("new-listing-pump / survivorship artifact. Demote the lead; DCA/hold stands.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

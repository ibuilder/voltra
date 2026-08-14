"""Higher-frequency momentum test — attempt #9 (user asked to test a faster strategy).

TrendBreak trades ~1.6x/month -> unvalidatable via dry-run. The fix for FREQUENCY:
a looser momentum-continuation signal run across ALL 16 Kraken pairs on 1h, so a
sample builds in weeks. The fix for EDGE is a separate question this answers.

Signal (crypto-friendly = momentum, not mean-reversion): enter long when close
breaks above the prior M-bar high (a fresh breakout); measure the K-bar-forward
return net of fees. This measures the signal's edge and its trade frequency at
once. Honest cost: FEE_RT = 0.21% round-trip (0.16% taker + 0.05% slippage).

Gate: mean per-trade > 0 after fees with P>=95% (bootstrap), AND enough trades
(>=~30/month) that a dry-run could confirm in weeks.

Usage:  python research/systematic/hf_momentum_test.py
"""

import glob
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FEE_RT = 0.00105 * 2          # 0.21% round-trip
RNG = np.random.default_rng(42)
GRID_M = [12, 24, 48]         # breakout lookback (bars)
GRID_K = [6, 12, 24]          # holding period (bars)


def load_pairs():
    frames = {}
    for f in glob.glob(str(ROOT / "user_data" / "data" / "kraken" / "*-1h.feather")):
        pair = os.path.basename(f).replace("-1h.feather", "")
        d = pd.read_feather(f).set_index("date").sort_index()
        frames[pair] = d[["high", "close"]]
    return frames


def signal_returns(frames, m, k):
    """All breakout signals across all pairs -> K-bar-forward net returns."""
    rets, span_days = [], 0
    for d in frames.values():
        high, close = d["high"], d["close"]
        prior_max = high.shift(1).rolling(m).max()
        breakout = (close > prior_max) & (close.shift(1) <= prior_max.shift(1))
        fwd = close.shift(-k) / close - 1.0
        r = fwd[breakout].dropna().to_numpy() - FEE_RT
        rets.append(r)
        span_days = max(span_days, (d.index[-1] - d.index[0]).days)
    allr = np.concatenate(rets) if rets else np.array([])
    return allr, span_days


def main():
    frames = load_pairs()
    total_days = max((d.index[-1] - d.index[0]).days for d in frames.values())
    print(f"pairs: {len(frames)}  |  ~{total_days} days of 1h data  |  fee {FEE_RT*100:.2f}% RT\n")
    print(f"{'M':>3} {'K':>3} {'trades':>7} {'trades/mo':>10} {'mean/trade':>11} {'cum':>9} {'P(mean>0)':>11}")
    print("-" * 60)
    passed = []
    for m in GRID_M:
        for k in GRID_K:
            r, _ = signal_returns(frames, m, k)
            if len(r) < 50:
                print(f"{m:>3} {k:>3} {len(r):>7}  (too few)"); continue
            means = np.array([RNG.choice(r, len(r), replace=True).mean() for _ in range(3000)])
            p = float(np.mean(means > 0))
            per_mo = len(r) / (total_days / 30.0)
            cum = float(np.prod(1 + r) - 1)   # note: overlapping signals, so illustrative
            edge = p >= 0.95 and r.mean() > 0
            if edge:
                passed.append((m, k))
            print(f"{m:>3} {k:>3} {len(r):>7} {per_mo:>9.0f} {r.mean():>+10.3%} {cum:>+8.0%} {p:>10.1%}{'  <-- EDGE' if edge else ''}")

    print("\n=== VERDICT ===")
    if passed:
        print(f"Configs clearing P>=95% after fees: {passed}")
        print("-> promising: port the best to a Freqtrade strategy, walk-forward + MC,")
        print("   then a short dry-run CAN confirm (high trade count). Attempt #9 lives.")
    else:
        print("No breakout/hold config clears the 95% edge gate after fees.")
        print("-> momentum-continuation on 1h across 16 pairs adds FREQUENCY but not EDGE;")
        print("   the 0.21% round-trip fee eats the small 1h moves. Joins the rejected")
        print("   ledger. Frequency was never the whole problem — fee-surviving edge is.")


if __name__ == "__main__":
    raise SystemExit(main())

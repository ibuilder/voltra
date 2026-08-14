"""Validate the promising HF-momentum config the HONEST way (walk-forward, OOS).

The in-sample sweep (hf_momentum_test.py) flagged (M=48,K=24) at P=99% — but that
was the best of 9 configs, on overlapping samples, in-sample. All three inflate
significance. This does it right:

  1. Split each pair's 1h history: TRAIN (older) vs TEST (newer, unseen).
  2. NON-OVERLAPPING trades only (one position per pair at a time = realistic).
  3. Pick the best config on TRAIN, then validate THAT config on TEST.
  4. An edge that's real survives out-of-sample; an artifact evaporates.

Usage:  python research/systematic/hf_momentum_validate.py
"""

import glob
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FEE_RT = 0.00105 * 2
RNG = np.random.default_rng(42)
SPLIT = pd.Timestamp("2025-06-01", tz="UTC")   # train < SPLIT <= test
GRID = [(m, k) for m in (12, 24, 48) for k in (6, 12, 24)]


def load_pairs():
    out = {}
    for f in glob.glob(str(ROOT / "user_data" / "data" / "kraken" / "*-1h.feather")):
        pair = os.path.basename(f).replace("-1h.feather", "")
        out[pair] = pd.read_feather(f).set_index("date").sort_index()[["high", "close"]]
    return out


def nonoverlap_trades(d, m, k):
    """One position per pair at a time: enter on a fresh M-bar-high breakout,
    exit K bars later, then look for the next entry. Returns net per-trade rets."""
    high = d["high"].to_numpy()
    close = d["close"].to_numpy()
    n = len(close)
    prior_max = pd.Series(d["high"]).shift(1).rolling(m).max().to_numpy()
    rets, i = [], m + 1
    while i < n - k:
        if close[i] > prior_max[i] and close[i - 1] <= prior_max[i - 1]:
            rets.append(close[i + k] / close[i] - 1.0 - FEE_RT)
            i += k                      # non-overlapping: jump past the hold
        else:
            i += 1
    return np.array(rets)


def collect(frames, when, m, k):
    rets = []
    for d in frames.values():
        seg = d[d.index < SPLIT] if when == "train" else d[d.index >= SPLIT]
        if len(seg) > m + k + 5:
            rets.append(nonoverlap_trades(seg, m, k))
    return np.concatenate(rets) if rets else np.array([])


def stats(r):
    if len(r) < 30:
        return None
    means = np.array([RNG.choice(r, len(r), replace=True).mean() for _ in range(5000)])
    return {"n": len(r), "mean": r.mean(), "cum": float(np.prod(1 + r) - 1),
            "p": float(np.mean(means > 0))}


def main():
    frames = load_pairs()
    print(f"pairs {len(frames)} | train < {SPLIT.date()} <= test | non-overlapping | fee {FEE_RT*100:.2f}% RT\n")

    # 1) pick the best config on TRAIN only
    best = None
    print("TRAIN sweep (pick winner here):")
    for m, k in GRID:
        s = stats(collect(frames, "train", m, k))
        if not s:
            continue
        if s["mean"] > 0 and (best is None or s["p"] > best[2]["p"]):
            best = (m, k, s)
    for m, k in GRID:
        s = stats(collect(frames, "train", m, k))
        if s:
            star = " *" if best and (m, k) == (best[0], best[1]) else ""
            print(f"  M={m:>2} K={k:>2}  n={s['n']:>5} mean={s['mean']:+.3%} P={s['p']:.0%}{star}")

    if not best:
        print("\nNo positive-mean config even in-sample train. REJECT.")
        return 0

    m, k, _ = best
    # 2) validate that ONE config on unseen TEST
    ts = stats(collect(frames, "test", m, k))
    tr = best[2]
    print(f"\nWinner on train: M={m} K={k}")
    print(f"  TRAIN: n={tr['n']} mean={tr['mean']:+.3%} cum={tr['cum']:+.0%} P(mean>0)={tr['p']:.1%}")
    if ts:
        print(f"  TEST : n={ts['n']} mean={ts['mean']:+.3%} cum={ts['cum']:+.0%} P(mean>0)={ts['p']:.1%}")

    print("\n=== VERDICT ===")
    if ts and ts["p"] >= 0.95 and ts["mean"] > 0:
        print("Edge SURVIVES out-of-sample after fees. Genuinely promising — port to a")
        print("Freqtrade strategy, full walk-forward + Monte Carlo, then a (now feasible,")
        print("high-frequency) dry-run to confirm. This is the first thing that has passed.")
    else:
        pv = f"{ts['mean']:+.3%}, P={ts['p']:.0%}" if ts else "insufficient test trades"
        print(f"Edge does NOT survive out-of-sample ({pv}). The in-sample P=99% was the")
        print("multiple-comparisons + overlapping-sample artifact we suspected. REJECT —")
        print("frequency is achievable, a fee-surviving edge is not. Boring (DCA/hold) wins.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

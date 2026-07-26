"""Kronos out-of-sample forecast-skill test (Phase 1).

The cheap, decisive question before any integration: does Kronos have real
predictive skill on our held-out Kraken data, after fees? If directional
accuracy is a coin flip, there is no edge to build on.

Method (honest, no look-ahead):
  - Roll a non-overlapping window over a held-out OOS slice of real Kraken 1h
    candles. For each window: feed `lookback` past candles, ask Kronos to
    forecast the next `horizon`, compare predicted vs actual close direction.
  - Naive strategy: go long for the horizon when Kronos predicts up; else flat.
    Fees modeled. Per-trade returns then get bootstrapped for significance.

Setup (Kronos is not committed here — it's external research code):
  git clone https://github.com/shiyu-coder/Kronos  (anywhere)
  set KRONOS_PATH to that folder.

Usage:
  KRONOS_PATH=/path/to/Kronos python research/kronos/skill_test.py \
      --pair BTC_USD --start 2025-01-01 --end 2025-07-01 \
      --lookback 512 --horizon 24 --limit 0
"""

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FEE = 0.00105 * 2  # round-trip: 0.16% RT taker + 0.05% slippage, both sides


def load_kronos(max_context):
    kp = os.environ.get("KRONOS_PATH")
    if not kp or not Path(kp).is_dir():
        sys.exit("Set KRONOS_PATH to a cloned https://github.com/shiyu-coder/Kronos")
    sys.path.insert(0, kp)
    from model import Kronos, KronosTokenizer, KronosPredictor
    tok = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    mdl = Kronos.from_pretrained("NeoQuasar/Kronos-small")
    return KronosPredictor(mdl, tok, device="cpu", max_context=max_context)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pair", default="BTC_USD")
    ap.add_argument("--start", default="2025-01-01")
    ap.add_argument("--end", default="2025-07-01")
    ap.add_argument("--lookback", type=int, default=512)
    ap.add_argument("--horizon", type=int, default=24)
    ap.add_argument("--limit", type=int, default=0, help="max windows (0 = all)")
    ap.add_argument("--temp", type=float, default=0.7)
    ap.add_argument("--out", default=str(ROOT / "research" / "kronos"))
    args = ap.parse_args()

    df = pd.read_feather(ROOT / "user_data" / "data" / "kraken" / f"{args.pair}-1h.feather")
    df = df.rename(columns={"date": "timestamps"}).reset_index(drop=True)
    test_lo = pd.Timestamp(args.start, tz="UTC")
    test_hi = pd.Timestamp(args.end, tz="UTC")

    predictor = load_kronos(args.lookback)

    # window starts: each forecast uses [i-lookback, i) history to predict [i, i+horizon)
    idx = df.index[(df["timestamps"] >= test_lo) & (df["timestamps"] < test_hi)]
    starts = list(range(int(idx[0]), int(idx[-1]) - args.horizon, args.horizon))
    starts = [s for s in starts if s - args.lookback >= 0]
    if args.limit:
        starts = starts[: args.limit]
    print(f"{args.pair}: {len(starts)} forecast windows, lookback={args.lookback} horizon={args.horizon}")

    # Incremental CSV — each window is written as it completes, so a stopped
    # run loses nothing and can be summarized/resumed from the CSV.
    csv_path = Path(args.out) / f"skill-{args.pair}-{args.start}.csv"
    done = set()
    if csv_path.exists():
        prev = pd.read_csv(csv_path)
        done = set(prev["i"].tolist())
        print(f"resuming: {len(done)} windows already done in {csv_path.name}")
    else:
        csv_path.write_text("i,pred_up,hit,ret\n")

    with csv_path.open("a") as fh:
        for n, i in enumerate(starts):
            if i in done:
                continue
            hist = df.iloc[i - args.lookback : i]
            fut = df.iloc[i : i + args.horizon]
            x_df = hist[["open", "high", "low", "close", "volume"]].reset_index(drop=True)
            pred = predictor.predict(
                df=x_df,
                x_timestamp=hist["timestamps"].reset_index(drop=True),
                y_timestamp=fut["timestamps"].reset_index(drop=True),
                pred_len=args.horizon, T=args.temp, top_p=0.9, sample_count=1, verbose=False,
            )
            entry = float(hist["close"].iloc[-1])
            pred_up = bool(float(pred["close"].iloc[-1]) > entry)
            actual_up = bool(float(fut["close"].iloc[-1]) > entry)
            ret = ((float(fut["close"].iloc[-1]) / entry - 1.0) - FEE) if pred_up else ""
            fh.write(f"{i},{int(pred_up)},{int(pred_up == actual_up)},{ret}\n")
            fh.flush()
            if (n + 1) % 10 == 0:
                print(f"  {n+1}/{len(starts)}", flush=True)

    res = pd.read_csv(csv_path)
    hits = res["hit"].to_numpy()
    rets = res.loc[res["pred_up"] == 1, "ret"].dropna().to_numpy()
    if len(rets) == 0:
        rets = np.array([0.0])

    # bootstrap significance of the naive strategy's mean per-trade return
    rng = np.random.default_rng(42)
    means = np.array([rng.choice(rets, size=len(rets), replace=True).mean() for _ in range(5000)])

    print("\n=== Kronos OOS forecast-skill result ===")
    print(f"windows: {len(hits)}  |  directional accuracy: {hits.mean():.1%}  (50% = coin flip)")
    print(f"naive long-on-up trades: {len(rets)}  |  mean/trade after fees: {rets.mean():+.3%}")
    print(f"  cumulative (compounded): {np.prod(1+rets)-1:+.1%}")
    print(f"  bootstrap P(mean>0): {np.mean(means>0):.1%}  (need >=95% for a real edge)")
    verdict = "SKILL — worth Phase 2" if (hits.mean() > 0.55 and np.mean(means > 0) >= 0.95) else \
              "NO significant skill — reject (like CandlePattern/regime/FnG)"
    print(f"VERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

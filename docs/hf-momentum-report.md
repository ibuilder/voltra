# Higher-frequency momentum test — attempt #9

**Date:** 2026-08-14 · **Verdict: REJECT.** Frequency achievable; edge is not.

## Why

The dry-run milestone showed TrendBreak trades too rarely (~1.6/mo) to ever be
validated. The chosen fix was to test a **higher-frequency** active strategy — a
momentum-continuation breakout run across **all 16 Kraken pairs** on 1h, which
fires 130–300×/month (a dry-run *could* confirm that in weeks).

## What we found — and the trap we avoided

In-sample sweep (`research/systematic/hf_momentum_test.py`) over 9 configs flagged
`M=48, K=24` at **P(mean>0)=99%**. That looked like a winner. It wasn't — three
things inflate it: (1) best-of-9 configs = multiple comparisons, (2) overlapping
K-bar windows violate the bootstrap's independence, (3) in-sample only.

The honest test (`hf_momentum_validate.py`): pick the config on TRAIN, validate on
unseen TEST, **non-overlapping** trades.

| M=48, K=24 | trades | mean/trade (net) | P(mean>0) |
|---|---|---|---|
| Train (< 2025-06) | 3,663 | **+0.160%** | 97% |
| **Test (unseen)** | 1,152 | **−0.074%** | **31%** |

The edge **flipped negative out-of-sample.** The in-sample 99% was exactly the
artifact we suspected. Every other config was already negative after fees.

## Conclusion

Frequency is easy (300 trades/mo across 16 pairs). A **fee-surviving edge is not**
— the 0.21% round-trip fee eats the small 1h moves, and the one config that beat it
in-sample was overfitting. This is attempt **#9**:

> Kronos · Alpha101 · CandlePattern · 200d-MA regime · Fear&Greed · mean-reversion
> · TrendBreak (unprovable) · **HF-momentum** — none clear the fee-surviving edge gate.

Nine honest attempts, zero edges. That is itself the finding: a retail-scale
directional edge on liquid crypto majors is very hard to find, and our own tooling
keeps proving it. The realistic product for a hands-off user remains **DCA / hold**
(needs no edge, tracks the market). The value here isn't a winning strategy — it's
a validation process that refuses to fool itself, and caught a P=99% mirage.

# Alpha-Zoo research (Vibe-Trading review)

Tests whether WorldQuant's **Alpha101** formulaic alphas (Kakushadze 2015), as
surfaced by [HKUDS/Vibe-Trading](https://github.com/HKUDS/Vibe-Trading)'s Alpha
Zoo, have a fee-surviving edge on our Kraken basket. **Result: no (breadth-4
cross-sectional).** See [../../docs/alpha-zoo-report.md](../../docs/alpha-zoo-report.md).

## Files
- `alpha_ops.py` — the Alpha101 operator toolkit (rank, delay, ts_rank,
  correlation, decay_linear, …), panel form.
- `alpha_test.py` — loads Kraken BTC/ETH/SOL/XRP, resamples to daily, computes a
  curated alpha subset, and bootstraps **excess** return over the equal-weight
  basket (the gate that isn't fooled by a rising market).

## Reproduce
```bash
python research/alpha-zoo/alpha_test.py
```
Needs the Kraken 1h feathers in `user_data/data/kraken/` and pandas/numpy (host
python is fine — no torch/heavy deps, unlike the Kronos test).

## Why rejected
Alpha101 are cross-sectional equity alphas built for universes of thousands.
`rank()` over 4 coins has no breadth, so every alpha underperformed simply holding
the basket. Not imported. The framework half of Vibe-Trading (LLM swarms, broker
connectors, MCP tooling) was also skipped — tooling, not edge.

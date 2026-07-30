# Alpha-Zoo research report (Vibe-Trading review)

**Date:** 2026-07-30 · **Verdict: REJECT (for our 4-coin basket).**

## What prompted this

Reviewed [HKUDS/Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (MIT) — an
open-source AI-agent research framework. Its **framework** (LLM swarms, ~50 MCP
tools, 10 broker connectors, 16 chat integrations, memory) is deliberately **not**
imported: it's research/agent tooling, adds moving parts, and produces no edge —
the same surface-sprawl we've avoided. The project itself claims no proven alpha.

The one concrete, testable asset was its **Alpha Zoo** — 452 published formulaic
signals (Qlib158, **Alpha101 / Kakushadze 2015**, GTJA191, academic factors). Those
are precise math over OHLCV, so — exactly as we did with Kronos — we tested them on
our own Kraken data instead of trusting them.

## Method

`research/alpha-zoo/` reimplements the Alpha101 operator set and a curated 10-alpha
subset, computed on **daily** Kraken bars for **BTC/ETH/SOL/XRP** (1186 days,
2023-01-01 → 2026-03-31; daily is Alpha101's native horizon and keeps fees
survivable). Spot-only strategy: each day hold the single coin the alpha ranks
highest; fees (0.16% RT + 0.05% slip) charged on switches.

**The gate that matters:** edge is measured as **excess return over the
equal-weight basket**, bootstrapped (5,000×). A rising market lifts *any* long-only
strategy, so raw P(mean>0) is not skill — P(mean **excess** > 0) ≥ 95% is.

> A first cut using raw P(mean>0) flagged `alpha004` as an "edge" (98%). It was a
> false positive: its +297% still *trailed* buy-&-hold BTC (+310%) and the basket
> (+402%). Correcting the benchmark is the whole point.

## Result

Benchmark to beat: equal-weight basket **+402.5%** (buy-&-hold BTC +310.6%).

| alpha | strat cum | excess/day | beats hold? | P(excess>0) |
|---|---|---|---|---|
| alpha004 | +297.0% | −0.026% | no | 29.2% |
| alpha006 | +44.2% | −0.073% | no | 9.6% |
| alpha002 | +0.9% | −0.096% | no | 8.1% |
| alpha001 | +7.9% | −0.106% | no | 3.2% |
| alpha101 | −14.5% | −0.128% | no | 1.7% |
| alpha012 | −77.2% | −0.253% | no | 0.0% |

**0 of 9 alphas beat buy-and-hold; none clear the 95% excess-edge gate.**

## Conclusion

Alpha101 does **not** transfer to a 4-coin crypto basket — `rank()` across 4 names
has almost no cross-sectional breadth (these alphas assume thousands of stocks).
Joins the documented rejected-experiments list (Kronos, CandlePattern, 200d-MA
regime filter, Fear&Greed gate). **Do not import.**

What *could* still be worth a future spike (not done here): the **time-series**
factors from Qlib158 (many are single-asset momentum/volatility features) as
candidate inputs to a FreqAI **filter** — but only if the core edge is first
proven. The bottleneck remains the edge and the 30-day dry-run, not more signals.

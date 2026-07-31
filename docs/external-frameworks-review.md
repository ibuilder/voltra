# External frameworks & strategy-source review

**Date:** 2026-07-31. Reviewed two repos the user flagged, same discipline as the
Vibe-Trading / Kronos spikes: take what's concrete and testable, reject framework
sprawl, and prove any claim on our own Kraken data.

## 1. NautilusTrader (nautechsystems/nautilus_trader)

**What it is:** a production-grade, event-driven trading *platform* (Rust core +
Python), a direct competitor to Freqtrade. Order-book-level backtesting (queue
position, partial fills, latency), research-to-live parity, 17+ venue adapters
incl. Kraken. **No pre-built strategies, no proven edge** — pure infrastructure.
License: **LGPL-3.0** (copyleft — conflicts with our MIT if we vendored its code).

**Verdict: do NOT migrate; do NOT import.**
- Swapping Freqtrade → Nautilus discards our entire proven core (strategies,
  validation, dry-run, the whole stack) for another framework that *also* has no
  edge. The bottleneck has never been the framework.
- Its headline strength — order-book / microstructure execution realism — matters
  most for HFT/intraday. Our strategies are 1h/4h swing + weekly DCA: **not
  latency- or queue-sensitive**, so the thing Nautilus is best at barely helps us.
- We already run a **live dry-run** against real Kraken prices — that is *stronger*
  execution realism than any simulator.

**What we DID take — its one transferable lesson.** Nautilus exists because
*backtests that look good under optimistic fills often die under realistic
execution.* That's our discipline too, so we implemented it:
`scripts/execution_stress.py` re-runs the edge-significance test on our real 172
TrendBreak trades while adding progressively worse slippage.

| extra slippage (RT) | mean/trade | P(mean>0) |
|---|---|---|
| 0.00% | +0.49% | 93.4% |
| 0.10% | +0.39% | 89.5% |
| 0.25% | +0.24% | 77.8% |
| 0.40% | +0.09% | 60.8% |

The edge is **already below the 95% gate** under modeled costs and **collapses**
as fills get realistic. Exactly Nautilus's point, quantified — and one more
reason not to go live. No framework migration required.

## 2. awesome-systematic-trading (paperswithbacktest/…)

**What it is:** a curated **reading list** — papers, libraries, books — not
executable strategies. No backtested code, no reported edge; it points to
academic descriptions and libraries we already use (Freqtrade, vectorbt).

**Verdict: useful as a reference, nothing to import.** Its strategy *categories*
are trend-following (we run it — TrendBreak), MA-crossover (basic/public), and
**mean-reversion** — the one category we hadn't tested. So we tested it:
`research/systematic/meanrev_test.py`, "long the most-oversold coin daily," on our
basket.

| lookback | strat cum | beats hold? | P(excess>0) |
|---|---|---|---|
| 1d | −20% | no | 5.4% |
| 3d | −31% | no | 0.7% |
| 5d | −17% | no | 1.3% |
| 10d | +7% | no | 5.2% |

**REJECT.** Every lookback loses to buy-and-hold (+403% basket); buying the most-
oversold coin in a trending 4-coin basket is catching knives.

## Rejected-experiments ledger (running)

Kronos · Alpha101/Qlib zoo · CandlePattern · 200d-MA regime filter · Fear&Greed
gate · **mean-reversion** — all tested on our data, none cleared the fee-surviving
95% edge gate. NautilusTrader and Vibe-Trading frameworks: not imported (sprawl,
no edge). The consistent finding across every external source: **the bottleneck is
edge and evidence, not tooling, models, or more signals.** The needle only moves
with the 30-day dry-run.

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

## 3. CCXT (ccxt/ccxt)

**What it is:** the MIT-licensed unified exchange API library (100+ venues). We
already use it — **Freqtrade runs on CCXT under the hood**, and CLAUDE.md mandates
"use Freqtrade/CCXT abstractions." So there's nothing to "adopt"; it's already the
foundation.

**What we DID implement with it** — the useful direct application: measure the
*real* slippage on our pairs instead of guessing. `research/execution/
measure_slippage.py` pulls Kraken's live order book via CCXT (public, read-only)
and computes spread + fill slippage to market-buy a given size:

| pair | spread | buy $25 | buy $1000 |
|---|---|---|---|
| BTC/USD | 0.0 bps | 0.0 | 0.0 |
| ETH/USD | 0.1 bps | 0.0 | 0.0 |
| SOL/USD | 1.3 bps | 0.7 | 0.7 |
| XRP/USD | 0.9 bps | 0.4 | 0.9 |

Worst observed: **1.3 bps** — vs. the **5 bps (0.05%)** our backtests assume. So
**our slippage assumption is conservative**, and the edge weakness is *not* a
hidden execution cost; the signal itself is thin (confirming execution_stress.py).
A genuinely useful, honest result — and it closes the loop on the Nautilus lesson.

## 4. Microsoft Qlib (microsoft/qlib)

**What it is:** an MIT-licensed AI/ML quant *platform* (25+ model architectures,
Alpha158/Alpha360 factor libraries, RL execution, PIT database). **Equity-focused
(A-shares / US stocks), no native crypto.**

**Verdict: do NOT import.**
- It's a framework, like Nautilus/Vibe-Trading — infrastructure, not edge.
- Its factor libraries (Alpha158/360) are the **same cross-sectional family we
  already tested and rejected** (Alpha101, docs/alpha-zoo-report.md).
- Qlib's own premise is a large liquid universe (800+ names) for cross-sectional
  learning; the source itself notes it "transfers poorly" to a handful of assets.
  On our 4-coin basket the breadth is nil and overfitting risk is severe.
- The one forward idea it shares with our roadmap — ML *on factors* as a signal
  filter (our "FreqAI filter" note) — still needs a factor edge to filter, which
  every test says we don't have. Not worth building against 4 coins.

## 5. Hummingbot (hummingbot/hummingbot)

**What it is:** an Apache-2.0 framework for **market-making and arbitrage** —
liquidity provision, not directional trading. Core strategies: pure/Avellaneda/
cross-exchange market making, AMM arb. Supports Kraken spot.

**Verdict: do NOT import — decided by our own measured data.** Market making only
profits when the captured spread beats fees: `net/cycle ~= spread - 2 x maker_fee`.
We measured Kraken's live spreads with CCXT (`research/execution/mm_economics.py`):

| pair | live spread | | fee tier | maker/side | net/cycle (best spread) |
|---|---|---|---|---|---|
| BTC/USD | 0.5 bps | | $0 (retail) | 25 bps | **−48.7 bps** |
| ETH/USD | 0.8 bps | | $250k/mo | 10 bps | −18.7 bps |
| SOL/USD | 1.3 bps | | $1M/mo | 6 bps | −10.7 bps |
| XRP/USD | 0.1 bps | | $10M/mo | 0 bps | +1.3 bps |

The spreads are 0.1–1.3 bps *precisely because* professional MMs paying ~0 fees
already compressed them. To break even we'd need spread > 2× our maker fee
(>50 bps at retail; >12 bps even at $1M/mo). We have ~1 bps. **Every fee tier a
retail account can reach is deeply negative.** Arbitrage needs multiple funded
exchanges we don't run (Kraken-only). Hummingbot is a fine MM framework — for a
different game, at institutional fee tiers, than ours.

## 6. backtesting.py (kernc/backtesting.py)

**What it is:** a lightweight **single-instrument** OHLC backtester (AGPL-3.0) —
simple API, fast, built-in optimizer, interactive plots.

**Verdict: do NOT adopt — a downgrade + duplicate for us.**
- We already have Freqtrade backtesting: multi-pair crypto, realistic fee/slippage
  modeling, hyperopt, walk-forward, and live-trading parity. backtesting.py is
  single-asset with simpler execution modeling — the *opposite* of the execution-
  realism lesson (§1, §3).
- Our quick single-asset research niche is already covered by host pandas scripts
  (`alpha_test.py`, `meanrev_test.py`, `execution_stress.py`) — no Docker needed.
- **AGPL-3.0** is aggressive copyleft and conflicts with our MIT repo.
- Its only extras (interactive plots, optimizer) we don't need — we have hyperopt,
  our own analysis, and the cockpit.

## Rejected-experiments ledger (running)

Kronos · Alpha101/Qlib zoo · CandlePattern · 200d-MA regime filter · Fear&Greed
gate · **mean-reversion** — all tested on our data, none cleared the fee-surviving
95% edge gate. Frameworks not imported: NautilusTrader,
Vibe-Trading, **Qlib** (sprawl/no edge), **Hummingbot** (market-making is
structurally unprofitable at retail fees — proven with measured spreads),
**backtesting.py** (downgrade + duplicate + AGPL). Already the foundation / used
directly: **CCXT** (used it to measure real slippage AND market-making economics). The
consistent finding across every external source: **the bottleneck is edge and
evidence, not tooling, models, or more signals.** The needle only moves with the
30-day dry-run.

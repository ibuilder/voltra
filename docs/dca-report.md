# Conservative mode (DCA) — honest vs-buy-and-hold report

**Date:** 2026-07-31 · Strategy: `DcaAccumulateStrategy` · bot: `voltra-dca` (:8083)

## What it is

Dollar-cost averaging: buy a small **fixed** amount ($25) of each coin
(BTC/ETH/SOL/XRP) on a **weekly** schedule and **hold** — no market timing, no
take-profit, no stop-loss (only a far −50% catastrophe backstop). It rides out
dips and keeps buying them. This is the hands-off "Conservative" mode in the
cockpit, and a deliberate exception to the active-strategy risk rules
(see CLAUDE.md — DCA is a separate lower-risk category).

## Does it "make money"? The honest comparison

Equal-weight basket, daily, 2023-01-01 → 2026-03-31 (a mostly-rising window), same
total capital deployed either way:

| Approach | Return (on invested) | Max drawdown |
|---|---|---|
| **Lump-sum** (all in day 0, hold) | **+353%** | −63% |
| **DCA** (weekly buys) | **+28%** | −60% |

**DCA does NOT beat buy-and-hold** — not close, in a rising market. Because DCA
holds cash and deploys it slowly, most of the capital misses the early run-up.
Its drawdown is only marginally lower here, too.

So why offer it? Because "beat the market" is the wrong goal for a hands-off user:
- **No timing / no lump sum needed.** DCA is how you deploy *ongoing* income
  (you rarely have a lump sum to drop in on day 0). Return-on-invested understates
  it — each buy is made with money you didn't have on day 0.
- **Removes emotion.** Fixed schedule, no decisions, no panic-selling.
- **Smoother entry price** across volatility.

## Where it sits vs. our other modes

Uncomfortable but honest, from everything we've measured:

1. **Buy-and-hold the basket** — highest return, if you can stomach −60%+ dips.
2. **DCA (this mode)** — lower return, but disciplined and hands-off.
3. **Active TrendBreak** — currently *trails* buy-and-hold (dry-run scoreboard:
   −1.3% vs BTC +7.5%). The "clever" bot underperforms just holding.

The through-line of this whole project holds: for a passive user, boring beats
clever. DCA is the honest conservative option — not a money printer. The cockpit's
vs-buy-and-hold scoreboard will keep telling the truth for each mode.

## Verified

- Bot live in dry-run (`voltra-dca`, :8083), seeded $25 in all 4 coins, weekly
  adds via Freqtrade position adjustment. Schedule math unit-tested
  (`tests/test_strategies.py::test_dca_*`, 6 cases). No stop/RR/drawdown-halt by
  design; small fixed stake + catastrophe backstop + spot + dry-run per the DCA rule.

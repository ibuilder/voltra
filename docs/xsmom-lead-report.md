# The first real lead: cross-sectional momentum (16-coin basket)

**Date:** 2026-08-14 · **Verdict: the strongest edge candidate the project has
found — promote to full validation, with eyes open. NOT a live green light.**

## The finding

After 9 rejected attempts, hunting the documented crypto premia (research: Liu 2020,
Yang 2019, JFQA trend factor) with the breadth we finally have (16 pairs), one
cleared the honest gate: **cross-sectional momentum** — each week, hold the **top-3
coins by trailing 14-day return**, equal-weight, rebalance weekly.

Measured as **excess over the equal-weight-16 buy-and-hold basket** (so a bull
market can't fake skill), 2023-01 → 2026-03:

- Strategy **+1215%** vs buy-and-hold **+165%**
- Excess **+0.17%/day**, excess **Sharpe 1.40**, **P(excess>0) = 99.5%**
- Beats buy-and-hold in **3 of 4 years** (2023 +5%, 2024 +462%, 2025 +87%, 2026 −14%)
- Held **positive out-of-sample** on a train/test split (the first strategy to do so)

## Why this one is credible (the stress tests)

- **Fee-robust:** still clears the 95% gate at a punishing **0.50%/side** fee
  (P=95.1%) — far above the ~1 bps spreads we measured — so it is NOT a
  slippage/small-cap-cost artifact. Only breaks at an unrealistic 1.00%/side.
- **Academically grounded:** cross-sectional momentum is one of the most robust
  documented anomalies across asset classes and is specifically reported in crypto.
- **Enough frequency to actually validate:** weekly rebalance across 16 coins
  produces plenty of trades — a dry-run could confirm it in ~2 months, unlike
  TrendBreak (which was unprovable).

## The honest caveats (do not skip)

- **Brutal drawdown: −60%** (the literature's warning, confirmed). A hands-off
  user would panic out. This is NOT a low-stress, set-and-forget strategy.
- **Regime-dependent magnitude:** exclude the 2024 alt-season and P falls to 83%
  (still positive, +0.074%/day, but below the gate). A big part of the edge is
  "alts trend hard in bull markets." In a prolonged bear or a momentum crash, it
  bleeds.
- **Recent underperformance:** 2026 YTD it trailed the basket (−14% excess).
- **Survivorship bias:** the 16 pairs are ones that exist on Kraken *today*; coins
  that died aren't in the set, which flatters any momentum backtest. Needs
  survivorship-corrected data to fully trust.

## ⚠️ Survivorship correction (2026-08-14) — materially tempers the above

The headline +1215% was measured on 16 coins that *survived* to today, including
new-listing pumpers (WLD 2025-03, CELO/BNB 2025-04, SUI 2023-05). Momentum
backtests are especially flattered by both. `xsmom_survivorship.py` re-ran the
exact strategy on survivorship-safer universes:

| universe | strat vs hold | excess Sharpe | P(excess>0) |
|---|---|---|---|
| full 16 | +1215% vs +165% | 1.40 | 99% |
| full-window 12 (drop late-listers) | +757% vs +282% | 0.80 | 92% |
| **majors 9** (established, liquid) | +158% vs **+250%** | **−0.16** | **38%** |

**The edge halves when the new-listing pumps are removed, and disappears entirely
on liquid majors** (it underperforms buy-and-hold there). So the signal lives almost
entirely in **newer, smaller alts** — exactly where survivorship bias is worst,
liquidity thinnest, and real slippage highest. This is a large downgrade: much of
the apparent edge is new-listing / small-cap selection, not a robust momentum
premium a retail account can safely harvest.

## Verdict & next steps (revised after survivorship correction)

XS-momentum is still the **best lead the hunt produced** — the only signal to beat
buy-and-hold out-of-sample with a broad basket — but the survivorship correction
downgrades it from "promote toward a live sleeve" to **"observe honestly in dry-run;
do not commit real money."** The concrete reads:

- On **liquid majors it has no edge** (underperforms holding). Whatever edge exists
  is in **small/new-cap alts**, where the backtest is least trustworthy (dead coins
  invisible) and real slippage is worst — the CCXT measurement covered majors, not
  thin alts.
- So the backtest almost certainly **overstates** the live, tradable edge.

Therefore the honest plan is:

1. **Built** (done): Freqtrade strategy + `voltra-xsmom` dry-run bot on the 16-pair
   basket, with a drawdown circuit-breaker.
2. **Let the dry-run be the arbiter** — real fills on the *current* universe, real
   slippage on the small caps, no survivorship. Feed those into Monte Carlo as they
   accrue. This is now the decisive test, precisely because the backtest is
   survivorship-suspect.
3. **Do NOT plan live capital** on the backtest. Only reconsider if the *live*
   dry-run shows a genuine, liquidity-aware edge over a couple of months.
4. Expect the likely honest outcome to land between "small real edge in alts" and
   "zero after real costs" — the majors result says be skeptical.

For a passive, low-stress user, **DCA/hold is still the right core** — it never
draws down 60% relative to just holding. XS-momentum is the "active sleeve for
someone who can stomach the swings," and it's the first such thing worth building.

## Built & verified (2026-08-14)

Ported to a real Freqtrade strategy (`CrossSectionalMomentumStrategy`, config
`config.xsmom.json`, 16-pair basket, top-3 by 14d, weekly Monday rebalance,
MaxDrawdown circuit-breaker + −30% catastrophe stop). The critical check — does
the Freqtrade backtest reproduce the research edge *without* look-ahead:

| Freqtrade backtest (2023→2026, fee 0.1%/side) | value |
|---|---|
| Trades | 262 |
| Total profit | **+1607%** (research: +1215%; same ballpark) |
| Profit factor | 1.47 · Calmar 71 |
| Win rate | 46.6% (momentum: fewer, bigger wins) |
| Max drawdown | **−64.7%** (matches the ~−60% warning) |

Plausible, realistic numbers (no absurd 90% win-rate that a look-ahead bug
produces) → the port is sound. Ranking math unit-tested
(`tests/test_strategies.py::test_xsm_*`, 3 cases; 30 tests pass).

**Live dry-run started**: `voltra-xsmom` bot (:8084, dry-run), in the cockpit's
mode switcher as "Momentum — top-3 of 16". First trades on the next Monday
rebalance; ~2 months of fills will confirm (or refute) the backtested edge live.

## Scripts
`research/systematic/factor_premia_test.py` (walk-forward across premia) ·
`xsmom_robustness.py` (per-year + drawdown) · fee/ex-2024 stress inline.
Reproducible on host pandas, no Docker.

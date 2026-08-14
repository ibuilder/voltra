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

## Verdict & next steps

This is the **best outcome the hunt produced** — a genuine, fee-surviving,
significant cross-sectional-momentum edge, exactly where the theory said to look
once we had breadth. It earns promotion, not deployment:

1. **Port to a Freqtrade strategy** (top-3 by 14d, weekly rebalance, the 16-pair
   basket) with a drawdown circuit-breaker.
2. **Harder validation:** multi-fold walk-forward, survivorship-corrected data,
   and Monte Carlo on the realized trades.
3. **Dry-run** — now feasible (enough trades) to confirm in ~2 months.
4. Only after all that, and only as a **small risk-managed sleeve** (not the
   passive core), consider tiny live capital.

For a passive, low-stress user, **DCA/hold is still the right core** — it never
draws down 60% relative to just holding. XS-momentum is the "active sleeve for
someone who can stomach the swings," and it's the first such thing worth building.

## Scripts
`research/systematic/factor_premia_test.py` (walk-forward across premia) ·
`xsmom_robustness.py` (per-year + drawdown) · fee/ex-2024 stress inline.
Reproducible on host pandas, no Docker.

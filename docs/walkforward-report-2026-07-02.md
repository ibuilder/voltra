# Phase 3 — Hyperopt + walk-forward report (2026-07-02)

**Method**: 300-epoch hyperopt per strategy (MultiMetricHyperOptLoss, seed 42)
on **2024 data only**; tuned parameters then backtested untouched on
**2025-01-01 → 2026-07-02** (out-of-sample). Fees 0.105%/side, protections on.
Rejection rule: OOS profit factor drop >30% vs in-sample = overfit, discard.

## Results

| Metric | TrendBreak IS (2024) | TrendBreak OOS (25–26) | SolCross IS (2024) | SolCross OOS (25–26) |
|---|---|---|---|---|
| Trades | 79 | 61 | 18 | 8 |
| Profit | +13.0% | +10.6% | +2.0% | +0.8% |
| Profit factor | 1.28 | **1.28** | 1.77 | **1.56** |
| Max drawdown | 10.8% | 8.6% | 1.0% | 1.1% |
| PF degradation | — | **0%** ✅ | — | **12%** ✅ |

Pre-tuning baseline (full period): TrendBreak PF 0.76, SolCross PF 0.43 —
both strategies flipped from losing to modestly profitable, and neither
collapsed out-of-sample. The walk-forward rule passes for both.

## Tuned parameters (committed in user_data/strategies/*.json)

- **TrendBreak**: volume ≥2.4× avg, breakout buffer 0.8% above the level
  (skip marginal pokes), stop 2.2×ATR, target 2.7R, trail after 1.9R.
  The optimizer's message: *take far fewer, far cleaner breakouts* —
  79 trades/year vs 150 before.
- **SolCross**: majors momentum ≥1.5%/4h, lag ≥0.4%, stop 3.8×ATR (wide —
  sized down automatically by the 1% risk rule), target 3.7R, trail after
  1.6R, abandon after 11h. The max-hold exit fixed the biggest bleed.

## Against the Phase 5 live gates

| Gate | Required | TrendBreak OOS | SolCross OOS |
|---|---|---|---|
| Profit factor | >1.3 | 1.28 ❌ (by a hair) | 1.56 ✅ |
| Max drawdown | <15% | 8.6% ✅ | 1.1% ✅ |
| 30-day dry-run match | pending | ⏳ started 2026-07-02 | ⏳ started 2026-07-02 |

## Honest caveats — read before getting excited

1. **SolCross's sample is 26 trades in 2.5 years.** PF 1.56 on 8 OOS trades
   is statistically indistinguishable from luck. It stays experimental; the
   dry-run divergence check matters more than the backtest for this one.
2. **TrendBreak misses the PF gate by 0.02** — treat 1.28 as "keep watching",
   not "almost there". Its consolation: 61 OOS trades with zero PF
   degradation is a genuinely stable configuration.
3. Data is Coinbase research-grade; re-validate on real Kraken data when the
   trades backfill completes.
4. One hyperopt pass = one shot of selection bias. Monthly re-hyperopt with
   walk-forward (Phase 6) is the guard against regime change, not a promise.

## Addendum: CandlePatternStrategy (Strategy B) — REJECTED

Implemented per plan section 3B (hammer / bullish engulfing / morning star,
gated to the 38.2–61.8% fib retracement of the last swing, confirmation
candle required, 4h uptrend filter, same ATR/RR framework; 7 signal tests).

| Config | Trades | Profit | PF | Max DD |
|---|---|---|---|---|
| Defaults, 2024–2026 | 513 | −45.3% | 0.69 | 47.2% |
| Hyperopt best, 2024 in-sample | 165 | −14.2% | 0.66 | 15.1% |

Even the optimizer's best configuration loses in-sample — there is no edge
to validate out-of-sample. The optimizer converged on "minimize damage"
(zone_tolerance 0, stop 4×ATR), which is what a search looks like when the
entry signal carries no information. **Not deployed to any bot.** The code
and tests stay in the repo as reference; revisit only with a fundamentally
different gating idea (e.g., order-flow or higher-timeframe confluence),
not more parameter tuning.

## Deployed

Both dry-run bots now run the tuned parameters (auto-loaded from the .json
param files). Main bot switched PlaceholderStrategy → TrendBreakStrategy,
whitelist aligned to the validated pairs (BTC/ETH/SOL). Phase 4's 30-day
dry-run clock starts now: 2026-07-02.

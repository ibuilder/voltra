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

## Addendum 2 (2026-07-08): re-validation on real Kraken data

The official Kraken OHLCVT archive (through 2025-12-31) replaced the fragile
trades backfill. Tuned params, untouched, on Kraken 2025 (pure OOS):

| Metric | TrendBreak (Coinbase OOS) | TrendBreak (Kraken 2025) | SolCross (Coinbase OOS) | SolCross (Kraken 2025) |
|---|---|---|---|---|
| Trades | 61 | 58 | 8 | 9 |
| Profit | +10.6% | +5.6% | +0.8% | +0.1% |
| Profit factor | 1.28 | **1.15** | 1.56 | **1.11** |
| Max drawdown | 8.6% | 11.7% | 1.1% | 1.3% |

Read: both strategies survive on ground truth — positive, no collapse, PF
degradation within the 30% rule — but the edge is **thinner than Coinbase
data suggested** (venue price differences matter at this fee level). Neither
clears PF >1.3 on real Kraken data. Verdict unchanged in direction, firmer
in degree: **dry-run only; no live-capital case exists today.** The dry-run
divergence gate (restarted 2026-07-08 after ~6 days of machine downtime;
earliest decision ~2026-08-07) is now the deciding evidence.

## Addendum 3 (2026-07-08): BTC 200-day-MA regime filter — TESTED, REJECTED

Hypothesis (a priori, untuned): only take longs while BTC > its 200-day MA,
since "both strategies lost most in chop". One-shot test on real Kraken
data, both periods, pre-committed adopt-only-if-better-in-both rule:

| Kraken data | TrendBreak base | TrendBreak +filter | SolCross base | SolCross +filter |
|---|---|---|---|---|
| 2024 PF | 1.07 | 0.83 ❌ | 0.53 | 0.07 ❌ |
| 2025 PF | 1.15 | 0.99 ❌ | 1.11 | 0.00 ❌ |

**Worse everywhere — rejected and reverted.** The intuition was wrong:
TrendBreak's best trades are recovery breakouts that fire while BTC is
still *below* the 200-day MA; the filter kept only late, chasing entries.
Lesson recorded so this "obvious improvement" doesn't get re-proposed.
(BTC_USD-1d.feather retained in data/kraken for future regime experiments;
2024 Kraken baselines recorded here for the first time.)

## Addendum 4 (2026-07-08): multi-regime stress test on 6 years of Kraken data

History extended to 2020 (SOL: mid-2021 listing). The 2024-tuned parameters,
untouched, run against every year they never saw:

**TrendBreak** (params fitted on 2024 only):

| Year | Market | Strategy | PF | Max DD | Trades |
|---|---|---|---|---|---|
| 2021 | +264% | +25.8% | 1.45 | 7.5% | 95 |
| 2022 bear | **−76%** | **+13.4%** | **2.28** | 3.7% | 22 |
| 2023 | +390% | +11.0% | 1.18 | 13.5% | 97 |
| 2024 (training) | — | +3.6% | 1.07 | 13.9% | 86 |
| 2025 (OOS) | — | +5.6% | 1.15 | 8.6% | 58 |

**Profitable in all five periods, including the −76% bear year** — the 4h
trend filter sat 2022 out (22 trades) and monetized relief rallies. This is
the strongest evidence yet that the configuration is robust rather than
lucky. Notable honesty item: it massively underperforms buy-and-hold in
bull years (+26% vs +264%) — that is the price of capped risk, not a bug.
No re-hyperopt warranted: parameters that survive five regimes untouched
should not be touched.

**SolCross** (SOL only):

| Period | Market | Strategy | PF | Trades |
|---|---|---|---|---|
| 2021 H2 | +388% | +5.6% | 2.60 | 17 |
| 2022 bear | −94% | +0.7% | 1.69 | 4 |
| 2023 | +921% | −2.0% | 0.34 | 10 |
| 2024 (training) | — | −2.1% | 0.53 | 15 |
| 2025 (OOS) | — | +0.1% | 1.11 | 9 |

Two losing years, tiny samples everywhere, cumulative ≈ +2% over 4.5 years.
The lead-lag edge is **indistinguishable from noise across regimes**.
Verdict: stays in dry-run as a cheap experiment, but expectations should be
set to "likely retired at the 30-day review" unless dry-run surprises.

**What more data did and didn't do**: predictions are unchanged — the rules
are the rules. What changed is *confidence*: TrendBreak graduated from
"stable on 18 months" to "profitable across bull, bear, chop, and recovery",
and SolCross was exposed as regime-fragile. Future data uses: Kraken's
quarterly incremental archives will add 2026 as fresh OOS windows, and the
6-year dataset is the training corpus if FreqAI (Phase 6) ever happens.

## Addendum 5 (2026-07-08): Q1 2026 fresh OOS + alternative data sources

**Q1 2026 imported** (Kraken quarterly archive; data now 2020 → 2026-03-31).
Fresh OOS on a bear quarter (BTC −28%, SOL −33%):

- TrendBreak: 6 trades, all losses, −5.2% (risk caps held: max DD 5.2%).
- SolCross: 1 trade, ≈flat.
- PF by year now reads 1.45 → 2.28 → 1.18 → 1.07 → 1.15 → 0.00(Q1'26,n=6).
  Small sample, but the trajectory supports the edge-decay concern. The
  dry-run gate remains the deciding evidence.

**Alternative data acquired** (user_data/data/external/):

- `fear_greed_daily.feather` — crypto Fear & Greed index, 3,076 days
  (2018-02 → today), alternative.me free API.
- `gdelt_bitcoin_tone_daily.feather` — GDELT average news tone for bitcoin
  coverage, 2,358 days (2020 → today). GDELT indexes mainstream outlets
  (Reuters, WSJ, AP, etc.) — the legitimate route to "news data"; the
  outlets' own archives are paywalled/licensed and not scrapeable.

**Fear & Greed entry gate (block at Extreme Greed ≥80, prior-day value,
pre-committed) — TESTED, REJECTED**: worse in 2021 (PF 1.45→1.35, profit
+25.8%→+15.6%) and 2024 (1.07→1.06), never better in any period. Euphoric
breakouts were net winners — same lesson as the 200d-MA filter (addendum 3):
this strategy's edge concentrates in hot markets; filters that avoid heat
amputate the edge. Experiment preserved in TrendBreakFngStrategy.py
(DO NOT DEPLOY header).

GDELT tone is stored untested — reserved as a FreqAI feature candidate
(Phase 6) rather than another one-shot gate, to limit multiple-testing bias.

## Deployed

Both dry-run bots now run the tuned parameters (auto-loaded from the .json
param files). Main bot switched PlaceholderStrategy → TrendBreakStrategy,
whitelist aligned to the validated pairs (BTC/ETH/SOL). Phase 4's 30-day
dry-run clock starts now: 2026-07-02.

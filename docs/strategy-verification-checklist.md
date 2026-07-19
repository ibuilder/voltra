# Strategy verification checklist

Every strategy must clear this before dry-run promotion, and every gate before
live capital. Distilled from the project's own rules + the AI-trading-bot
playbook research (Monte Carlo, win-rate paradox, repaint/lookahead, cost
realism). Do not relax a gate to fit a result.

## 1. Correctness (before any backtest is trustworthy)

- [ ] **No lookahead/repaint.** Indicators use only closed-bar data
      (`shift(1)` / `high[1]`). Pine: no `request.security` without
      `lookahead_off` + `[1]`; alerts fire on bar close. (See the audit note in
      `strategies/pine/*.pine`.)
- [ ] **Stops trigger on confirmed fills, not intrabar touch.** Freqtrade
      `custom_stoploss` + `stoploss_on_exchange` handle this; verify in the
      first live week that stop orders actually appear in the exchange book.
- [ ] Signal unit tests pass (entry fires on the setup, not mid-range).

## 2. Cost realism

- [ ] Fees + slippage modeled: `--fee 0.00105` (0.16% RT taker + 0.05%
      slippage). Never quote a fee-free backtest.
- [ ] Tested across multiple market regimes (bull/bear/chop) — we use
      2021–2026 Kraken data incl. the 2022 −76% bear.

## 3. Overfitting controls

- [ ] Hyperopt on the training window only; validate out-of-sample.
- [ ] Reject if OOS profit factor drops > 30% vs in-sample.

## 4. Statistical significance (Monte Carlo) — the win-rate paradox guard

A high win rate or a single good backtest is not an edge. Run
`scripts/montecarlo.py` on the strategy's real trades:

- [ ] **P(mean per-trade > 0) ≥ 95%** in bootstrap (5,000+ sims).
- [ ] **Median bootstrap max-drawdown < 15%.**
- [ ] Bootstrap P(profitable over the test horizon) reported and understood.
- [ ] Kelly fraction computed; if Kelly ≈ 0, the edge is too thin to size —
      do not deploy regardless of a pretty equity curve.

> Status 2026-07-16: TrendBreak (172 trades) FAILS this — P(mean>0)=81%,
> median MC max-DD=16%. See montecarlo-report-2026-07-16.md.

## 5. Live gates (all must pass — currently NOT met)

| Gate | Threshold | TrendBreak |
|---|---|---|
| OOS profit factor | > 1.3 | ✗ 1.07–1.18 |
| Backtest max drawdown | < 15% | ✗ MC median 16% |
| MC edge significance | P(mean>0) ≥ 95% | ✗ 81% |
| 30-day dry-run vs backtest | within ~20% | ⏳ pending unbroken uptime |
| Fresh trade-only API key | present | ✗ |

## 6. The honest fix when a gate fails

- Insignificant edge → **more sample or a stronger signal**, not re-tuning the
  same trades. Feed accumulating dry-run fills back into the Monte Carlo.
- Too much drawdown → smaller size / better exits / regime gating (test it —
  our 200d-MA and Fear&Greed gates were tried and REJECTED; document any new one).
- If gates keep failing, the correct outcome may be: do not trade this live.

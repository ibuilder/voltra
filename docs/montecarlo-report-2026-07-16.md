# Monte Carlo edge validation — 2026-07-16

Method from the "AI trading bot playbooks" research: don't trust a single
backtest path; **bootstrap the actual trades thousands of times** and read the
*distribution* of outcomes. Built as `scripts/montecarlo.py`.

Input: 172 real TrendBreak trades (BTC/ETH/SOL/XRP, 2024–2026, fees modeled),
resampled as **account-level** returns (profit_abs / $5,000 wallet — the honest
account view, not per-position profit_ratio which overstates both return and
drawdown).

## Result (5,000 simulations)

| Metric | Value | Read |
|---|---|---|
| Actual total return | +18.6% (PF 1.18) | one path over 2 years |
| Bootstrap median return | +18.4% | typical path |
| Bootstrap 5th–95th pct | **−17.1% … +71.3%** | wide; downside is real |
| **P(profitable over 2y)** | **77.1%** | ~23% of paths lose money |
| Mean return / trade | +0.11% | tiny |
| 90% CI of the mean | **−0.10% … +0.33%** | lower bound is negative |
| **P(mean per-trade > 0)** | **80.8%** | **below the 95% edge bar** |
| Kelly fraction | +5.7% (half: +2.8%) | thin positive edge |
| Median max drawdown | **16.0%** | already > the 15% gate |
| 95th-pct / worst max DD | 29.4% / 46.5% | severe tail risk |

## Verdict

**The edge is NOT statistically significant.** At 81% confidence the mean
per-trade return is positive — you want ≥95% before risking money. Roughly one
in five two-year paths loses money outright, and the realistic drawdown (median
16%, tail to 46%) exceeds the project's own 15% max-drawdown gate. The single
backtest's ~13% drawdown was an optimistic draw, not the expected experience.

This does not say the strategy is worthless — Kelly is positive (+5.7%), the
payoff ratio (1.94) is healthy, and the median path is clearly up. It says the
**sample is too small and the edge too thin to trust yet**: 172 trades cannot
distinguish a real +0.11%/trade edge from noise at the confidence level that
should gate real capital.

## What this changes

1. **New hard gate** (added to the verification checklist): a strategy needs
   **P(mean > 0) ≥ 95%** in bootstrap AND **median bootstrap max-DD < 15%**
   before live capital — in addition to the existing PF/OOS/dry-run gates.
   TrendBreak currently fails both.
2. **More evidence, not more tuning.** The fix for an insignificant edge is a
   larger sample (more pairs, longer history, or the ongoing dry-run trades) or
   a genuinely stronger signal — not re-hyperopting on the same 172 trades.
3. The dry-run remains the live evidence stream; feed its real fills into this
   same tool as they accumulate.

Run it yourself:
```
python scripts/montecarlo.py user_data/backtest_results/tb_account_returns.json --sims 5000
```

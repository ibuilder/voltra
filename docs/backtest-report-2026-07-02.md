# Backtest report — 2026-07-02

**Data**: Coinbase Exchange hourly OHLCV (research-grade proxy; Kraken trades
backfill still running), 2024-01-03 → 2026-07-02, 100% candle coverage.
**Costs modeled**: fee 0.105%/side (= 0.16% round-trip taker + 0.05% slippage).
**Protections enabled**, 1% risk sizing active, $5,000 starting balance.

## Verdict vs the Phase 5 live gates

| Gate | Required | TrendBreak | SolCrossSignal |
|---|---|---|---|
| Profit factor | > 1.3 | 0.76 ❌ | 0.43 ❌ |
| Max drawdown | < 15% | 40.5% ❌ | 16.6% ❌ |
| Profitable at all | — | −39.4% ❌ | −13.7% ❌ |

**Neither strategy goes anywhere near live capital in its current form.**

## TrendBreakStrategy (BTC+ETH+SOL, 379 trades)

- Win rate 33.8%, Sharpe −0.88, CAGR −18.2%. Market itself was +0.5%.
- The exit-reason table tells the story: the 71 trades that reached the 1:2
  target were great (+$5,542, 100% winners by construction), but **189 trades
  died on the initial stop** (−$7,304). The 2×ATR stop is too tight for 1h
  breakout noise — most breakouts retrace through it before trending.
- Diagnosis: entry quality (any 20-bar high on volume) is too loose; a raw
  breakout entry buys local tops. Needs retest-based entries, wider stops with
  smaller size, or a regime filter — hyperopt territory, Phase 3.

## SolCrossSignalStrategy (SOL only, 51 trades)

- Win rate 19.6%, PF 0.43, −13.7% (vs SOL buy-and-hold −19.0% — beat the
  market, still lost money).
- The lead-lag thesis shows a pulse: all 4 trades that reached the 2:1 target
  won, and entries are rare (0.06/day) as designed. But the **always-trailing
  2×ATR stop choked 28 trades** out at −0.76% avg before the catch-up move
  could develop, and 11 hit the full stop.
- Diagnosis: exits, not entries, are the main defect. Trail only after 1R
  (like TrendBreak does), or hold for a fixed horizon since the thesis is
  "SOL catches up within hours", not "SOL trends".

## What this means (per the plan's own rules)

This is the process working, not failing: fees+slippage modeled, gates
enforced, and no parameter was fitted to this data yet. Next steps per
Phase 3:

1. Hyperopt both strategies on **2024 data only** (stops, RR, volume
   multiplier, momentum thresholds).
2. Validate out-of-sample on 2025–2026; reject any config whose OOS profit
   factor drops >30% vs in-sample.
3. Re-run this report on real Kraken data when the backfill completes.

Dry-run continues meanwhile — it costs nothing and exercises the plumbing.

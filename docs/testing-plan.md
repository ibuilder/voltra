# SolSignal testing-phase plan (dry-run → go/no-go)

Start: 2026-07-14 (whitelist finalized to BTC/ETH/SOL/XRP).
Purpose: decide, with evidence, whether TrendBreak's thin edge is real enough
to risk real money — or not.

## What is running

| Bot | Port | Strategy | Whitelist | Role |
|---|---|---|---|---|
| solsignal-dry | 8080 | TrendBreak (tuned) | BTC/ETH/SOL/XRP | primary candidate |
| solsignal-cross | 8081 | SolCross lead-lag | SOL | tracked experiment |

Both dry-run, $5,000 paper each. Reporter container writes
`docs/reports/report-<date>.md` daily. Dashboards: 8080 (FreqUI), 8899 (custom).

## The 30-day clock — checkpoints

Judge at the 30-day mark, not before; early weeks are tiny samples.

- **Day 0 (done)**: whitelist finalized, bots running, data restored, tests
  green (21), containers healthy.
- **Weekly**: read the report. Confirm the bot is actually up (uptime is the
  #1 risk — see below), trades are firing, and divergence isn't wild.
- **Day 30 (~2026-08-13)**: the go/no-go decision below.

## Go / no-go decision tree (at day 30)

1. **Was the bot up ~continuously?** If it was offline for days (Docker/sleep),
   the sample is invalid → extend, don't decide. (This already happened once.)
2. **Did dry-run track backtest within ~20%?** Trades/week and PnL vs the
   expectations in `scripts/report.py`. Large negative divergence = the
   backtest lied (slippage, fills) → do NOT go live.
3. **Do the plan's hard gates pass?**
   - OOS profit factor > 1.3 — **currently FAILING (4-pair 2025 PF 1.07)**
   - backtest max drawdown < 15% — passing (13.7%)
   - 30-day dry-run within 20% — TBD
4. **If gates fail** (likely on PF): the honest options, in order —
   a. Keep dry-running; it costs nothing. Collect more evidence.
   b. Improve the edge (Phase 6 below), re-validate walk-forward.
   c. Decide the edge is too thin and stop. This is a legitimate outcome.
   Do **not** relax the gates to fit the results.
5. **If all gates pass**: follow `production-checklist.md` section E. Start at
   $500–1,000, keep dry-run running as the control.

## The #1 operational risk: uptime

The machine has taken the bots offline twice (reboot with no Docker
autostart; sleep). Each outage invalidates the dry-run window. Before trusting
any 30-day result:
- Enable Docker Desktop autostart + disable AC sleep (checklist section A), OR
- Move to a $5–10/mo VPS (`git clone` + `.env` + `docker compose up -d`).
Until this is fixed, the dry-run clock cannot be trusted to run unbroken.

## Phase 6 backlog (only if the edge needs improving)

Ordered by expected value, all requiring walk-forward validation before adoption:
1. Monthly re-hyperopt on a rolling window (edge maintenance, not tuning).
2. FreqAI as a *filter* on TrendBreak entries, trained on the 6-year dataset
   + the GDELT/Fear&Greed features already stored in data/external/. This is
   the one "adaptive model" worth trying — but as a filter, never a signal
   generator, and only if it beats baseline out-of-sample.
3. Quarterly Kraken archive import (`import_kraken_csv.py --merge`) to keep the
   backtest set current and add fresh OOS windows.

## Rejected — do not re-propose (all tested, documented)

CandlePattern strategy · BTC 200d-MA regime filter · Fear & Greed entry gate
· broad-basket "trade everything" · hand-picking coins by single-window PF.
See walkforward-report addenda 3–5 and per-coin-analysis-2026-07-14.md.

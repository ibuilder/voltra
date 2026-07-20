# Voltra roadmap

A Now / Next / Later view. Honest about the fact that the single most important
milestone is not a feature — it's proving (or disproving) the edge. See the
[Monte Carlo report](docs/montecarlo-report-2026-07-16.md) and the
[verification checklist](docs/strategy-verification-checklist.md).

## ✅ Done

- Freqtrade Docker stack; dry-run config; FreqUI + custom dashboard; screener.
- TrendBreak & SolCross strategies with 1% ATR sizing, on-exchange stops,
  MaxDrawdown/StoplossGuard/Cooldown protections.
- 6 years of ground-truth Kraken data; hyperopt + walk-forward validation.
- Per-coin edge analysis → validated basket **BTC/ETH/SOL/XRP**.
- **Monte Carlo + Kelly edge validation** (`scripts/montecarlo.py`).
- Enterprise ops: Caddy TLS ingress, health monitoring + dry-run tripwire,
  backups + tested restore, rate limiting, log rotation, CI.
- TradingView / Pine v6 webhook bridge (isolated experimental bot).
- Tauri desktop controller + signed autoupdater.
- WordPress monitor plugin with persistent data collection + CSV export.
- Trade/audit ledger export; incident runbook; key-rotation procedures.
- Free 24/7 deployment path (Oracle Always-Free + systemd).

## 🔜 Now (the only milestone that matters)

- [ ] **Run an unbroken 30-day dry-run** on the free VM. Uptime is the #1 risk.
- [ ] Feed accumulating real fills into `montecarlo.py` and watch whether
      P(edge>0) climbs from 81% toward the 95% gate.
- [ ] Read the weekly divergence report; decide go / no-go at day 30.

## ⏭️ Next (only if the edge proves out)

- [ ] Monthly re-hyperopt on a rolling window, walk-forward validated
      (reject >30% OOS degradation). Edges decay; this is maintenance.
- [ ] A market-regime filter that actually survives validation (the 200d-MA
      and Fear&Greed filters were tested and **rejected** — documented).
- [ ] Grow the validated pair set via the screener to increase sample size.
- [ ] Telegram alerting wired end-to-end.

## 🧭 Later (product direction, if this becomes a business)

- [ ] FreqAI as a *filter* on existing signals (never a signal generator).
- [ ] Additional strategy families: funding-rate carry, mean-reversion pairs.
- [ ] Hosted multi-bot offering (the "sell AI trading bots" direction) — only
      on top of strategies that have cleared every gate on real capital first.
- [ ] Public performance page driven by the WordPress data-collection layer.

## Non-goals

- Promising profit. Voltra is a disciplined process, not a money machine.
- Shipping any live-trading default. `dry_run: false` is always a human-only,
  per-deployment decision.
- Relaxing a gate to make a strategy "pass."

# Production checklist — Voltra go-live runbook

Nothing here promises profit. The measured edge (real Kraken data, fees
modeled) is PF 1.15 / ~+5.6%/yr on TrendBreak — at $1,000 that's roughly
$50/yr if reality matches backtest. Going live is buying *information*
about whether it does, at a price you cap yourself.

## A. Machine readiness (do these NOW — they protect the dry-run gate)

- [ ] **One-command autostart install** (recommended). In PowerShell:
  `powershell -ExecutionPolicy Bypass -File C:\Server\voltra\scripts\install-autostart.ps1`
  This copies `scripts\start-voltra.cmd` into your Startup folder (brings
  the whole stack up at every login) and disables AC sleep/hibernate. No admin
  needed. Undo instructions print at the end. Absence of this cost 6 days of
  dry-run in July — it is the #1 production task.
- [ ] Verify after next login: `docker compose ps` shows all 4 containers up,
  and `user_data\logs\autostart.log` has a fresh "compose up -d done" line.
- [ ] **Or better: a small VPS** (~$5–10/mo, e.g. Hetzner/DigitalOcean).
  `git clone` + copy `.env` + `docker compose up -d` is the whole migration.
  A box that reboots or sleeps will eventually miss a stop-loss placement
  window or invalidate another dry-run month.
- [ ] Containers are self-healing otherwise: `restart: unless-stopped` +
  healthchecks. Check anytime with `docker compose ps` (look for "healthy").

## B. Exchange account (before funding)

- [ ] **Rotate the API key** — the current one transited a chat conversation.
  Kraken → Settings → API → delete old, create new, paste into `.env`.
- [ ] Permissions on the new key: Query Funds ✓, Query Orders & Trades ✓,
  Create & Modify Orders ✓, Cancel Orders ✓, **Withdraw ✗ (never)**.
- [ ] **IP whitelist** the key to this machine's/VPS's public IP.
- [ ] 2FA on the Kraken account itself; withdrawal address allowlisting on.

## C. Monitoring (during the 30-day window)

- [ ] Telegram alerts: create a bot via @BotFather, put token + chat id in
  `.env`, set `FREQTRADE__TELEGRAM__ENABLED=true`, restart. Do this NOW so
  you trust the alert path before real money depends on it.
- [ ] Read `docs/reports/report-<date>.md` weekly (regenerated daily by the
  reporter container). Divergence beyond ±20% at the 30-day mark = no-go.
- [ ] Dashboards: FreqUI http://127.0.0.1:8080 · custom http://127.0.0.1:8899

## D. The gates (from the plan — all must pass; currently NOT passed)

| Gate | Threshold | Status 2026-07-08 |
|---|---|---|
| OOS profit factor | > 1.3 | ❌ TrendBreak 1.15, SolCross 1.11 (real Kraken data) |
| Backtest max drawdown | < 15% | ✅ 11.7% / 1.3% |
| 30-day dry-run divergence | within ~20% | ⏳ window ends ~2026-08-07 |

If PF stays under 1.3 on ground truth, the honest options are: keep
dry-running, improve the strategies (regime filter, monthly re-hyperopt with
walk-forward — Phase 6), or don't go live. Do NOT relax the gates to fit
the results.

## E. Go-live day (human-only, in this order)

1. Fund Kraken with $500–1,000 — money you can lose entirely.
2. Fresh API key (B) in `.env` on the production machine.
3. Set `dry_run_wallet` aside: edit `user_data/config.live.json` —
   set `stake_currency` funding matches, review `max_open_trades: 3`.
4. **The flip (yours alone)**: `config.live.json` → `"dry_run": false`.
5. Point ONE compose service at `config.live.json` (copy the `freqtrade`
   service, new name/port/db-url) — keep the dry-run bots running as the
   control group.
6. `docker compose up -d` → watch the first trades in FreqUI + Telegram.
7. First week: check daily that on-exchange stop orders actually appear in
   Kraken's order book after each entry (Orders → Open). A bot crash must
   leave protected positions, not naked ones.

## F. Rollback (know it before you need it)

- Stop live trading now: `docker compose stop <live-service>` — open
  positions keep their on-exchange stops.
- Flatten everything: FreqUI → force-exit all, or Kraken web UI directly.
- Kill switch is automatic: MaxDrawdown protection halts entries at −3%/day;
  the −8% hard stoploss caps any single position.

## G. What actually improves the odds of making money (Phase 6)

1. Monthly re-hyperopt on a rolling window, walk-forward validated, same
   >30%-degradation rejection — edges decay; this is maintenance, not tuning.
2. A market-regime filter (e.g., only long when BTC > its 200-day MA) —
   both strategies lost most in chop; trade less, keep more.
3. More validated pairs via the screener list (each needs its own backtest
   before joining the live whitelist).
4. FreqAI as a *filter* on existing signals, never as the signal.
5. Accept slow: at 1% risk/trade and PF ~1.2, wealth comes from decades or
   better strategies, not from this month.

# Voltra enterprise production readiness

Status: **platform hardened; live trading NOT authorized.** This document
covers the production *infrastructure*. Whether to trade real money is a
separate, human-only decision gated below.

## The go-live boundary (read first)

"Production ready" here means the **platform** is secure, observable, and
recoverable. It does **not** mean the system trades real money. Flipping to
live is blocked by four independent gates, all still open:

| Gate | Status | Owner |
|---|---|---|
| `dry_run: false` flip | never done by tooling | **human only** |
| OOS profit factor > 1.3 | ❌ 1.07 (4-pair) | evidence |
| 30-day dry-run within 20% | ⏳ needs unbroken uptime | evidence |
| Fresh trade-only Kraken key | ❌ current key invalid | human |

Every bot runs `dry_run: true`, and the **healthwatch tripwire** fires CRITICAL
if any bot ever reports `dry_run: false` — an unauthorized live-mode bot is
treated as a security incident.

## Architecture (9 services, one Docker network)

```
                         Internet (TradingView, you)
                                   │  HTTPS 443
                        ┌──────────▼───────────┐
                        │  caddy (TLS ingress) │  security headers, HSTS
                        └───┬───────┬───────┬──┘
              /frequi/ →    │  /webhook/ →  │   / →
                  ┌─────────▼──┐ ┌──▼───────────┐ ┌▼───────────┐
                  │ freqtrade  │ │ webhook-relay│ │ dashboard  │
                  │  (bot #1)  │ │  (secret)    │ │ (static)   │
                  └────────────┘ └──┬───────────┘ └────────────┘
                  ┌────────────┐    │ forceenter/exit
                  │freqtrade-  │ ┌──▼───────────┐
                  │cross(bot#2)│ │freqtrade-    │
                  └────────────┘ │webhook(bot#3)│
                                 └──────────────┘
   sidecars: reporter (divergence) · healthwatch (alerts+tripwire) · backup
```

## Security posture

- **TLS termination** at Caddy (auto Let's Encrypt with a real domain, TLS 1.3,
  HSTS, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`,
  `-Server`). Local dev uses Caddy's internal CA (self-signed).
- **Rate limiting**: 120 req/min/IP at the ingress (custom Caddy image with the
  rate-limit module, `ops/Caddy.Dockerfile`). First run: `docker compose build caddy`.
- **Secrets** only in `.env` (gitignored): exchange keys, API creds, JWT/WS
  tokens, relay secret. `config*.json` hold no secrets (keys injected from env).
  Back `.env` up in a password manager, never in git or the backup archives.
- **Container hardening**: every service runs `no-new-privileges`, json-file
  log rotation (10 MB × 5), and the bots have a 1 GB memory limit.
- **Relay auth**: shared secret validated server-side, constant-time compare.
- **Network**: all host port bindings are `127.0.0.1`-only today.

### Production lockdown (do on the VPS, before exposing anything)

1. Remove the `127.0.0.1:80xx` port lines from the bot/relay/dashboard services
   so **only Caddy** is reachable; the rest talk over the private compose net.
2. Publish Caddy on `80:80` and `443:443`; set `VOLTRA_DOMAIN` +
   `CADDY_ACME_EMAIL` → automatic real TLS cert.
3. Host firewall: allow only 22/80/443; enable fail2ban on SSH.
4. Exchange account: 2FA on, API key trade-only + IP-whitelisted + no withdraw.

## Observability & alerting

- **healthwatch** polls every bot each 60s (90s startup grace, 2-poll debounce
  to avoid flapping). Alerts to log always, plus `ALERT_WEBHOOK_URL` and/or
  Telegram if configured. The `dry_run` tripwire alerts immediately (no
  debounce).
- **reporter** writes the dry-run-vs-backtest divergence report every 6h.
- **healthchecks** on all bots (`/api/v1/ping`) drive Docker restart/visibility.
- Dashboards: FreqUI (`/frequi` via Caddy, or :8080) and the custom board (:8899).

## Backups & disaster recovery

- **backup** sidecar archives trade DBs + configs + tuned params every 6h to
  `user_data/backups/`, retaining 28 (~1 week). Secrets excluded by design.
- **RPO** ≈ 6h (worst-case data loss between backups). Tighten via
  `BACKUP_INTERVAL`. Copy `user_data/backups/` off-box for real DR.
- **RTO**: minutes. Restore procedure:
  1. `git clone` the repo on the target host.
  2. Restore `.env` from your password manager.
  3. Extract the latest archive over `user_data/`:
     `tar xzf user_data/backups/voltra-<stamp>.tar.gz -C user_data/`
  4. `docker compose up -d` → healthwatch confirms all bots `ok`.
- Market data is reproducible from `scripts/import_kraken_csv.py`, so it is not
  in the backup (keeps archives small).

## CI

`.github/workflows/ci.yml` runs the pytest suite (strategy signal logic +
relay logic), validates every JSON config/param, and lints the compose file on
push/PR.

## Operations

- **Trade/audit ledger**: `python scripts/export_ledger.py` → CSV of every
  trade (dates, prices, fees, realized P&L, exit reason) for accounting/tax
  records. Reads the SQLite DBs directly.
- **Incident runbook**: docs/incident-runbook.md (tripwire, crash mid-position,
  failed stop, exchange outage, partial fills, emergency flatten).
- **Key rotation**: docs/key-rotation.md (schedule + per-secret procedures).

## What is intentionally NOT here (documented, not built)

- Full Prometheus/Grafana metrics stack — overkill for a single node; the
  healthwatch + reporter cover the actual signals. Add if you scale out.
- Basic-auth / rate-limit on Caddy routes — FreqUI has JWT auth and the relay
  has its secret; add a bcrypt basic_auth block and a rate-limit plugin build
  if exposing widely.
- Secrets manager (Vault) — `.env` + password manager is proportional here.

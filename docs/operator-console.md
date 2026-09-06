# Operator checklist — desktop console (dry-run)

Use this after the Voltra Controller is installed. Trading stays in Docker.
The app never sets `dry_run: false`. Live trading is a separate, human-only
edit — do not do it from this list.

Do the three stages **in order**. Stop if a box fails.

## 0. Before you start

- [ ] Docker Desktop (or Engine) is installed and running on this machine **or**
      you will only use Remote VPS (skip local Docker then).
- [ ] You have a Voltra checkout with `docker-compose.yml`.
- [ ] `.env` exists (`cp .env.example .env`) and
      `FREQTRADE__API_SERVER__PASSWORD` is set.
- [ ] Confirm no committed config is live:

```
python3 scripts/check_console.py
```

That check also proves Caddy `/bot/*` routes, compose services, and the
desktop slug list still match.

## 1. Local snapshot

In the Controller: **Local stack**.

- [ ] Project folder is the Voltra checkout (Browse if the default is wrong).
- [ ] Docker banner is green. If not: install Docker, or **Copy .env.example**.
- [ ] **Start stack** (or `docker compose up -d` in the checkout).
- [ ] Fleet cards appear for momentum, DCA, TrendBreak, lead-lag, webhook.
- [ ] Click TrendBreak (dry). Mode pill says **dry-run**, not LIVE.
- [ ] If **LIVE TRIPWIRE** shows: stop. You did not enable that from the app.
      Inspect `user_data/config*.json` and do not continue to remote.

Local URLs (loopback only):

| Bot | Port |
|---|---|
| TrendBreak (dry) | `http://127.0.0.1:8080` |
| SolCross | `http://127.0.0.1:8081` |
| Webhook | `http://127.0.0.1:8082` |
| DCA | `http://127.0.0.1:8083` |
| XS-momentum | `http://127.0.0.1:8084` |
| Cockpit | `http://127.0.0.1:8899` |

## 2. Caddy on the 24/7 host

On the VPS (Oracle or Hetzner), from the repo root:

```
git pull
./scripts/deploy.sh
```

`deploy.sh` refuses to start if any `user_data/config*.json` has
`dry_run: false`. It waits for **all five** bots to report healthy
(including DCA and XS-momentum).

- [ ] `.env` on the VPS has a real `VOLTRA_DOMAIN` (public hostname, not an IP)
      and `CADDY_ACME_EMAIL`.
- [ ] After deploy: `https://<domain>` loads the cockpit.
- [ ] These paths exist (Caddy `handle_path`):

```
https://<domain>/bot/dry
https://<domain>/bot/dca
https://<domain>/bot/xsmom
https://<domain>/bot/cross
https://<domain>/bot/webhook
https://<domain>/frequi
```

Host guides: [deploy-oracle-free.md](deploy-oracle-free.md) ·
[deploy-hetzner.md](deploy-hetzner.md).

## 3. Remote TLS probe

In the Controller: **Remote VPS**.

- [ ] Origin is `https://your-domain` only — no `/bot/…`, no IP, no `http://`.
- [ ] WebUI user/password match the VPS `.env`. Save (OS keychain).
- [ ] **Test TLS connection** succeeds. It JWT-auths `/bot/dry` only.
- [ ] Fleet loads over TLS. Tripwire stays off.
- [ ] Laptop Docker is **not** required in this mode. 24/7 stays on the VPS.

If the probe fails: Caddy not redeployed, wrong password, or the hostname
resolves to a private address (the client refuses that).

## Do not do from the console

- Do not flip `dry_run` in any config from this app (it cannot, and must not).
- Do not call Freqtrade start/stop/forceenter via REST from the controller.
- Do not treat **Apply Kraken key to .env** as go-live. That only writes keys.
- Do not publish a GitHub release as latest until you have run stages 1–3
  against a real bot.

Build/release notes: [desktop-app.md](desktop-app.md).
Go-live (later, human-only): [production-checklist.md](production-checklist.md).

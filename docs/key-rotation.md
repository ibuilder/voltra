# Secret & key rotation

All secrets live in `.env` (gitignored) or wp-config.php — never in git.
Rotate on a schedule and immediately on any suspected leak. After editing
`.env`, apply with `docker compose up -d --force-recreate <service>`.

## Schedule

| Secret | Routine | Always rotate if… |
|---|---|---|
| Kraken API key/secret | every 90 days | leaked, or before first go-live |
| `RELAY_SECRET` | every 90 days | TradingView webhook exposed / leaked |
| API_SERVER password | every 90 days | shared or leaked |
| JWT_SECRET_KEY / WS_TOKEN | every 180 days | leaked |
| WordPress plugin creds | with API password | WP DB compromised |
| Tauri updater signing key | only if leaked | leaked (then re-release) |

## 1. Kraken API key (do before go-live — the current one is invalid)

1. Kraken → Settings → API → **Add key**. Permissions: Query Funds, Query
   Orders & Trades, Create & Modify Orders, Cancel Orders. **NO withdrawal.**
2. **IP-whitelist** the key to your VPS/desktop public IP.
3. Put the new values in `.env`:
   ```
   FREQTRADE__EXCHANGE__KEY=...
   FREQTRADE__EXCHANGE__SECRET=...
   ```
4. `docker compose up -d --force-recreate freqtrade freqtrade-cross freqtrade-webhook`
5. Verify: `docker logs solsignal-freqtrade` shows no auth error; a balance
   call succeeds.
6. **Delete the old key** on Kraken.

## 2. RELAY_SECRET (TradingView webhook)

1. `python -c "import secrets; print(secrets.token_urlsafe(24))"` → new value in
   `.env` as `RELAY_SECRET=`.
2. `docker compose up -d --force-recreate webhook-relay`.
3. Update the secret in your TradingView alert payload(s) to match.

## 3. API_SERVER password (FreqUI / dashboard / WP plugin)

1. New value → `.env` `FREQTRADE__API_SERVER__PASSWORD=`.
2. `docker compose up -d --force-recreate freqtrade freqtrade-cross freqtrade-webhook`.
3. Update it wherever it's used: FreqUI login, the custom dashboard, and the
   WordPress plugin settings (or `SOLSIGNAL_API_PASSWORD` in wp-config.php).

## 4. JWT_SECRET_KEY / WS_TOKEN

New 32-byte hex each (`python -c "import secrets; print(secrets.token_hex(32))"`)
in `.env`, then force-recreate the bots. Existing FreqUI sessions will need to
re-login.

## 5. Tauri updater signing key (only if leaked)

The private key is the update trust root. If it leaks, an attacker could push a
malicious update. To rotate: generate a new keypair
(`npx @tauri-apps/cli signer generate`), update the pubkey in
`desktop/src-tauri/tauri.conf.json`, replace the repo secret, and cut a new
release. Users on the old key must reinstall manually.

## Leak response

1. Rotate the affected secret(s) now (above).
2. For a Kraken-key leak: also review recent orders/withdrawals on Kraken and
   enable/verify withdrawal address allowlisting + account 2FA.
3. Note the incident in the runbook.

# Incident runbook

What to do when things break. Assumes the Docker stack (see
docker-compose.yml) and the enterprise deployment (docs/enterprise-readiness.md).
Keep this reachable from your phone.

**Golden rule:** if you are unsure and money is at risk, **flatten and stop**
first, diagnose second. In dry-run nothing is at risk — practice these now.

## Fast commands

```bash
cd /opt/solsignal            # or C:\Server\solsignal
docker compose ps                                  # health of all services
docker logs solsignal-freqtrade --tail 100         # a bot's log
docker logs solsignal-healthwatch --tail 50        # alerts + tripwire
docker compose restart <service>                   # restart one service
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d  # bring all up
```

FreqUI (manual control): http://127.0.0.1:8080 (or https://<domain>/frequi).
Kraken web UI is the ultimate manual override for real positions.

---

## 1. DRY-RUN TRIPWIRE fired (bot reports dry_run=false)

**Severity: CRITICAL.** A bot is live and nobody authorized it.
1. Stop that bot immediately: `docker compose stop <service>`.
2. Check who/what changed the config: `git log -p -- user_data/config*.json`.
3. If unexplained, treat as a breach: rotate the Kraken key and all secrets
   (docs/key-rotation.md), review access.
4. Do not restart until the config is confirmed `dry_run: true` and the cause
   is understood.

## 2. Bot crashed / restarting mid-position (live)

Freqtrade + `restart: unless-stopped` auto-restart the container, and on boot
freqtrade **reconciles** open trades from its DB against the exchange. If the
stoploss was placed on-exchange (`stoploss_on_exchange: true`), the position
stayed protected while the bot was down.
1. Confirm it recovered: `docker compose ps` (healthy) and FreqUI shows the
   open trade with its stop.
2. Verify the stop order exists on Kraken (Orders → Open). If missing → §3.
3. Check the log for the crash cause; if it crash-loops, `docker compose stop`
   the bot and flatten manually (§6) before investigating.

## 3. Stop-loss failed to place on the exchange

Risk: a naked position with no protection.
1. FreqUI → the trade → **Force exit**, OR place a manual stop/market-sell on
   Kraken directly.
2. Check exchange connectivity and API-key permissions (needs Create/Modify
   Orders). A key with only query rights can read but not place stops.
3. Once flat/safe, restart the bot and confirm the next entry places its stop.

## 4. Exchange outage / API errors

Freqtrade retries transient errors. Positions with on-exchange stops remain
protected by Kraken even if the bot can't reach the API.
1. Confirm it's the exchange, not you: check Kraken status page + your network.
2. Do NOT panic-flatten on a brief blip. If the outage is prolonged and you
   hold positions, decide via the Kraken web UI directly.
3. After recovery, freqtrade reconciles automatically; verify open trades match
   between FreqUI and Kraken.

## 5. Partial fills / stuck orders

Freqtrade handles partial fills and cancels unfilled orders after
`unfilledtimeout` (10 min in our config). If an order is stuck:
1. FreqUI → cancel the open order, or cancel on Kraken.
2. Check `order_types` and `unfilledtimeout` in the config if it recurs.

## 6. Emergency: flatten everything and stop

1. FreqUI → each open trade → **Force exit** (market). OR on Kraken web:
   sell each held asset to USD manually.
2. Stop the live bot: `docker compose stop <live-service>`.
3. Cancel any remaining open orders on Kraken.
4. Confirm zero open positions and zero open orders before walking away.

## 7. Dry-run diverges sharply from backtest (divergence alert)

Not an emergency, but a stop signal for going live.
1. Read the latest `docs/reports/report-<date>.md`.
2. Large negative divergence = slippage/fills worse than modeled → the backtest
   overstated the edge. Do NOT go live. Feed real fills into
   `scripts/montecarlo.py` and re-check significance.

## 8. Disk full / DB corruption

1. Log rotation caps container logs (10 MB × 5). If the disk still fills, check
   `user_data/logs/` and `user_data/backups/` sizes.
2. DB corruption: stop the stack, restore the latest archive
   (docs/enterprise-readiness.md → DR), restart.

## After any incident

- Note what happened, the impact, and the fix here or in a dated file.
- If it can recur, add a test or a monitor so it pages you next time.

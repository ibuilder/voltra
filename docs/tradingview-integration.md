# TradingView / Pine Script v6 integration

## What this is (and is not)

**Pine Script v6** (TradingView's Nov-2024 charting language) and TradingView
"signals" (webhook alerts) are now integrated as an **optional, isolated,
experimental** input — not a replacement for the validated strategies.

**Read this first — the discipline caveat.** External TradingView signals
**cannot be backtested, walk-forward validated, or fee/slippage-modeled** in
our framework. They bypass the exact process that is this project's real edge.
So TradingView drives a **separate bot #3 only**, dry-run, tracked apart from
the validated TrendBreak/SolCross bots. Never point TradingView at the primary
bots. A TV signal that "looks great on the chart" is precisely the kind of
unvalidated input the build plan warns against.

## The two legitimate uses

1. **Prototyping (recommended).** Sketch an idea visually in Pine v6, then
   *port the logic to a Python strategy* where it CAN be backtested and
   walk-forward validated (see workflow below). `strategies/pine/*.pine` are
   reference translations, not the source of truth.
2. **Experimental live signalling.** Route TradingView alerts to bot #3 to see
   how an external signal behaves in dry-run — still wrapped in Voltra's
   ATR stop + 1% sizing + protections.

## Architecture

```
TradingView (Pine v6 alert)                     your machine / VPS
   |  HTTPS POST {secret, action, pair}      +---------------------------+
   +---------------------------------------> | webhook-relay :8090       |
                                             |  validate shared secret   |
                                             |  normalize pair           |
                                             +------------+--------------+
                                                          | REST forceenter/exit
                                             +------------v--------------+
                                             | freqtrade-webhook (bot#3) |
                                             |  :8082 dry-run, isolated  |
                                             |  ATR stop + 1% + protect  |
                                             +---------------------------+
```

- **webhook-relay** (`webhook_relay/relay.py`, FastAPI): validates the shared
  secret, maps `action` -> forceenter/forceexit, normalizes `pair`
  (`KRAKEN:BTCUSD` / `BTCUSD` / `ETH/USDT` -> `BTC/USD` etc).
- **bot #3** (`WebhookRelayStrategy`): generates no signals of its own; entries
  arrive only via `/forceenter`. Every forced trade still gets a 2xATR
  on-exchange stop and the MaxDrawdown/StoplossGuard/Cooldown protections.
  Profit exits are left to TradingView (`action:"close"`); the ATR stop is the
  crash-safety if a close alert never arrives.

## Payload format

TradingView alert message (must be valid JSON so TV sends `application/json`):

```json
{"secret": "<RELAY_SECRET from .env>", "action": "buy", "pair": "BTC/USD"}
```

- `action`: `buy|long|enter|open` -> entry; `sell|close|exit|flat` -> exit
- `pair` (or `ticker`): `BTC/USD`, `BTCUSD`, `KRAKEN:BTCUSD`, `ETH/USDT` all work
- `secret`: must equal `RELAY_SECRET` in `.env` (else 401)

## Setup

1. Bot #3 + relay run automatically (`docker compose up -d`). Relay health:
   `curl http://127.0.0.1:8090/health`.
2. Local smoke test (no TradingView needed):
   ```
   SECRET=$(grep ^RELAY_SECRET= .env | cut -d= -f2)
   curl -X POST http://127.0.0.1:8090/webhook -H 'Content-Type: application/json' \
        -d "{\"secret\":\"$SECRET\",\"action\":\"buy\",\"pair\":\"BTC/USD\"}"
   ```
3. **Expose the relay to TradingView** — the relay binds to `127.0.0.1:8090`
   and TradingView is on the public internet, so you need an HTTPS tunnel:
   - Easiest: Cloudflare Tunnel (`cloudflared tunnel --url http://localhost:8090`)
     or ngrok (`ngrok http 8090`) -> use the `https://.../webhook` URL in the alert.
   - Production: a real reverse proxy (Caddy/nginx) with TLS.
   - **Never expose plain http.** The shared secret is the only auth; without
     TLS it travels in cleartext.
4. In TradingView: add `VoltraTrendBreak.pine` to a chart -> Create Alert ->
   Condition = the indicator -> Webhook URL = your tunnel `/webhook` -> paste the
   JSON payload as the alert message (with your real secret). Needs **TV Pro+**.

## Pine v6 -> Python porting workflow (the disciplined path)

1. Prototype the idea in Pine v6 on TradingView charts; eyeball it across
   regimes.
2. Translate the entry/exit logic into a `pandas`-only function in a new
   `user_data/strategies/*.py` (mirror the existing strategies' structure).
3. Backtest it: `docker compose run --rm freqtrade backtesting --strategy X
   --timerange 20240101- --fee 0.00105 --enable-protections`.
4. Hyperopt on 2024, validate out-of-sample on 2025-2026, reject if OOS PF
   drops >30%.
5. Only then deploy to a dry-run bot. Same gates as everything else.

## Pine v6 notable features (for reference)

Dynamic multi-symbol `request.*()` (now allowed in loops/conditionals),
`bid`/`ask` on the `1T` timeframe, enums, runtime `log.*`, polylines, stricter
bool casting (`if myFloat` -> `if myFloat != 0`), lazy `and`/`or`, and strategy
order auto-trimming past 9,000 orders. Migrate v5 scripts via the Pine Editor's
"Convert to v6".

## Security checklist

- [ ] Relay reachable only via HTTPS (tunnel/proxy), never plain http.
- [ ] `RELAY_SECRET` is long/random and lives only in `.env` (gitignored).
- [ ] Bot #3 stays `dry_run: true` — same human-only rule as every bot.
- [ ] Rotate `RELAY_SECRET` if it ever leaks; restart the relay.

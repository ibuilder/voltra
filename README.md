# SolSignal

Freqtrade crypto trading bot. Kraken (primary) / Coinbase Advanced Trade (backup),
pairs BTC/USD · ETH/USD · SOL/USD plus screener output.

**Mode discipline: Backtest → Dry-run (30+ days) → Small live capital. Never skip a stage.**

## Setup

1. Install Docker Desktop (done) and make sure it's running.
2. `cp .env.example .env` and fill in WebUI credentials (exchange keys not needed
   until the live gate; Telegram optional).
3. `docker compose pull`
4. `docker compose up -d` → FreqUI at http://127.0.0.1:8080

`user_data/config.json` (dry-run) and `user_data/config.live.json` are
**gitignored by design** — secrets stay in `.env`, and configs never leave this
machine. If you clone fresh, regenerate them from the build plan.

## Build phases

| Phase | Deliverable | Status |
|---|---|---|
| 0 | Scaffold: repo, Docker, dry-run config, WebUI | ✅ done |
| 1 | `scripts/screener.py` + 2y of 1h/4h OHLCV | ✅ screener done; backfill runs in background |
| 2 | TrendBreakStrategy + pytest + backtest report | ⬜ |
| 3 | CandlePatternStrategy + hyperopt + walk-forward | ⬜ |
| 4 | 30-day dry-run on always-on machine + `scripts/report.py` | ⬜ |
| 5 | Live gate (human decision only) | ⬜ |
| 6 | Strategy C (ICT/MacroWindow, experimental) + FreqAI filter | ⬜ |

## Live gate (all must pass)

- Out-of-sample profit factor > 1.3
- Backtest max drawdown < 15%
- 30-day dry-run within ~20% of backtest expectancy
- Start with $500–1,000 max; keep dry-run running in parallel as control

## Risk rules (coded into every strategy — see CLAUDE.md)

Max 1% risk/trade · max 3 positions (2 correlated) · −3% daily kill switch ·
cooldown after 2 straight losses · stoploss on-exchange · fees 0.16% RT +
0.05% slippage in every backtest.

## Kraken-specific notes

- Kraken's OHLCV endpoint only serves the last 720 candles, and Freqtrade
  blocks plain candle downloads for Kraken entirely — all history comes from
  trades-based download (`--dl-trades`). The `data-daemon` compose service
  handles this in the background: a one-time 2y backfill of BTC/ETH/SOL
  (many hours; `user_data/data/.backfill_complete` marks it done), then an
  incremental refresh of every screened pair every 6h. Check progress with
  `docker compose logs -f data-daemon`. Keep `user_data/data/` — it is the
  product of that work.
- Refresh the pair whitelist anytime with `python scripts/screener.py`, then
  copy new pairs into `user_data/config.json` and restart.
- Freqtrade handles Kraken's XBT↔BTC naming; always write `BTC/USD` in configs.
- Rate limit is set to 3100ms in config per Freqtrade's Kraken recommendation.

## Disclaimer

Most retail algo traders lose money. The edge is the process — realistic
fee/slippage modeling, walk-forward validation, the 30-day dry-run gate, small
sizing — not the entry signals. Treat the first six months as tuition.
Technical guidance, not financial advice.

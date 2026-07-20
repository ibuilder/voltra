<p align="center">
  <img src="brand/logo/voltra-logo-tagline.png" alt="Voltra — Crypto Trading Engine" width="420">
</p>

<p align="center">
  <a href="https://github.com/ibuilder/voltra/actions"><img src="https://img.shields.io/badge/tests-33%20passing-brightgreen" alt="tests"></a>
  <img src="https://img.shields.io/badge/mode-dry--run-0ea5e9" alt="dry-run">
  <img src="https://img.shields.io/badge/license-MIT-6366f1" alt="MIT">
  <img src="https://img.shields.io/badge/status-experimental-7c3aed" alt="experimental">
</p>

<p align="center">
  <b>An automated crypto trading engine built the honest way:</b><br>
  backtest → walk-forward → Monte Carlo → 30-day dry-run → small live capital. Never skip a stage.
</p>

<p align="center">
  <a href="https://ibuilder.github.io/voltra/">Website</a> ·
  <a href="ROADMAP.md">Roadmap</a> ·
  <a href="CHANGELOG.md">Changelog</a> ·
  <a href="DISCLAIMER.md">Disclaimer</a> ·
  <a href="docs/enterprise-readiness.md">Architecture</a>
</p>

---

Freqtrade-based crypto trading bot. Kraken (primary) / Coinbase Advanced Trade
(backup), pairs BTC/USD · ETH/USD · SOL/USD plus screener output.

> **Honest status:** this is experimental software in the validation phase. The
> current strategy's edge is **not yet statistically significant** (Monte Carlo
> P(edge>0) = 81%, below the 95% bar) — see
> [the Monte Carlo report](docs/montecarlo-report-2026-07-16.md). It runs in
> **paper-trading (dry-run) only**. Not financial advice; you can lose money.

## Desktop app (run it on its own)

The **Voltra Controller** is a lightweight Tauri system-tray app that manages
the whole Docker stack — start/stop, live status, open dashboard, and a checkbox
to launch at login (no manual Startup-folder steps). It's a controller only; it
never enables live trading. Build/release and GitHub setup:
[docs/desktop-app.md](docs/desktop-app.md). Source in `desktop/`.

**Important:** read [DISCLAIMER.md](DISCLAIMER.md) — experimental software,
trading carries real risk of loss, not financial advice, default is paper only.

## Host it 24/7 for free

To run the stack always-on and reach it from anywhere, deploy to a free VM:
[docs/deploy-oracle-free.md](docs/deploy-oracle-free.md) (Oracle Cloud
Always-Free ARM, $0/mo). Production overlay `docker-compose.prod.yml` exposes
only Caddy (TLS) publicly; `scripts/deploy.sh` + `deploy/voltra.service`
make it turnkey and boot-persistent. At small capital, free hosting is the
right call — a paid VPS would cost more than the strategy is expected to earn
(see the cost analysis in that guide).

## Setup (Docker directly)

1. Install Docker Desktop (done) and make sure it's running.
2. `cp .env.example .env` and fill in WebUI credentials (exchange keys not needed
   until the live gate; Telegram optional).
3. `docker compose pull`
4. `docker compose up -d` →
   - **FreqUI** (full control panel, bundled with freqtrade): http://127.0.0.1:8080
   - **Voltra dashboard** (custom Tailwind read-only view): http://127.0.0.1:8899
   Both use the same login from `.env` (`FREQTRADE__API_SERVER__USERNAME`/`PASSWORD`).
   The custom dashboard is a single static page (`dashboard/index.html`) that reads
   the freqtrade REST API; its origin must be listed in `api_server.CORS_origins`
   in `user_data/config.json`.

`user_data/config.json` (dry-run) and `user_data/config.live.json` are
**gitignored by design** — secrets stay in `.env`, and configs never leave this
machine. If you clone fresh, regenerate them from the build plan.

## Bots ↔ dashboards: how they connect

Mental model: **a "bot" is one freqtrade process** (one Docker container) defined
by one config file + one strategy + one SQLite database + one REST API port.
**Dashboards are just API clients** — they hold no data and run no strategies;
they log into a bot's REST API (username/password from `.env` → JWT token) and
render what it reports. Any dashboard can point at any bot.

Current fleet:

| Bot | Container | API port | Strategy | Pairs |
|---|---|---|---|---|
| voltra-dry | voltra-freqtrade | 8080 | TrendBreakStrategy (tuned) | BTC/ETH/SOL/XRP |
| voltra-cross | voltra-freqtrade-cross | 8081 | SolCrossSignalStrategy | SOL/USD |
| voltra-webhook | voltra-freqtrade-webhook | 8082 | WebhookRelayStrategy (TradingView-driven, experimental) | BTC/ETH/SOL/XRP |

Plus `webhook-relay` (:8090) bridging TradingView alerts → bot #3 — see
[docs/tradingview-integration.md](docs/tradingview-integration.md).

To view a bot:
- **FreqUI** (http://127.0.0.1:8080): top-left bot selector → "Add new bot" →
  enter `http://127.0.0.1:8081` + the `.env` username/password. FreqUI stores
  multiple bots and switches between them.
- **Voltra dashboard** (http://127.0.0.1:8899): pick the bot's API URL from
  the dropdown on the login screen.

To register a NEW bot (bot #3, etc.):
1. Copy `user_data/config.json` → `config.<name>.json`; change `bot_name` and
   `pair_whitelist`.
2. Add a compose service like `freqtrade-cross`: unique container name, unique
   host port (`127.0.0.1:8082:8080`), unique `--db-url` sqlite file, and the
   `--strategy` it should run. `docker compose up -d <service>`.
3. Add its URL in FreqUI ("Add new bot") and/or the dashboard datalist in
   `dashboard/index.html`.

The bots share nothing but the `.env` login and the `user_data/data/` candle
cache — separate wallets, separate trades, separate databases.

## Build phases

| Phase | Deliverable | Status |
|---|---|---|
| 0 | Scaffold: repo, Docker, dry-run config, WebUI | ✅ done |
| 1 | `scripts/screener.py` + 2y of 1h/4h OHLCV | ✅ screener done; backfill runs in background |
| 2 | TrendBreakStrategy + pytest + backtest report | ✅ both strategies implemented, 14 tests pass; backtests on 2.5y data: **both fail the gates** — see [docs/backtest-report-2026-07-02.md](docs/backtest-report-2026-07-02.md) |
| 3 | CandlePatternStrategy + hyperopt + walk-forward | ✅ TrendBreak & SolCross pass the overfit rule; **CandlePattern implemented, tested, and REJECTED** (loses even in-sample after tuning) — see [docs/walkforward-report-2026-07-02.md](docs/walkforward-report-2026-07-02.md) |
| 4 | 30-day dry-run on always-on machine + `scripts/report.py` | 🔶 dry-run running; whitelist finalized to validated basket BTC/ETH/SOL/XRP ([per-coin analysis](docs/per-coin-analysis-2026-07-14.md)); plan in [testing-plan.md](docs/testing-plan.md) |
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

## Weekly report

`python scripts/report.py` writes `docs/reports/weekly-<date>.md`: per-bot
PnL, drawdown, and — the Phase 5 gate input — divergence between dry-run
results and pro-rata backtest expectations (>20% = red flag, judge at day 30).
To automate it, create a Windows scheduled task (run once, as admin if needed):

    schtasks /Create /SC WEEKLY /D MON /ST 08:00 /TN "Voltra Weekly Report" ^
      /TR "\"C:\laragon\bin\python\python-3.10\python.exe\" \"C:\Server\voltra\scripts\report.py\""

## Kraken-specific notes

- Kraken's OHLCV endpoint only serves the last 720 candles, and Freqtrade
  blocks plain candle downloads for Kraken entirely — all history comes from
  trades-based download (`--dl-trades`). The `data-daemon` compose service
  handles this in the background: a one-time 2y backfill of BTC/ETH/SOL,
  then a 6-hourly incremental refresh of every screened pair. At ~1,000
  trades per request and a 3.1s rate limit, the BTC backfill realistically
  takes **days** — the daemon survives restarts, and
  `user_data/data/.backfill_complete` marks completion. Check progress with
  `docker compose logs -f data-daemon`. Keep `user_data/data/` — it is the
  product of that work.
- Faster path if Phase 2 needs data sooner: Kraken publishes official
  quarterly OHLCVT CSV archives (support.kraken.com → "Downloadable
  historical OHLCVT data") that convert to freqtrade format in minutes.
- Refresh the pair whitelist anytime with `python scripts/screener.py`, then
  copy new pairs into `user_data/config.json` and restart.
- Freqtrade handles Kraken's XBT↔BTC naming; always write `BTC/USD` in configs.
- Rate limit is set to 3100ms in config per Freqtrade's Kraken recommendation.

## Disclaimer

Most retail algo traders lose money. The edge is the process — realistic
fee/slippage modeling, walk-forward validation, the 30-day dry-run gate, small
sizing — not the entry signals. Treat the first six months as tuition.
Technical guidance, not financial advice.

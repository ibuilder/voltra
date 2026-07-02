# SolSignal — Freqtrade crypto bot

## Rules for Claude Code
- Python 3.11, Freqtrade framework, Docker deployment. Do not hand-roll exchange
  API code — use Freqtrade/CCXT abstractions.
- NEVER set dry_run: false. Live config changes are human-only.
- Every strategy must implement: 1% risk sizing, ATR stoploss (on-exchange),
  1:2 min RR, MaxDrawdown + CooldownPeriod protections.
- Every strategy change requires: unit tests pass + backtest report
  (2024–2026, fees 0.16% RT, slippage 0.05%) before commit.
- Hyperopt only on training window; always validate out-of-sample.
- Secrets via .env only. Confirm .gitignore covers config*.json and .env.
- Timeframes: 1h entries, 4h informative trend filter.
- Pairs: BTC/USD, ETH/USD, SOL/USD + screener output.

## Commands
- Backtest: docker compose run --rm freqtrade backtesting --strategy <S> --timerange 20240101-
- Hyperopt: docker compose run --rm freqtrade hyperopt --strategy <S> --spaces buy sell --timerange 20240101-20250101
- Dry-run:  docker compose up -d

# Changelog

All notable changes to this project are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/); this project uses date-based
milestones (pre-1.0, no semantic-version guarantees yet).

## [Unreleased]

### Added
- **Desktop controller (Tauri v2)** — a lightweight system-tray app that
  starts/stops the Docker stack, shows live service status, opens the
  dashboard, and self-enables run-on-login. No manual Startup-folder step.
- **Signed autoupdater** — GitHub Releases + `latest.json`; updates are
  signature-verified and prompt before installing (never silent).
- **Release CI** (`.github/workflows/release.yml`) builds the Windows
  `.exe`/`.msi` via `tauri-action` on `app-v*` tags.
- LICENSE (MIT), DISCLAIMER, CHANGELOG.

## [2026-07-15] Enterprise hardening + testing

### Added
- Caddy TLS ingress (HSTS, security headers, single front door).
- `healthwatch` monitoring sidecar with a **dry-run tripwire** (alerts CRITICAL
  if any bot reports `dry_run: false`).
- Automated backup sidecar (6h, retention, restore-drill verified).
- Compose hardening: `no-new-privileges`, log rotation, memory limits.
- CI running the test suite (33 tests) + JSON/compose validation.
- TradingView / Pine v6 integration: webhook relay + isolated experimental
  bot #3, with the disciplined Pine→Python porting workflow.

### Fixed
- Critical: the old `data-daemon` was silently truncating the historical data
  archive to 14 days; removed it, data now from the quarterly Kraken archive.
- Reporter stale-report race; monitoring startup false-alarms (grace+debounce).

## [2026-07-08] Strategy validation

### Added
- TrendBreak (Strategy A) and SolCross (BTC/ETH→SOL lead-lag) strategies with
  1% ATR risk sizing, on-exchange stops, and protections.
- Hyperopt + walk-forward validation; 6 years of ground-truth Kraken data.
- Per-coin edge analysis → validated basket **BTC/ETH/SOL/XRP**.

### Rejected (documented, kept for reference)
- CandlePattern strategy, BTC-200d-MA regime filter, Fear & Greed entry gate —
  all tested, none improved out-of-sample results.

## [2026-07-01] Scaffold

### Added
- Freqtrade Docker stack, dry-run config, FreqUI, custom dashboard, screener.

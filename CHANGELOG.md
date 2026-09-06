# Changelog

All notable changes to this project are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/); this project uses date-based
milestones (pre-1.0, no semantic-version guarantees yet).

## [Unreleased]

### Added
- **Operator console checklist** — `docs/operator-console.md` (local snapshot →
  Caddy deploy → remote TLS probe). `scripts/check_console.py` keeps Caddy
  slugs, compose ports, deploy health waits, and the desktop client aligned.
- **Desktop live snapshot** — Tauri controller JWT-auths to localhost
  Freqtrade bots (creds from `.env`) and shows a fleet strip plus balance,
  closed+open P&L, W/L, drawdown, and open positions. Tokens stay in Rust;
  `dry_run` is never flipped. A LIVE tripwire banner appears if a bot reports live.
- **Docker health in the controller** — detects missing CLI / stopped daemon /
  wrong folder / missing `.env`, with copy-from-example and an install link.
  Login autostart waits until Docker is ready.
- **Remote VPS console** — desktop can JWT to `https://<domain>/bot/{dry,dca,xsmom,cross,webhook}`
  (Caddy TLS). Origin allowlisted (HTTPS, public hostname, known slugs).
  WebUI creds in the OS keychain. Laptop Docker is not started in remote mode.
- **Caddy** now exposes `/bot/dca` and `/bot/xsmom` alongside dry/cross/webhook.
- **Cross-platform installers** — release CI builds Windows (NSIS/MSI), macOS
  (DMG), and Linux (AppImage/deb) from `app-v*` tags.
- **Project folder Browse** + OS-aware default (`C:\Server\solsignal`,
  `~/voltra`, `/opt/voltra`).
- **Test TLS connection** on Remote VPS (JWT to `/bot/dry`; tripwire if live).
- **WordPress monitor 0.2.1** — default bot list includes DCA and XS-momentum.
- **Simple cockpit dashboard** (:8899) — single-page, brand-styled: plain-English
  status, Start/Stop/Reload bot-command buttons, an honest **vs-buy-and-hold
  scoreboard**, a strategy-mode switcher, and P/L that includes open positions.
- **Conservative (DCA) mode** — `DcaAccumulateStrategy`: buys a small fixed amount
  of each coin weekly and holds (new `voltra-dca` bot on :8083). Honest
  vs-buy-and-hold report in docs/dca-report.md; DCA is scoped as a separate
  lower-risk strategy category in CLAUDE.md.
- **Research: Alpha-Zoo / Vibe-Trading review** — tested WorldQuant Alpha101 on the
  Kraken basket; rejected (no fee-surviving edge on 4 coins). docs/alpha-zoo-report.md.
- **Official Voltra branding** — logo/favicon kit, README banner, GitHub Pages
  site (docs/index.html), ROADMAP. Tauri app icons replaced with branded set.

### Changed
- **Rebranded SolSignal → Voltra** across the entire project (code, container
  names, plugin, env vars, docs). Public repo: github.com/ibuilder/voltra.

## [app-v0.1.0] — 2026-07-27 · First desktop release

First installable, auto-updating Windows build of the Voltra Controller:
<https://github.com/ibuilder/voltra/releases/tag/app-v0.1.0>

### Added
- **Desktop controller (Tauri v2)** — a lightweight system-tray app that
  starts/stops the Docker stack, shows live service status, opens the
  dashboard, and self-enables run-on-login. No manual Startup-folder step.
- **Kraken API key entry** — paste key/secret, stored **OS-encrypted** in
  Windows Credential Manager (never plaintext); an "Open Kraken API page" button
  deep-links to Kraken's key creation (there is no OAuth for this). Saving a key
  never enables live trading — `dry_run` stays a human-only change.
- **Signed autoupdater** — GitHub Releases + `latest.json`; updates are
  signature-verified and prompt before installing (never silent).
- **Release CI** (`.github/workflows/release.yml`) builds the Windows
  `.exe`/`.msi` via `tauri-action` on `app-v*` tags.
- LICENSE (MIT), DISCLAIMER, CHANGELOG.

### Fixed
- Updater manifest (`latest.json`) wasn't being produced — enabled
  `bundle.createUpdaterArtifacts` (a Tauri v2 requirement), so the signed
  updater assets upload and auto-update works.
- Auto-update now targets the **NSIS** package (`updaterJsonPreferNsis`) to
  match the per-user install and avoid a UAC prompt on update.
- Autostart launcher pointed at a nonexistent `C:\Server\voltra`; corrected to
  the real checkout so login persistence actually works.

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

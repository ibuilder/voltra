# Voltra Controller (desktop app) — build & release

A lightweight **Tauri** system-tray app that runs the Docker trading stack "on
its own": start/stop, live status, open dashboard, and a checkbox to launch at
login (no manual Startup-folder or PowerShell steps). It is a **controller**,
not the bot — all trading logic stays in the Docker containers, and it never
enables live trading.

## What you get

- Windows: `Voltra Controller.exe` (NSIS + MSI). macOS: `.dmg`. Linux: AppImage + `.deb`.
- Tray icon: Start stack / Stop stack / Open Dashboard / Show / Quit.
- Window: **Local stack** or **Remote VPS** mode, service list, autostart,
  project-folder picker, **live fleet snapshot** (JWT — P&L + open positions),
  **Kraken API key entry** (OS-encrypted).
- Auto-updates from signed GitHub Releases (prompts before installing).

## Prerequisites to build (one-time, on your machine or CI)

- Node 20+, Rust (stable). Windows: MSVC build tools. macOS: Xcode CLT.
  Linux: WebKitGTK 4.1 (`libwebkit2gtk-4.1-dev`).
- The build is normally done by **GitHub Actions** (`.github/workflows/release.yml`),
  so you don't need a local toolchain — see "Release" below.

Local dev build:
```
cd desktop
npm install
npm run tauri dev      # run it live
npm run tauri build    # produce the installer in src-tauri/target/release/bundle
```

Snapshot-client unit tests (no GTK / Docker needed):

```
cargo test --manifest-path desktop/src-tauri/freqtrade-client/Cargo.toml
```

## Release (what's done vs. what's left)

**Already done** (in the repo now):
- Repo exists and is public: `github.com/ibuilder/voltra`.
- Updater signing keypair generated; the **public** key is wired into
  `desktop/src-tauri/tauri.conf.json` (`plugins.updater.pubkey`). The **private**
  key is at `desktop/.tauri-signing.key` (gitignored) — it was generated with an
  **empty password**.
- The updater endpoint already points at `ibuilder/voltra`.

**Left to you** (needs your GitHub auth + handles the private key):

```
# 1. add the signing private key as repo Actions secrets
#    (GitHub -> Settings -> Secrets and variables -> Actions -> New secret)
#      TAURI_SIGNING_PRIVATE_KEY           = full contents of desktop/.tauri-signing.key
#      TAURI_SIGNING_PRIVATE_KEY_PASSWORD  = (leave empty — the key has no password)

# 2. cut a release: CI builds, signs, and publishes the installer + latest.json
git tag app-v0.1.0 && git push origin app-v0.1.0
```

The release is created as a **draft**, and GitHub's `/releases/latest` (the
updater endpoint + the site's Download button) **ignores drafts**. So the final
manual step: open **Releases**, review the drafted `Voltra Controller app-v0.1.0`,
and click **Publish release**. Only then does the Download link work and do
installed apps see the update (signature-verified, prompt before install).

## Autoupdater safety

- Updates are **signature-verified** against your public key and **prompt before
  installing** (`dialog: true`) — never silent. A tampered artifact is rejected.
- The private signing key is the trust root: keep it offline/secret. If it leaks,
  rotate it (new keypair → new pubkey in config → new release).
- This matters because the app manages money-adjacent infrastructure. Only ever
  point the updater endpoint at a release channel you control.

## Configuration

- The app looks for an existing checkout in this order: `C:\Server\solsignal`,
  `~/voltra`, `/opt/voltra`. Use **Browse** or type a path; it's saved to the
  app config dir.
- The app finds `docker` on PATH, the Windows Docker Desktop default path, or
  `/usr/bin` / `/usr/local/bin`.
- **Docker health check:** the window shows whether the CLI, daemon,
  `docker-compose.yml`, and `.env` WebUI password are ready. Missing Docker
  deep-links to the install docs; missing `.env` can be copied from
  `.env.example`. The stack is not auto-started at login until Docker is ready.

### Kraken API key

- **You create the key on Kraken** — there is no "log in with Kraken" that
  provisions a key (exchanges don't expose OAuth for that). The **Open Kraken API
  page** button deep-links to Kraken's key management; make a key with **Query +
  Trade** permissions, **no Withdraw**, IP-whitelisted to this machine.
- Paste key + secret and **Save securely** → stored in **Windows Credential
  Manager** (encrypted by the OS), never a plaintext file. The window only shows a
  masked fingerprint afterward.
- **Apply to bot (.env)** writes `FREQTRADE__EXCHANGE__KEY/SECRET` into the
  project `.env` so the key is ready — then restart the stack to load it.
- **A key is not needed for the dry-run** (Freqtrade simulates fills). It only
  matters at go-live, which is still a separate, manual, human-only step — saving
  or applying a key **never** flips `dry_run`.

### Live snapshot (positions / P&L)

- **Local:** JWT to `127.0.0.1:8080–8084` using `.env` WebUI creds.
- **Remote VPS:** JWT to `https://<your-domain>/bot/{dry,dca,xsmom,cross,webhook}`
  (Caddy). Origin must be HTTPS on a public hostname (no IPs, no http, no
  userinfo). WebUI user/password live in the OS keychain, not a file.
- The access token never leaves the Rust process. A fleet strip shows every bot;
  click one for P&L and open positions.
- It only reads `/show_config`, `/profit`, `/balance`, and `/status`. It does
  not start/stop the bot via REST and **never** writes `dry_run`.
- If a bot reports `dry_run: false`, the window shows a **LIVE TRIPWIRE**
  banner. That is display-only — go-live remains a human-only config edit.
- Remote mode does **not** start Docker on the laptop. 24/7 trading stays on
  the VPS; the desktop is a console. See
  [deploy-oracle-free.md](deploy-oracle-free.md) /
  [deploy-hetzner.md](deploy-hetzner.md).

## Limits (honest)

- The controller keeps the stack running across logins and crashes, but it can't
  run while the PC is fully off or asleep — for uninterrupted 24/7 operation a
  small always-on VPS is still the robust option.
- It does not and will not flip `dry_run`. Going live remains a manual,
  human-only edit to `config.live.json`.

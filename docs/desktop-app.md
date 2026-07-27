# Voltra Controller (desktop app) — build & release

A lightweight **Tauri** system-tray app that runs the Docker trading stack "on
its own": start/stop, live status, open dashboard, and a checkbox to launch at
login (no manual Startup-folder or PowerShell steps). It is a **controller**,
not the bot — all trading logic stays in the Docker containers, and it never
enables live trading.

## What you get

- One `Voltra Controller.exe` (NSIS installer + MSI). Double-click installs.
- Tray icon: Start stack / Stop stack / Open Dashboard / Show / Quit.
- Window: service list, autostart toggle, project-folder picker, **Kraken API
  key entry** (OS-encrypted).
- Auto-updates from signed GitHub Releases (prompts before installing).

## Prerequisites to build (one-time, on your machine or CI)

- Node 20+, Rust (stable), and on Windows the MSVC build tools.
- The build is normally done by **GitHub Actions** (`.github/workflows/release.yml`),
  so you don't need a local toolchain — see "Release" below.

Local dev build:
```
cd desktop
npm install
npm run tauri dev      # run it live
npm run tauri build    # produce the installer in src-tauri/target/release/bundle
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

- The app defaults the project folder to `C:\Server\solsignal`. Change it in the
  window if your checkout lives elsewhere; it's saved to the app config dir.
- The app finds `docker.exe` on PATH or at the Docker Desktop default location.
- It assumes Docker Desktop is installed. (A future version could bundle a
  Docker health check / install prompt.)

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

## Limits (honest)

- The controller keeps the stack running across logins and crashes, but it can't
  run while the PC is fully off or asleep — for uninterrupted 24/7 operation a
  small always-on VPS is still the robust option.
- It does not and will not flip `dry_run`. Going live remains a manual,
  human-only edit to `config.live.json`.

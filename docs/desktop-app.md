# Voltra Controller (desktop app) — build & release

A lightweight **Tauri** system-tray app that runs the Docker trading stack "on
its own": start/stop, live status, open dashboard, and a checkbox to launch at
login (no manual Startup-folder or PowerShell steps). It is a **controller**,
not the bot — all trading logic stays in the Docker containers, and it never
enables live trading.

## What you get

- One `Voltra Controller.exe` (NSIS installer + MSI). Double-click installs.
- Tray icon: Start stack / Stop stack / Open Dashboard / Show / Quit.
- Window: service list, autostart toggle, project-folder picker.
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

## Publishing to GitHub (handoff — needs your GitHub account)

I prepared everything; these commands are yours to run (they publish public
content and need your GitHub auth):

```
# 1. create the repo (private is fine; Releases still work)
gh repo create voltra --private --source . --remote origin --push

# 2. generate the updater signing keypair (KEEP THE PRIVATE KEY SECRET)
cd desktop && npx @tauri-apps/cli signer generate -w ../.tauri-signing.key
#    -> prints a PUBLIC key. Paste it into desktop/src-tauri/tauri.conf.json
#       at plugins.updater.pubkey (replacing REPLACE_WITH_YOUR_...).
#    -> also replace ibuilder in the endpoint URL with your GitHub user/org.

# 3. add the private key as repo secrets (Settings -> Secrets -> Actions)
#      TAURI_SIGNING_PRIVATE_KEY            = contents of .tauri-signing.key
#      TAURI_SIGNING_PRIVATE_KEY_PASSWORD   = the password you set
#    NEVER commit .tauri-signing.key (it is gitignored).

# 4. cut a release — the CI builds, signs, and publishes the installer + latest.json
git tag app-v0.1.0 && git push origin app-v0.1.0
```

The release is created as a **draft** — review it, then publish. Once published,
installed apps will see the update, verify its signature, and prompt to install.

## Autoupdater safety

- Updates are **signature-verified** against your public key and **prompt before
  installing** (`dialog: true`) — never silent. A tampered artifact is rejected.
- The private signing key is the trust root: keep it offline/secret. If it leaks,
  rotate it (new keypair → new pubkey in config → new release).
- This matters because the app manages money-adjacent infrastructure. Only ever
  point the updater endpoint at a release channel you control.

## Configuration

- The app defaults the project folder to `C:\Server\voltra`. Change it in the
  window if your checkout lives elsewhere; it's saved to the app config dir.
- The app finds `docker.exe` on PATH or at the Docker Desktop default location.
- It assumes Docker Desktop is installed. (A future version could bundle a
  Docker health check / install prompt.)

## Limits (honest)

- The controller keeps the stack running across logins and crashes, but it can't
  run while the PC is fully off or asleep — for uninterrupted 24/7 operation a
  small always-on VPS is still the robust option.
- It does not and will not flip `dry_run`. Going live remains a manual,
  human-only edit to `config.live.json`.

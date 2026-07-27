# Windows code signing (Authenticode)

Our releases are **not** yet Authenticode code-signed. The Tauri "signature" you
already have (minisign) only secures **auto-updates** — it does nothing for
Windows' own publisher trust. As a result:

- Some antivirus engines (Panda, Avast, etc.) flag the unsigned NSIS installer
  as a heuristic false positive (e.g. `W32/Exploit`).
- SmartScreen shows "Windows protected your PC" on first run.

Authenticode signing fixes both. This is the real cost of distributing a
trustworthy Windows app to the public.

## Why not just a cheap .pfx?

Since June 2023, public CAs must issue code-signing keys on **hardware** (HSM /
USB token) or via a **cloud signing service** — plain exportable `.pfx` OV certs
are effectively gone. A physical token can't be plugged into GitHub's cloud
runners, so for CI you want a **cloud** signing service.

## Recommended (free): SignPath Foundation

[SignPath Foundation](https://signpath.io/solutions/open-source-community) gives
qualifying open-source projects a **free** OV code-signing certificate. The key
is generated and held on their HSM — you never touch it. Voltra qualifies on the
basics: public repo, MIT license, released, functionality documented.

### 1. Apply (only you can — it's tied to your identity)

- Apply at <https://signpath.io/solutions/open-source-community>; check
  eligibility at <https://www.ossperks.com/programs/signpath/check>.
- Reviewed by a human; approval takes a few days to a few weeks. A money-adjacent
  project may get extra scrutiny — describe it honestly (draft below).

Ready-to-submit description:

> **Voltra** (MIT, github.com/ibuilder/voltra) is an open-source Freqtrade-based
> crypto trading toolkit. The artifact to sign is **Voltra Controller**, a small
> Tauri desktop app that starts/stops the project's Docker stack, shows status,
> and stores a user-provided exchange API key in the OS keychain. It ships in
> **dry-run** (simulated trades) and never enables live trading on its own.
> Functionality is documented at ibuilder.github.io/voltra and in the repo README
> / docs/desktop-app.md. Releases are built by GitHub Actions from tagged commits.

### 2. CI integration (I'll wire this on approval)

SignPath signs **after** the build, but our updater signature is computed **during**
the build — so signing the installer afterward would break auto-update. On approval
the release job is reordered to: build unsigned → submit installers to SignPath →
retrieve signed installers → **recompute** the Tauri updater signatures on the
signed files → build `latest.json` → publish. (This replaces the single
`tauri-action` publish step; the minisign updater key is unchanged, so update
continuity is preserved.) SignPath provides a GitHub Action + a project/signing-policy
slug that only exist post-approval — that's why this step waits for you.

### 3. Verify (first signed build)

```powershell
Get-AuthenticodeSignature .\Voltra.Controller_x.y.z_x64-setup.exe | Format-List Status, SignerCertificate
# Status: Valid
```

---

## Paid alternative: Azure Trusted Signing (~$10/month)

Cheapest, CI-native, no hardware token. Microsoft-run.

### 1. Enrol (one-time; identity validation takes a few days)

1. Azure portal → create a **Trusted Signing account** (pick a region — note the
   endpoint, e.g. `https://eus.codesigning.azure.net`).
2. Create a **Certificate Profile** (Public Trust). Choose:
   - **Individual** validation if you're signing as yourself, or
   - **Organization** validation for a company (needs a verifiable business).
   Microsoft verifies your identity — this is the multi-day step.
3. Note three names: the **endpoint URL**, the **account name**, the **certificate
   profile name**.

### 2. Create a service principal for CI

```bash
az ad sp create-for-rbac --name voltra-signing
# -> gives appId (AZURE_CLIENT_ID), password (AZURE_CLIENT_SECRET), tenant (AZURE_TENANT_ID)
```
Grant that service principal the **Trusted Signing Certificate Profile Signer**
role on the Trusted Signing account (Azure portal → your TS account → Access
control (IAM) → Add role assignment).

### 3. Add the repo secrets + variables

GitHub → repo → Settings → Secrets and variables → Actions:

| Kind | Name | Value |
|---|---|---|
| Secret | `AZURE_TENANT_ID` | tenant id |
| Secret | `AZURE_CLIENT_ID` | service-principal appId |
| Secret | `AZURE_CLIENT_SECRET` | service-principal password |
| Variable | `AZURE_TS_ENDPOINT` | e.g. `https://eus.codesigning.azure.net` |
| Variable | `AZURE_TS_ACCOUNT` | Trusted Signing account name |
| Variable | `AZURE_TS_PROFILE` | certificate profile name |

That's it. The release workflow already detects `AZURE_CLIENT_ID` and, when
present, installs `trusted-signing-cli` and injects a Tauri `signCommand` so
every bundle is Authenticode-signed **during** the build (before the updater
signature is computed, so `latest.json` stays valid). No workflow edit needed.

### 4. Cut a signed release

```bash
git tag app-v0.1.1 && git push origin app-v0.1.1
```
Then verify a downloaded installer:
```powershell
Get-AuthenticodeSignature .\Voltra.Controller_0.1.1_x64-setup.exe | Format-List Status, SignerCertificate
# Status should be "Valid"
```
The AV false positive and SmartScreen prompt should be gone (EV-class reputation
via Trusted Signing is immediate; brand-new profiles may take a short while to
warm up with SmartScreen).

## Alternatives

- **DigiCert KeyLocker / SSL.com eSigner** — cloud HSM signing, similar CI model,
  typically pricier. Swap the `signCommand` for their CLI; the rest is identical.
- **EV token (SafeNet, etc.)** — physical USB token; can't be used on cloud
  runners, so you'd sign on a self-hosted runner or locally. Not recommended here.

## Status

- [ ] Trusted Signing account + certificate profile created (identity validated)
- [ ] Service principal + IAM role assigned
- [ ] Secrets + variables added to the repo
- [ ] First signed release verified with `Get-AuthenticodeSignature`

Until these are done, distribute with the honest note that the installer is
unsigned (see the release notes), or keep distribution private.

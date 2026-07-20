# Deploy Voltra on Hetzner Cloud (~€4/mo, reliable 24/7)

The reliable paid alternative to the Oracle free tier. No idle-reclamation, no
capacity roulette, a real 99.9% uptime SLA. **Recommended once real money is
involved**; for dry-run, Oracle free ([deploy-oracle-free.md](deploy-oracle-free.md))
is fine. Same stack, same scripts — only the provider setup differs.

Cost: **CAX11** (2 vCPU ARM / 4 GB) ≈ €3.79/mo, or **CX22** (2 vCPU x86 / 4 GB)
≈ €4.51/mo. Our Docker images are multi-arch, so the cheaper ARM CAX11 works.

---

## 1. Create the server

1. Sign up at [hetzner.com/cloud](https://www.hetzner.com/cloud), add a payment
   method. **You do this — I can't create accounts.**
2. Console → **New Project** → **Add Server**.
3. **Location**: pick one near you (e.g. Ashburn/Hillsboro US, Falkenstein EU).
4. **Image**: Ubuntu 24.04.
5. **Type**: Shared vCPU → **CAX11** (ARM, cheapest) or **CX22** (x86).
6. **SSH key**: paste your public key (`~/.ssh/id_ed25519.pub`; make one with
   `ssh-keygen -t ed25519` if needed).
7. **Firewall**: create one now (next step) or attach after. Create the server.
   Note the **public IP**.

## 2. Firewall (one clean step — simpler than Oracle)

Console → **Firewalls** → Create. Inbound rules (source `0.0.0.0/0`, `::/0`):

| Port | Protocol |
|---|---|
| 22 | TCP (SSH) |
| 80 | TCP (HTTP / ACME) |
| 443 | TCP (HTTPS) |
| 443 | UDP (HTTP/3) |

Attach it to your server. Hetzner's Ubuntu image doesn't ship restrictive local
iptables, so **no OS-firewall edits are needed** (unlike Oracle).

## 3. Connect + harden SSH

```bash
ssh root@YOUR_SERVER_IP
apt update && apt install -y fail2ban
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh
```
(Optional but good: create a non-root sudo user and use that instead of root.)

## 4. Install Docker

```bash
curl -fsSL https://get.docker.com | sh
docker compose version   # confirm Compose v2
```

## 5. Get the code + secrets

```bash
mkdir -p /opt/voltra && git clone https://github.com/ibuilder/voltra /opt/voltra
cd /opt/voltra
cp .env.example .env
nano .env
```
Set at minimum (same as Oracle):
- `FREQTRADE__API_SERVER__USERNAME` / `PASSWORD`
- `FREQTRADE__API_SERVER__JWT_SECRET_KEY` / `WS_TOKEN`
  (`python3 -c "import secrets;print(secrets.token_hex(32))"`)
- `RELAY_SECRET` (`python3 -c "import secrets;print(secrets.token_urlsafe(24))"`)
- `VOLTRA_DOMAIN=trade.yourdomain.com` · `CADDY_ACME_EMAIL=you@example.com`
- Exchange keys stay EMPTY until go-live.

**Point your domain's A record at the server IP** (Hetzner also gives you a free
`*.your-server.de`-style reverse DNS, but a real domain is cleaner for TLS).

## 6. Launch + persist

```bash
./scripts/deploy.sh                                   # pulls + brings up prod overlay
sudo cp deploy/voltra.service /etc/systemd/system/    # start on boot
sudo systemctl daemon-reload && sudo systemctl enable --now voltra
```

Caddy auto-provisions a Let's Encrypt cert for `VOLTRA_DOMAIN`. Only Caddy is
public (80/443); bots/relay/dashboard stay loopback-only on the private network.

## 7. Verify + connect the WordPress plugin

```bash
docker compose ps                    # all healthy
curl -s https://trade.yourdomain.com -o /dev/null -w "%{http_code}\n"   # 200
```

Then in the DreamHost WordPress plugin (Voltra → Settings), the bots become
reachable at the per-bot routes:
```
voltra-dry|https://trade.yourdomain.com/bot/dry
voltra-cross|https://trade.yourdomain.com/bot/cross
voltra-webhook|https://trade.yourdomain.com/bot/webhook
```
API username `voltra`, and the password from `.env` (prefer defining
`VOLTRA_API_PASSWORD` in DreamHost's `wp-config.php`).

## Ongoing

- Update: `cd /opt/voltra && git pull && ./scripts/deploy.sh`
- Backups: copy `user_data/backups/` off-box periodically (e.g. `rclone` cron).
- Snapshots: Hetzner offers cheap volume snapshots for a full-VM backup.

## Oracle vs Hetzner — pick by phase

| | Oracle Always-Free | Hetzner CAX11 |
|---|---|---|
| Cost | $0 | ~€3.79/mo |
| Reliability | idle-reclamation risk; capacity roulette | 99.9% SLA, no games |
| Best for | dry-run data gathering | real money / set-and-forget |

Migration between them is identical — this same repo, `.env`, and
`./scripts/deploy.sh`. You're never locked in.

# Deploy Voltra on Oracle Cloud Always-Free ($0, 24/7)

The goal: run the whole stack 24/7 on a free ARM VM, reachable at
`https://your-domain` via Caddy's automatic TLS. Cost: **$0/month** (Oracle's
Always-Free ARM tier) plus a domain (~$10/yr, optional — you can use the IP).

Why Oracle free tier: it offers an **Ampere A1 (ARM)** allowance of up to 4
OCPU / 24 GB RAM that is *always* free (not a 12-month trial). Our stack needs
~2 GB; a 2 OCPU / 12 GB VM is comfortable and well within the free limit.

Everything below is a one-time setup. After it, updates are just
`git pull && ./scripts/deploy.sh`.

---

## 0. Prerequisites

- An Oracle Cloud account (free signup; a card is required for identity but the
  Always-Free resources never charge). **You must do the signup — I can't
  create accounts.**
- Optional: a domain name pointed at the VM (Cloudflare/Namecheap ~$10/yr). Real
  TLS needs a domain; without one you use the raw IP over http (fine for a
  private test, not for exposing the relay).

## 1. Create the VM

1. Oracle Cloud console → **Compute → Instances → Create Instance**.
2. **Image & shape** → change shape to **Ampere (ARM) → VM.Standard.A1.Flex**,
   set **2 OCPU / 12 GB**. Image: **Ubuntu 22.04 (aarch64)**.
3. **Add SSH keys**: upload your public key (`~/.ssh/id_ed25519.pub`; generate
   with `ssh-keygen -t ed25519` if needed). Save the private key safely.
4. **Networking**: keep the default VCN; ensure "Assign a public IPv4" is on.
5. Create. Note the **public IP**.

> Our Docker images (freqtrade, caddy, nginx) are multi-arch and run natively on
> arm64 — no changes needed.

## 2. Open the firewall (two layers)

**Oracle Security List** (cloud firewall): VCN → Security Lists → default →
Add Ingress Rules, source `0.0.0.0/0`, allow TCP **80**, **443**, and **443/UDP**
(HTTP/3). Port 22 is open by default.

**OS firewall** on the VM (Ubuntu ships with iptables rules on Oracle images):
```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p udp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

## 3. Harden SSH (5 minutes, do it)

```bash
sudo apt update && sudo apt install -y fail2ban
# disable password login (key-only)
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart ssh
```

## 4. Install Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker   # or log out/in so your user can run docker
docker compose version   # confirm Compose v2 is present
```

## 5. Get the code and secrets

```bash
sudo mkdir -p /opt/voltra && sudo chown $USER /opt/voltra
git clone <YOUR_REPO_URL> /opt/voltra
cd /opt/voltra
cp .env.example .env
```

Edit `.env` (`nano .env`) and set at minimum:
- `FREQTRADE__API_SERVER__USERNAME` / `PASSWORD`
- `FREQTRADE__API_SERVER__JWT_SECRET_KEY` / `WS_TOKEN`
  (`python3 -c "import secrets;print(secrets.token_hex(32))"`)
- `RELAY_SECRET` (`python3 -c "import secrets;print(secrets.token_urlsafe(24))"`)
- `VOLTRA_DOMAIN=trade.yourdomain.com` and `CADDY_ACME_EMAIL=you@example.com`
- Exchange keys stay EMPTY until go-live (dry-run needs none).

**Point your domain's A record at the VM's public IP** (and AAAA if you enabled
IPv6). TLS won't issue until DNS resolves.

## 6. Get the market data

The backtest archive isn't in git (it's large + reproducible). Either:
- copy `user_data/data/kraken/*.feather` up with `scp`, or
- re-run `python scripts/import_kraken_csv.py --zip <archive>` after fetching the
  Kraken quarterly archive (see docs/tradingview... no — see README Kraken notes).

Dry-run trading itself only needs recent candles, which the bots fetch live, so
you can start without the historical archive and add it later for backtests.

## 7. Launch

```bash
./scripts/deploy.sh          # pulls images, brings up with the prod overlay
```

The prod overlay publishes **only Caddy** on 80/443; the bots/relay/dashboard
stay on 127.0.0.1 (unreachable from the internet). Caddy auto-provisions a
Let's Encrypt cert for `VOLTRA_DOMAIN` within a minute.

Visit **https://trade.yourdomain.com** → the dashboard. FreqUI is at
`/frequi`. TradingView webhooks (if used) go to `/webhook/webhook`.

## 8. Start on boot

```bash
sudo cp deploy/voltra.service /etc/systemd/system/voltra.service
sudo systemctl daemon-reload
sudo systemctl enable --now voltra
```

Now the stack survives reboots automatically (the Linux equivalent of the
Windows autostart). Containers also self-heal via `restart: unless-stopped`.

## 9. Verify

```bash
docker compose ps                     # all services Up / healthy
docker logs voltra-healthwatch     # bots ok, dry_run tripwire armed
curl -s https://trade.yourdomain.com -o /dev/null -w "%{http_code}\n"  # 200
```

## Ongoing

- **Update**: `cd /opt/voltra && git pull && ./scripts/deploy.sh`
- **Backups**: the backup sidecar writes to `user_data/backups/`. For real DR,
  copy that folder off-box periodically (e.g. a cron `rclone` to object storage).
- **Monitoring**: set `ALERT_WEBHOOK_URL` (or Telegram token) in `.env` so
  healthwatch pushes alerts, then `./scripts/deploy.sh`.

## Cost reminder (be clear-eyed)

Hosting here is $0, which is the whole point — at $500–1,000 capital a **paid**
VPS would cost more than the strategy is expected to earn. Free hosting removes
that drag entirely, but it does not change the core reality: the strategy has
not cleared its profit-factor gate, so treat this as a learning deployment, not
an income stream, until the 30-day dry-run says otherwise. Not financial advice.

## Security posture (what this gives you)

- Only Caddy is internet-facing (TLS 1.3, HSTS, security headers).
- Bots/relay/dashboard are loopback-only + on the private compose net.
- `no-new-privileges`, log rotation, memory limits on every container.
- SSH key-only + fail2ban; cloud + OS firewall allow only 22/80/443.
- Every bot dry-run; healthwatch tripwire alerts if that ever changes.

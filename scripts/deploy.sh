#!/usr/bin/env bash
# Idempotent deploy/refresh of the SolSignal stack on a Linux VPS.
# Run from the repo root:  ./scripts/deploy.sh
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Copy .env.example to .env and fill it in first."
  exit 1
fi

# Sanity: never deploy with a live config by accident.
if grep -qsE '"dry_run"\s*:\s*false' user_data/config*.json; then
  echo "REFUSING: a config has dry_run=false. Live trading is a human-only change."
  exit 1
fi

echo "==> Pulling latest images"
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull

echo "==> Bringing up the stack (Caddy public on 80/443, rest loopback-only)"
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

echo "==> Waiting for bots to report healthy"
for c in solsignal-freqtrade solsignal-freqtrade-cross solsignal-freqtrade-webhook; do
  for _ in $(seq 1 24); do
    s=$(docker inspect --format '{{.State.Health.Status}}' "$c" 2>/dev/null || echo none)
    [ "$s" = "healthy" ] && break
    sleep 5
  done
  echo "   $c: $(docker inspect --format '{{.State.Health.Status}}' "$c" 2>/dev/null || echo '?')"
done

echo "==> Status"
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps --format "{{.Name}}: {{.Status}}"

echo "==> Done. Dashboard: https://${SOLSIGNAL_DOMAIN:-your-domain} (via Caddy)."

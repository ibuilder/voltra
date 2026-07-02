"""Pair-whitelist screener (Phase 1 — not yet implemented).

Pulls top-25 coins by 24h volume from the CoinGecko free API, filters for
Kraken availability and >$50M daily volume, and writes a pairlist JSON that
config.json can consume.

Planned usage:
    python scripts/screener.py --min-volume 50000000 --top 25 \
        --out user_data/pairlist.json
"""

raise NotImplementedError("Phase 1 deliverable — see build plan section 5.")

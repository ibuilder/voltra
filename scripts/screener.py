"""Pair-whitelist screener (Phase 1).

Pulls the top coins by 24h volume from the CoinGecko free API, keeps those
that trade against USD on Kraken with >$50M daily volume, and writes the
result to user_data/pairlist.json (a plain JSON list usable with freqtrade's
--pairs-file). BTC/ETH/SOL are always included regardless of screen results.

Usage:
    python scripts/screener.py [--top 25] [--min-volume 50000000]
                               [--out user_data/pairlist.json]
"""

import argparse
import json
import sys
from pathlib import Path

import requests

COINGECKO_MARKETS = "https://api.coingecko.com/api/v3/coins/markets"
KRAKEN_ASSET_PAIRS = "https://api.kraken.com/0/public/AssetPairs"

CORE_PAIRS = ["BTC/USD", "ETH/USD", "SOL/USD"]

# Pegged assets and wrapped duplicates — no point trading them against USD.
STABLE_OR_WRAPPED = {
    "USDT", "USDC", "DAI", "TUSD", "USDE", "USDS", "FDUSD", "PYUSD",
    "USD1", "BUSD", "EURC", "EURT", "WBTC", "WETH", "STETH", "WSTETH",
    "WEETH", "CBBTC", "CBETH", "RETH",
}


def kraken_usd_pairs() -> set[str]:
    """All wsnames (e.g. 'SOL/USD') Kraken offers against USD."""
    resp = requests.get(KRAKEN_ASSET_PAIRS, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("error"):
        raise RuntimeError(f"Kraken API error: {payload['error']}")
    pairs = set()
    for info in payload["result"].values():
        wsname = info.get("wsname", "")
        if wsname.endswith("/USD"):
            # Kraken legacy codes: XBT = BTC, XDG = DOGE. CCXT normalizes these.
            pairs.add(wsname.replace("XBT/", "BTC/").replace("XDG/", "DOGE/"))
    return pairs


def top_volume_coins(top: int) -> list[dict]:
    resp = requests.get(
        COINGECKO_MARKETS,
        params={
            "vs_currency": "usd",
            "order": "volume_desc",
            "per_page": top,
            "page": 1,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def screen(top: int, min_volume: float) -> list[str]:
    kraken_pairs = kraken_usd_pairs()
    selected = list(CORE_PAIRS)
    for coin in top_volume_coins(top):
        symbol = coin["symbol"].upper()
        volume = coin.get("total_volume") or 0
        pair = f"{symbol}/USD"
        if symbol in STABLE_OR_WRAPPED:
            reason = "stable/wrapped"
        elif volume < min_volume:
            reason = f"volume ${volume/1e6:,.0f}M < min"
        elif pair not in kraken_pairs:
            reason = "not on Kraken vs USD"
        elif pair in selected:
            reason = "core pair"
        else:
            selected.append(pair)
            reason = "SELECTED"
        print(f"{pair:<12} ${volume/1e6:>9,.0f}M  {reason}")
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=25)
    parser.add_argument("--min-volume", type=float, default=50_000_000)
    parser.add_argument("--out", default="user_data/pairlist.json")
    args = parser.parse_args()

    pairs = screen(args.top, args.min_volume)
    out = Path(args.out)
    out.write_text(json.dumps(pairs, indent=4) + "\n")
    print(f"\n{len(pairs)} pairs -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

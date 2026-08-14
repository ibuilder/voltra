"""Can we profitably MARKET-MAKE on Kraken? (Hummingbot review — decided by data.)

Hummingbot's whole point is market making: post a bid below mid and an ask above
mid, capture the spread, repeat. That is only profitable if the spread you capture
exceeds the fees you pay: net per round-trip ~= spread - 2 * maker_fee.

We already MEASURED Kraken's live spreads with CCXT (0-1.3 bps on our pairs). This
script pairs that against Kraken's real maker-fee tiers to compute whether MM could
ever work for us. Read-only public data; run in the freqtrade container:

    docker exec -i voltra-freqtrade python < research/execution/mm_economics.py
"""

import ccxt

PAIRS = ["BTC/USD", "ETH/USD", "SOL/USD", "XRP/USD"]

# Kraken spot MAKER fee by rolling 30-day USD volume (per side, %). Retail sits at
# the top row; the bottom rows need institutional volume most retail never reaches.
MAKER_TIERS = [
    ("$0 (retail)", 0.25),
    ("$50k/mo", 0.14),
    ("$250k/mo", 0.10),
    ("$1M/mo", 0.06),
    ("$10M/mo", 0.00),
]


def live_spreads_bps():
    kr = ccxt.kraken({"enableRateLimit": True})
    out = {}
    for p in PAIRS:
        ob = kr.fetch_order_book(p, limit=5)
        bid, ask = ob["bids"][0][0], ob["asks"][0][0]
        mid = (bid + ask) / 2
        out[p] = (ask - bid) / mid * 1e4
    return out


def main():
    spreads = live_spreads_bps()
    best = max(spreads.values())          # most-favorable pair to MM
    avg = sum(spreads.values()) / len(spreads)
    print("Market-making economics on Kraken (Hummingbot's core strategy)\n")
    print("Live spread captured (best case = full spread, optimistic):")
    for p, s in spreads.items():
        print(f"  {p:<9} {s:5.1f} bps")
    print(f"  best {best:.1f} bps | avg {avg:.1f} bps\n")

    print(f"{'fee tier':<14} {'maker/side':>10} {'break-even spread':>18} {'net/cycle (best)':>17}")
    print("-" * 62)
    for name, maker_pct in MAKER_TIERS:
        maker_bps = maker_pct * 100
        breakeven = 2 * maker_bps                    # spread must beat 2x maker fee
        net = best - 2 * maker_bps                   # optimistic: capture full best spread
        print(f"{name:<14} {maker_bps:>8.1f}b {breakeven:>16.0f}b {net:>+16.1f}b")

    print("\n=== VERDICT: do NOT import ===")
    print(f"Kraken spreads on our pairs are {avg:.1f} bps avg because professional")
    print("market makers (paying ~0 fees) have already compressed them. To profit we'd")
    print("need spread > 2x our maker fee = >50 bps at retail (>12 bps even at $1M/mo).")
    print(f"We measured {best:.1f} bps. Every tier a retail account can reach is deeply")
    print("negative. Market making these liquid pairs is structurally unprofitable for")
    print("us; arbitrage needs multiple funded exchanges we don't run (Kraken-only).")
    print("Hummingbot is a fine MM framework -- for a different game than ours.")


if __name__ == "__main__":
    main()

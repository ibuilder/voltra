"""Measure REAL Kraken slippage via CCXT (the library Freqtrade already uses).

CCXT's genuinely useful direct application for us: instead of guessing the 0.05%
slippage our backtests/stress-test assume, MEASURE it from Kraken's live order
book for our 4 pairs. This grounds the NautilusTrader execution-realism lesson in
actual current microstructure.

Read-only, public market data only — no API keys, no orders. CCXT is MIT-licensed
and already a Freqtrade dependency (so this needs no new packages; run it inside
the freqtrade container where ccxt lives):

    docker exec -i voltra-freqtrade python < research/execution/measure_slippage.py
"""

import ccxt

PAIRS = ["BTC/USD", "ETH/USD", "SOL/USD", "XRP/USD"]
NOTIONALS = [25, 1000]        # our DCA stake, and a larger clip
ASSUMED_SLIP_BPS = 5.0        # the 0.05% one-way we assume in backtests


def buy_slippage_bps(asks, mid, usd):
    """VWAP fill vs mid to market-buy `usd` of notional by walking the asks."""
    spent = filled_base = 0.0
    for entry in asks:
        price, amount = entry[0], entry[1]   # Kraken rows are [price, amount, ts]
        take = min(amount, (usd - spent) / price)
        spent += take * price
        filled_base += take
        if spent >= usd * 0.999:
            break
    if filled_base == 0:
        return None
    vwap = spent / filled_base
    return (vwap / mid - 1) * 1e4


def main():
    kr = ccxt.kraken({"enableRateLimit": True})
    print("Live Kraken order-book slippage (CCXT, public data)")
    print(f"assumed in our models: {ASSUMED_SLIP_BPS:.1f} bps one-way\n")
    header = f"{'pair':<9} {'spread':>8}" + "".join(f"{'buy $'+str(n):>12}" for n in NOTIONALS)
    print(header)
    print("-" * len(header))
    worst = 0.0
    for p in PAIRS:
        try:
            ob = kr.fetch_order_book(p, limit=100)
            bid, ask = ob["bids"][0][0], ob["asks"][0][0]
            mid = (bid + ask) / 2
            spread_bps = (ask - bid) / mid * 1e4
            slips = [buy_slippage_bps(ob["asks"], mid, n) for n in NOTIONALS]
            worst = max([worst, spread_bps] + [s for s in slips if s])
            cells = "".join(f"{s:>11.1f}b" if s is not None else f"{'n/a':>12}" for s in slips)
            print(f"{p:<9} {spread_bps:>7.1f}b{cells}")
        except Exception as e:
            print(f"{p:<9} ERROR: {e}")
    print("\n=== READ ===")
    print(f"Worst observed (spread or fill slippage): {worst:.1f} bps.")
    if worst <= ASSUMED_SLIP_BPS * 2:
        print(f"Our {ASSUMED_SLIP_BPS:.0f}-bps assumption is realistic-to-conservative for these")
        print("liquid pairs at our tiny size — the edge problem is NOT hidden slippage;")
        print("it's that the signal itself is too thin (see execution_stress.py).")
    else:
        print(f"Real slippage exceeds our {ASSUMED_SLIP_BPS:.0f}-bps assumption — re-run")
        print("execution_stress.py with the higher number; the edge is even thinner.")


if __name__ == "__main__":
    main()

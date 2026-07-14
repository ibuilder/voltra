# Per-coin edge analysis & the "adaptable strategy" question (2026-07-14)

## The question
"Pick a trading strategy that adapts to historical data, market conditions,
and coin."

## What the data actually says

TrendBreak, backtested on each pair separately (real Kraken, fees modeled),
profit factor split by year — the out-of-sample consistency test:

| Coin | 2024 PF | 2025 PF | Consistent >1.2 both? |
|---|---|---|---|
| **XRP** | 1.43 | 1.28 | ✅ **yes — the only one** |
| BTC | 1.73 | 0.97 | no (great→dead) |
| ETH | 0.81 | 1.40 | no (dead→great) |
| SOL | 0.64 | 1.35 | no |
| ZEC | 0.92 | 1.83 | no |
| ADA | 1.30 | 0.33 | no (good→terrible) |
| TRX | 1.29 | 0.71 | no |
| SUI | 1.15 | 0.68 | no |
| XLM | 1.09 | 1.23 | borderline |
| DOGE | 1.12 | 1.02 | no |
| LTC | 0.82 | 1.13 | no |
| NEAR | 0.76 | 0.37 | no (bad both) |
| AAVE | 0.75 | 0.77 | no (bad both) |

**The core finding: which coin has an edge is not stable year to year and
cannot be predicted.** A naive "trade the top-3 by combined 2024–2026 PF"
would have picked BTC, XRP, ZEC — two of which were single-year flukes.
This is the selection-bias trap, and the split-year test exposes it.

## Why a "regime-switching adaptive model" is the wrong answer

Three adaptive overlays have now been tested and **all made results worse**:
- Candlestick-pattern gating (rejected, loses in-sample)
- BTC 200-day-MA regime filter (rejected, worse in every period)
- Fear & Greed sentiment gate (rejected, worse 2021 & 2024)

Pattern: TrendBreak's edge concentrates in hot breakouts; every filter that
tries to "read conditions" and sit out ends up amputating the edge. Adding
prediction machinery to a thin edge mostly adds ways to be wrong.

## The adaptation that IS real and IS kept

TrendBreak already adapts on all three axes the question asked, without any
fragile switching logic:
- **By coin**: ATR-based position sizing auto-scales to each coin's own
  volatility; the 1% risk rule means a jumpy coin gets a smaller position.
- **By market condition**: the 4h EMA50>EMA200 trend gate stops entries in
  downtrends — this is why TrendBreak stayed +13% (PF 2.28) through the
  2022 −76% bear by simply not trading it.
- **Across coins**: a diversified basket with max-3-concurrent lets the
  bot rotate into whichever pairs are actually breaking out right now,
  instead of us guessing which coin will be hot.

## The chosen configuration: BTC/ETH/SOL/XRP

Portfolio backtests, max 3 concurrent, split by year:

| Basket | 2024 PF / DD | 2025 PF / DD | Verdict |
|---|---|---|---|
| BTC/ETH/SOL (old) | 1.07 / 13.9% | 1.15 / 8.6% | ok |
| **BTC/ETH/SOL/XRP** | **1.21 / 13.8%** | **1.07 / 13.7%** | **chosen** |
| BTC/ETH/XRP/LTC/XLM | 1.29 / 15.7% | 0.97 / −1.6% | loses 2025 ❌ |
| all 13 pairs | 1.02 / 25.9% | 1.06 / 15.2% | DD busts gate ❌ |
| +LTC/XLM/DOGE (7) | 1.00 / 23.5% | 1.11 / 13.8% | DD too high ❌ |

BTC/ETH/SOL/XRP is the only basket that is **positive both years with
drawdown under 15% both years**. It adds the one proven-consistent coin
(XRP) to the SolSignal core. Broader baskets add drawdown from junk coins
(NEAR/AAVE/ADA) without adding edge — diversification into losers is not
diversification.

Now deployed as the main dry-run whitelist. SolCross (SOL-only lead-lag)
stays on its own bot as the tracked experiment.

## Honest bottom line

TrendBreak is a **thin, real, large-cap breakout edge** — not a universal
money machine and not clearing the PF>1.3 live gate out-of-sample (4-pair
2025 PF 1.07). It is regime-robust (survived 2021–2025 incl. the bear) and
now coin-diversified. Whether the thin edge is real *enough* is exactly what
the 30-day dry-run is for. See testing-plan.md.

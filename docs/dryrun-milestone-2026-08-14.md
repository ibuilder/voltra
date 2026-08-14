# Dry-run milestone verdict — 2026-08-14

The "needle mover": feed the **real dry-run fills** into the Monte Carlo edge test
and decide. Ran it. The answer is decisive, and it's about *frequency*, not luck.

## What the dry-run actually produced

Dry-run running ~37 days (since 2026-07-08, with the known interruptions —
machine-off gaps + a Docker crash). Closed trades:

| bot | strategy | closed trades |
|---|---|---|
| voltra-dry | TrendBreak (BTC/ETH/SOL/XRP) | **2** (both losses) |
| voltra-cross | SolCross | 0 |
| voltra-webhook | Webhook (experimental) | 1 |
| voltra-dca | DCA (holds by design) | 0 |

The 2 TrendBreak trades: ETH −2.08% (stop) and ETH −0.89% (structure-failed).

## Monte Carlo on the real fills

`scripts/montecarlo.py` on the 2 fills: mean/trade −1.48%, P(mean>0) **0%**,
P(profitable) 0%. **But N=2 is statistically meaningless** — you cannot conclude
anything from two data points beyond "not encouraging."

## The real blocker (this is the finding)

At the observed live rate of **1.6 trades / 30 days**:

| to reach | why | time at this rate |
|---|---|---|
| N=30 | weak Monte Carlo minimum | **~18 months** |
| N=172 | the backtest sample size | **~9 years** |

**The dry-run cannot validate this strategy in any practical timeframe.** TrendBreak
trades far too rarely. The 30-day gate was premised on accumulating enough real
fills to re-run the significance test — at ~2 trades/month, that premise fails.

## Verdict

- Backtest edge was already **below the 95% gate** (P≈81%, and the execution-stress
  test showed it collapsing under realistic fills).
- Live: 2 trades, both losses — too few to conclude, but not encouraging.
- Structurally, live fills **can't** reach a significant sample for years.

Therefore TrendBreak's edge is **unproven and effectively unprovable via this
path.** The disciplined outcome stands, now firmly: **do not go live with it.**

## The honest path forward

1. **For a passive user, the realistic "make money on your desktop" answer is the
   Conservative (DCA) / hold mode** — it needs no proven edge, just tracks the
   market. Every test in this project says boring (hold/DCA) beats clever (the
   active bot) for someone hands-off. That mode is already built and running.
2. **If you want a validatable active strategy**, it must trade *far* more often
   (many more pairs, and/or a lower timeframe) so a sample accrues in months not
   years — but that's a new strategy needing its own validation, and lower
   timeframes face the fee/slippage headwinds we measured (CCXT: ~1 bps spread,
   but fees ~16 bps RT dominate). Not obviously winnable.
3. **Do not** flip TrendBreak live on hope. Two live losses and an unprovable
   sample is the opposite of a green light.

The needle moved — it pointed at "this strategy can't be proven; stop waiting on
it." That's the honest result the whole validation discipline was built to deliver.

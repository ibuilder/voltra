# Kronos forecast-skill test — result

**Verdict: REJECTED (zero-shot).** The Kronos foundation model shows no
fee-surviving directional edge on our held-out Kraken data.

## What was tested

[Kronos](https://github.com/shiyu-coder/Kronos) is an open forecasting
foundation model (decoder-only transformer over tokenized OHLCV, pre-trained on
45+ exchanges). Its own authors state it is *"not a production-ready
quantitative trading system."* We tested it as a **signal source**, the honest
first question: does it predict direction better than a coin flip, after fees,
on data it never saw?

Method (`research/kronos/skill_test.py`, no look-ahead):
- Model: **Kronos-small** (24.7M params) + Kronos-Tokenizer-base, CPU, zero-shot.
- Data: real Kraken **BTC/USD 1h**, held-out **2025-01-01 → 2025-07-01**.
- Rolling non-overlapping windows: 512h history → forecast next 24h.
- Compare predicted close direction vs actual; naive "long-when-up" strategy
  with 0.21% round-trip cost; bootstrap the per-trade returns for significance.

## Result (180 windows)

| Metric | Value | Bar |
|---|---|---|
| Directional accuracy | **50.6%** | >55% |
| Naive strategy mean/trade (after fees) | **−0.07%** | >0 |
| Cumulative return | **−10.2%** | >0 |
| Bootstrap P(edge > 0) | **39.5%** | ≥95% |

50.6% over 180 forecasts is statistically indistinguishable from random. The
naive strategy loses money after fees. This is the same treatment — and the same
outcome — as the CandlePattern, 200d-MA regime filter, and Fear & Greed
experiments: tested honestly, no significant edge, documented, not deployed.

## Honest caveats

- **Zero-shot only.** Kronos can be *fine-tuned* on a specific instrument; the
  authors expect that plus portfolio construction and risk neutralization. A
  fine-tuned model might differ — but that's a large research project with high
  overfitting risk, and a 50.6% zero-shot base is a weak starting point.
- Tested on BTC/USD 1h / 24h horizon. ETH/SOL and other horizons weren't run:
  a clean coin-flip with negative post-fee expectancy on 180 windows gives no
  reason to expect the alts to reveal a hidden edge, and Phase 1 is meant to be
  the cheap decisive filter, not exhaustive.
- Uses `sample_count=1, T=0.7`. Averaging more samples smooths the forecast but
  does not manufacture directional edge where the base rate is ~50%.

## Conclusion

Zero-shot Kronos is not a usable edge for Voltra. It stays as documented
research (`research/kronos/`), not deployed. The bottleneck is unchanged: the
way to a real edge is evidence (the running dry-run) or a genuinely better
signal that clears every gate — not a bigger forecasting model bolted on.

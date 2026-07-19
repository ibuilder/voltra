"""Monte Carlo + Kelly edge validation for a strategy's backtest trades.

Answers the question the profit factor alone can't: is the edge real, or is it
within the range of luck? Bootstraps the actual per-trade returns thousands of
times to get the *distribution* of outcomes, not a single lucky path.

Inputs a JSON list of per-trade profit_ratio (fractional P&L per trade), e.g.
exported from a freqtrade backtest:
    freqtrade backtesting ... --export trades
then extract trades[].profit_ratio to a JSON list.

Usage:
    python scripts/montecarlo.py user_data/backtest_results/tb_profit_ratios.json \
        [--sims 5000] [--risk-per-trade 0.01]

Reads returns as *per-trade fractional P&L on the position*. To model account
equity we scale each trade to the account by --risk-per-trade proxy is NOT used
for compounding here; instead we compound the raw per-trade ratios (as freqtrade
does with fixed stake), which is the honest reflection of the tested config.
"""

import argparse
import json
import sys

import numpy as np


def max_drawdown(equity: np.ndarray) -> float:
    """Max fractional drawdown of an equity curve (0..1)."""
    peak = np.maximum.accumulate(equity)
    return float(np.max((peak - equity) / peak))


def kelly_fraction(returns: np.ndarray) -> dict:
    """Classic Kelly for a win/loss process.

    f* = W - (1-W)/R, W=win rate, R=avg_win/avg_loss (both magnitudes).
    A value <= 0 means there is no edge worth betting.
    """
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    if len(wins) == 0 or len(losses) == 0:
        return {"kelly": 0.0, "win_rate": len(wins) / len(returns), "payoff": None}
    w = len(wins) / len(returns)
    avg_win = wins.mean()
    avg_loss = -losses.mean()
    payoff = avg_win / avg_loss
    kelly = w - (1 - w) / payoff
    return {"kelly": float(kelly), "win_rate": float(w), "payoff": float(payoff),
            "avg_win": float(avg_win), "avg_loss": float(avg_loss)}


def bootstrap(returns: np.ndarray, sims: int, rng: np.random.Generator) -> dict:
    """Resample trades with replacement; compound each path; collect stats."""
    n = len(returns)
    finals = np.empty(sims)
    dds = np.empty(sims)
    for i in range(sims):
        sample = rng.choice(returns, size=n, replace=True)
        equity = np.cumprod(1.0 + sample)
        finals[i] = equity[-1] - 1.0          # total return fraction
        dds[i] = max_drawdown(np.concatenate([[1.0], equity]))
    return {
        "median_return": float(np.median(finals)),
        "p05_return": float(np.percentile(finals, 5)),
        "p95_return": float(np.percentile(finals, 95)),
        "prob_profit": float(np.mean(finals > 0)),
        "median_maxdd": float(np.median(dds)),
        "p95_maxdd": float(np.percentile(dds, 95)),
        "worst_maxdd": float(np.max(dds)),
    }


def mean_significance(returns: np.ndarray, sims: int, rng: np.random.Generator) -> dict:
    """Bootstrap CI of the mean per-trade return. If the 5th percentile of the
    mean is <= 0, the edge is not statistically distinguishable from zero."""
    n = len(returns)
    means = np.array([rng.choice(returns, size=n, replace=True).mean() for _ in range(sims)])
    return {
        "mean_per_trade": float(returns.mean()),
        "mean_ci05": float(np.percentile(means, 5)),
        "mean_ci95": float(np.percentile(means, 95)),
        "prob_mean_positive": float(np.mean(means > 0)),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("returns_json")
    ap.add_argument("--sims", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    returns = np.array(json.load(open(args.returns_json)), dtype=float)
    rng = np.random.default_rng(args.seed)
    n = len(returns)

    pf_num = returns[returns > 0].sum()
    pf_den = -returns[returns < 0].sum()
    pf = pf_num / pf_den if pf_den else float("inf")

    boot = bootstrap(returns, args.sims, rng)
    sig = mean_significance(returns, args.sims, rng)
    kel = kelly_fraction(returns)

    print(f"=== Monte Carlo edge validation ({n} trades, {args.sims} sims) ===")
    print(f"Actual: total_return={np.prod(1+returns)-1:+.2%}  profit_factor={pf:.2f}  "
          f"win_rate={kel['win_rate']:.1%}")
    print()
    print("Bootstrap distribution of outcomes (resampling the real trades):")
    print(f"  median return : {boot['median_return']:+.1%}")
    print(f"  5th–95th pct  : {boot['p05_return']:+.1%}  …  {boot['p95_return']:+.1%}")
    print(f"  P(profitable) : {boot['prob_profit']:.1%}")
    print(f"  median maxDD  : {boot['median_maxdd']:.1%}   95th pct maxDD: {boot['p95_maxdd']:.1%}   worst: {boot['worst_maxdd']:.1%}")
    print()
    print("Is the edge real (mean per-trade > 0)?")
    print(f"  mean/trade    : {sig['mean_per_trade']:+.4%}")
    print(f"  90% CI        : {sig['mean_ci05']:+.4%}  …  {sig['mean_ci95']:+.4%}")
    print(f"  P(mean > 0)   : {sig['prob_mean_positive']:.1%}")
    print()
    print("Kelly sizing (how much edge is there to bet?):")
    if kel['payoff'] is None:
        print("  no wins or no losses — undefined")
    else:
        print(f"  payoff (W/L)  : {kel['payoff']:.2f}   avg_win={kel['avg_win']:.2%}  avg_loss={kel['avg_loss']:.2%}")
        print(f"  Kelly f*      : {kel['kelly']:+.1%}  "
              f"(half-Kelly: {kel['kelly']/2:+.1%})")
    print()
    # Verdict
    verdict = []
    if sig['prob_mean_positive'] < 0.95:
        verdict.append(f"edge NOT significant at 95% (only {sig['prob_mean_positive']:.0%} of resamples positive)")
    else:
        verdict.append("edge significant at 95%")
    if kel['payoff'] is not None and kel['kelly'] <= 0.02:
        verdict.append(f"Kelly says bet ~0% (f*={kel['kelly']:+.1%}) — edge too thin to size meaningfully")
    print("VERDICT: " + "; ".join(verdict))
    return 0


if __name__ == "__main__":
    sys.exit(main())

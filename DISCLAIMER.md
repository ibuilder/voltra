# Disclaimer — read before using Voltra

**Voltra is experimental software for automated cryptocurrency trading.
Cryptocurrency trading carries a high risk of loss. You can lose some or all of
your money. Use this software entirely at your own risk.**

## Not financial advice

Nothing in this repository — code, backtests, reports, strategies, or
documentation — is financial, investment, tax, or legal advice. The authors are
not licensed financial advisors. Backtest and dry-run results are **not**
indicative of future performance. Most retail algorithmic traders lose money.

## No warranty

This software is provided "as is", without warranty of any kind (see LICENSE).
The authors are not liable for any losses, damages, missed trades, exchange
outages, bugs, or data errors arising from its use.

## Your responsibility

- **Default is paper trading.** Every bot ships with `dry_run: true`. Enabling
  live trading (`dry_run: false`) is a manual, human-only change. Do not enable
  it until you fully understand the code and have validated it yourself.
- The project's own gates (out-of-sample profit factor > 1.3, max drawdown
  < 15%, a 30-day dry-run within ~20% of backtest expectancy) are **not met**
  at the time of writing. There is no evidence this system is profitable.
- You are responsible for securing your exchange API keys (trade-only, no
  withdrawal, IP-whitelisted), your funds, and your infrastructure.
- Only trade with money you can afford to lose completely.
- You are responsible for compliance with the laws and tax rules of your
  jurisdiction.

## Auto-updates

The desktop controller can auto-update from signed GitHub Releases. Updates are
signature-verified and prompt before installing — never silent. Only install
updates from the official release channel you trust.

By using this software you acknowledge and accept these terms.

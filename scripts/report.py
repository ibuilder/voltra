"""Weekly dry-run performance report (Phase 4).

Reads every bot's REST API, summarizes the week, and — the part that gates
Phase 5 — compares cumulative dry-run results against pro-rata backtest
expectations from the walk-forward report. Divergence beyond ~20% means the
backtest doesn't describe reality and nothing goes live.

Usage:
    python scripts/report.py            # writes docs/reports/weekly-<date>.md
    python scripts/report.py --stdout   # print only
"""

import argparse
import json
import sys
from base64 import b64encode
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent

# Walk-forward OOS expectations (docs/walkforward-report-2026-07-02.md):
# per-week figures derived from the 2025-01-01 -> 2026-07-02 OOS window
# (78.1 weeks, $5,000 start). Update after every re-hyperopt.
DRY_RUN_START = datetime(2026, 7, 2, tzinfo=timezone.utc)
EXPECTATIONS = {
    "http://127.0.0.1:8080": {
        "name": "solsignal-dry (TrendBreak)",
        "trades_per_week": 61 / 78.1,
        "profit_usd_per_week": 0.1058 * 5000 / 78.1,
    },
    "http://127.0.0.1:8081": {
        "name": "solsignal-cross (SolCross)",
        "trades_per_week": 8 / 78.1,
        "profit_usd_per_week": 0.0077 * 5000 / 78.1,
    },
}


def load_env_credentials() -> tuple[str, str]:
    creds = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("FREQTRADE__API_SERVER__") and "=" in line:
            key, _, value = line.partition("=")
            creds[key.rsplit("__", 1)[1]] = value.strip()
    return creds["USERNAME"], creds["PASSWORD"]


def api(base: str, path: str, token: str) -> dict:
    r = requests.get(f"{base}/api/v1{path}",
                     headers={"Authorization": f"Bearer {token}"}, timeout=15)
    r.raise_for_status()
    return r.json()


def login(base: str, user: str, password: str) -> str:
    basic = b64encode(f"{user}:{password}".encode()).decode()
    r = requests.post(f"{base}/api/v1/token/login",
                      headers={"Authorization": f"Basic {basic}"}, timeout=15)
    r.raise_for_status()
    return r.json()["access_token"]


def divergence(actual: float, expected: float) -> str:
    if expected == 0:
        return "n/a"
    d = (actual - expected) / abs(expected)
    flag = "OK" if abs(d) <= 0.20 else "DIVERGENT"
    return f"{d:+.0%} ({flag})"


def bot_section(base: str, exp: dict, user: str, password: str) -> str:
    try:
        token = login(base, user, password)
        cfg = api(base, "/show_config", token)
        profit = api(base, "/profit", token)
        balance = api(base, "/balance", token)
        status = api(base, "/status", token)
        daily = api(base, "/daily?timescale=8", token)
    except Exception as err:
        return f"## {exp['name']} — UNREACHABLE\n\n`{base}`: {err}\n"

    weeks = max((datetime.now(timezone.utc) - DRY_RUN_START).total_seconds()
                / (7 * 86400), 0.01)
    closed = profit.get("closed_trade_count", 0)
    pnl = profit.get("profit_closed_coin", 0.0)
    wins, losses = profit.get("winning_trades", 0), profit.get("losing_trades", 0)
    week_rows = "".join(
        f"| {d['date']} | {d['abs_profit']:+.2f} | {d['trade_count']} |\n"
        for d in daily.get("data", [])
    )

    return f"""## {exp['name']}

- State: **{cfg.get('state', '?')}** · dry_run: {cfg.get('dry_run')} · \
strategy: {cfg.get('strategy')} · freqtrade {cfg.get('version')}
- Balance: {balance.get('total', 0):,.2f} {cfg.get('stake_currency', 'USD')} \
· open trades: {len(status)}
- Closed trades: {closed} ({wins}W/{losses}L) · closed PnL: {pnl:+,.2f} USD
- Max drawdown: {profit.get('max_drawdown', 0):.2%}

**Divergence vs backtest expectation** ({weeks:.1f} weeks since {DRY_RUN_START:%Y-%m-%d}):

| Metric | Actual | Expected (pro-rata) | Divergence |
|---|---|---|---|
| Trades | {closed} | {exp['trades_per_week'] * weeks:.1f} | {divergence(closed, exp['trades_per_week'] * weeks)} |
| PnL (USD) | {pnl:+.2f} | {exp['profit_usd_per_week'] * weeks:+.2f} | {divergence(pnl, exp['profit_usd_per_week'] * weeks)} |

Last 8 days:

| Date | PnL (USD) | Trades |
|---|---|---|
{week_rows}"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stdout", action="store_true", help="print, don't write")
    args = parser.parse_args()

    user, password = load_env_credentials()
    today = datetime.now(timezone.utc)
    body = "\n".join(bot_section(base, exp, user, password)
                     for base, exp in EXPECTATIONS.items())
    report = (
        f"# SolSignal weekly report — {today:%Y-%m-%d}\n\n"
        f"{body}\n"
        "---\n"
        "Gate reminder: live capital requires OOS PF >1.3, backtest DD <15%, "
        "AND 30 days of dry-run within ~20% of expectations. "
        "Early weeks WILL look divergent — small samples, don't panic; "
        "judge at the 30-day mark.\n"
    )

    if args.stdout:
        print(report)
    else:
        out = ROOT / "docs" / "reports" / f"weekly-{today:%Y-%m-%d}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

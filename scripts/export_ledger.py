"""Trade / audit ledger export.

Reads the freqtrade SQLite databases directly (source of truth, works even if
the bots are stopped) and writes a flat CSV ledger of trades — one row per
trade — suitable for accounting, tax records, and audit.

Each CLOSED trade is a realized gain/loss event: it carries open/close dates,
prices, amount, stake, fees, realized P&L, and the exit reason. This is what an
accountant needs; every closed crypto trade is typically a taxable event.

Usage:
    python scripts/export_ledger.py                 # all DBs -> user_data/exports/ledger-<date>.csv
    python scripts/export_ledger.py --open          # include still-open trades
    python scripts/export_ledger.py --out ledger.csv
"""

import argparse
import csv
import glob
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (csv column, db column) — db column may be None for derived/meta fields.
COLUMNS = [
    ("db_file", None),
    ("trade_id", "id"),
    ("bot_strategy", "strategy"),
    ("exchange", "exchange"),
    ("pair", "pair"),
    ("is_open", "is_open"),
    ("trading_mode", "trading_mode"),
    ("open_date_utc", "open_date"),
    ("close_date_utc", "close_date"),
    ("amount", "amount"),
    ("open_rate", "open_rate"),
    ("close_rate", "close_rate"),
    ("stake_amount", "stake_amount"),
    ("open_trade_value", "open_trade_value"),
    ("fee_open_cost", "fee_open_cost"),
    ("fee_close_cost", "fee_close_cost"),
    ("realized_profit", "realized_profit"),
    ("close_profit_abs", "close_profit_abs"),
    ("close_profit_ratio", "close_profit"),
    ("exit_reason", "exit_reason"),
    ("enter_tag", "enter_tag"),
    ("stop_loss", "stop_loss"),
]


def rows_from_db(db_path: Path, include_open: bool):
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    have = {r[1] for r in con.execute("PRAGMA table_info(trades)")}
    where = "" if include_open else " WHERE is_open = 0"
    for r in con.execute(f"SELECT * FROM trades{where} ORDER BY open_date"):
        out = {}
        for csv_col, db_col in COLUMNS:
            if db_col is None:
                out[csv_col] = db_path.name
            else:
                out[csv_col] = r[db_col] if db_col in have else ""
        yield out
    con.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--open", action="store_true", help="include still-open trades")
    ap.add_argument("--db-glob", default=str(ROOT / "user_data" / "*.sqlite"))
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    dbs = sorted(Path(p) for p in glob.glob(args.db_glob))
    if not dbs:
        print(f"no databases matched {args.db_glob}", file=sys.stderr)
        return 1

    out_path = Path(args.out) if args.out else (
        ROOT / "user_data" / "exports" / f"ledger-{datetime.now(timezone.utc):%Y%m%d}.csv"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[c for c, _ in COLUMNS])
        writer.writeheader()
        for db in dbs:
            for row in rows_from_db(db, args.open):
                writer.writerow(row)
                total += 1

    realized = 0.0
    # quick P&L summary for the console
    with out_path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["is_open"] in ("0", "False", "false") and row["close_profit_abs"]:
                try:
                    realized += float(row["close_profit_abs"])
                except ValueError:
                    pass

    print(f"wrote {total} trade rows -> {out_path}")
    print(f"realized P&L across closed trades: {realized:+.2f} (stake currency)")
    print("NB: dry-run trades are simulated. This is a record, not tax advice.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

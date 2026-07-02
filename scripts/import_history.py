"""Bulk-import hourly OHLCV history from Coinbase Exchange's public API.

Kraken's API can't serve deep candle history (720-candle cap) and its official
CSV archive lives behind a Drive quota, so this pulls research-grade data from
Coinbase (the plan's designated backup venue) — no API key needed. Prices on
Coinbase USD books track Kraken within basis points for majors; final
validation still happens on real Kraken data once the trades backfill lands.

Writes freqtrade-format feather files (1h native + 4h resample):
    user_data/data/coinbase/BTC_USD-1h.feather  etc.

Usage:
    python scripts/import_history.py [--pairs BTC-USD ETH-USD SOL-USD]
                                     [--start 2024-01-01]
                                     [--out user_data/data/coinbase]
"""

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

API = "https://api.exchange.coinbase.com/products/{pair}/candles"
GRANULARITY = 3600          # 1h
CHUNK = 300                 # API max candles per request
SLEEP = 0.15                # stay well under the 10 req/s public limit


def fetch_pair(pair: str, start: datetime) -> pd.DataFrame:
    """Page through [time, low, high, open, close, volume] rows, oldest first."""
    rows = []
    cursor = start
    end_time = datetime.now(timezone.utc)
    while cursor < end_time:
        chunk_end = min(cursor + timedelta(hours=CHUNK), end_time)
        resp = requests.get(
            API.format(pair=pair),
            params={
                "granularity": GRANULARITY,
                "start": cursor.isoformat(),
                "end": chunk_end.isoformat(),
            },
            headers={"User-Agent": "solsignal-research/1.0"},
            timeout=30,
        )
        resp.raise_for_status()
        rows.extend(resp.json())
        cursor = chunk_end
        print(f"\r{pair}: {len(rows):>6} candles through {cursor:%Y-%m-%d}", end="")
        time.sleep(SLEEP)
    print()

    df = pd.DataFrame(rows, columns=["time", "low", "high", "open", "close", "volume"])
    df["date"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = (
        df.drop(columns=["time"])
        .drop_duplicates(subset="date")
        .sort_values("date")
        .reset_index(drop=True)
    )
    return df[["date", "open", "high", "low", "close", "volume"]].astype(
        {c: "float64" for c in ("open", "high", "low", "close", "volume")}
    )


def resample_4h(df: pd.DataFrame) -> pd.DataFrame:
    """1h -> 4h anchored at midnight UTC (freqtrade's alignment)."""
    out = (
        df.set_index("date")
        .resample("4h", label="left", closed="left")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna(subset=["open"])
        .reset_index()
    )
    return out


def coverage(df: pd.DataFrame, hours: int) -> str:
    expected = (df["date"].iloc[-1] - df["date"].iloc[0]) / pd.Timedelta(hours=hours) + 1
    return (
        f"{df['date'].iloc[0]:%Y-%m-%d} -> {df['date'].iloc[-1]:%Y-%m-%d %H:%M} "
        f"({len(df)} candles, {len(df) / expected:.1%} of expected)"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", nargs="+", default=["BTC-USD", "ETH-USD", "SOL-USD"])
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--out", default="user_data/data/coinbase")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)

    for pair in args.pairs:
        df = fetch_pair(pair, start)
        if df.empty:
            print(f"{pair}: NO DATA — skipped")
            continue
        base = pair.replace("-", "_")
        df.to_feather(out_dir / f"{base}-1h.feather")
        df4 = resample_4h(df)
        df4.to_feather(out_dir / f"{base}-4h.feather")
        print(f"  1h: {coverage(df, 1)}")
        print(f"  4h: {coverage(df4, 4)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Convert Kraken's official OHLCVT CSV archive into freqtrade feather files.

The archive (support.kraken.com -> "Downloadable historical OHLCVT data") is
one big zip of <PAIR>_<minutes>.csv files with rows:
    epoch_seconds,open,high,low,close,volume,trades
No header. Legacy tickers: XBT = BTC, XDG = DOGE. This is ground-truth Kraken
data — it supersedes the Coinbase research import for validation runs.

Usage:
    python scripts/import_kraken_csv.py --zip <path/to/archive.zip>
        [--pairs BTC ETH SOL ...] [--since 2023-01-01]
        [--out user_data/data/kraken]
"""

import argparse
import sys
import zipfile
from pathlib import Path

import pandas as pd

# our symbol -> kraken archive symbol
LEGACY = {"BTC": "XBT", "DOGE": "XDG"}
TIMEFRAMES = {"60": "1h", "240": "4h"}


def convert(zf: zipfile.ZipFile, member: str, out_file: Path, since: str,
            merge: bool = False) -> str:
    with zf.open(member) as fh:
        df = pd.read_csv(
            fh, header=None,
            names=["ts", "open", "high", "low", "close", "volume", "trades"],
        )
    df["date"] = pd.to_datetime(df["ts"], unit="s", utc=True)
    df = df[df["date"] >= pd.Timestamp(since, tz="UTC")]
    df = df[["date", "open", "high", "low", "close", "volume"]].astype(
        {c: "float64" for c in ("open", "high", "low", "close", "volume")}
    )
    if merge and out_file.exists():
        existing = pd.read_feather(out_file)
        df = pd.concat([existing, df])
    df = (
        df.drop_duplicates(subset="date")
        .sort_values("date")
        .reset_index(drop=True)
    )
    if df.empty:
        return f"  {member}: no rows since {since} - SKIPPED"
    df.to_feather(out_file)
    return (
        f"  {member} -> {out_file.name}: {len(df)} candles, "
        f"{df['date'].iloc[0]:%Y-%m-%d} to {df['date'].iloc[-1]:%Y-%m-%d}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", required=True)
    parser.add_argument("--pairs", nargs="+",
                        default=["BTC", "ETH", "SOL", "XRP", "CELO", "BNB",
                                 "DOGE", "ADA", "XLM", "TRX", "ZEC", "SUI",
                                 "NEAR", "LTC", "WLD", "AAVE"])
    parser.add_argument("--since", default="2023-01-01")
    parser.add_argument("--out", default="user_data/data/kraken")
    parser.add_argument("--merge", action="store_true",
                        help="append to existing feathers (quarterly updates)")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(args.zip) as zf:
        members = {Path(n).name: n for n in zf.namelist() if n.endswith(".csv")}
        for symbol in args.pairs:
            archive_sym = LEGACY.get(symbol, symbol)
            for minutes, tf in TIMEFRAMES.items():
                name = f"{archive_sym}USD_{minutes}.csv"
                if name not in members:
                    print(f"  {name}: NOT IN ARCHIVE - skipped")
                    continue
                out_file = out_dir / f"{symbol}_USD-{tf}.feather"
                print(convert(zf, members[name], out_file, args.since, args.merge))
    return 0


if __name__ == "__main__":
    sys.exit(main())

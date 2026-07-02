#!/bin/sh
# Background data-storage daemon (runs inside the freqtrade image).
#
# Pass 1 (once): backfill 2y of 1h/4h candles for the core pairs from Kraken
#   trades data. Kraken's OHLCV API caps at 720 candles, and freqtrade blocks
#   plain candle downloads for Kraken entirely — everything goes via
#   --dl-trades. The initial backfill takes many hours; a marker file records
#   completion so restarts skip it.
# Pass 2 (forever): incremental trades refresh of every screened pair every
#   6h. Trades are cached in user_data/data/kraken/trades/, so each cycle only
#   fetches what's new since the last run.
set -u

CONFIG=/freqtrade/user_data/config.json
PAIRS_FILE=/freqtrade/user_data/pairlist.json
MARKER=/freqtrade/user_data/data/.backfill_complete
# Marker is only written if this file really exists — exit codes alone lie.
CORE_PROOF=/freqtrade/user_data/data/kraken/BTC_USD-1h.feather

if [ ! -f "$MARKER" ]; then
    echo "[data-daemon] Backfilling 2y of BTC/ETH/SOL via --dl-trades (many hours)..."
    freqtrade download-data --config "$CONFIG" \
        --pairs BTC/USD ETH/USD SOL/USD \
        --dl-trades -t 1h 4h --timerange 20240101-
    if [ $? -eq 0 ] && [ -f "$CORE_PROOF" ]; then
        touch "$MARKER"
        echo "[data-daemon] Backfill complete."
    else
        echo "[data-daemon] Backfill FAILED - will retry on next container restart."
    fi
fi

while true; do
    echo "[data-daemon] Incremental trades refresh of screened pairs..."
    freqtrade download-data --config "$CONFIG" \
        --pairs-file "$PAIRS_FILE" --dl-trades -t 1h 4h --days 14 \
        || echo "[data-daemon] Refresh failed - retrying next cycle."
    sleep 21600
done

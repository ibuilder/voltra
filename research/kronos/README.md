# Kronos research (Phase 1: forecast-skill test)

Evaluates whether the [Kronos](https://github.com/shiyu-coder/Kronos)
forecasting foundation model has a fee-surviving directional edge on our
held-out Kraken data. **Result: no (zero-shot).** See
[../../docs/kronos-report.md](../../docs/kronos-report.md).

## Reproduce

Kronos + PyTorch are heavy externals and are **not** vendored here.

```bash
# 1. clone Kronos anywhere
git clone https://github.com/shiyu-coder/Kronos /some/path/Kronos

# 2. deps (CPU torch is fine)
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install einops huggingface_hub safetensors

# 3. run (downloads Kronos-small from HuggingFace on first use)
export KRONOS_PATH=/some/path/Kronos
python research/kronos/skill_test.py --pair BTC_USD \
    --start 2025-01-01 --end 2025-07-01 --lookback 512 --horizon 24 --limit 0
```

The run writes each window to `skill-<pair>-<start>.csv` incrementally, so it is
resumable — re-running continues from where it stopped. `--limit N` caps windows
for a quick check.

Requires the Kraken feather data in `user_data/data/kraken/` (see the repo's
Kraken data notes).

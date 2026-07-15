"""Tests for the healthwatch monitor's decision logic — especially the
dry-run tripwire, the safety control that must fire if a bot goes live.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "ops"))

from healthwatch import classify_config


def test_healthy_dryrun_bot_is_ok():
    state, detail = classify_config(
        {"dry_run": True, "state": "running", "strategy": "TrendBreakStrategy"}
    )
    assert state == "ok"
    assert "dry_run" in detail


def test_dry_run_tripwire_fires_critical():
    # The whole point: a bot reporting dry_run=false is a CRITICAL security event.
    state, detail = classify_config(
        {"dry_run": False, "state": "running", "strategy": "TrendBreakStrategy"}
    )
    assert state == "critical"
    assert "TRIPWIRE" in detail


def test_stopped_bot_is_warn():
    state, _ = classify_config({"dry_run": True, "state": "stopped"})
    assert state == "warn"


def test_tripwire_beats_stopped():
    # dry_run=false must win even if the bot is also not running.
    state, detail = classify_config({"dry_run": False, "state": "stopped"})
    assert state == "critical" and "TRIPWIRE" in detail

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import check_console

ROOT = Path(__file__).resolve().parents[1]


def test_console_fleet_matches_caddy_compose_and_client():
    errors = check_console.run_checks(ROOT)
    assert errors == [], "\n".join(errors)


def test_caddy_check_catches_missing_slug():
    errs = check_console.check_caddy("handle_path /bot/dry/* {\n")
    assert any("dca" in e for e in errs)


def test_deploy_check_requires_dca_wait():
    errs = check_console.check_deploy(
        'grep dry_run false\nfor c in voltra-freqtrade; do echo "$c"; done\n'
    )
    assert any("voltra-freqtrade-dca" in e for e in errs)

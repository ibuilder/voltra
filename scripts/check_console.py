#!/usr/bin/env python3
"""Static alignment check for the desktop console + Caddy fleet.

No Docker, no secrets, no network. Fails if slugs, compose services, or
deploy health waits drift apart. Refuses committed dry_run=false.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Must stay in sync with desktop/src-tauri/freqtrade-client REMOTE_SLUGS / BOT_DEFS
# and ops/Caddyfile handle_path /bot/<slug>.
FLEET = (
    ("dry", "freqtrade", "voltra-freqtrade", 8080),
    ("cross", "freqtrade-cross", "voltra-freqtrade-cross", 8081),
    ("webhook", "freqtrade-webhook", "voltra-freqtrade-webhook", 8082),
    ("dca", "freqtrade-dca", "voltra-freqtrade-dca", 8083),
    ("xsmom", "freqtrade-xsmom", "voltra-freqtrade-xsmom", 8084),
)

LIVE_RE = re.compile(r'"dry_run"\s*:\s*false')


def _read(root: Path, rel: str) -> str:
    path = root / rel
    if not path.is_file():
        raise FileNotFoundError(f"missing {rel}")
    return path.read_text(encoding="utf-8")


def check_caddy(caddy: str) -> list[str]:
    errors = []
    for slug, *_ in FLEET:
        needle = f"handle_path /bot/{slug}/*"
        if needle not in caddy:
            errors.append(f"Caddyfile missing {needle}")
    return errors


def check_compose(compose: str) -> list[str]:
    errors = []
    for slug, service, container, port in FLEET:
        if f"{service}:" not in compose:
            errors.append(f"compose missing service {service} (slug {slug})")
        if f"container_name: {container}" not in compose:
            errors.append(f"compose missing container {container}")
        if f"127.0.0.1:{port}:8080" not in compose:
            errors.append(f"compose missing loopback port {port} for {slug}")
    return errors


def check_deploy(deploy: str) -> list[str]:
    errors = []
    if "dry_run" not in deploy or "false" not in deploy:
        errors.append("deploy.sh must refuse dry_run=false")
    for *_, container, _port in FLEET:
        if container not in deploy:
            errors.append(f"deploy.sh does not wait on {container}")
    return errors


def check_rust_client(lib: str) -> list[str]:
    errors = []
    slugs = {slug for slug, *_ in FLEET}
    for slug in slugs:
        if f'"{slug}"' not in lib:
            errors.append(f"freqtrade-client missing slug {slug!r}")
    for _slug, _svc, _ctr, port in FLEET:
        if str(port) not in lib:
            errors.append(f"freqtrade-client missing local port {port}")
    if "REMOTE_SLUGS" not in lib:
        errors.append("freqtrade-client missing REMOTE_SLUGS")
    return errors


def check_env_example(env: str) -> list[str]:
    errors = []
    for key in (
        "FREQTRADE__API_SERVER__USERNAME",
        "FREQTRADE__API_SERVER__PASSWORD",
        "VOLTRA_DOMAIN",
    ):
        if key not in env:
            errors.append(f".env.example missing {key}")
    return errors


def check_no_live_configs(root: Path) -> list[str]:
    errors = []
    for path in root.glob("user_data/config*.json"):
        text = path.read_text(encoding="utf-8")
        if LIVE_RE.search(text):
            errors.append(f"{path.relative_to(root)} has dry_run=false")
    return errors


def run_checks(root: Path | None = None) -> list[str]:
    root = root or ROOT
    errors: list[str] = []
    errors.extend(check_caddy(_read(root, "ops/Caddyfile")))
    errors.extend(check_compose(_read(root, "docker-compose.yml")))
    errors.extend(check_deploy(_read(root, "scripts/deploy.sh")))
    errors.extend(check_rust_client(_read(root, "desktop/src-tauri/freqtrade-client/src/lib.rs")))
    errors.extend(check_env_example(_read(root, ".env.example")))
    errors.extend(check_no_live_configs(root))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Align console, Caddy, and compose")
    parser.parse_args(argv)
    try:
        errors = run_checks()
    except FileNotFoundError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    if errors:
        print("FAIL: console alignment")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("OK: Caddy, compose, deploy waits, and desktop slugs match. dry_run stays human-only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

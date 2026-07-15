"""SolSignal automated backup sidecar.

Periodically archives trade databases + configs + tuned params to a
timestamped tar.gz with retention. Secrets (.env) are DELIBERATELY excluded —
back those up separately in a password manager.

Restore: stop the stack, extract the archive over user_data/, start the stack.

Env:
  BACKUP_INTERVAL   seconds between backups (default 21600 = 6h)
  BACKUP_KEEP       how many archives to retain (default 28 ~ 1 week at 6h)
  BACKUP_DIR        output dir (default /freqtrade/user_data/backups)
"""

import os
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path

USER_DATA = Path("/freqtrade/user_data")
INTERVAL = int(os.environ.get("BACKUP_INTERVAL", "21600"))
KEEP = int(os.environ.get("BACKUP_KEEP", "28"))
BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", str(USER_DATA / "backups")))

# What to back up (globs relative to USER_DATA). NB: config*.json hold no
# secrets (keys are injected from .env at runtime), so they are safe to archive.
INCLUDE = ["*.sqlite", "*.sqlite-*", "config*.json", "strategies/*.json", "pairlist.json"]


def log(msg: str) -> None:
    print(f"[backup] {msg}", flush=True)


def make_backup() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = BACKUP_DIR / f"solsignal-{stamp}.tar.gz"
    members = []
    for pattern in INCLUDE:
        members.extend(sorted(USER_DATA.glob(pattern)))
    with tarfile.open(out, "w:gz") as tar:
        for m in members:
            if m.is_file():
                tar.add(m, arcname=m.relative_to(USER_DATA))
    log(f"wrote {out.name} ({len(members)} files, {out.stat().st_size // 1024} KB)")
    return out


def prune() -> None:
    archives = sorted(BACKUP_DIR.glob("solsignal-*.tar.gz"))
    for old in archives[:-KEEP] if len(archives) > KEEP else []:
        old.unlink()
        log(f"pruned {old.name}")


def main() -> None:
    log(f"start: every {INTERVAL}s, keep {KEEP}, dir {BACKUP_DIR}")
    while True:
        try:
            make_backup()
            prune()
        except Exception as e:  # never let the loop die
            log(f"ERROR: {type(e).__name__}: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()

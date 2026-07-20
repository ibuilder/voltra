"""Package the WordPress plugin into an installable .zip.

WordPress installs plugins from a zip whose top-level entry is the plugin
folder. This reads the version from the plugin header and writes
dist/voltra-monitor-<version>.zip.

Usage:
    python scripts/package_plugin.py
"""

import os
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "wordpress-plugin" / "voltra-monitor"
MAIN = SRC / "voltra-monitor.php"


def version() -> str:
    m = re.search(r"Version:\s*([0-9][0-9A-Za-z.\-]*)", MAIN.read_text(encoding="utf-8"))
    return m.group(1) if m else "0.0.0"


def main() -> int:
    if not SRC.is_dir():
        print(f"plugin source not found: {SRC}", file=sys.stderr)
        return 1
    ver = version()
    out = ROOT / "dist" / f"voltra-monitor-{ver}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(SRC.rglob("*")):
            if path.is_file():
                z.write(path, path.relative_to(SRC.parent))
                count += 1
    print(f"built {out.relative_to(ROOT)} ({out.stat().st_size} bytes, {count} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

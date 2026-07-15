#!/usr/bin/env python3
"""Run all HTML documentation checks."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def run(name: str) -> int:
    return subprocess.call([sys.executable, str(SCRIPTS / name)])


def main() -> int:
    for script in ("check_generated_docs.py", "check_docs_links.py", "check_docs_canonical.py"):
        code = run(script)
        if code:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

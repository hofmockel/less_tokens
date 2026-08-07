#!/usr/bin/env python3
"""Audit AGENTS.md with the same budget/ref checks as claudemd_audit.py."""

from __future__ import annotations

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from claudemd_audit import main  # noqa: E402


def _has_path_arg(args: list[str]) -> bool:
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg == "--budget":
            skip_next = True
            continue
        if arg.startswith("-"):
            continue
        return True
    return False


if __name__ == "__main__":
    if not _has_path_arg(sys.argv[1:]):
        sys.argv.insert(1, str(BASE / "AGENTS.md"))
    sys.exit(main())

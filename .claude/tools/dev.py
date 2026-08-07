#!/usr/bin/env python3
"""Dev command shim: one source for the test invocations CLAUDE.md used to
hardcode as prose. Wraps the venv's pytest with the same paths CI uses.

Usage:
    .claude/.venv-tokens/bin/python .claude/tools/dev.py unit
    .claude/.venv-tokens/bin/python .claude/tools/dev.py integration
    .claude/.venv-tokens/bin/python .claude/tools/dev.py all
    .claude/.venv-tokens/bin/python .claude/tools/dev.py single <nodeid>
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UNIT_DIR = ".claude/tests/unit/"
INTEGRATION_DIR = ".claude/tests/integration/"


def run_pytest(args: list[str]) -> int:
    cmd = [sys.executable, "-m", "pytest", *args, "-v"]
    return subprocess.call(cmd, cwd=REPO_ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("unit", help="Run unit tests")
    sub.add_parser("integration", help="Run integration tests")
    sub.add_parser("all", help="Run unit + integration tests")
    single = sub.add_parser("single", help="Run one test by nodeid")
    single.add_argument(
        "nodeid", help="e.g. .claude/tests/unit/test_chunkers.py::test_name"
    )

    ns = parser.parse_args()

    if ns.command == "unit":
        return run_pytest([UNIT_DIR])
    if ns.command == "integration":
        return run_pytest([INTEGRATION_DIR])
    if ns.command == "all":
        return run_pytest([UNIT_DIR, INTEGRATION_DIR])
    if ns.command == "single":
        return run_pytest([ns.nodeid])
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

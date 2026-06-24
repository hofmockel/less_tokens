#!/usr/bin/env python3
"""Backlog-lifecycle gate — a shipped item must leave BACKLOG.

Convention: when a CHANGELOG `[Unreleased]` entry ships a backlog item, it cites
that item's stable ID in brackets, e.g. `- [P1] Delete hook-duplicating prose`.
This gate fails if any cited ID still has a heading in BACKLOG.md — i.e. the item
shipped but was never deleted, the exact bookkeeping bug the lifecycle rule warns
about. Deterministic, stdlib-only, no done-marker needed.

IDs are `<letters><digits>` (P1, F2, G10, C3). BACKLOG headings look like
`- **P1 — ...**`; CHANGELOG citations look like `[P1]`.

Usage:
  python .claude/tools/changelog_gate.py            # gate CWD repo
  python .claude/tools/changelog_gate.py --root DIR
Exit 0 = clean, 1 = a shipped ID still lingers in BACKLOG, 2 = missing file.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ID = r"[A-Z]+\d+"
CITED = re.compile(rf"\[({ID})\]")           # [P1] in a CHANGELOG entry
HEADING = re.compile(rf"\*\*({ID})\s*—")      # **P1 — in BACKLOG


def unreleased_section(changelog: str) -> str:
    """Text between `## [Unreleased]` and the next `## ` heading."""
    m = re.search(r"^##\s*\[Unreleased\]\s*$", changelog, re.MULTILINE)
    if not m:
        return ""
    rest = changelog[m.end():]
    nxt = re.search(r"^##\s", rest, re.MULTILINE)
    return rest[: nxt.start()] if nxt else rest


def cited_ids(changelog: str) -> set[str]:
    return set(CITED.findall(unreleased_section(changelog)))


def backlog_ids(backlog: str) -> set[str]:
    return set(HEADING.findall(backlog))


def check(root: Path) -> int:
    changelog = root / "CHANGELOG.md"
    backlog = root / "BACKLOG.md"
    for f in (changelog, backlog):
        if not f.exists():
            print(f"changelog_gate: {f.name} not found", file=sys.stderr)
            return 2
    lingering = sorted(
        cited_ids(changelog.read_text()) & backlog_ids(backlog.read_text())
    )
    if lingering:
        for i in lingering:
            print(
                f"changelog_gate: {i} shipped (CHANGELOG [Unreleased]) "
                f"but still in BACKLOG.md — delete it.",
                file=sys.stderr,
            )
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".", help="repo root (default: CWD)")
    return check(Path(ap.parse_args().root))


if __name__ == "__main__":
    sys.exit(main())

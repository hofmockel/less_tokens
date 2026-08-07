#!/usr/bin/env python3
"""Merge gate for the backlog/changelog lifecycle. Two rules, both now law
(were honor-system prose in CLAUDE.md / BACKLOG.md):

1. Changelog-exists: a PR touching shipped code under `.claude/` or `agents/`
   (tests excluded) must include `CHANGELOG.md` in its diff with a non-empty
   `## [Unreleased]` section.
2. Backlog cross-check: when an `[Unreleased]` entry ships a backlog item it
   cites the item's ID (`- [P2] ...`); the gate fails if any cited ID still has
   a heading in `BACKLOG.md`, so a shipped item can't linger.

Pure checks (`check`, `lingering_backlog_ids`) are unit-testable; the CLI gathers
the diff from git and reads the two files. Wired into CI and `.pre-commit-config.yaml`.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

CHANGELOG = "CHANGELOG.md"
BACKLOG = "BACKLOG.md"

ID = r"[A-Z]+\d+"
CITED = re.compile(rf"\[({ID})\]")  # [P1] in a CHANGELOG entry
HEADING = re.compile(rf"\*\*({ID})\s*—")  # **P1 — in BACKLOG


def is_code_change(path: str) -> bool:
    """True for shipped Python under .claude/ or agents/, excluding tests."""
    p = path.replace("\\", "/")
    if not p.endswith(".py"):
        return False
    if "/tests/" in p or p.startswith("tests/"):
        return False
    return p.startswith(".claude/") or p.startswith("agents/")


def unreleased_section(changelog_text: str) -> str:
    """Text between `## [Unreleased]` and the next `## ` heading."""
    m = re.search(r"^##\s*\[Unreleased\]\s*$", changelog_text, re.MULTILINE)
    if not m:
        return ""
    rest = changelog_text[m.end() :]
    nxt = re.search(r"^##\s", rest, re.MULTILINE)
    return rest[: nxt.start()] if nxt else rest


def unreleased_entries(changelog_text: str) -> list[str]:
    """Return the `- ` bullet lines under the `## [Unreleased]` heading."""
    return [
        ln.strip()
        for ln in unreleased_section(changelog_text).splitlines()
        if ln.strip().startswith("- ")
    ]


def cited_ids(changelog_text: str) -> set[str]:
    """Backlog IDs cited in `[Unreleased]` (e.g. `[P2]`)."""
    return set(CITED.findall(unreleased_section(changelog_text)))


def backlog_ids(backlog_text: str) -> set[str]:
    """IDs that still have a `**P1 — ...**` heading in BACKLOG.md."""
    return set(HEADING.findall(backlog_text))


def lingering_backlog_ids(changelog_text: str, backlog_text: str) -> list[str]:
    """IDs cited as shipped but still present in BACKLOG — the lifecycle bug."""
    return sorted(cited_ids(changelog_text) & backlog_ids(backlog_text))


def check(changed_files: list[str], changelog_text: str) -> tuple[bool, str]:
    """Rule 1 (changelog-exists). Pure — no git, no IO."""
    code = sorted(f for f in changed_files if is_code_change(f))
    if not code:
        return True, "no shipped-code change in diff; changelog gate skipped"

    if CHANGELOG not in {f.replace("\\", "/") for f in changed_files}:
        return False, (
            f"code changed ({', '.join(code)}) but {CHANGELOG} is not in the diff.\n"
            f"Add an entry under `## [Unreleased]` before merging."
        )
    if not unreleased_entries(changelog_text):
        return False, (
            f"code changed but `## [Unreleased]` in {CHANGELOG} has no entries.\n"
            f"Add at least one `- ` bullet describing the change."
        )
    return True, f"changelog gate ok ({len(code)} code file(s) documented)"


def _git(args: list[str]) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=False
    ).stdout


def changed_files(base: str | None) -> list[str]:
    """Files changed vs `base` (three-dot). Falls back to staged+working tree."""
    if base:
        out = _git(["diff", "--name-only", f"{base}...HEAD"])
        if out.strip():
            return [line for line in out.splitlines() if line.strip()]
    # local / pre-commit: staged + unstaged vs HEAD
    out = _git(["diff", "--name-only", "HEAD"]) + _git(
        ["diff", "--name-only", "--cached"]
    )
    return sorted({line for line in out.splitlines() if line.strip()})


def main(argv: list[str]) -> int:
    base = None
    if os.environ.get("GITHUB_BASE_REF"):
        base = f"origin/{os.environ['GITHUB_BASE_REF']}"
    if len(argv) > 1:
        base = argv[1]

    repo = Path(__file__).resolve().parents[2]
    text = (
        (repo / CHANGELOG).read_text(encoding="utf-8")
        if (repo / CHANGELOG).exists()
        else ""
    )
    backlog_text = (
        (repo / BACKLOG).read_text(encoding="utf-8")
        if (repo / BACKLOG).exists()
        else ""
    )

    ok = True
    # Rule 1: changelog-exists
    ok1, msg = check(changed_files(base), text)
    print(f"changelog-gate: {msg}", file=sys.stdout if ok1 else sys.stderr)
    ok &= ok1
    # Rule 2: backlog cross-check
    lingering = lingering_backlog_ids(text, backlog_text)
    if lingering:
        for i in lingering:
            print(
                f"changelog-gate: {i} shipped (CHANGELOG [Unreleased]) "
                f"but still in {BACKLOG} — delete it.",
                file=sys.stderr,
            )
        ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

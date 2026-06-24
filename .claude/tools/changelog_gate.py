#!/usr/bin/env python3
"""Merge gate: a code-changing PR must record a CHANGELOG `[Unreleased]` entry.

Replaces the honor-system lifecycle prose (was in CLAUDE.md / BACKLOG.md). The
rule is now law: if a PR touches shipped code under `.claude/` or `agents/`
(tests excluded), `CHANGELOG.md` must appear in the diff and its `[Unreleased]`
section must contain at least one entry.

Core check is pure (`check`) so it is unit-testable; the CLI gathers the diff
from git. Wired into CI (`.github/workflows/tests.yml`) and `.pre-commit-config.yaml`.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

CHANGELOG = "CHANGELOG.md"


def is_code_change(path: str) -> bool:
    """True for shipped Python under .claude/ or agents/, excluding tests."""
    p = path.replace("\\", "/")
    if not p.endswith(".py"):
        return False
    if "/tests/" in p or p.startswith("tests/"):
        return False
    return p.startswith(".claude/") or p.startswith("agents/")


def unreleased_entries(changelog_text: str) -> list[str]:
    """Return the `- ` bullet lines under the `## [Unreleased]` heading."""
    lines = changelog_text.splitlines()
    out: list[str] = []
    in_block = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if in_block:
                break  # reached the next release heading
            in_block = stripped.lower().startswith("## [unreleased]")
            continue
        if in_block and stripped.startswith("- "):
            out.append(stripped)
    return out


def check(changed_files: list[str], changelog_text: str) -> tuple[bool, str]:
    """(ok, message). Pure — no git, no IO."""
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
    out = _git(["diff", "--name-only", "HEAD"]) + _git(["diff", "--name-only", "--cached"])
    return sorted({line for line in out.splitlines() if line.strip()})


def main(argv: list[str]) -> int:
    base = None
    if "GITHUB_BASE_REF" in os.environ and os.environ["GITHUB_BASE_REF"]:
        base = f"origin/{os.environ['GITHUB_BASE_REF']}"
    if len(argv) > 1:
        base = argv[1]

    repo = Path(__file__).resolve().parents[2]
    changelog_path = repo / CHANGELOG
    text = changelog_path.read_text(encoding="utf-8") if changelog_path.exists() else ""

    ok, msg = check(changed_files(base), text)
    stream = sys.stdout if ok else sys.stderr
    print(f"changelog-gate: {msg}", file=stream)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

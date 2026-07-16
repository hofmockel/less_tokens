"""Shared freshness gate for continue.md handoff docs.

continue.md embeds "_Last updated at HEAD `<hash>`_" as an anchor. This
compares that hash against the repo's current HEAD so a stale handoff can't
be silently trusted by a fresh agent that reads it directly (bypassing the
/continue skill's own Phase 1 staleness check).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

HASH_RE = re.compile(r"_Last updated at HEAD `([0-9a-f]{7,40})`")
PREVIEW_LINES = 10


def _git(repo: Path, *args: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True
    )
    return proc.returncode, proc.stdout, proc.stderr


def check_continue_freshness(file_path: str, *, repo: Path) -> tuple[int, str, str]:
    """Returns (exit_code, stdout, stderr). exit_code 2 blocks the Read."""
    p = Path(file_path)
    if p.name != "continue.md":
        return 0, "", ""
    if not p.is_absolute():
        p = repo / p
    if not p.exists():
        return 0, "", ""
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0, "", ""
    match = HASH_RE.search(text)
    if not match:
        return 0, "", ""
    recorded = match.group(1)
    if _git(repo, "cat-file", "-e", recorded)[0] != 0:
        return 0, "", ""
    code, out, _ = _git(repo, "rev-list", "--count", f"{recorded}..HEAD")
    if code != 0:
        return 0, "", ""
    try:
        count = int(out.strip())
    except ValueError:
        return 0, "", ""
    if count == 0:
        return 0, "", ""
    _, log_out, _ = _git(repo, "log", "--oneline", f"{recorded}..HEAD")
    lines = log_out.strip().splitlines()
    preview = "\n".join(lines[:PREVIEW_LINES])
    more = f"\n  … and {len(lines) - PREVIEW_LINES} more" if len(lines) > PREVIEW_LINES else ""
    msg = (
        f"continue.md is {count} commit(s) stale (recorded HEAD {recorded[:7]}).\n"
        f"Run: git log --oneline {recorded[:7]}..HEAD\n{preview}{more}\n"
        "Read those commits before trusting this handoff's Current state / Open work sections."
    )
    return 2, "", msg

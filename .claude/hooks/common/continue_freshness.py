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


def _touches_continue_md(repo: Path, ref: str) -> bool:
    _, out, _ = _git(repo, "show", "--name-only", "--format=", ref)
    return "continue.md" in out.splitlines()


def _staleness_result(repo: Path, recorded: str, ref: str) -> tuple[int, str, str] | None:
    """Common tail: compare `recorded` against `ref`, or None if not stale/unknown."""
    if _git(repo, "cat-file", "-e", recorded)[0] != 0:
        return None
    code, out, _ = _git(repo, "rev-list", "--count", f"{recorded}..{ref}")
    if code != 0:
        return None
    try:
        count = int(out.strip())
    except ValueError:
        return None
    if count == 0:
        return None
    if count == 1 and _touches_continue_md(repo, ref):
        # The only commit "ahead" of `recorded` is `ref` itself, and that
        # commit is the one that updated continue.md — it structurally
        # cannot embed its own not-yet-existing hash, so this exact 1-commit
        # gap is unavoidable, not drift. (Same gap the repo's own 410eff2
        # "close self-referential staleness gap" commit worked around by
        # hand instead of fixing the checker.)
        return None
    _, log_out, _ = _git(repo, "log", "--oneline", f"{recorded}..{ref}")
    lines = log_out.strip().splitlines()
    preview = "\n".join(lines[:PREVIEW_LINES])
    more = f"\n  … and {len(lines) - PREVIEW_LINES} more" if len(lines) > PREVIEW_LINES else ""
    msg = (
        f"continue.md is {count} commit(s) stale (recorded HEAD {recorded[:7]}).\n"
        f"Run: git log --oneline {recorded[:7]}..{ref}\n{preview}{more}\n"
        "Read those commits before trusting this handoff's Current state / Open work sections."
    )
    return 2, "", msg


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
    return _staleness_result(repo, match.group(1), "HEAD") or (0, "", "")


def check_continue_freshness_at_ref(
    repo: Path, ref: str, *, rel_path: str = "continue.md"
) -> tuple[int, str, str]:
    """Like check_continue_freshness, but checks continue.md as committed at
    `ref` (e.g. a commit about to be pushed) instead of the working tree +
    HEAD. Used by the native pre-push hook, where what matters is the content
    being sent, not what happens to be checked out locally right now.
    """
    proc = subprocess.run(
        ["git", "-C", str(repo), "show", f"{ref}:{rel_path}"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return 0, "", ""
    match = HASH_RE.search(proc.stdout)
    if not match:
        return 0, "", ""
    return _staleness_result(repo, match.group(1), ref) or (0, "", "")

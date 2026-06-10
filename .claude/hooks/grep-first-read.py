#!/usr/bin/env python3
"""PreToolUse hook: block whole-file Reads of large files (S13).

When Claude tries to Read a file with no offset and the file exceeds
GREP_FIRST_LINE_THRESHOLD lines, block and tell it to locate the target first:

  * /def <symbol>  (symbols.py — AST-exact, no embeddings cost)
  * search.py "<query>"  (for prose / non-symbol targets)

Then Read only the relevant slice.

Exemptions (no double gate):
  * Any Read with an explicit offset — deliberate slice, always pass.
  * File is in last-search.json and the search is recent — auto-slice.py
    will redirect to the exact slice; no need to also block here.
  * File is indexed AND no recent search — search-first.py already blocks;
    adding a second block message is noise.

install.py wires this as PreToolUse on Read.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# Repo resolution (shared pattern across all hooks)
# ---------------------------------------------------------------------------

def _resolve_repo() -> Path:
    if os.environ.get("LESS_TOKENS_REPO"):
        return Path(os.environ["LESS_TOKENS_REPO"]).resolve()
    curr = Path(__file__).resolve().parent
    for _ in range(4):
        if (curr / "CLAUDE.md").exists() or (curr / ".git").exists():
            return curr
        curr = curr.parent
    curr = Path.cwd().resolve()
    for _ in range(10):
        if (curr / ".git").exists() or (curr / "CLAUDE.md").exists():
            return curr
        if curr == curr.parent:
            break
        curr = curr.parent
    return Path(__file__).resolve().parent.parent.parent


REPO = _resolve_repo()
sys.path.insert(0, str(REPO / ".claude" / "tools"))

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

try:
    from search_config import (
        GREP_FIRST_LINE_THRESHOLD,
        active_state_dir as _active_state_dir,
        WINDOW_SECONDS,
    )
except Exception:
    GREP_FIRST_LINE_THRESHOLD = 150
    def _active_state_dir() -> Path:  # type: ignore[misc]
        return REPO / ".claude" / "state"
    WINDOW_SECONDS = 300

RANGES_FILE = _active_state_dir() / "last-search.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count_lines(p: Path) -> int:
    n = 0
    try:
        with p.open("rb") as f:
            for _ in f:
                n += 1
    except OSError:
        return 0
    return n


def _in_last_search(p: Path) -> bool:
    """True if file appears in a recent auto-slice search result."""
    try:
        if (time.time() - RANGES_FILE.stat().st_mtime) > WINDOW_SECONDS:
            return False
        data = json.loads(RANGES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    for key in data:
        kp = Path(key)
        if kp == p or kp.name == p.name or str(p).endswith(str(kp)):
            return True
    return False


def _is_indexed(p: Path) -> bool:
    """True if search-first.py would gate this file."""
    try:
        from search_config import (
            EXCLUDED_DIR_NAMES,
            EXCLUDED_DIR_PREFIXES,
            INDEXED_SOURCE_DIRS,
        )
    except Exception:
        return False
    try:
        rel = p.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return False
    parts = set(Path(rel).parts)
    if parts & set(EXCLUDED_DIR_NAMES):
        return False
    if any(rel.startswith(px) for px in EXCLUDED_DIR_PREFIXES):
        return False
    if "/" not in rel:
        return rel.endswith((".md", ".py", ".sql"))
    if any(rel.startswith(d) for d in INDEXED_SOURCE_DIRS):
        return rel.endswith((".py", ".sql"))
    return False


def _search_was_recent() -> bool:
    state_file = _active_state_dir() / "last-search"
    try:
        return (time.time() - state_file.stat().st_mtime) < WINDOW_SECONDS
    except OSError:
        return False


def _symbol_hint(p: Path) -> str:
    """Suggest /def if the filename maps to known symbols."""
    try:
        from symbols import lookup  # type: ignore[import]
        hits = lookup(p.stem)
        if hits:
            return f"  /def {p.stem}  ->  {hits[0]['file']}:{hits[0]['line']}\n"
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Main check
# ---------------------------------------------------------------------------

def check(file_path: str, offset: object) -> str | None:
    """Return a block reason string or None to allow."""
    if not GREP_FIRST_LINE_THRESHOLD:
        return None
    if offset:  # deliberate slice
        return None
    if not file_path:
        return None

    p = Path(file_path)
    if not p.exists():
        return None  # let Read raise its own error

    # Exempt: auto-slice will redirect to exact lines
    if _in_last_search(p):
        return None

    # Exempt: search-first already blocks (indexed + no recent search)
    if _is_indexed(p) and not _search_was_recent():
        return None

    n = _count_lines(p)
    if n <= GREP_FIRST_LINE_THRESHOLD:
        return None

    venv_py = str(REPO / ".claude" / ".venv-tokens" / "bin" / "python")
    hint = _symbol_hint(p)
    return (
        f"Grep-first gate (S13): {p.name} is {n:,} lines "
        f"(threshold {GREP_FIRST_LINE_THRESHOLD}). "
        f"Locate target before reading the whole file.\n\n"
        f"Options:\n"
        f"{hint}"
        f"  {venv_py} .claude/tools/symbols.py <name>    # exact file:line for any symbol\n"
        f"  {venv_py} .claude/tools/search.py \"<query>\"  # vector search for prose/concepts\n\n"
        f"Then: Read(file_path={file_path!r}, offset=<line>, limit=<n>)\n"
        f"To skip this gate, pass offset=1."
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("tool_name") != "Read":
        return 0
    inp = payload.get("tool_input", {})
    reason = check(inp.get("file_path", ""), inp.get("offset"))
    if reason:
        print("Grep-first: " + reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

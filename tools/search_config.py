"""Portable search/embeddings configuration — the only file to edit when
transplanting the vector-search system to a new codebase.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent


def _platform_python(base: Path) -> Path:
    if sys.platform == "win32":
        return base / "Scripts" / "python.exe"
    return base / "bin" / "python"


def _active_venv_python() -> Path | None:
    """The active venv's interpreter, from $VIRTUAL_ENV, if it exists.

    `activate` sets VIRTUAL_ENV and it reliably points at the live venv on
    every platform, so it's the most trustworthy signal — preferred over the
    configured relative path.
    """
    env = os.environ.get("VIRTUAL_ENV")
    if not env:
        return None
    py = _platform_python(Path(env))
    return py if py.exists() else None


def _venv_python(venv_rel: str) -> Path:
    """Resolve venv python across platforms.

    A live $VIRTUAL_ENV wins so an activated venv is used without editing
    this file; otherwise fall back to BASE/venv_rel.
    Windows: Scripts/python.exe  |  macOS/Linux: bin/python
    """
    active = _active_venv_python()
    if active is not None:
        return active
    return _platform_python(BASE / venv_rel)


# Venv python used for embeddings — change "app/.venv" to your venv location.
VENV_PY = _venv_python("app/.venv")

# Bare directory names excluded from indexing (used by embeddings.py parts check).
EXCLUDED_DIR_NAMES: set[str] = {
    ".venv", "__pycache__", "legacy", "backups", ".git", "reports", "node_modules",
}

# Path prefixes excluded by hooks' is_indexed() startswith check.
# Includes runtime dirs (.claude/) that embeddings never sees.
EXCLUDED_DIR_PREFIXES: tuple[str, ...] = (
    "legacy/", "backups/", ".claude/", "parity/", "reports/",
    "app/.venv/", "__pycache__/",
)

# Subdirectories whose *.py and *.sql files are indexed.
# Also used by hooks to gate the search-first and auto-refresh rules.
INDEXED_SOURCE_DIRS: tuple[str, ...] = ("tools/", "schema/")

# Root-level glob patterns that are also indexed (hooks use this too).
INDEXED_ROOT_GLOBS: tuple[str, ...] = ("*.md",)

# Extra markdown globs outside the repo root (relative to BASE), e.g.
# "docs/*.md". Indexed alongside INDEXED_ROOT_GLOBS but keyed by full
# relative path so a root and a subdir file of the same name don't
# collide. Default empty — host installs only index root markdown.
INDEXED_DOC_GLOBS: tuple[str, ...] = ()

# Embedding model + its vector dimension. Change both together when switching
# models, then re-run `embeddings.py refresh --full` (a dimension mismatch
# against an existing index.db yields silently wrong scores).
EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM: int = 384

# When True, chunk_python prepends the module docstring to each top-level
# def/class chunk so a single search hit carries the file's purpose without a
# follow-up Read. Opt-in: it grows every code chunk and changes content
# hashes, so the next refresh re-embeds all Python sources. Default off.
CHUNK_INCLUDE_MODULE_CONTEXT: bool = False

# source_type values returned by enumerate_sources() — drives --source-type CLI choices.
SOURCE_TYPES: list[str] = ["doc", "code", "journal", "changelog", "note"]

# --- Strategy 3: Tool Output Truncation ---
MAX_TOOL_OUTPUT_CHARS: int = 4000   # ~1000 tokens; set 0 to disable
TOOL_OUTPUT_HEAD_LINES: int = 50    # Bash: lines kept from output start
TOOL_OUTPUT_TAIL_LINES: int = 20    # Bash: lines kept from output end (errors live here)

# --- Strategy 5: Conversation Compaction Trigger ---
MAX_SESSION_CHARS: int = 500_000    # ~125k tokens; set 0 to disable

STATE_DIR: Path = BASE / ".claude" / "state"

# --- Token savings tracking (Strategy metrics) ---
TRACK_SAVINGS = False   # set True via: python tools/stats.py

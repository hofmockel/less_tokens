"""Portable search/embeddings configuration — the only file to edit when
transplanting the vector-search system to a new codebase.
"""
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent


def _venv_python(venv_rel: str) -> Path:
    """Resolve venv python across platforms.
    Windows: Scripts/python.exe  |  macOS/Linux: bin/python
    """
    if sys.platform == "win32":
        return BASE / venv_rel / "Scripts" / "python.exe"
    return BASE / venv_rel / "bin" / "python"


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
INDEXED_SOURCE_DIRS: tuple[str, ...] = ("tools/", "app/", "schema/")

# Root-level glob patterns that are also indexed (hooks use this too).
INDEXED_ROOT_GLOBS: tuple[str, ...] = ("*.md",)

# source_type values returned by enumerate_sources() — drives --source-type CLI choices.
SOURCE_TYPES: list[str] = ["doc", "code", "journal", "changelog", "note"]

# --- Strategy 3: Tool Output Truncation ---
MAX_TOOL_OUTPUT_CHARS: int = 4000   # ~1000 tokens; set 0 to disable
TOOL_OUTPUT_HEAD_LINES: int = 50    # Bash: lines kept from output start
TOOL_OUTPUT_TAIL_LINES: int = 20    # Bash: lines kept from output end (errors live here)

# --- Strategy 5: Conversation Compaction Trigger ---
MAX_SESSION_CHARS: int = 500_000    # ~125k tokens; set 0 to disable

# --- Multi-agent state location ---
# Where the search-first state file lives. Default `.claude/state/` for Claude Code;
# Cline / other adapters override to `.less_tokens/state/` so non-Claude projects
# don't get a stray `.claude/` directory.
STATE_DIR: Path = BASE / ".claude" / "state"

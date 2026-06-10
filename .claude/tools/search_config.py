"""Portable search/embeddings configuration — the only file to edit when
transplanting the vector-search system to a new codebase.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent.parent
CLAUDE_DIR = BASE / ".claude"


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
VENV_PY = _venv_python(".claude/.venv-tokens")

# Directory names excluded from indexing if they appear anywhere in the path.
# Used by embeddings.py and hooks to gate the search-first and auto-refresh rules.
EXCLUDED_DIR_NAMES: set[str] = {
    ".venv", "__pycache__", "legacy", "backups", ".git", "reports", "node_modules",
    ".claude", "parity",
}

# Path prefixes excluded by hooks' is_indexed() check.
EXCLUDED_DIR_PREFIXES: tuple[str, ...] = (
    "app/.venv/",
)

# Subdirectories whose *.py and *.sql files are indexed.
# Also used by hooks to gate the search-first and auto-refresh rules.
INDEXED_SOURCE_DIRS: tuple[str, ...] = ()

# Root-level glob patterns that are also indexed (hooks use this too).
# Supports recursive patterns via pathlib's `**`, e.g. "docs/**/*.md" or
# "**/*.md" — use one of those for doc-heavy repos whose markdown lives
# in subdirectories (default "*.md" only matches files at the repo root).
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

# Approximate chars per token — used by search.py to estimate result token cost.
# English prose: ~4 chars/token; dense code: ~3 chars/token. Tune if your corpus differs.
CHARS_PER_TOKEN: int = 4

# --- Strategy 3: Tool Output Truncation ---
MAX_TOOL_OUTPUT_CHARS: int = 4000   # ~1000 tokens; set 0 to disable
TOOL_OUTPUT_HEAD_LINES: int = 50    # Bash: lines kept from output start
TOOL_OUTPUT_TAIL_LINES: int = 20    # Bash: lines kept from output end (errors live here)

# --- Strategy 5: Conversation Compaction Trigger ---
MAX_SESSION_CHARS: int = 500_000    # ~125k tokens; set 0 to disable

# Optional: identify the Claude model this install targets. When set to a
# known ID (see tools/model_profiles.py), tools/search.py uses the model's
# recommended default `k` and warns if returned chunks risk filling the
# context window. When None, the static DEFAULT_K (3) applies. Example:
#   AGENT_MODEL = "claude-sonnet-4-6"
AGENT_MODEL: str | None = None

LESS_TOKENS_DIR: Path = BASE / ".less_tokens"
CLAUDE_STATE_DIR: Path = CLAUDE_DIR / "state"
CODEX_STATE_DIR: Path = LESS_TOKENS_DIR / "state"
STATE_DIR: Path = CLAUDE_STATE_DIR   # backward-compat alias — do not remove


def state_dir_for(agent: str | None = None) -> Path:
    if agent == "claude":
        return CLAUDE_STATE_DIR
    if agent == "codex":
        return CODEX_STATE_DIR
    return STATE_DIR


def active_state_dir() -> Path:
    explicit = os.environ.get("LESS_TOKENS_STATE_DIR")
    if explicit:
        return Path(explicit)
    return state_dir_for(os.environ.get("LESS_TOKENS_AGENT"))


_STATE_AGENT_AWARE: bool = True   # sentinel for installer merge check

# Search-first hook gate: how long after a search Reads on indexed files are
# allowed without re-searching. Increase for long edit sessions; decrease to
# force fresher context. Read by hooks/search-first.py.
WINDOW_SECONDS: int = 300

# --- Token savings tracking (Strategy metrics) ---
TRACK_SAVINGS = False   # set True via: python .claude/tools/stats.py

# --- CLAUDE.md budget (claudemd skill + claudemd-budget hook) ---
# CLAUDE.md is always-loaded, never searched — every token is a per-turn tax.
# The audit tool warns and the PostToolUse hook blocks when CLAUDE.md exceeds
# this token estimate. Set 0 to disable the hook. Move cut detail to the
# overflow doc (which IS indexed) so it stays discoverable by search.
CLAUDE_MD_TOKEN_BUDGET: int = 1200
CLAUDE_MD_OVERFLOW_DOC: str = "documentation.md"

# --- Caveman output enforcement (Stop hook: caveman-reminder.py) ---
# Checks the last assistant turn (not tool output) for filler phrases and an
# over-long prose body. Code fences are exempt. Set False to disable.
CAVEMAN_ENFORCE: bool = True
MAX_RESPONSE_WORDS: int = 600   # prose-word ceiling per turn; 0 disables the word check

# --- Noise-file read guard (read-guard.py) ---
# PreToolUse on Read blocks whole-file reads of high-noise files (pure token
# waste). A Read with an explicit offset (i.e. a slice) is always allowed.
# Set READ_DENY_GLOBS empty to disable glob blocking.
READ_DENY_GLOBS: tuple[str, ...] = (
    "*.lock", "*-lock.json", "*-lock.yaml", "package-lock.json", "yarn.lock",
    "poetry.lock", "Pipfile.lock", "Cargo.lock", "pnpm-lock.yaml", "composer.lock",
    "go.sum",
    "*.min.js", "*.min.css", "*.map",
    "*.ipynb",
    "*.pdf", "*.zip", "*.tar", "*.gz", "*.tgz", "*.whl", "*.so", "*.dll",
    "*.bin", "*.pyc", "*.png", "*.jpg", "*.jpeg", "*.gif", "*.ico",
)
# Data files (below) are allowed up to this many lines; over it the guard
# suggests head/wc/column-summary instead. Set 0 to disable the size check.
READ_DENY_DATA_MAX_LINES: int = 1000
READ_DENY_DATA_EXTS: tuple[str, ...] = (
    ".csv", ".tsv", ".json", ".jsonl", ".ndjson", ".parquet",
)

# --- S13: Grep-first Read gate (grep-first-read.py) ---
# PreToolUse on Read: block whole-file Reads of files over this line count when
# no offset is given. Claude is told to locate the target first via the symbol
# index (/def) then Read only the relevant slice.
# Files already handled by auto-slice (in last-search.json) or search-first
# (indexed, no recent search) are exempted — no double gate.
# Set 0 to disable.
GREP_FIRST_LINE_THRESHOLD: int = 150

# --- S10: Post-edit diff + re-Read block ---
# PostToolUse on Edit|Write: emit a unified diff as hookSpecificOutput so
# Claude has the change in context without re-reading the whole file.
# PreToolUse on Read: block a verify re-Read of the same file within this
# many seconds of the edit (diff already in context).  Set 0 to disable
# the block.  MAX_DIFF_LINES caps the emitted diff; 0 = no cap.
LAST_EDIT_WINDOW_SECONDS: int = 120
MAX_DIFF_LINES: int = 60

# --- G2: In-session re-read/re-search cache (context-cache.py) ---
# PreToolUse on Read|Grep: block repeat calls whose payload is already in
# context. Read cache is invalidated by file mtime change; Grep cache expires
# after CONTEXT_CACHE_GREP_TTL seconds. Set CONTEXT_CACHE_ENABLED=False to
# disable entirely.
CONTEXT_CACHE_ENABLED: bool = True
CONTEXT_CACHE_GREP_TTL: int = 300  # seconds; mirrors WINDOW_SECONDS

# --- G3: Directory listing dump control (listing-guard.py + lean-ls.py) ---
# PreToolUse on Bash: intercept ls -R / find . / tree and replace with lean-ls
# output (depth-limited, .gitignore-aware, dir-count summary). Set False to
# disable interception and pass the command through unchanged.
LISTING_GUARD_ENABLED: bool = True

# PostToolUse on Glob: cap result count; append "N more files..." tail when
# exceeded. Set 0 to disable. lean-ls outputs are already compact; this is a
# safety net for large wildcard Glob calls.
MAX_GLOB_RESULTS: int = 100

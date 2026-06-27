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
    """Return interpreter from $VIRTUAL_ENV if set, else None."""
    env = os.environ.get("VIRTUAL_ENV")
    if not env:
        return None
    py = _platform_python(Path(env))
    return py if py.exists() else None


def _venv_python(venv_rel: str) -> Path:
    """Return active-venv python if $VIRTUAL_ENV is set, else BASE/venv_rel."""
    active = _active_venv_python()
    if active is not None:
        return active
    return _platform_python(BASE / venv_rel)


# Venv python used for embeddings — change "app/.venv" to your venv location.
VENV_PY = _venv_python(".claude/.venv-tokens")

# Directory names excluded from indexing (path segment match).
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

# Root-level glob patterns indexed by embeddings.py and checked by hooks. Supports `**`.
INDEXED_ROOT_GLOBS: tuple[str, ...] = ("*.md",)

# Extra globs relative to BASE (e.g. "docs/*.md"). Keyed by full path to avoid collisions.
INDEXED_DOC_GLOBS: tuple[str, ...] = ()

# Embedding model + dimension — change both together; mismatch yields silently wrong scores.
EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM: int = 384

# When True, prepend module docstring to each chunk. Changes all hashes → full re-embed.
CHUNK_INCLUDE_MODULE_CONTEXT: bool = False

# Max chars per chunk; oversized chunks are split. 2000 ≈ 500 tokens. Set 0 to disable.
MAX_CHUNK_CHARS: int = 2000

# source_type values returned by enumerate_sources() — drives --source-type CLI choices.
SOURCE_TYPES: list[str] = ["doc", "code", "journal", "changelog", "note"]

# Chars per token estimate for search.py cost display (prose ~4, code ~3).
CHARS_PER_TOKEN: int = 4

# --- Strategy 3: Tool Output Truncation ---
MAX_TOOL_OUTPUT_CHARS: int = 4000   # ~1000 tokens; set 0 to disable
TOOL_OUTPUT_HEAD_LINES: int = 50    # Bash: lines kept from output start
TOOL_OUTPUT_TAIL_LINES: int = 20    # Bash: lines kept from output end (errors live here)

# Codex adapters use tighter output caps; LESS_TOKENS_CODEX_* env vars override.
CODEX_MAX_TOOL_OUTPUT_CHARS: int = 1500
CODEX_MAX_FILESYSTEM_READ_CHARS: int = 1200
CODEX_TOOL_OUTPUT_HEAD_LINES: int = 30
CODEX_TOOL_OUTPUT_TAIL_LINES: int = 20
CODEX_APPLY_PATCH_DIFF_CHARS: int = 1200

# --- Strategy 5: Conversation Compaction Trigger ---
MAX_SESSION_CHARS: int = 500_000    # ~125k tokens; set 0 to disable

# Claude model ID for context-aware k selection (see model_profiles.py). None → DEFAULT_K=3.
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

# Seconds after a search that Read calls on indexed files are allowed without re-searching.
WINDOW_SECONDS: int = 300

# Token savings tracking is always on and local-only (state/savings.jsonl);
# disable with the LESS_TOKENS_NO_STATS=1 environment variable.

# --- CLAUDE.md budget (claudemd skill + claudemd-budget hook) ---
# Always-loaded; every token is a per-turn tax. Set 0 to disable.
CLAUDE_MD_TOKEN_BUDGET: int = 1200
CLAUDE_MD_OVERFLOW_DOC: str = "DOCUMENTATION.md"

# --- Always-loaded rule budgets (claudemd_audit.py --rules) ---
# Per-file cap for .claude/rules/*.md. Set 0 to disable.
RULES_TOKEN_BUDGET: int = 600
RULES_OVERFLOW_DOC: str = "DOCUMENTATION.md"

# --- AGENTS.md budget (agentsmd-budget Codex hook) --- Always-loaded by Codex. Set 0 to disable.
AGENTS_MD_TOKEN_BUDGET: int = 1200
AGENTS_MD_OVERFLOW_DOC: str = "DOCUMENTATION.md"

# --- Skill description budget (claudemd_audit.py --skills) ---
# Always-loaded descriptions; long/overlapping ones are a per-turn tax. Set cap to 0 to disable.
SKILL_DESC_WORD_CAP: int = 50
SKILL_DESC_DUP_SIM: float = 0.85
SKILLS_DIR: str = ".claude/skills"

# --- Search result dedup (search.py) --- Drop a hit whose cosine to an already-selected
# hit is >= this, so two files with near-identical content don't both spend budget; the
# freed slot backfills the next distinct hit. Set >= 1.0 to disable (unit-vector cosine maxes at 1).
SEARCH_DEDUP_SIM: float = 0.97

# --- Caveman output enforcement (Stop hook: caveman-reminder.py) --- Set False to disable.
CAVEMAN_ENFORCE: bool = True
MAX_RESPONSE_WORDS: int = 600   # prose-word ceiling per turn; 0 disables the word check

# --- Noise-file read guard (read-guard.py) --- Sliced reads always pass. Empty to disable.
READ_DENY_GLOBS: tuple[str, ...] = (
    "*.lock", "*-lock.json", "*-lock.yaml", "package-lock.json", "yarn.lock",
    "poetry.lock", "Pipfile.lock", "Cargo.lock", "pnpm-lock.yaml", "composer.lock",
    "go.sum",
    "*.min.js", "*.min.css", "*.map",
    "*.ipynb",
    "*.pdf", "*.zip", "*.tar", "*.gz", "*.tgz", "*.whl", "*.so", "*.dll",
    "*.bin", "*.pyc", "*.png", "*.jpg", "*.jpeg", "*.gif", "*.ico",
)
# Data files allowed up to this many lines; over it guard suggests head/wc. Set 0 to disable.
READ_DENY_DATA_MAX_LINES: int = 1000
READ_DENY_DATA_EXTS: tuple[str, ...] = (
    ".csv", ".tsv", ".json", ".jsonl", ".ndjson", ".parquet",
)

# --- S13: Grep-first Read gate (grep-first-read.py) --- Block unsliced reads over this line count. Set 0 to disable.
GREP_FIRST_LINE_THRESHOLD: int = 150

# --- S10: Post-edit diff + re-Read block --- Diff emitted after Edit; re-Read blocked within window. Set 0 to disable.
LAST_EDIT_WINDOW_SECONDS: int = 120
MAX_DIFF_LINES: int = 60

# --- G2: In-session re-read/re-search cache (context-cache.py) --- Set False to disable.
CONTEXT_CACHE_ENABLED: bool = True
CONTEXT_CACHE_GREP_TTL: int = 300  # seconds; mirrors WINDOW_SECONDS
CONTEXT_CACHE_BASH_TTL: int = 120

# --- G3: Directory listing dump control (listing-guard.py + lean-ls.py) --- Set False to disable.
LISTING_GUARD_ENABLED: bool = True

# Glob result cap; excess appended as "N more files...". Set 0 to disable.
MAX_GLOB_RESULTS: int = 100

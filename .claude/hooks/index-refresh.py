#!/usr/bin/env python3
"""PostToolUse hook: re-embed indexed files after Edit/Write.

Receives the tool call JSON on stdin. If the touched file is in the indexed
set, fire `embeddings.py refresh` in the background — fastembed model load
is ~1-2s, which is too long to block every Edit. Fire-and-forget means a
search done immediately after an edit may briefly return stale results, but
the index converges within seconds.

Multiple rapid edits enqueue multiple refresh processes; each does its own
content-hash diff and only re-embeds what changed, so they're idempotent and
self-coalescing — last one wins.
"""
from __future__ import annotations

import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path

def _resolve_repo() -> Path:
    if os.environ.get("LESS_TOKENS_REPO"):
        return Path(os.environ["LESS_TOKENS_REPO"]).resolve()
    # Per-project install: walk up from __file__
    curr = Path(__file__).resolve().parent
    for _ in range(4):
        if (curr / "CLAUDE.md").exists() or (curr / ".git").exists():
            return curr
        curr = curr.parent
    # Global install fallback: hooks live outside the project tree, so walk up from cwd
    curr = Path.cwd().resolve()
    for _ in range(10):
        if (curr / ".git").exists() or (curr / "CLAUDE.md").exists():
            return curr
        if curr == curr.parent:
            break
        curr = curr.parent
    return Path(__file__).resolve().parent.parent.parent


REPO = _resolve_repo()

try:
    sys.path.insert(0, str(REPO / ".claude" / "tools"))
    from search_config import (  # noqa: E402
        EXCLUDED_DIR_NAMES,
        EXCLUDED_DIR_PREFIXES,
        INDEXED_ROOT_GLOBS,
        INDEXED_SOURCE_DIRS as INDEXED_DIRS,
        VENV_PY,
    )
except Exception:
    EXCLUDED_DIR_NAMES: set = set()
    EXCLUDED_DIR_PREFIXES: tuple = ()
    INDEXED_ROOT_GLOBS: tuple = ("*.md",)  # type: ignore[assignment]
    INDEXED_DIRS: tuple = ()
    VENV_PY = None  # type: ignore[assignment]

# Prefer project-local embeddings.py; fall back to global (alongside this hook)
_local_embeddings = REPO / ".claude" / "tools" / "embeddings.py"
_global_embeddings = Path(__file__).resolve().parent.parent / "tools" / "embeddings.py"
EMBEDDINGS_PY: Path = _local_embeddings if _local_embeddings.exists() else _global_embeddings


def _detach_kwargs(platform: str) -> dict:
    """Popen kwargs that fully detach the background refresh from this process.

    start_new_session is POSIX-only; on Windows it is silently ignored and the
    child stays attached to the parent, so Windows needs creationflags instead.
    """
    if platform == "win32":
        detached = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        new_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        return {"creationflags": detached | new_group}
    return {"start_new_session": True}


def is_indexed(path: Path) -> bool:
    try:
        rel = path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return False

    parts = set(Path(rel).parts)
    if bool(parts & EXCLUDED_DIR_NAMES):
        return False
    if any(rel.startswith(p) for p in EXCLUDED_DIR_PREFIXES):
        return False

    if "/" not in rel:
        return any(fnmatch.fnmatch(rel, g) for g in INDEXED_ROOT_GLOBS)
    if any(rel.startswith(d) for d in INDEXED_DIRS):
        return rel.endswith((".py", ".sql"))
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool_name = payload.get("tool_name")
    if tool_name not in ("Edit", "Write"):
        return 0
    file_path = payload.get("tool_input", {}).get("file_path", "")
    if not file_path:
        return 0
    if not is_indexed(Path(file_path)):
        return 0
    if VENV_PY is None or not VENV_PY.exists():
        return 0

    try:
        from search_config import active_state_dir as _asd
        _state_dir = _asd()
    except Exception:
        _state_dir = REPO / ".claude" / "state"
    log = _state_dir / "index-refresh.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("ab") as f:
        subprocess.Popen(
            [str(VENV_PY), str(EMBEDDINGS_PY), "refresh"],
            cwd=REPO,
            stdout=f,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            **_detach_kwargs(sys.platform),
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

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

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "tools"))
from search_config import (  # noqa: E402
    EXCLUDED_DIR_PREFIXES as EXCLUDED_DIRS,
    INDEXED_SOURCE_DIRS as INDEXED_DIRS,
    VENV_PY,
)


def is_indexed(path: Path) -> bool:
    try:
        rel = path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return False
    if any(("/" + d) in ("/" + rel) or rel.startswith(d) for d in EXCLUDED_DIRS):
        return False
    if "/" not in rel:
        return rel.endswith(".md")
    if any(rel.startswith(d) for d in INDEXED_DIRS):
        return rel.endswith((".py", ".sql", ".md"))
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
    if not VENV_PY.exists():
        return 0

    log = REPO / ".claude" / "state" / "index-refresh.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("ab") as f:
        subprocess.Popen(
            [str(VENV_PY), "tools/embeddings.py", "refresh"],
            cwd=REPO,
            stdout=f,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Codex PostToolUse hook: re-embed indexed files after apply_patch/Edit/Write."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _resolve_repo() -> Path:
    if os.environ.get("LESS_TOKENS_REPO"):
        return Path(os.environ["LESS_TOKENS_REPO"]).resolve()
    curr = Path(__file__).resolve().parent
    for _ in range(6):
        if (curr / ".git").exists() or (curr / "AGENTS.md").exists():
            return curr
        curr = curr.parent
    return Path(__file__).resolve().parent.parent.parent.parent


REPO = _resolve_repo()
sys.path.insert(0, str(REPO / ".less_tokens" / "hooks"))
sys.path.insert(0, str(REPO / "agents" / "common" / "hooks"))
sys.path.insert(0, str(REPO / ".less_tokens" / "tools"))
sys.path.insert(0, str(REPO / ".claude" / "tools"))

from payload import normalize_codex  # noqa: E402
from index_refresh import check_index_refresh  # noqa: E402

try:
    from search_config import (  # noqa: E402
        active_state_dir,
        EXCLUDED_DIR_NAMES,
        EXCLUDED_DIR_PREFIXES,
        INDEXED_ROOT_GLOBS,
        INDEXED_SOURCE_DIRS,
        VENV_PY,
    )
    config = {
        "venv_py": REPO / ".less_tokens" / "bin" / "python",
        "excluded_prefixes": EXCLUDED_DIR_PREFIXES,
        "excluded_names": EXCLUDED_DIR_NAMES,
        "dirs": INDEXED_SOURCE_DIRS,
        "root_globs": INDEXED_ROOT_GLOBS,
        "tool_prefix": ".less_tokens/tools",
    }
    state_dir = active_state_dir()
except Exception:
    config = {}
    state_dir = REPO / ".less_tokens" / "state"

raw = json.loads(sys.stdin.read())
payload = normalize_codex(raw)
code, stdout, stderr = check_index_refresh(payload, repo=REPO, state_dir=state_dir, config=config)
if stdout:
    print(stdout)
if stderr:
    print(stderr, file=sys.stderr)
sys.exit(code)

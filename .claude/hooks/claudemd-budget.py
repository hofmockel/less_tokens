#!/usr/bin/env python3
"""PostToolUse hook: keep CLAUDE.md within its token budget.

Fires after Edit/Write/MultiEdit on a CLAUDE.md file. Exits 2 with a terse
nudge when the file is over CLAUDE_MD_TOKEN_BUDGET or contains stale
`path:line` references. Disabled when budget is 0.
install.py wires this into the host settings file.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


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

try:
    from search_config import CLAUDE_MD_TOKEN_BUDGET, CLAUDE_MD_OVERFLOW_DOC
    import claudemd_audit as cma
except Exception:
    CLAUDE_MD_TOKEN_BUDGET = 1200
    CLAUDE_MD_OVERFLOW_DOC = "DOCUMENTATION.md"
    cma = None


def _target(payload: dict) -> str:
    return payload.get("tool_input", {}).get("file_path", "")


def main() -> int:
    if CLAUDE_MD_TOKEN_BUDGET == 0 or cma is None:
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("tool_name", "") not in {"Edit", "Write", "MultiEdit"}:
        return 0
    fp = _target(payload)
    if not fp or Path(fp).name != "CLAUDE.md":
        return 0
    p = Path(fp)
    if not p.exists():
        return 0

    try:
        a = cma.audit(p, CLAUDE_MD_TOKEN_BUDGET)
    except Exception:
        return 0

    problems = []
    if a["over_budget"]:
        problems.append(
            f"CLAUDE.md ~{a['total_tokens']:,} tokens (budget {a['budget']:,}, "
            f"over by {a['total_tokens'] - a['budget']:,}). It is always-loaded — "
            f"move detail to {CLAUDE_MD_OVERFLOW_DOC} (indexed). Run the claudemd skill."
        )
    if a["dead_refs"]:
        refs = ", ".join(f"L{r['line']}:{r['ref']}" for r in a["dead_refs"][:5])
        problems.append(f"stale refs in CLAUDE.md: {refs} — fix or drop (prefer symbol names over line numbers).")
    if problems:
        print(" ".join(problems), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

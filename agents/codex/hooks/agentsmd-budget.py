#!/usr/bin/env python3
"""Codex PostToolUse hook: keep AGENTS.md within its token budget.

Fires after Edit/Write on an AGENTS.md file. Exits 2 with a terse nudge
when the file is over AGENTS_MD_TOKEN_BUDGET or contains stale `path:line`
references. Disabled when budget is 0.
install.py wires this into .codex/hooks.json.
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
    for _ in range(6):
        if (curr / ".git").exists() or (curr / "AGENTS.md").exists():
            return curr
        curr = curr.parent
    return Path(__file__).resolve().parent.parent.parent.parent


REPO = _resolve_repo()
sys.path.insert(0, str(REPO / ".less_tokens" / "tools"))
sys.path.insert(0, str(REPO / ".claude" / "tools"))

try:
    from search_config import AGENTS_MD_TOKEN_BUDGET, AGENTS_MD_OVERFLOW_DOC
    import claudemd_audit as cma
except Exception:
    AGENTS_MD_TOKEN_BUDGET = 1200
    AGENTS_MD_OVERFLOW_DOC = "documentation.md"
    cma = None


def main() -> int:
    if AGENTS_MD_TOKEN_BUDGET == 0 or cma is None:
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("tool_name", "") not in {"Edit", "Write"}:
        return 0
    fp = payload.get("tool_input", {}).get("file_path", "")
    if not fp or Path(fp).name != "AGENTS.md":
        return 0
    p = Path(fp)
    if not p.exists():
        return 0

    try:
        a = cma.audit(p, AGENTS_MD_TOKEN_BUDGET)
    except Exception:
        return 0

    problems = []
    if a["over_budget"]:
        problems.append(
            f"AGENTS.md ~{a['total_tokens']:,} tokens (budget {a['budget']:,}, "
            f"over by {a['total_tokens'] - a['budget']:,}). It is always-loaded — "
            f"move detail to {AGENTS_MD_OVERFLOW_DOC} (indexed). Run the agentsmd skill."
        )
    if a["dead_refs"]:
        refs = ", ".join(f"L{r['line']}:{r['ref']}" for r in a["dead_refs"][:5])
        problems.append(f"stale refs in AGENTS.md: {refs} — fix or drop.")
    if problems:
        print(" ".join(problems), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

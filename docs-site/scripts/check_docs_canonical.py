#!/usr/bin/env python3
"""Check HTML docs keep root Markdown files as canonical operational docs."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SITE = REPO / "docs-site" / "site"
REQUIRED = {
    "README.md",
    "DOCUMENTATION.md",
    "agents/common/hooks/hook_manifest.py",
    "agents/common/hooks/parity.json",
}


def main() -> int:
    if not SITE.exists():
        print("docs-site/site missing; run build_docs.py first", file=sys.stderr)
        return 1
    text = "\n".join(path.read_text(encoding="utf-8") for path in SITE.rglob("*.html"))
    missing = [path for path in REQUIRED if path not in text]
    if missing:
        print("missing canonical source links: " + ", ".join(missing), file=sys.stderr)
        return 1
    forbidden = [".less_tokens/state/events.jsonl", ".claude/state/savings.jsonl"]
    leaked = [item for item in forbidden if item in text and "never published" not in text and "written under" not in text]
    if leaked:
        print("possible raw telemetry publication: " + ", ".join(leaked), file=sys.stderr)
        return 1
    print("canonical docs ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

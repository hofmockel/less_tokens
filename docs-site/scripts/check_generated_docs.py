#!/usr/bin/env python3
"""Verify generated docs-site files match source registries."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "docs-site" / "scripts"))

import build_docs  # noqa: E402


def main() -> int:
    code = build_docs.build(check=True)
    if code == 0:
        print("generated docs ok")
    return code


if __name__ == "__main__":
    raise SystemExit(main())

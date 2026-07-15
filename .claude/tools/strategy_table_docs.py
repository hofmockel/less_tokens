#!/usr/bin/env python3
"""Render README.md's strategy table from strategy_registry.STRATEGIES."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from strategy_registry import STRATEGIES  # noqa: E402

README = REPO / "README.md"
BEGIN = "<!-- strategy-table: begin -->"
END = "<!-- strategy-table: end -->"


def render() -> str:
    lines = [
        BEGIN,
        "| Strategy | How | Savings | Flag |",
        "|---|---|---|---|",
    ]
    for row in STRATEGIES:
        lines.append(f"| **{row.name}** | {row.how} | {row.savings} | {row.flag} |")
    lines.append(END)
    return "\n".join(lines)


def _replace_block(text: str, block: str) -> str:
    pattern = rf"{re.escape(BEGIN)}.*?{re.escape(END)}"
    if not re.search(pattern, text, flags=re.DOTALL):
        raise ValueError("missing strategy table markers")
    return re.sub(pattern, block, text, flags=re.DOTALL)


def update_docs(*, check: bool) -> int:
    block = render()
    text = README.read_text(encoding="utf-8")
    updated = _replace_block(text, block)
    if updated == text:
        if not check:
            print(f"{README.relative_to(REPO)} already up to date")
        return 0
    if check:
        print(f"{README.relative_to(REPO)} is out of date", file=sys.stderr)
        return 1
    README.write_text(updated, encoding="utf-8")
    print(f"updated {README.relative_to(REPO)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    return update_docs(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())

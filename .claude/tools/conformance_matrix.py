#!/usr/bin/env python3
"""Render README.md's/DOCUMENTATION.md's conformance-matrix table from HP1's
workload catalog (agents/common/conformance/workloads.py) and its evidence
store (agents/common/conformance/matrix.json).

Mirrors hook_parity_docs.py's render()/update_docs() shape, but a new file
rather than a fork of it: the schema here is workload x agent x release with
four evidence booleans plus a basis label, not hook_parity_docs.py's binary
hook x agent shipped/missing shape.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from agents.common.conformance.workloads import WORKLOADS  # noqa: E402

MATRIX = REPO / "agents" / "common" / "conformance" / "matrix.json"
DOCS = (REPO / "README.md", REPO / "DOCUMENTATION.md")
BEGIN = "<!-- conformance-matrix: begin -->"
END = "<!-- conformance-matrix: end -->"

# Agent + release cells checked for each workload. Claude has no version
# string exposed the way `codex --version` does, so its release is a capture
# date; Codex uses the X.Y.Z form already used under `codex-hooks/`.
CELLS: tuple[tuple[str, str], ...] = (
    ("claude", "2026-07-21"),
    ("codex", "0.144.6"),
)


def _bool(value: bool) -> str:
    return "yes" if value else "no"


def _row(workload_slug: str, agent: str, release: str, entry: dict) -> str:
    key = f"{workload_slug}:{agent}:{release}"
    if entry.get("status") == "not_yet_measured":
        return f"| `{key}` | — | — | — | — | not_yet_measured | — |"
    return (
        f"| `{key}` | {_bool(entry['code_present'])} | {_bool(entry['configured'])} | "
        f"{_bool(entry['event_fired'])} | {_bool(entry['action_enforced'])} | "
        f"{entry['basis']} | [{entry['fixture']}]({entry['fixture']}) |"
    )


def render() -> str:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    lines = [
        BEGIN,
        "",
        "Every cell below is either a live-captured, agent+release-tagged workload " +
        "measurement or an explicit `not_yet_measured` gap — never a guessed number. " +
        "`code_present`/`configured`/`event_fired`/`action_enforced` are reported " +
        "separately so shipped-but-unwired and wired-but-unenforced are never " +
        "conflated with fully proven. See each fixture for method and caveats.",
        "",
        "| Workload:agent:release | Code present | Configured | Event fired | Action enforced | Basis | Fixture |",
        "|---|---|---|---|---|---|---|",
    ]
    for workload in WORKLOADS:
        for agent, release in CELLS:
            key = f"{workload.slug}:{agent}:{release}"
            entry = matrix.get(key)
            if entry is None:
                lines.append(f"| `{key}` | — | — | — | — | missing from matrix.json | — |")
                continue
            lines.append(_row(workload.slug, agent, release, entry))
    lines.extend(["", END])
    return "\n".join(lines)


def _replace_block(text: str, block: str) -> str:
    pattern = rf"{re.escape(BEGIN)}.*?{re.escape(END)}"
    if not re.search(pattern, text, flags=re.DOTALL):
        raise ValueError("missing conformance-matrix markers")
    return re.sub(pattern, block, text, flags=re.DOTALL)


def update_docs(*, check: bool) -> int:
    block = render()
    dirty: list[Path] = []
    for path in DOCS:
        text = path.read_text(encoding="utf-8")
        updated = _replace_block(text, block)
        if updated != text:
            dirty.append(path)
            if not check:
                path.write_text(updated, encoding="utf-8")

    if dirty and check:
        for path in dirty:
            print(f"{path.relative_to(REPO)} is out of date", file=sys.stderr)
        return 1
    if not check:
        for path in dirty:
            print(f"updated {path.relative_to(REPO)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    return update_docs(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())

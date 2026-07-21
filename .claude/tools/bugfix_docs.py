#!/usr/bin/env python3
"""Render agents/common/bugfix-protocol.md's data-bearing blocks.

Two sources, mirroring bug_hunt_docs.py's split:
- `protocol_mode.MODE_HEURISTIC` -> the "mode-detection" block. Shared verbatim with
  bug_hunt_docs.py so bug-hunt-protocol.md and bugfix-protocol.md can never disagree
  on what "docs mode" vs "code mode" means (see protocol_mode.py's docstring).
- `bugfix_registry` -> severity-rubric/verification-commands/commit-template. These
  are less_tokens' own CODE-MODE defaults for THIS repo, not generic across targets
  — there's no equivalent registry for docs-mode targets (see bugfix_registry.py's
  docstring), so the docs-mode section of the protocol doc is hand-authored prose,
  not rendered here.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bugfix_registry import (  # noqa: E402
    COMMIT_MESSAGE_TEMPLATE,
    REGRESSION_TEST_DIR,
    REGRESSION_TEST_NAMING,
    SEVERITY_TIERS,
    VERIFICATION_COMMANDS,
)
from protocol_mode import MODE_HEURISTIC  # noqa: E402

PROTOCOL = REPO / "agents" / "common" / "bugfix-protocol.md"

BLOCKS = {
    "mode-detection": (
        "<!-- mode-detection: begin -->",
        "<!-- mode-detection: end -->",
    ),
    "severity-rubric": (
        "<!-- severity-rubric: begin -->",
        "<!-- severity-rubric: end -->",
    ),
    "verification-commands": (
        "<!-- verification-commands: begin -->",
        "<!-- verification-commands: end -->",
    ),
    "commit-template": (
        "<!-- commit-template: begin -->",
        "<!-- commit-template: end -->",
    ),
}


def _render_mode_detection() -> str:
    begin, end = BLOCKS["mode-detection"]
    return "\n".join([begin, MODE_HEURISTIC.rstrip("\n"), end])


def _render_severity_rubric() -> str:
    begin, end = BLOCKS["severity-rubric"]
    lines = [begin, "| Tier | Definition | Example |", "|---|---|---|"]
    for tier in SEVERITY_TIERS:
        lines.append(f"| **{tier.label}** | {tier.definition} | {tier.example} |")
    lines.append(end)
    return "\n".join(lines)


def _render_verification_commands() -> str:
    begin, end = BLOCKS["verification-commands"]
    lines = [
        begin,
        f"Regression test convention: `{REGRESSION_TEST_NAMING}` in `{REGRESSION_TEST_DIR}`.",
        "",
        "Run in order after the minimal fix, before changelog/backlog/commit:",
        "",
    ]
    for i, vc in enumerate(VERIFICATION_COMMANDS, start=1):
        lines.append(f"{i}. **{vc.label}** — `{vc.command}`")
    lines.append(end)
    return "\n".join(lines)


def _render_commit_template() -> str:
    begin, end = BLOCKS["commit-template"]
    return "\n".join([begin, "```", COMMIT_MESSAGE_TEMPLATE, "```", end])


RENDERERS = {
    "mode-detection": _render_mode_detection,
    "severity-rubric": _render_severity_rubric,
    "verification-commands": _render_verification_commands,
    "commit-template": _render_commit_template,
}


def _replace_block(text: str, name: str, block: str) -> str:
    begin, end = BLOCKS[name]
    pattern = rf"{re.escape(begin)}.*?{re.escape(end)}"
    if not re.search(pattern, text, flags=re.DOTALL):
        raise ValueError(f"missing markers for block {name!r}")
    return re.sub(pattern, block, text, flags=re.DOTALL)


def update_docs(*, check: bool) -> int:
    text = PROTOCOL.read_text(encoding="utf-8")
    updated = text
    for name, render in RENDERERS.items():
        updated = _replace_block(updated, name, render())

    if updated == text:
        if not check:
            print(f"{PROTOCOL.relative_to(REPO)} already up to date")
        return 0
    if check:
        print(f"{PROTOCOL.relative_to(REPO)} is out of date", file=sys.stderr)
        return 1
    PROTOCOL.write_text(updated, encoding="utf-8")
    print(f"updated {PROTOCOL.relative_to(REPO)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    return update_docs(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())

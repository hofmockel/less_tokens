#!/usr/bin/env python3
"""Render agents/common/bug-hunt-protocol.md's data-bearing blocks from bug_hunt_registry."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bug_hunt_registry import (  # noqa: E402
    COVERAGE_THRESHOLD,
    OVERLAP_THRESHOLD,
    PROMPT_TEMPLATE,
    SEVERITY_TIERS,
    TARGET_FILES,
)

PROTOCOL = REPO / "agents" / "common" / "bug-hunt-protocol.md"

BLOCKS = {
    "severity-rubric": (
        "<!-- severity-rubric: begin -->",
        "<!-- severity-rubric: end -->",
    ),
    "target-files": ("<!-- target-files: begin -->", "<!-- target-files: end -->"),
    "thresholds": ("<!-- thresholds: begin -->", "<!-- thresholds: end -->"),
    "prompt-template": (
        "<!-- prompt-template: begin -->",
        "<!-- prompt-template: end -->",
    ),
}


def _render_severity_rubric() -> str:
    begin, end = BLOCKS["severity-rubric"]
    lines = [begin, "| Tier | Definition | Example |", "|---|---|---|"]
    for tier in SEVERITY_TIERS:
        lines.append(f"| **{tier.label}** | {tier.definition} | {tier.example} |")
    lines.append(end)
    return "\n".join(lines)


def _render_target_files() -> str:
    begin, end = BLOCKS["target-files"]
    files = ", ".join(f"`{name}`" for name in sorted(TARGET_FILES))
    lines = [begin, f"{files} ({len(TARGET_FILES)} files).", end]
    return "\n".join(lines)


def _render_thresholds() -> str:
    begin, end = BLOCKS["thresholds"]
    lines = [
        begin,
        f"2. **Overlap** — of bugs surfaced, how many match a prior-round bug by file:line or "
        f'paraphrase? Record as `{{"matched": N, "total": N}}`. Passes at >= {OVERLAP_THRESHOLD:.0%}.',
        f"3. **File coverage** — list new files hit in `new_files`; scorer accumulates across all "
        f"rounds vs the target file list. Passes at >= {COVERAGE_THRESHOLD:.0%}.",
        end,
    ]
    return "\n".join(lines)


def _render_prompt_template() -> str:
    begin, end = BLOCKS["prompt-template"]
    return "\n".join([begin, "```", PROMPT_TEMPLATE, "```", end])


RENDERERS = {
    "severity-rubric": _render_severity_rubric,
    "target-files": _render_target_files,
    "thresholds": _render_thresholds,
    "prompt-template": _render_prompt_template,
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

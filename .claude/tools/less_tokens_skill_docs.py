#!/usr/bin/env python3
"""Render Claude and Codex less-tokens skills from a shared template."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from string import Template

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "agents" / "common" / "skills" / "less-tokens"
TEMPLATE = SOURCE / "SKILL.md.template"


@dataclass(frozen=True)
class Overlay:
    target: Path
    description: str
    runtime_path: str
    instruction_doc: str
    command_prefix: str
    audit_command: str
    state_path: str
    digest_constraints: str
    reminder_hook: str
    delegation_file: str


OVERLAYS = {
    "claude": Overlay(
        target=REPO / "agents" / "claude" / "skills" / "less-tokens" / "SKILL.md",
        description=(
            "Token-efficient codebase exploration for Claude. Use to search the codebase, "
            "look up a symbol, check a file before reading, audit CLAUDE.md size, or decide "
            "whether to spawn a subagent."
        ),
        runtime_path=".claude/tools/",
        instruction_doc="CLAUDE.md",
        command_prefix=".claude/.venv-tokens/bin/python .claude/tools",
        audit_command=(
            ".claude/.venv-tokens/bin/python .claude/tools/claudemd_audit.py"
        ),
        state_path=".claude/state",
        digest_constraints="parent must not read the source first.",
        reminder_hook="caveman-reminder.py",
        delegation_file="claude-delegation.md",
    ),
    "codex": Overlay(
        target=REPO / "agents" / "codex" / "skills" / "less-tokens" / "SKILL.md",
        description=(
            "Token-efficient codebase exploration for Codex. Use to search the codebase, "
            "look up a symbol, check a file before reading, or audit AGENTS.md size."
        ),
        runtime_path=".less_tokens/",
        instruction_doc="AGENTS.md",
        command_prefix=".less_tokens/bin/python .less_tokens/tools",
        audit_command=".less_tokens/bin/python .less_tokens/tools/agentsmd_audit.py",
        state_path=".less_tokens/state",
        digest_constraints="fork_context=false; parent must not read the source first.",
        reminder_hook="terse-reminder.py",
        delegation_file="codex-delegation.md",
    ),
}


def render(agent: str) -> str:
    overlay = OVERLAYS[agent]
    values = {
        field: getattr(overlay, field)
        for field in (
            "description",
            "runtime_path",
            "instruction_doc",
            "command_prefix",
            "audit_command",
            "state_path",
            "digest_constraints",
            "reminder_hook",
        )
    }
    values["delegation"] = (
        (SOURCE / overlay.delegation_file).read_text(encoding="utf-8").rstrip("\n")
    )
    return Template(TEMPLATE.read_text(encoding="utf-8")).substitute(values)


def update_skills(*, check: bool) -> int:
    dirty: list[Path] = []
    for agent, overlay in OVERLAYS.items():
        rendered = render(agent)
        current = overlay.target.read_text(encoding="utf-8")
        if rendered == current:
            continue
        dirty.append(overlay.target)
        if not check:
            overlay.target.write_text(rendered, encoding="utf-8")

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
    return update_skills(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())

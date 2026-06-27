#!/usr/bin/env python3
"""Generate docs parity tables from the shared hook manifest."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from agents.common.hooks.hook_manifest import HOOK_SPECS, HookSpec, HookWire  # noqa: E402

PARITY = REPO / "agents" / "common" / "hooks" / "parity.json"
DOCS = (REPO / "README.md", REPO / "DOCUMENTATION.md")
BEGIN = "<!-- hook-parity: begin -->"
END = "<!-- hook-parity: end -->"


def _status(value: str) -> str:
    return "shipped" if value == "shipped" else "missing"


def _feature_parity(claude: str, codex: str) -> str:
    if claude == "shipped" and codex == "shipped":
        return "yes"
    if claude == "shipped":
        return "Claude only"
    if codex == "shipped":
        return "Codex only"
    return "missing"


def _wires(wires: tuple[HookWire, ...]) -> str:
    if not wires:
        return ""
    return ", ".join(
        f"{wire.event} `{wire.matcher or '*'}`" for wire in wires
    )


def _agent_cell(agent: str, spec: HookSpec, status: str) -> str:
    if status != "shipped":
        return "missing"
    script = spec.claude_script if agent == "claude" else spec.codex_script
    wires = spec.claude if agent == "claude" else spec.codex
    strength = "enforced" if agent == "claude" else "best-effort"
    hook_dir = ".claude/hooks" if agent == "claude" else ".codex/hooks"
    detail = _wires(wires)
    return f"{strength}; `{hook_dir}/{script}`; {detail}"


def render() -> str:
    parity = json.loads(PARITY.read_text(encoding="utf-8"))
    lines = [
        BEGIN,
        "",
        "Feature parity means the same strategy is shipped for both agents. "
        "Enforcement parity is intentionally different: Claude hooks are direct "
        "enforcement, while Codex hooks are best-effort adapters through "
        "`.codex/hooks.json`.",
        "",
        "| Strategy | Feature parity | Claude enforcement | Codex enforcement |",
        "|---|---|---|---|",
    ]
    for spec in HOOK_SPECS:
        row = parity[spec.name]
        claude = _status(row.get("claude", "missing"))
        codex = _status(row.get("codex", "missing"))
        feature = _feature_parity(claude, codex)
        if row.get("optional"):
            feature += "; default-on optional"
        lines.append(
            f"| `{spec.name}` | {feature} | "
            f"{_agent_cell('claude', spec, claude)} | "
            f"{_agent_cell('codex', spec, codex)} |"
        )
    lines.extend(["", END])
    return "\n".join(lines)


def _replace_block(text: str, block: str) -> str:
    pattern = rf"{re.escape(BEGIN)}.*?{re.escape(END)}"
    if not re.search(pattern, text, flags=re.DOTALL):
        raise ValueError("missing hook parity markers")
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

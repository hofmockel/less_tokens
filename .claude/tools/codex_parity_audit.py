#!/usr/bin/env python3
"""Audit Codex hook wiring against the shared less_tokens hook manifest."""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from agents.common.hooks.hook_manifest import HOOK_SPECS  # noqa: E402


@dataclass(frozen=True)
class AuditRow:
    strategy: str
    feature: str
    enforcement: str
    notes: str


def _load_hooks(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [], "missing .codex/hooks.json"
    except (OSError, json.JSONDecodeError) as exc:
        return [], f"unreadable .codex/hooks.json: {exc}"
    hooks = data.get("hooks")
    if not isinstance(hooks, list):
        return [], ".codex/hooks.json has no list-valued hooks key"
    return [h for h in hooks if isinstance(h, dict)], None


def _is_writable(path: Path) -> bool:
    target = path if path.exists() else path.parent
    return target.exists() and os.access(target, os.W_OK)


def _script_in_command(command: str, script: str) -> bool:
    normalized = command.replace("\\", "/")
    return normalized.endswith(f".codex/hooks/{script}") or f".codex/hooks/{script}" in normalized


def _has_hook(hooks: list[dict[str, Any]], *, event: str, matcher: str, script: str) -> bool:
    for hook in hooks:
        if hook.get("event") != event or hook.get("matcher", "") != matcher:
            continue
        if _script_in_command(str(hook.get("command", "")), script):
            return True
    return False


def audit(root: Path) -> tuple[list[AuditRow], list[str]]:
    root = root.resolve()
    hooks_json = root / ".codex" / "hooks.json"
    hooks, hooks_error = _load_hooks(hooks_json)
    problems: list[str] = []
    if hooks_error:
        problems.append(hooks_error)
    if not _is_writable(hooks_json):
        problems.append(".codex/hooks.json or parent directory is not writable")

    rows: list[AuditRow] = []
    for spec in HOOK_SPECS:
        feature = "feature-parity" if spec.claude and spec.codex else "missing-feature-parity"
        if not spec.codex or not spec.codex_script:
            rows.append(AuditRow(spec.name, feature, "missing", "no Codex adapter in manifest"))
            continue

        script_path = root / ".codex" / "hooks" / spec.codex_script
        missing = [
            f"{wire.event}:{wire.matcher or '<empty>'}"
            for wire in spec.codex
            if not _has_hook(hooks, event=wire.event, matcher=wire.matcher, script=spec.codex_script)
        ]
        notes: list[str] = []
        if not script_path.exists():
            notes.append(f"missing script {script_path.relative_to(root).as_posix()}")
        if missing:
            notes.append("missing matcher(s): " + ", ".join(missing))
        if hooks_error:
            notes.append("hook file unavailable")

        enforcement = "best-effort-only"
        if missing or not script_path.exists() or hooks_error:
            enforcement = "unwired"
            problems.append(f"{spec.name}: {'; '.join(notes) or 'unwired'}")
        rows.append(AuditRow(spec.name, feature, enforcement, "; ".join(notes) or "adapter wired; Codex hook delivery can still fail open"))
    return rows, problems


def _text_report(root: Path, rows: list[AuditRow], problems: list[str]) -> str:
    lines = [
        "Codex enforcement parity audit",
        f"root: {root.resolve()}",
        "",
        "strategy | feature | enforcement | notes",
        "---|---|---|---",
    ]
    for row in rows:
        lines.append(f"{row.strategy} | {row.feature} | {row.enforcement} | {row.notes}")
    if problems:
        lines.extend(["", "Problems:"])
        lines.extend(f"- {p}" for p in problems)
    else:
        lines.extend(["", "Problems: none"])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    rows, problems = audit(args.root)
    if args.json:
        print(json.dumps({
            "root": str(args.root.resolve()),
            "rows": [asdict(row) for row in rows],
            "problems": problems,
        }, indent=2))
    else:
        print(_text_report(args.root, rows, problems), end="")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Audit Codex hook wiring against the shared less_tokens hook manifest."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shlex
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any


@dataclass(frozen=True)
class AuditRow:
    strategy: str
    feature: str
    enforcement: str
    notes: str


# Codex's `Stop` hook is schema-defined but never fires in headless `codex
# exec` (DECISIONS.md CX18); these three adapters have no viable Stop-based
# wiring today and their missing-command status is an accepted, indefinite
# platform limitation, not a regression to gate CI on. Still reported as
# "unwired" in the row output — only suppressed from the blocking `problems`
# list, and only for the exact missing-command gap CX18 describes (a missing
# script or stale/unreadable hooks.json for these specs is still a real bug).
ACCEPTED_UNWIRED = {"compact-trigger", "terse-output", "savings-html"}


def _load_hooks(
    path: Path, manifest: ModuleType
) -> tuple[list[dict[str, Any]], str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [], "missing .codex/hooks.json"
    except (OSError, json.JSONDecodeError) as exc:
        return [], f"unreadable .codex/hooks.json: {exc}"
    raw_hooks = data.get("hooks")
    hooks, well_formed = manifest.flatten_codex_hooks(raw_hooks)
    if not well_formed:
        return [], ".codex/hooks.json hooks value is malformed or unsupported"
    if manifest.codex_hooks_schema(raw_hooks) != "event-keyed":
        return (
            [],
            ".codex/hooks.json uses the retired nested schema; run install.py --update",
        )
    return hooks, None


def _is_writable(path: Path) -> bool:
    target = path if path.exists() else path.parent
    return target.exists() and os.access(target, os.W_OK)


def _script_in_command(command: str, script: str) -> bool:
    normalized = command.replace("\\", "/")
    return (
        normalized.endswith(f".codex/hooks/{script}")
        or f".codex/hooks/{script}" in normalized
    )


def _load_manifest(root: Path) -> ModuleType:
    candidates = (
        root / "agents" / "common" / "hooks" / "hook_manifest.py",
        root / ".less_tokens" / "hooks" / "hook_manifest.py",
        root / ".claude" / "hooks" / "common" / "hook_manifest.py",
    )
    path = next((candidate for candidate in candidates if candidate.exists()), None)
    if path is None:
        raise FileNotFoundError("installed hook_manifest.py is missing")
    name = f"_less_tokens_hook_manifest_{abs(hash(path))}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _expected_entries(
    root: Path, hooks: list[dict[str, Any]], manifest: ModuleType
) -> list[tuple[str, str, str]]:
    aggressive = any(
        "LESS_TOKENS_CODEX_SAVINGS=aggressive" in str(hook.get("command", ""))
        for hook in hooks
    )
    launcher = root / ".less_tokens" / "bin" / "python"
    if os.name == "nt":
        launcher = launcher.with_suffix(".cmd")
    args = SimpleNamespace(no_truncate=False, no_compact=False, no_caveman=False)
    return manifest.build_codex_hook_entries(
        launcher.resolve().as_posix(),
        root,
        args,
        savings_profile="aggressive" if aggressive else "balanced",
    )


def _matching_hooks(
    hooks: list[dict[str, Any]],
    *,
    event: str,
    matcher: str,
    script: str,
) -> list[dict[str, Any]]:
    return [
        hook
        for hook in hooks
        if hook.get("event") == event
        and hook.get("matcher", "") == matcher
        and _script_in_command(str(hook.get("command", "")), script)
    ]


def _run_representative_from_nested_cwd(root: Path, command: str) -> str | None:
    if os.name == "nt":
        return None  # Codex hook env prefixes are POSIX shell syntax today.
    parts = shlex.split(command)
    env = os.environ.copy()
    while parts and "=" in parts[0] and parts[0].split("=", 1)[0].isidentifier():
        key, value = parts.pop(0).split("=", 1)
        env[key] = value
    if not parts:
        return "representative hook command is empty"
    nested_cwd = root / ".codex" / "hooks"
    try:
        result = subprocess.run(
            parts,
            cwd=nested_cwd,
            env=env,
            input='{"hook_event_name":"PreToolUse","tool_name":"noop","tool_input":{}}\n',
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"representative hook command failed from nested cwd: {exc}"
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "no output").strip()[-300:]
        return f"representative hook command failed from nested cwd (exit {result.returncode}): {detail}"
    return None


def audit(root: Path) -> tuple[list[AuditRow], list[str]]:
    root = root.resolve()
    hooks_json = root / ".codex" / "hooks.json"
    problems: list[str] = []

    try:
        manifest = _load_manifest(root)
    except (ImportError, OSError, AttributeError) as exc:
        problems.append(f"cannot derive expected Codex hook commands: {exc}")
        return [], problems

    hooks, hooks_error = _load_hooks(hooks_json, manifest)
    if hooks_error:
        problems.append(hooks_error)
    if not _is_writable(hooks_json):
        problems.append(".codex/hooks.json or parent directory is not writable")

    try:
        expected_entries = _expected_entries(root, hooks, manifest)
    except (ImportError, OSError, AttributeError) as exc:
        problems.append(f"cannot derive expected Codex hook commands: {exc}")
        return [], problems

    rows: list[AuditRow] = []
    representative_command: str | None = None
    for spec in manifest.HOOK_SPECS:
        feature = (
            "feature-parity" if spec.claude and spec.codex else "missing-feature-parity"
        )
        if not spec.codex or not spec.codex_script:
            candidate_script = spec.codex_script or spec.claude_script
            orphaned = [
                hook
                for hook in hooks
                if candidate_script
                and _script_in_command(str(hook.get("command", "")), candidate_script)
            ]
            if orphaned:
                note = f"no Codex adapter in manifest, but .codex/hooks.json still wires {candidate_script}"
                problems.append(f"{spec.name}: {note}")
                rows.append(AuditRow(spec.name, feature, "missing", note))
            else:
                rows.append(
                    AuditRow(
                        spec.name, feature, "missing", "no Codex adapter in manifest"
                    )
                )
            continue

        script_path = root / ".codex" / "hooks" / spec.codex_script
        expected_for_spec = [
            entry
            for entry in expected_entries
            if _script_in_command(entry[2], spec.codex_script)
        ]
        missing: list[str] = []
        stale: list[str] = []
        for event, matcher, expected_command in expected_for_spec:
            label = f"{event}:{matcher or '<empty>'}"
            matches = _matching_hooks(
                hooks,
                event=event,
                matcher=matcher,
                script=spec.codex_script,
            )
            if not any(
                str(hook.get("command", "")) == expected_command for hook in matches
            ):
                missing.append(label)
            if any(
                str(hook.get("command", "")) != expected_command for hook in matches
            ):
                stale.append(label)
            if spec.name == "search-first" and any(
                str(hook.get("command", "")) == expected_command for hook in matches
            ):
                representative_command = expected_command
        notes: list[str] = []
        if not script_path.exists():
            notes.append(f"missing script {script_path.relative_to(root).as_posix()}")
        if missing:
            notes.append("missing exact command(s): " + ", ".join(missing))
        if stale:
            notes.append("stale command(s): " + ", ".join(stale))
        if hooks_error:
            notes.append("hook file unavailable")

        enforcement = "best-effort-only"
        if missing or stale or not script_path.exists() or hooks_error:
            enforcement = "unwired"
            accepted = (
                spec.name in ACCEPTED_UNWIRED
                and missing
                and not stale
                and script_path.exists()
                and not hooks_error
            )
            if accepted:
                notes.append("accepted platform limitation, see DECISIONS.md CX18")
            else:
                problems.append(f"{spec.name}: {'; '.join(notes) or 'unwired'}")
        rows.append(
            AuditRow(
                spec.name,
                feature,
                enforcement,
                "; ".join(notes)
                or "adapter wired; Codex hook delivery can still fail open",
            )
        )

    if representative_command:
        command_problem = _run_representative_from_nested_cwd(
            root, representative_command
        )
        if command_problem:
            problems.append(command_problem)
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
        lines.append(
            f"{row.strategy} | {row.feature} | {row.enforcement} | {row.notes}"
        )
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
        print(
            json.dumps(
                {
                    "root": str(args.root.resolve()),
                    "rows": [asdict(row) for row in rows],
                    "problems": problems,
                },
                indent=2,
            )
        )
    else:
        print(_text_report(args.root, rows, problems), end="")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Shared adapter helpers for Codex hook wrappers."""
from __future__ import annotations

import json
import os
import re
import shlex
import sys
from datetime import datetime, timezone
from collections.abc import Callable
from pathlib import Path


_KNOWN_EVENTS = {
    "SessionStart",
    "SubagentStart",
    "PreToolUse",
    "PermissionRequest",
    "PostToolUse",
    "PreCompact",
    "PostCompact",
    "UserPromptSubmit",
    "SubagentStop",
    "Stop",
}
_TOOL_EVENTS = {"PreToolUse", "PermissionRequest", "PostToolUse"}
_SCHEMA_LOG_LIMIT = 64
_SCHEMA_FIELD_LIMIT = 32


def resolve_repo() -> Path:
    if os.environ.get("LESS_TOKENS_REPO"):
        return Path(os.environ["LESS_TOKENS_REPO"]).resolve()
    for start in (Path(__file__).resolve().parent, Path.cwd().resolve()):
        curr = start
        for _ in range(8):
            if (curr / ".git").exists() or (curr / "AGENTS.md").exists():
                return curr
            curr = curr.parent
    return Path(__file__).resolve().parent.parent.parent.parent


def bootstrap() -> Path:
    repo = resolve_repo()
    os.environ.setdefault("LESS_TOKENS_AGENT", "codex")
    sys.path[:0] = [
        str(repo),
        str(repo / "agents" / "common" / "hooks"),
        str(repo / ".less_tokens" / "hooks"),
        str(repo / ".less_tokens" / "tools"),
        str(repo / ".claude" / "tools"),
    ]
    return repo


def _state_dir() -> Path:
    configured = os.environ.get("LESS_TOKENS_STATE_DIR")
    return Path(configured) if configured else resolve_repo() / ".less_tokens" / "state"


def _type_name(value: object) -> str:
    if value is None:
        return "null"
    return type(value).__name__


def _record_schema_drift(raw: object, reason: str) -> None:
    """Record bounded schema metadata without retaining payload values."""
    try:
        fields = sorted(str(key)[:80] for key in raw)[:_SCHEMA_FIELD_LIMIT] if isinstance(raw, dict) else []
        record = {
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "payload_type": _type_name(raw),
            "fields": fields,
        }
        if isinstance(raw, dict):
            event = raw.get("hook_event_name")
            tool = raw.get("tool_name")
            record["event"] = str(event)[:80] if isinstance(event, str) else _type_name(event)
            record["tool"] = str(tool)[:80] if isinstance(tool, str) else _type_name(tool)
            record["field_types"] = {
                key: _type_name(raw[key]) for key in fields if key in raw
            }

        path = _state_dir() / "codex-hook-schema-drift.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        previous = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        encoded = json.dumps(record, sort_keys=True, separators=(",", ":"))
        path.write_text("\n".join([*previous[-(_SCHEMA_LOG_LIMIT - 1):], encoded]) + "\n", encoding="utf-8")
    except Exception as exc:
        try:
            print(f"[codex-runtime] failed to record schema drift: {exc}", file=sys.stderr)
        except Exception:
            return


def _schema_issue(raw: dict) -> str | None:
    event = raw.get("hook_event_name")
    if not isinstance(event, str) or not event:
        return "missing-or-invalid-hook-event"
    if event not in _KNOWN_EVENTS:
        return "unknown-hook-event"
    if event in _TOOL_EVENTS:
        if not isinstance(raw.get("tool_name"), str) or not raw.get("tool_name"):
            return "missing-or-invalid-tool-name"
        if not isinstance(raw.get("tool_input"), dict):
            return "missing-or-invalid-tool-input"
    if event == "PostToolUse" and "tool_response" not in raw and "tool_result" not in raw:
        return "missing-tool-response"
    return None


def load_json_stdin(*mappers: Callable[[dict], dict]) -> dict:
    try:
        raw = json.loads(sys.stdin.read() or "{}")
    except Exception:
        _record_schema_drift({}, "invalid-json")
        return {}
    if not isinstance(raw, dict):
        _record_schema_drift(raw, "non-object-payload")
        return {}
    issue = _schema_issue(raw)
    if issue:
        _record_schema_drift(raw, issue)
    for mapper in mappers:
        raw = mapper(raw)
    return raw


def print_result(code: int, stdout: str, stderr: str) -> int:
    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)
    return code


def pre_tool_deny(reason: str) -> str:
    """Return the current Codex PreToolUse structured deny contract."""
    return json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    })


def pre_tool_allow(updated_input: dict) -> str:
    """Return the current Codex PreToolUse structured rewrite contract."""
    return json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": updated_input,
        }
    })


def print_pre_tool_result(code: int, stdout: str, stderr: str) -> int:
    """Translate legacy hook outcomes to Codex's native PreToolUse contract."""
    if code == 2:
        print(pre_tool_deny(stderr or stdout or "Tool call denied by hook."))
        return 0
    return print_result(code, stdout, stderr)


def bash_slice_updated_input(
    tool_name: object,
    tool_input: object,
    *,
    start: int,
    limit: int,
) -> dict | None:
    """Safely rewrite an unambiguous whole-file Bash read to an exact slice."""
    if tool_name != "Bash" or not isinstance(tool_input, dict):
        return None
    command = tool_input.get("command")
    if not isinstance(command, str):
        return None
    parsed = _parse_bash_read(command)
    if parsed is None:
        return None
    file_path, offset = parsed
    if offset is not None or not file_path or file_path.startswith("-"):
        return None
    end = start + max(1, limit) - 1
    updated = dict(tool_input)
    updated["command"] = f"sed -n {shlex.quote(f'{start},{end}p')} {shlex.quote(file_path)}"
    return updated


# @modelcontextprotocol/server-filesystem renamed its read tool from
# read_file to read_text_file (confirmed live against v2026.7.10); accept
# both so an older pinned server version doesn't silently no-op these hooks.
FILESYSTEM_READ_TOOLS = ("mcp__filesystem__read_file", "mcp__filesystem__read_text_file")


def map_read(raw: dict) -> dict:
    if raw.get("tool_name") in FILESYSTEM_READ_TOOLS:
        inp = raw.setdefault("tool_input", {})
        raw["tool_name"] = "Read"
        inp["file_path"] = inp.get("path", "")
    return raw


def map_read_or_search(raw: dict) -> dict:
    tool = raw.get("tool_name", "")
    if tool in FILESYSTEM_READ_TOOLS:
        return map_read(raw)
    if tool.startswith("mcp__filesystem__") and "search" in tool:
        raw["tool_name"] = "Grep"
    return raw


# CX25: a default Codex install exposes no `mcp__filesystem__` server, so the
# 6 hooks gated on that matcher alone never fire — Bash is the only real
# default-install read path. Recognize a narrow, unambiguous set of
# single-file read shapes and rewrite them into the same synthetic Read shape
# `map_read` produces, so downstream hook logic (which only ever branches on
# tool_name=="Read" + tool_input file_path/offset) needs no changes.
#
# Deliberately conservative: any shell metacharacter (pipe, redirect, glob,
# substitution, chaining) bails out and leaves the call as plain Bash, so the
# 6 hooks silently no-op on it today. That is the same fail-open behavior an
# unrecognized command already gets — no regression, just an unclosed gap
# documented rather than guessed at (CX25 acceptance).
_BASH_READ_METACHARS = re.compile(r"[|&;<>`~*?{}\[\]]|\$\(")
_SED_PRINT_SCRIPT = re.compile(r"^(\d+)(?:,\d+)?p$")


def _parse_bash_read(command: str) -> tuple[str, int | None] | None:
    if _BASH_READ_METACHARS.search(command):
        return None
    try:
        parts = shlex.split(command)
    except ValueError:
        return None
    if not parts:
        return None
    name = Path(parts[0]).name
    args = parts[1:]

    if name == "cat":
        if len(args) == 1 and not args[0].startswith("-"):
            return args[0], None
        return None

    if name in ("head", "tail"):
        positionals: list[str] = []
        skip_next = False
        for arg in args:
            if skip_next:
                skip_next = False
                continue
            if arg == "-n":
                skip_next = True
                continue
            if arg.startswith("-n") or re.fullmatch(r"-\d+", arg):
                continue
            if arg.startswith("-"):
                return None  # e.g. tail -f, head -c: not a bounded read
            positionals.append(arg)
        if len(positionals) == 1:
            return positionals[0], 1  # partial read; exact offset unused by consumers
        return None

    if name == "sed":
        if "-n" not in args:
            return None
        rest = [a for a in args if a != "-n"]
        if len(rest) != 2:
            return None
        script, path = rest
        match = _SED_PRINT_SCRIPT.fullmatch(script)
        if not match:
            return None
        return path, int(match.group(1))

    return None


def map_bash_read(raw: dict) -> dict:
    if raw.get("tool_name") != "Bash":
        return raw
    command = (raw.get("tool_input") or {}).get("command", "")
    if not isinstance(command, str) or not command.strip():
        return raw
    parsed = _parse_bash_read(command)
    if parsed is None:
        return raw
    file_path, offset = parsed
    raw["tool_name"] = "Read"
    new_input: dict = {"file_path": file_path}
    if offset is not None:
        new_input["offset"] = offset
    raw["tool_input"] = new_input
    return raw

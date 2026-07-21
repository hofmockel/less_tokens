"""Single source of truth for less_tokens hook wiring."""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace


@dataclass(frozen=True)
class HookWire:
    event: str
    matcher: str


@dataclass(frozen=True)
class HookSpec:
    name: str
    optional_flag: str | None = None
    claude_script: str | None = None
    claude: tuple[HookWire, ...] = ()
    codex_script: str | None = None
    codex: tuple[HookWire, ...] = ()


HOOK_SPECS: tuple[HookSpec, ...] = (
    HookSpec(
        name="budget-observer",
        claude_script="budget-observer.py",
        claude=(
            HookWire("PreToolUse", "Read|Grep|Glob|Bash"),
            HookWire("PostToolUse", "Read|Grep|Glob|Bash|Edit|Write"),
        ),
        codex_script="budget-observer.py",
        codex=(
            HookWire("PreToolUse", "mcp__filesystem__.*|Bash"),
            HookWire("PostToolUse", "Bash|mcp__filesystem__.*|apply_patch|Edit|Write"),
        ),
    ),
    HookSpec(
        name="search-first",
        claude_script="search-first.py",
        claude=(HookWire("PreToolUse", "Read"), HookWire("PreToolUse", "Grep")),
        codex_script="search-first.py",
        codex=(HookWire("PreToolUse", "mcp__filesystem__.*|Bash"),),
    ),
    HookSpec(
        name="read-guard",
        claude_script="read-guard.py",
        claude=(HookWire("PreToolUse", "Read"),),
        codex_script="read-guard.py",
        codex=(HookWire("PreToolUse", "mcp__filesystem__.*|Bash"),),
    ),
    HookSpec(
        name="auto-slice",
        claude_script="auto-slice.py",
        claude=(HookWire("PreToolUse", "Read"),),
        codex_script="auto-slice.py",
        codex=(HookWire("PreToolUse", "mcp__filesystem__.*|Bash"),),
    ),
    HookSpec(
        name="grep-first-read",
        claude_script="grep-first-read.py",
        claude=(HookWire("PreToolUse", "Read"),),
        codex_script="grep-first-read.py",
        codex=(HookWire("PreToolUse", "mcp__filesystem__.*|Bash"),),
    ),
    HookSpec(
        name="read-after-edit",
        claude_script="read-after-edit.py",
        claude=(HookWire("PreToolUse", "Read"),),
        codex_script="read-after-edit.py",
        codex=(HookWire("PreToolUse", "mcp__filesystem__.*|Bash"),),
    ),
    # Blocks reads of a stale continue.md (recorded HEAD behind current HEAD)
    # until the drift is surfaced. This catches direct reads that bypass the
    # installed continue skill's own Phase 1 staleness check.
    HookSpec(
        name="continue-freshness",
        claude_script="continue-freshness.py",
        claude=(HookWire("PreToolUse", "Read"),),
        codex_script="continue-freshness.py",
        codex=(HookWire("PreToolUse", "mcp__filesystem__.*|Bash"),),
    ),
    HookSpec(
        name="context-cache",
        claude_script="context-cache.py",
        claude=(
            HookWire("PreToolUse", "Read|Grep"),
            HookWire("PostToolUse", "Read|Grep"),
        ),
        codex_script="context-cache.py",
        codex=(
            HookWire("PreToolUse", "mcp__filesystem__.*|Bash"),
            HookWire("PostToolUse", "Bash"),
            HookWire("PostToolUse", "mcp__filesystem__.*"),
        ),
    ),
    HookSpec(
        name="post-edit-diff",
        claude_script="post-edit-diff.py",
        claude=(HookWire("PostToolUse", "Edit|Write"),),
        codex_script="post-edit-diff.py",
        codex=(HookWire("PostToolUse", "apply_patch|Edit|Write"),),
    ),
    HookSpec(
        name="index-refresh",
        claude_script="index-refresh.py",
        claude=(HookWire("PostToolUse", "Edit|Write"),),
        codex_script="index-refresh.py",
        codex=(HookWire("PostToolUse", "apply_patch|Edit|Write"),),
    ),
    HookSpec(
        name="agent-md-budget",
        claude_script="claudemd-budget.py",
        claude=(HookWire("PostToolUse", "Edit|Write"),),
        codex_script="agentsmd-budget.py",
        codex=(HookWire("PostToolUse", "Edit|Write"),),
    ),
    HookSpec(
        name="lean-output",
        claude_script="lean-output.py",
        claude=(HookWire("PostToolUse", "Bash"),),
        codex_script="lean-output.py",
        codex=(HookWire("PostToolUse", "Bash"),),
    ),
    HookSpec(
        name="listing-guard",
        claude_script="listing-guard.py",
        claude=(HookWire("PreToolUse", "Bash"),),
        codex_script="listing-guard.py",
        codex=(HookWire("PreToolUse", "Bash"),),
    ),
    HookSpec(
        name="truncate-output",
        optional_flag="truncate",
        claude_script="truncate-output.py",
        claude=(HookWire("PostToolUse", "Bash|Read|WebFetch|Glob"),),
        # CX28: Codex 0.144.6 can add PostToolUse feedback, but exposes no
        # contract that replaces or suppresses the original tool result.
        # Keep known-noisy Codex calls bounded through CX27 PreToolUse gates.
    ),
    # Claude-only (G15/SA1): no Codex Task-boundary hook exists — Codex has no
    # subagent-spawn tool to cap a return from.
    HookSpec(
        name="subagent-cap",
        optional_flag="truncate",
        claude_script="subagent-cap.py",
        claude=(HookWire("PostToolUse", "Task"),),
    ),
    # Claude-only (SA2): no Codex Task-boundary hook exists, same reasoning as
    # subagent-cap above. Always wired (not gated by an optional flag) — this
    # is measurement only, no output mutation.
    HookSpec(
        name="subagent-fanout",
        claude_script="subagent-fanout.py",
        claude=(
            HookWire("PreToolUse", "Task"),
            HookWire("PostToolUse", "Task"),
        ),
    ),
    HookSpec(
        name="compact-trigger",
        optional_flag="compact",
        claude_script="compact-trigger.py",
        claude=(HookWire("PostToolUse", ".*"),),
        codex_script="compact-trigger.py",
        codex=(
            HookWire("PreCompact", "manual|auto"),
            HookWire("PostCompact", "manual|auto"),
        ),
    ),
    HookSpec(
        name="subagent-guidance",
        codex_script="subagent-guidance.py",
        codex=(HookWire("SubagentStart", ""),),
    ),
    HookSpec(
        name="terse-output",
        optional_flag="caveman",
        claude_script="caveman-reminder.py",
        # SubagentStop (G15): a Claude child's final turn fires SubagentStop, not
        # Stop. Both wires point at the same script — it reads transcript_path/
        # stop_hook_active off stdin and never inspects hook_event_name, so it
        # behaves identically for a subagent's own transcript.
        claude=(HookWire("Stop", ""), HookWire("SubagentStop", "")),
        codex_script="terse-reminder.py",
        codex=(HookWire("Stop", ""), HookWire("SubagentStop", "")),
    ),
    # Regenerates state/savings.html at real assistant/subagent stop boundaries
    # on both platforms. Codex output must use the event's JSON response shape.
    HookSpec(
        name="savings-html",
        claude_script="savings-html.py",
        # SubagentStop (G15): same reasoning as terse-output above.
        claude=(HookWire("Stop", ""), HookWire("SubagentStop", "")),
        codex_script="savings-html.py",
        codex=(HookWire("Stop", ""), HookWire("SubagentStop", "")),
    ),
)


def _optional_enabled(agent: str, optional_flag: str, args: object) -> bool:
    """Decide whether an optional savings hook is wired (CL2/CX2).

    Claude and Codex installs wire these by default; ``--no-<flag>`` opts out.
    The explicit ``--<flag>`` remains accepted for back-compat and now matches
    the default set.
    """
    if bool(getattr(args, f"no_{optional_flag}", False)):
        return False
    if agent in {"claude", "codex"}:
        return True
    return bool(getattr(args, optional_flag, False))


def hook_entries(agent: str, py_command: str, args: object) -> list[tuple[str, str, str]]:
    if agent not in {"claude", "codex"}:
        raise ValueError(f"unsupported hook agent: {agent}")

    entries: list[tuple[str, str, str]] = []
    for spec in HOOK_SPECS:
        if spec.optional_flag and not _optional_enabled(agent, spec.optional_flag, args):
            continue
        script = spec.claude_script if agent == "claude" else spec.codex_script
        wires = spec.claude if agent == "claude" else spec.codex
        if not script or not wires:
            continue
        hook_dir = ".claude/hooks" if agent == "claude" else ".codex/hooks"
        command = f"{py_command} {Path(hook_dir) / script}"
        entries.extend((wire.event, wire.matcher, command) for wire in wires)
    return entries


def build_codex_hook_entries(
    py_command: str,
    target_root: Path,
    args: object,
    savings_profile: str = "balanced",
) -> list[tuple[str, str, str]]:
    """Build the exact cwd-independent commands written to Codex hooks.json."""
    env = "LESS_TOKENS_AGENT=codex"
    effective_args = args
    if savings_profile == "aggressive":
        env = f"{env} LESS_TOKENS_CODEX_SAVINGS=aggressive"
        effective_args = SimpleNamespace(**{
            **vars(args),
            "no_truncate": False,
            "no_compact": False,
            "no_caveman": False,
        })

    prefix = f"{env} {shlex.quote(py_command)}"
    entries = hook_entries("codex", prefix, effective_args)
    rewritten = []
    for event, matcher, command in entries:
        prefix_part, script = command.rsplit(" ", 1)
        normalized_script = script.replace("\\", "/")
        if normalized_script.startswith(".codex/hooks/"):
            script = shlex.quote(str((target_root / normalized_script).resolve()))
        rewritten.append((event, matcher, f"{prefix_part} {script}"))
    return rewritten


CODEX_HOOK_CONTRACT_MIN = (0, 142, 3)
CODEX_HOOK_CONTRACT_MAX = (0, 144, 6)
CODEX_HOOK_CONTRACT_RANGE = "0.142.3–0.144.6"


def parse_codex_version(output: str) -> tuple[int, int, int] | None:
    """Return the first release triple from `codex --version` output."""
    match = re.search(r"(?<!\d)(\d+)\.(\d+)\.(\d+)(?!\d)", output)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def codex_hook_contract_supports(version: tuple[int, int, int]) -> bool:
    """Whether *version* is inside the release window verified for CX26."""
    return CODEX_HOOK_CONTRACT_MIN <= version <= CODEX_HOOK_CONTRACT_MAX


def _flat_codex_handler(event: str, group: dict, handler: dict) -> dict:
    """Normalize one handler while retaining unrelated valid metadata."""
    flat = {
        "event": event,
        "matcher": group.get("matcher"),
        "command": handler.get("command"),
    }
    group_extra = {k: v for k, v in group.items() if k not in {"event", "matcher", "hooks"}}
    handler_extra = {
        k: v for k, v in handler.items() if k not in {"type", "command"}
    }
    if group_extra:
        flat["_group_extra"] = group_extra
    if handler.get("type") != "command" or handler_extra:
        flat["_handler"] = dict(handler)
    return flat


def _flatten_codex_group(event: object, group: object) -> list[dict] | None:
    if not isinstance(event, str) or not isinstance(group, dict):
        return None
    handlers = group.get("hooks")
    if not isinstance(handlers, list) or not handlers:
        return None
    flat: list[dict] = []
    for handler in handlers:
        if not isinstance(handler, dict) or not isinstance(handler.get("type"), str):
            return None
        if handler.get("type") == "command" and not isinstance(handler.get("command"), str):
            return None
        flat.append(_flat_codex_handler(event, group, handler))
    return flat


def codex_hooks_schema(raw_hooks: object) -> str:
    """Classify the supported current/legacy hook representations."""
    if isinstance(raw_hooks, dict):
        return "event-keyed"
    if isinstance(raw_hooks, list) and all(isinstance(group, list) for group in raw_hooks):
        return "legacy-nested"
    return "malformed"


def flatten_codex_hooks(raw_hooks: object) -> tuple[list[dict], bool]:
    """Parse current event-keyed hooks and the retired CX21 nested format.

    The event-keyed representation is the only format rendered after CX26.
    Legacy input remains readable so update and uninstall can preserve unrelated
    valid hooks while migrating the file. Any malformed group fails the whole
    parse instead of being silently discarded.
    """
    schema = codex_hooks_schema(raw_hooks)
    flat: list[dict] = []
    if schema == "event-keyed":
        assert isinstance(raw_hooks, dict)
        for event, groups in raw_hooks.items():
            if not isinstance(groups, list):
                return [], False
            for group in groups:
                normalized = _flatten_codex_group(event, group)
                if normalized is None:
                    return [], False
                flat.extend(normalized)
        return flat, True
    if schema == "legacy-nested":
        assert isinstance(raw_hooks, list)
        for matcher_group in raw_hooks:
            for group in matcher_group:
                if not isinstance(group, dict):
                    return [], False
                normalized = _flatten_codex_group(group.get("event"), group)
                if normalized is None:
                    return [], False
                flat.extend(normalized)
        return flat, True
    return [], False


def codex_hooks_json_value(flat: list[dict]) -> dict[str, list[dict]]:
    """Render the canonical event-keyed `hooks.json` value."""
    events: dict[str, list[dict]] = {}
    for item in flat:
        event = item.get("event")
        if not isinstance(event, str):
            raise ValueError("Codex hook entry is missing a string event")
        handler = dict(item.get("_handler", {}))
        if not handler:
            handler = {"type": "command", "command": item.get("command")}
        elif item.get("command") is not None:
            handler["command"] = item["command"]
        group = dict(item.get("_group_extra", {}))
        if item.get("matcher") is not None:
            group["matcher"] = item["matcher"]
        group["hooks"] = [handler]
        events.setdefault(event, []).append(group)
    return events

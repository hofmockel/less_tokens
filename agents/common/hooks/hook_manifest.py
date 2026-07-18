"""Single source of truth for less_tokens hook wiring."""
from __future__ import annotations

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
        codex_script="truncate-output.py",
        codex=(HookWire("PostToolUse", "Bash|mcp__filesystem__.*"),),
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
        codex=(HookWire("PostToolUse", ".*"),),
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
        codex=(HookWire("PostToolUse", ".*"),),
    ),
    # Regenerates state/savings.html. Claude can do this once per assistant turn
    # through Stop; Codex has no native Stop equivalent, so refresh after tools.
    HookSpec(
        name="savings-html",
        claude_script="savings-html.py",
        # SubagentStop (G15): same reasoning as terse-output above.
        claude=(HookWire("Stop", ""), HookWire("SubagentStop", "")),
        codex_script="savings-html.py",
        codex=(HookWire("PostToolUse", ".*"),),
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


def flatten_codex_hooks(raw_hooks: object) -> tuple[list[dict], bool]:
    """Flatten the CLI's required `[[{event,matcher,hooks:[{type,command}]}, ...]]`
    shape (CX21/DECISIONS.md) to `{event,matcher,command}` dicts. Anything else —
    missing, malformed, or the pre-CX21 flat shape the CLI rejects — normalizes to
    `([], False)` so callers can distinguish "no hooks yet" from "wrong schema" and
    treat both install checking (install.py) and the deployed parity audit
    (codex_parity_audit.py) as one source of truth for the shape.
    """
    if not (isinstance(raw_hooks, list) and all(isinstance(g, list) for g in raw_hooks)):
        return [], False
    flat = []
    for group in raw_hooks:
        for h in group:
            if not isinstance(h, dict):
                continue
            inner = h.get("hooks")
            if not (isinstance(inner, list) and inner and isinstance(inner[0], dict)):
                continue
            command = inner[0].get("command")
            if command is None:
                continue
            flat.append({"event": h.get("event"), "matcher": h.get("matcher"), "command": command})
    return flat, True


def codex_hooks_json_value(flat: list[dict]) -> list:
    """Wrap a flat `{event,matcher,command}` list back into the CLI's nested shape.

    CX23: entries that share a matcher-group array with a different declared
    `event` fire mislabeled as whichever event actually triggered (confirmed
    at production scale — every `PostToolUse` entry fired as `PreToolUse`).
    One group array per declared event isolates them; an isolated
    `PostToolUse`-only group simply doesn't fire in headless `codex exec`
    rather than firing with the wrong label and payload.
    """
    if not flat:
        return []
    groups: dict[str, list[dict]] = {}
    for h in flat:
        groups.setdefault(h["event"], []).append(h)
    return [
        [
            {
                "event": h["event"],
                "matcher": h["matcher"],
                "hooks": [{"type": "command", "command": h["command"]}],
            }
            for h in entries
        ]
        for entries in groups.values()
    ]

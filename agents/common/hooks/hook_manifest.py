"""Single source of truth for less_tokens hook wiring."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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
        codex=(HookWire("PreToolUse", "mcp__filesystem__.*"),),
    ),
    HookSpec(
        name="read-guard",
        claude_script="read-guard.py",
        claude=(HookWire("PreToolUse", "Read"),),
        codex_script="read-guard.py",
        codex=(HookWire("PreToolUse", "mcp__filesystem__.*"),),
    ),
    HookSpec(
        name="auto-slice",
        claude_script="auto-slice.py",
        claude=(HookWire("PreToolUse", "Read"),),
        codex_script="auto-slice.py",
        codex=(HookWire("PreToolUse", "mcp__filesystem__.*"),),
    ),
    HookSpec(
        name="grep-first-read",
        claude_script="grep-first-read.py",
        claude=(HookWire("PreToolUse", "Read"),),
        codex_script="grep-first-read.py",
        codex=(HookWire("PreToolUse", "mcp__filesystem__.*"),),
    ),
    HookSpec(
        name="read-after-edit",
        claude_script="read-after-edit.py",
        claude=(HookWire("PreToolUse", "Read"),),
        codex_script="read-after-edit.py",
        codex=(HookWire("PreToolUse", "mcp__filesystem__.*"),),
    ),
    HookSpec(
        name="context-cache",
        claude_script="context-cache.py",
        claude=(HookWire("PreToolUse", "Read|Grep"),),
        codex_script="context-cache.py",
        codex=(HookWire("PreToolUse", "mcp__filesystem__.*"),),
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
        claude=(HookWire("Stop", ""),),
        codex_script="terse-reminder.py",
        codex=(HookWire("PostToolUse", ".*"),),
    ),
    # Regenerates state/savings.html. Claude can do this once per assistant turn
    # through Stop; Codex has no native Stop equivalent, so refresh after tools.
    HookSpec(
        name="savings-html",
        claude_script="savings-html.py",
        claude=(HookWire("Stop", ""),),
        codex_script="savings-html.py",
        codex=(HookWire("PostToolUse", ".*"),),
    ),
)


def _optional_enabled(agent: str, optional_flag: str, args: object) -> bool:
    """Decide whether an optional savings hook is wired (CL2).

    Claude installs wire these by default; ``--no-<flag>`` opts out. Codex stays
    opt-in via ``--<flag>`` until its mirror (CX2). The explicit ``--<flag>`` is
    still accepted on both agents for back-compat (a no-op on Claude).
    """
    if bool(getattr(args, f"no_{optional_flag}", False)):
        return False
    if agent == "claude":
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

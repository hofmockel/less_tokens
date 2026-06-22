# Maintaining Claude and Codex Paths

This document is an implementation plan for maintaining `less_tokens` as a multi-agent toolkit instead of porting it from Claude Code to Codex as a replacement. The goal is to keep one shared search/indexing core while supporting separate Claude and Codex integration layers.

## Goal

Maintain both paths by treating Claude Code and Codex as adapters over one shared `less_tokens` core.

The rule:

> One index/search engine, one config model, one test suite for shared behavior; separate thin adapters for Claude and Codex installation, instructions, hook payloads, and runtime state.

Do **not** fork `.claude/tools/search.py`, `.claude/tools/embeddings.py`, `.claude/schema/index.sql`, or savings/stat logic. Instead, split responsibilities like this:

```text
core:        .claude/tools/, .claude/schema/, shared hook logic
claude:      CLAUDE.md, .claude/hooks, .claude/settings.json wiring
codex:       AGENTS.md, .less_tokens/skills, .codex/hooks.json wiring (when available)
installer:   --agent claude|codex|both
```

> **Codex hook caveat (from field testing):** `.codex/hooks.json` and `.agents/skills/` may not be writable in all Codex environments. Treat Codex hook wiring and skill installation as optional capabilities. The Codex MVP installs shared tools under `.less_tokens/` and the skill under `.less_tokens/skills/less-tokens/`; hooks and `.agents/skills/` are added only when the runtime confirms they are available.

## Current repo facts to preserve

The existing codebase already has a partial separation:

- The core search and indexing path lives in `.claude/tools/` and `.claude/schema/`.
- The current agent integration path is Claude-specific.
- `install.py` copies shared assets and wires `.claude/settings.json`.
- `.claude/tools/search_config.py` centralizes venv, indexed paths, model settings, output truncation, compaction limits, and state.
- `STATE_DIR` currently defaults to `.claude/state`, which must become agent-aware or neutral.

The multi-agent implementation should preserve existing Claude behavior by default while adding Codex as an optional path.

## Target architecture

### Shared core

Keep these files agent-neutral:

```text
.claude/tools/
  db.py
  embeddings.py
  search.py
  search_config.py
  savings_log.py
  stats.py
  agentsmd_audit.py    # AGENTS.md / CLAUDE.md budget and ref checker
  read_guard.py        # noisy-file denylist guard
  lean-ls.py           # compact directory listing

.claude/schema/
  index.sql
```

The shared core must not know whether Claude or Codex is driving it. It should only:

- enumerate source files,
- chunk content,
- build and migrate `index.db`,
- embed chunks,
- run semantic search,
- record search/savings events through configurable state paths.

### Agent adapters

Add adapter directories:

```text
agents/
  common/
    hooks/
      payload.py
      search_first.py
      index_refresh.py
      truncate_output.py
      compact_trigger.py
      terse_reminder.py
    instructions/
      core.md

  claude/
    hooks/
      search-first.py
      index-refresh.py
      truncate-output.py
      compact-trigger.py
      caveman-reminder.py
    instructions/
      CLAUDE.md.fragment
    settings.py

  codex/
    hooks/
      search-first.py
      index-refresh.py
      truncate-output.py
      compact-trigger.py
      terse-reminder.py
    instructions/
      AGENTS.md.fragment
    settings.py
    skills/
      less-tokens/
        SKILL.md          # installed to .less_tokens/skills/less-tokens/ (fallback from .agents/skills/)
```

The files under `agents/common/` contain behavior. The files under `agents/claude/` and `agents/codex/` only:

1. parse the agent hook payload,
2. call shared logic,
3. format the response in the agent's expected style,
4. choose the right state directory.

## Installer UX

Add an explicit agent selector:

```bash
python3 install.py --agent claude
python3 install.py --agent codex
python3 install.py --agent both
```

Backward-compatible default:

```bash
python3 install.py
# equivalent to:
python3 install.py --agent claude
```

Recommended common installs:

```bash
python3 install.py --agent both --truncate --compact --caveman
python3 install.py --agent codex --build
```

### Installer behavior by mode

| Mode | Copies shared core | Claude hooks/settings | Codex hooks/settings | Instructions |
|---|---:|---:|---:|---|
| `--agent claude` | Yes | Yes | No | `CLAUDE.md` |
| `--agent codex` | Yes | No | Yes | `AGENTS.md` + skill |
| `--agent both` | Yes | Yes | Yes | both |

## Installer implementation details

### Add an agent enum or parser helper

Add a small helper near the argument parsing code:

```python
from enum import Enum


class Agent(str, Enum):
    CLAUDE = "claude"
    CODEX = "codex"
```

Parse CLI input like this:

```python
ap.add_argument(
    "--agent",
    choices=["claude", "codex", "both"],
    default="claude",
    help="Which agent integration to install; default preserves existing Claude behavior.",
)
```

Normalize it to a set:

```python
def selected_agents(value: str) -> set[Agent]:
    if value == "both":
        return {Agent.CLAUDE, Agent.CODEX}
    return {Agent(value)}
```

### Split hook entry builders

Current code has a single Claude-specific hook builder. Replace this pattern:

```python
def _build_hook_entries(venv_py, target_root, args):
    ...
```

with:

```python
def build_claude_hook_entries(venv_py: Path, target_root: Path, args: argparse.Namespace) -> list[tuple[str, str, str]]:
    ...


def build_codex_hook_entries(venv_py: Path, target_root: Path, args: argparse.Namespace) -> list[tuple[str, str, str]]:
    ...
```

Claude entries keep the existing shape:

```python
[
    ("PreToolUse", "Read", f"{py} .claude/hooks/search-first.py"),
    ("PostToolUse", "Edit|Write", f"{py} .claude/hooks/index-refresh.py"),
]
```

Codex entries should point at `.codex/hooks` and include Codex-relevant tools:

```python
[
    ("PreToolUse", "Bash|mcp__filesystem__.*", f"{py} .codex/hooks/search-first.py"),
    ("PostToolUse", "Bash|apply_patch|Edit|Write", f"{py} .codex/hooks/index-refresh.py"),
]
```

Optional Codex entries:

```python
if args.truncate:
    entries.append(("PostToolUse", "Bash|mcp__filesystem__.*", f"{py} .codex/hooks/truncate-output.py"))
if args.compact:
    entries.append(("PostToolUse", ".*", f"{py} .codex/hooks/compact-trigger.py"))
if args.caveman:
    entries.append(("PostToolUse", ".*", f"{py} .codex/hooks/terse-reminder.py"))
```

### Split settings writers

Keep the current settings writer for Claude, but rename it:

```python
def wire_claude_settings(settings_path: Path, entries: list[tuple[str, str, str]], dry_run: bool = False) -> tuple[int, int]:
    ...
```

Add a Codex writer:

```python
def wire_codex_hooks_json(hooks_path: Path, entries: list[tuple[str, str, str]], dry_run: bool = False) -> tuple[int, int]:
    ...
```

Do not force Claude and Codex into one generic JSON writer. The final file shape and supported metadata may diverge. Keep the abstraction at the level of desired hook entries, not final JSON layout.

### Make install specs agent-aware

Current install specs deploy hooks only to `.claude/hooks`. Replace that with agent-aware specs:

```python
def _install_specs(agents: set[Agent], caveman: bool) -> list[tuple[str, str, frozenset[str]]]:
    specs = [
        (".claude/tools", ".claude/tools", frozenset({"search_config.py"})),
        (".claude/schema", ".claude/schema", frozenset()),
    ]

    if Agent.CLAUDE in agents:
        specs.append(("agents/claude/hooks", ".claude/hooks", frozenset()))

    if Agent.CODEX in agents:
        # .codex/hooks may not be writable in all Codex environments — install only when available
        if _dir_is_writable(".codex"):
            specs.append(("agents/codex/hooks", ".codex/hooks", frozenset()))
        # prefer .agents/skills/ but fall back to .less_tokens/skills/
        skill_target = ".agents/skills" if _dir_is_writable(".agents") else ".less_tokens/skills"
        specs.append(("agents/codex/skills", skill_target, frozenset()))

    if caveman:
        specs.append((".claude/rules", ".claude/rules", frozenset()))

    return specs
```

### Update collision checks

Collision checks should still protect shared `.claude/tools/` and `.claude/schema/` by default. They should also account for selected agent trees:

- For Claude installs, check `.claude/hooks` for exact files managed by this project.
- For Codex installs, check `.codex/hooks` (if present) and the resolved skill target (`.agents/skills/less-tokens` or `.less_tokens/skills/less-tokens`).
- Do not treat unrelated user hooks in `.claude/hooks` or `.codex/hooks` as fatal unless a managed file name conflicts and differs.

### Make uninstall agent-aware

Support:

```bash
python3 install.py --uninstall --agent claude
python3 install.py --uninstall --agent codex
python3 install.py --uninstall --agent both
```

Rules:

- `--agent claude --uninstall`: remove only Claude hook wiring and Claude hook files.
- `--agent codex --uninstall`: remove only Codex hook wiring (if installed), Codex hook files, and the optional skill (from whichever target was used).
- `--agent both --uninstall`: remove both agent integrations.
- Never remove shared `.claude/tools/`, `.claude/schema/`, or `index.db` unless no installed agents remain, or unless an explicit purge flag is passed.
- Keep `--purge-index` explicit.

## State management

Use one shared index, but separate runtime state.

### Shared index

Keep:

```text
index.db
index.db-wal
index.db-shm
```

as project-level artifacts shared by Claude, Codex, and manual CLI use.

### Separate runtime state

Add state constants to `.claude/tools/search_config.py`:

```python
STATE_ROOT: Path = BASE / ".less_tokens" / "state"
CLAUDE_STATE_DIR: Path = BASE / ".claude" / "state"
CODEX_STATE_DIR: Path = BASE / ".less_tokens" / "state"  # .codex/ may not be writable
STATE_DIR: Path = STATE_ROOT
```

Add an agent-aware resolver:

```python
def state_dir_for(agent: str | None = None) -> Path:
    if agent == "claude":
        return CLAUDE_STATE_DIR
    if agent == "codex":
        return CODEX_STATE_DIR
    return STATE_DIR
```

Allow environment overrides:

```python
def active_state_dir() -> Path:
    explicit = os.environ.get("LESS_TOKENS_STATE_DIR")
    if explicit:
        return Path(explicit)
    return state_dir_for(os.environ.get("LESS_TOKENS_AGENT"))
```

Update `.claude/tools/search.py` to write `last-search` to `active_state_dir()` rather than a hardcoded `STATE_DIR`.

Hook adapters should run with one of:

```bash
LESS_TOKENS_AGENT=claude
LESS_TOKENS_AGENT=codex
```

or pass the state directory directly:

```bash
LESS_TOKENS_STATE_DIR=.claude/state
LESS_TOKENS_STATE_DIR=.codex/state
```

This prevents a Claude search from accidentally satisfying Codex's search-first gate, and vice versa.

## Shared hook payload model

Add `agents/common/hooks/payload.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HookPayload:
    agent: str
    event: str | None
    tool_name: str
    tool_input: dict[str, Any]
    tool_output: str
    transcript_path: Path | None
    touched_files: tuple[Path, ...]
```

### Claude payload normalization

Claude adapter payloads should map to the common shape:

```python
def normalize_claude(payload: dict[str, Any]) -> HookPayload:
    tool_input = payload.get("tool_input") or {}
    return HookPayload(
        agent="claude",
        event=payload.get("hook_event_name"),
        tool_name=payload.get("tool_name", ""),
        tool_input=tool_input,
        tool_output=payload.get("tool_response") or payload.get("tool_result") or "",
        transcript_path=_path_or_none(payload.get("transcript_path")),
        touched_files=_claude_touched_files(payload),
    )
```

`_claude_touched_files()` should read `tool_input.file_path` for `Read`, `Edit`, and `Write` payloads.

### Codex payload normalization

Codex adapter payloads should also map to the common shape:

```python
def normalize_codex(payload: dict[str, Any]) -> HookPayload:
    tool_input = payload.get("tool_input") or {}
    return HookPayload(
        agent="codex",
        event=payload.get("hook_event_name"),
        tool_name=payload.get("tool_name", ""),
        tool_input=tool_input,
        tool_output=payload.get("tool_response") or payload.get("tool_result") or "",
        transcript_path=_path_or_none(payload.get("transcript_path")),
        touched_files=_codex_touched_files(payload),
    )
```

`_codex_touched_files()` should handle at least:

- `apply_patch` payloads,
- Bash commands that write files,
- MCP filesystem tools if configured,
- direct `file_path` fields when present.

Start conservatively: if an `apply_patch` payload is detected and parsing touched files is uncertain, run a normal `embeddings.py refresh`. The refresh path is already content-hash based and safe to run repeatedly.

## Shared hook logic

Implement shared functions under `agents/common/hooks/`.

### Search-first

Shared function:

```python
def search_first(payload: HookPayload, *, state_dir: Path, repo_root: Path) -> HookDecision:
    ...
```

Responsibilities:

- determine whether the attempted file read targets an indexed file,
- check whether `state_dir / "last-search"` is recent,
- return allow/block with a message,
- log savings if a read is blocked.

Claude adapter:

- call for `Read` payloads only,
- block with the existing Claude-compatible exit behavior.

Codex adapter:

- call for direct file-read payloads when available,
- optionally inspect Bash/MCP commands for read-like operations,
- treat as best-effort guardrail, not a sandbox boundary.

### Index refresh

Shared function:

```python
def refresh_index_if_needed(payload: HookPayload, *, repo_root: Path, venv_py: Path) -> HookDecision:
    ...
```

Responsibilities:

- inspect `payload.touched_files`,
- if any touched file is indexed, spawn `.claude/tools/embeddings.py refresh`,
- write logs under the agent-specific state directory,
- do not block the agent unless subprocess launch itself fails.

Claude adapter:

- trigger on `Edit|Write`.

Codex adapter:

- trigger on `apply_patch`, configured filesystem tools, and relevant Bash writes.

### Output truncation

Shared function:

```python
def truncate_tool_output(payload: HookPayload, *, max_chars: int, head_lines: int, tail_lines: int) -> HookDecision:
    ...
```

Responsibilities:

- read `payload.tool_output`,
- preserve existing Bash head/tail strategy,
- preserve existing generic 60/40 split strategy,
- log savings.

Claude adapter:

- support existing `tool_result` behavior and `tool_response` fallback.

Codex adapter:

- prefer `tool_response`, with `tool_result` fallback.
- emit Codex-compatible hook output.

### Compaction trigger

Shared function:

```python
def compact_trigger(payload: HookPayload, *, state_dir: Path, max_session_chars: int) -> HookDecision:
    ...
```

Responsibilities:

- use `payload.transcript_path`,
- compare file size to threshold,
- apply hysteresis,
- write an agent-specific marker file.

Claude adapter message:

```text
Session transcript is now N chars. Run /compact before the next tool call.
```

Codex adapter message:

```text
Session transcript is now N chars. Start a fresh/compacted Codex session before the next tool call if context pressure is high.
```

### Terse/caveman reminder

Keep the shared verbose-pattern detector. Use different adapter wording:

Claude:

```text
Caveman mode on. Short sentence. No filler.
```

Codex:

```text
Keep response concise. No filler.
```

## Instruction files

Do not maintain entirely separate hand-written instruction documents. They will drift.

Use shared fragments:

```text
agents/common/instructions/core.md
agents/claude/instructions/CLAUDE.md.fragment
agents/codex/instructions/AGENTS.md.fragment
```

Generated or merged outputs:

```text
CLAUDE.md = common core + Claude fragment
AGENTS.md = common core + Codex fragment
```

### Shared instruction content

`agents/common/instructions/core.md` should include:

- project purpose,
- install model,
- test commands,
- architecture,
- source indexing rules,
- chunking strategies,
- backlog/changelog workflow,
- known bugs that apply to all agents.

### Claude-specific instruction content

`CLAUDE.md.fragment` should include:

- Claude hook paths,
- `.claude/settings.json` wiring,
- `Read`, `Edit`, and `Write` tool behavior,
- `/compact` wording,
- caveman mode instructions.

### Codex-specific instruction content

`AGENTS.md.fragment` should include:

- Codex hook paths,
- `.codex/hooks.json` wiring,
- Codex skill usage,
- `apply_patch` refresh behavior,
- best-effort limitation of search-first hooks,
- concise-output wording.

## Codex skill

Add a repo-local skill at:

```text
agents/codex/skills/less-tokens/SKILL.md
```

Install target (in order of preference):

1. `.agents/skills/less-tokens/SKILL.md` — if `.agents/` is writable
2. `.less_tokens/skills/less-tokens/SKILL.md` — fallback (always writable; confirmed working in field testing)

Suggested content:

```markdown
---
name: less-tokens
description: Use before exploring indexed repository files; runs local vector search before reading full files.
---

# less_tokens search workflow

Before reading indexed files, run:

    <venv-python> .less_tokens/tools/search.py "<query>"

If the index is missing or stale, run:

    <venv-python> .less_tokens/tools/embeddings.py refresh

Prefer the default top 3 chunks. Read full files only after search identifies the likely target path or section.

If search returns no useful chunks, proceed with normal repository inspection and consider refreshing the index.

For directory navigation, prefer `rg --files` over `find . -R` or `tree`. For AGENTS.md hygiene:

    <venv-python> .less_tokens/tools/agentsmd_audit.py

For noisy-file checks before reading:

    <venv-python> .less_tokens/tools/read_guard.py <path>
```

## Deployed file layout

After `--agent claude`:

```text
.claude/tools/
.claude/schema/
.claude/hooks/search-first.py
.claude/hooks/index-refresh.py
.claude/hooks/truncate-output.py
.claude/hooks/compact-trigger.py
.claude/hooks/caveman-reminder.py
.claude/settings.json
CLAUDE.md
```

After `--agent codex`:

```text
.claude/tools/
.claude/schema/

# always installed:
.less_tokens/tools/search.py
.less_tokens/tools/embeddings.py
.less_tokens/tools/db.py
.less_tokens/tools/symbols.py
.less_tokens/tools/agentsmd_audit.py
.less_tokens/tools/read_guard.py
.less_tokens/tools/lean-ls.py
.less_tokens/schema/index.sql
.less_tokens/skills/less-tokens/SKILL.md   # fallback when .agents/ is not writable
AGENTS.md

# installed only when runtime confirms writability:
.codex/hooks/search-first.py
.codex/hooks/index-refresh.py
.codex/hooks/truncate-output.py
.codex/hooks/compact-trigger.py
.codex/hooks/terse-reminder.py
.codex/hooks.json
.agents/skills/less-tokens/SKILL.md        # preferred over .less_tokens/skills/ when available
```

After `--agent both`, both sets should exist and share one `index.db`.

## Backward compatibility requirements

These must remain true:

1. `python3 install.py` installs Claude support just like today.
2. Existing Claude users do not need new flags.
3. Existing `.claude/tools/search.py` and `.claude/tools/embeddings.py` CLI usage remains valid.
4. Existing Claude tests continue to pass.
5. Existing `.claude/settings.json` wiring remains idempotent.
6. Existing generated `index.db` remains usable unless a schema migration explicitly changes it.

## Testing strategy

### Add hook payload fixtures

Create fixtures:

```text
.claude/tests/fixtures/hooks/
  claude/
    pre_read_indexed.json
    post_edit_indexed.json
    post_bash_large_output.json
    transcript_large.json
  codex/
    post_apply_patch.json
    post_bash_large_output.json
    mcp_filesystem_read.json
    transcript_large.json
```

### Core tests

Add or update tests for shared behavior:

```bash
pytest .claude/tests/unit/test_common_hooks.py -v
pytest .claude/tests/unit/test_search.py -v
pytest .claude/tests/unit/test_chunkers.py -v
```

Core tests should verify:

- indexed-file detection,
- recent-search detection,
- truncation behavior,
- compaction hysteresis,
- verbose-pattern detection,
- detached refresh launch decisions.

### Claude adapter tests

Add tests:

```bash
pytest .claude/tests/unit/test_claude_hooks.py -v
pytest .claude/tests/integration/test_install_claude.py -v
```

Claude adapter tests should verify:

- `Read` payloads can be blocked by search-first,
- `Edit|Write` payloads trigger index refresh,
- `tool_result` and `tool_response` are both accepted for truncation,
- `.claude/settings.json` wiring stays idempotent,
- `python3 install.py` still defaults to Claude mode.

### Codex adapter tests

Add tests:

```bash
pytest .claude/tests/unit/test_codex_hooks.py -v
pytest .claude/tests/integration/test_install_codex.py -v
```

Codex adapter tests should verify:

- `apply_patch` payloads trigger refresh,
- Codex payloads normalize `tool_response`,
- `.codex/hooks.json` wiring is idempotent,
- `AGENTS.md` is generated or updated safely,
- `.agents/skills/less-tokens/SKILL.md` is installed,
- search-first behavior is best-effort and does not claim complete enforcement.

### Both-mode install tests

Add tests:

```bash
pytest .claude/tests/integration/test_install_both.py -v
```

Both-mode tests should verify:

- shared core is copied once,
- Claude hooks point to `.claude/hooks`,
- Codex hooks point to `.codex/hooks`,
- `search_config.py` is merged once,
- uninstalling Claude does not remove Codex,
- uninstalling Codex does not remove Claude,
- `--purge-index` deletes `index.db` only when explicitly requested.

## PR sequence

Implement in small PRs.

### PR 1: shared hook core

- Add `agents/common/hooks/`.
- Move behavior from existing Claude hooks into shared functions.
- Keep existing `hooks/*.py` deployed paths working.
- Add shared hook tests.
- Verify current Claude tests still pass.

### PR 2: agent-aware state

- Add `STATE_ROOT`, `CLAUDE_STATE_DIR`, `CODEX_STATE_DIR`.
- Add `active_state_dir()`.
- Update `.claude/tools/search.py` and hooks to use `active_state_dir()` or an adapter-supplied state path.
- Preserve `.claude/state` for current Claude installs.

### PR 3: installer agent selector

- Add `--agent claude|codex|both`.
- Keep default `claude`.
- Rename existing hook writer to `wire_claude_settings()`.
- Add agent-aware install specs.
- Keep existing install integration tests passing.

### PR 4: Codex instructions and skill

- Add `agents/codex/instructions/AGENTS.md.fragment`.
- Add `agents/codex/skills/less-tokens/SKILL.md`.
- Add installer support for writing/updating `AGENTS.md`.
- Install skill to `.less_tokens/skills/less-tokens/` (always) and `.agents/skills/less-tokens/` (when writable).
- Add `agentsmd_audit.py`, `read_guard.py`, and `lean-ls.py` to shared core.
- Add tests for generated/merged Codex instruction assets.

### PR 5: Codex hooks and settings

- Add `agents/codex/hooks/` adapters.
- Add `.codex/hooks.json` writer with writability probe — skip gracefully if not available.
- Add Codex payload fixtures and tests.
- Add `--agent codex` and `--agent both` integration tests.
- Verify that a Codex install with no `.codex/` write access still produces a functional MVP (tools + skill + AGENTS.md).

Status: implemented for the core Codex adapter set, including search-first, read guard, auto-slice, grep-first read, read-after-edit, context cache, listing guard, lean-output, post-edit diff, index refresh, and AGENTS.md budget checks.

### PR 6: docs and release notes

- Update `README.md` and `documentation.md`.
- Add changelog entry.
- Document compatibility matrix.
- Document known limitations of Codex hook enforcement.

## Compatibility matrix

| less_tokens version | Claude support | Codex support | Notes |
|---|---|---|---|
| current | stable | stable | `--agent codex\|both`; shared index, separate runtime state |

## Known limitations to document

### Hook enforcement differs by agent

Claude's current path can block direct `Read` tool calls. Codex now has a broader hook set, but it should still be treated as a best-effort guardrail unless the active Codex runtime exposes every relevant read, edit, search, and Bash path to hooks.

The Codex path should not claim sandbox-like enforcement. It should say:

> Token-reduction hooks are enforced where hook-visible tool calls expose file paths or commands. The system remains backed by `AGENTS.md` and the `less-tokens` skill for cases hooks cannot intercept.

### Codex hook and skill installation is environment-dependent

Field testing confirmed that `.codex/skills` is not writable in all Codex environments and `.agents/skills/` may also be unavailable. The installer must probe before writing. The `.less_tokens/skills/` fallback is always safe because `less_tokens` already owns that directory.

If `.codex/hooks.json` does not exist and cannot be created, Codex hook behavior is unavailable for that install. The MVP still works: search, symbols, read guards, and AGENTS.md audit all run as explicit script calls without any hook wiring.

### Lazy tool discovery reduces MCP pruning priority

Codex has deferred tool discovery via `tool_search`. The Claude-specific `mcp-prune` direction has lower value in Codex. Do not make it a Codex-side feature.

### Apply-patch parsing can start conservative

For Codex `apply_patch`, begin by refreshing the index when a patch occurs. Later, optimize by parsing touched paths.

This is acceptable because `embeddings.py refresh` is incremental and content-hash based.

### Shared index can be stale briefly

Both Claude and Codex adapters should preserve the existing fire-and-forget refresh behavior. A search immediately after an edit may briefly return stale results, but the index should converge within seconds.

## What not to do

### Do not copy Claude hooks unchanged into Codex

The existing hooks assume Claude payloads and Claude state paths. Copying them into `.codex/hooks` unchanged will produce silent no-ops, especially for index refresh after Codex `apply_patch`.

### Do not fork the search/index core

There should not be `.claude/tools/search_claude.py` and `.claude/tools/search_codex.py`, nor separate schemas. That would double maintenance and create inconsistent results.

### Do not hand-maintain unrelated `CLAUDE.md` and `AGENTS.md`

Use shared fragments or generated content. Otherwise commands, architecture notes, and known bugs will drift.

### Do not make one giant universal hook script

Avoid large `if agent == ...` scripts. Use shared behavior plus thin adapters.

## Acceptance criteria

The multi-agent work is complete when all of the following are true:

- `python3 install.py` behaves like the current Claude install.
- `python3 install.py --agent claude` behaves the same as the default.
- `python3 install.py --agent codex` installs `.less_tokens/` tools and `AGENTS.md`; conditionally installs Codex hooks and skill to preferred targets when writable.
- `python3 install.py --agent both` installs both agent layers over one shared core.
- Claude and Codex state files are separate.
- Claude and Codex share the same `index.db`.
- Shared hook behavior is unit-tested once.
- Claude payload normalization is tested.
- Codex payload normalization is tested.
- Installer tests cover Claude, Codex, and both modes.
- Installer probes writability before installing to `.codex/` or `.agents/` paths.
- Codex skill falls back to `.less_tokens/skills/less-tokens/SKILL.md` when preferred targets are unavailable.
- Documentation clearly states Codex hook enforcement is best-effort.
- Documentation notes that `.codex/hooks.json` and `.agents/skills/` are optional, not guaranteed.

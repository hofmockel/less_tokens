# Multi-Agent Implementation Plan

## Context

`install.py` today is Claude-only. `multi-agent.md` specifies a full `--agent claude|codex|both`
installer. Three planning agents explored the codebase and reached consensus on architecture.
This plan implements the six-PR sequence from `multi-agent.md` against the real codebase state.

**No `agents/` directory exists. No `.less_tokens/` directory exists.** Both are new.

---

## Architecture Consensus

| Decision | Choice | Reason |
|---|---|---|
| Agent selector type | `set[str]` not an Enum | Simpler; avoids import; `"claude" in agents` reads clearly |
| Shared hook logic | `agents/common/hooks/` with 4 shared modules | Avoids copy-and-drift across 13 hooks |
| Adapter hook import | Resolve `LESS_TOKENS_REPO` at runtime, insert `agents/common/hooks/` into sys.path | Consistent with how Claude hooks import `.claude/tools/` |
| Codex tools source | Map `.claude/tools/` → `.less_tokens/tools/` in `_install_specs()` | No duplicate source tree needed |
| `STATE_DIR` backward compat | Keep `STATE_DIR = CLAUDE_STATE_DIR`; add `active_state_dir()` | All existing Claude hooks still work unchanged |
| `wire_settings()` compat | Keep name; add alias `wire_claude_settings`; add new `wire_codex_hooks_json()` | Existing test imports won't break |
| MVP Codex hooks | 4: index-refresh, truncate-output, compact-trigger, search-first | Other 9 are Claude-specific or redundant in Codex |
| AGENTS.md management | `handle_agents_md()` with HTML comment sentinels | Idempotent; safe for projects with existing AGENTS.md |

---

## PR 1: Shared Hook Core

**Goal:** Extract shared logic from Claude hooks into `agents/common/hooks/`. No behavior changes.

### New files to create

```
agents/
  __init__.py
  common/
    __init__.py
    hooks/
      __init__.py
      payload.py
      search_first.py
      index_refresh.py
      truncate_output.py
      compact_trigger.py
```

**`agents/common/hooks/payload.py`**

```python
@dataclass(frozen=True)
class HookPayload:
    agent: str
    tool_name: str
    tool_input: dict
    tool_output: str          # normalized from tool_result or tool_response
    transcript_path: Path | None
    touched_files: tuple[Path, ...]

def normalize_claude(payload: dict) -> HookPayload: ...
def normalize_codex(payload: dict) -> HookPayload: ...
def _path_or_none(v) -> Path | None: ...
```

- `normalize_claude`: reads `tool_result` first, `tool_response` fallback; `touched_files` from `tool_input["file_path"]` for Read/Edit/Write
- `normalize_codex`: reads `tool_response` first, `tool_result` fallback; `apply_patch` → empty `touched_files` (conservative)

**`agents/common/hooks/search_first.py`**

Extract `is_indexed()`, `search_was_recent()`, `_grep_symbol_hint()` from `.claude/hooks/search-first.py`:

```python
def check_search_first(
    payload: HookPayload,
    *,
    repo: Path,
    state_dir: Path,
    config: dict,
) -> tuple[int, str, str]:   # (exit_code, stdout, stderr)
```

**`agents/common/hooks/index_refresh.py`**

Extract `is_indexed()` check and detached `Popen` refresh logic from `.claude/hooks/index-refresh.py`:

```python
def check_index_refresh(
    payload: HookPayload,
    *,
    repo: Path,
    state_dir: Path,
    config: dict,
) -> tuple[int, str, str]:
```

For `apply_patch` tool name: skip `is_indexed()`, run `embeddings.py refresh` unconditionally.

**`agents/common/hooks/truncate_output.py`**

Extract `truncate_bash()`, `truncate_chars()`, `truncate_glob()` from `.claude/hooks/truncate-output.py`:

```python
def check_truncate_output(
    payload: HookPayload,
    *,
    max_chars: int,
    head_lines: int,
    tail_lines: int,
    max_glob_results: int,
) -> tuple[int, str, str]:
```

**`agents/common/hooks/compact_trigger.py`**

Extract file-size check and hysteresis from `.claude/hooks/compact-trigger.py`:

```python
def check_compact_trigger(
    payload: HookPayload,
    *,
    state_dir: Path,
    max_session_chars: int,
    message: str,    # agent-specific wording
) -> tuple[int, str, str]:
```

State file: `state_dir / "compact-trigger-last"`.

### New test file

`.claude/tests/unit/test_common_hooks.py` — tests for `is_indexed()`, `search_was_recent()`,
`check_truncate_output`, `check_compact_trigger`, `normalize_claude`, `normalize_codex`. Use
`load_hook()` from conftest for module-level tests; `monkeypatch` for config isolation.

---

## PR 2: Agent-Aware State

**Goal:** Add `active_state_dir()` to `search_config.py`. Update hooks and `search.py` to use it.

### `.claude/tools/search_config.py` — line 112

Replace:
```python
STATE_DIR: Path = CLAUDE_DIR / "state"
```
With:
```python
STATE_ROOT: Path = BASE / ".less_tokens" / "state"
CLAUDE_STATE_DIR: Path = CLAUDE_DIR / "state"
CODEX_STATE_DIR: Path = BASE / ".less_tokens" / "state"
STATE_DIR: Path = CLAUDE_STATE_DIR   # backward-compat alias — do not remove

def state_dir_for(agent: str | None = None) -> Path:
    if agent == "claude": return CLAUDE_STATE_DIR
    if agent == "codex":  return CODEX_STATE_DIR
    return STATE_DIR

def active_state_dir() -> Path:
    explicit = os.environ.get("LESS_TOKENS_STATE_DIR")
    if explicit: return Path(explicit)
    return state_dir_for(os.environ.get("LESS_TOKENS_AGENT"))

_STATE_AGENT_AWARE: bool = True   # sentinel for installer merge check
```

`os` is already imported. `active_state_dir()` reads env vars at call time (not import time).

### `install.py` — new `merge_agent_aware_functions()` function

Add after `merge_search_config()` (line 303). Checks for `def active_state_dir` in dst via string
scan; if absent, appends the full block (constants + functions + sentinel). Called from
`handle_search_config()` (line 523) after the variable merge.

### Hook files to update (8 files)

| Hook | Current | Change |
|---|---|---|
| `.claude/hooks/search-first.py:52` | `search_config.STATE_DIR / "last-search"` | `search_config.active_state_dir() / "last-search"` |
| `.claude/hooks/auto-slice.py:47-50` | fallback `STATE_DIR = REPO / ".claude" / "state"`; module-level `RANGES_FILE` | Import `active_state_dir`; `RANGES_FILE = active_state_dir() / "last-search.json"` |
| `.claude/hooks/compact-trigger.py:46` | `STATE_FILE = REPO / ".claude" / "state" / "compact-trigger-last"` (hardcoded) | Import `active_state_dir`; `STATE_FILE = active_state_dir() / "compact-trigger-last"` |
| `.claude/hooks/index-refresh.py:113` | `log = REPO / ".claude" / "state" / "index-refresh.log"` (hardcoded) | Import `active_state_dir`; `log = active_state_dir() / "index-refresh.log"` |
| `.claude/hooks/context-cache.py` | Module-level `CACHE_FILE = STATE_DIR / "context-cache.json"` | Make lazy: `def _cache_file(): return active_state_dir() / "context-cache.json"` |
| `.claude/hooks/post-edit-diff.py` | Module-level `LAST_EDIT_FILE = STATE_DIR / "last-edit.json"` | Inline in `_record_edit()`: `last_edit_file = active_state_dir() / "last-edit.json"` |
| `.claude/hooks/read-after-edit.py` | Module-level `LAST_EDIT_FILE = STATE_DIR / "last-edit.json"` | Inline in `_load_edits()` and main block |
| `.claude/hooks/grep-first-read.py` | Module-level `RANGES_FILE` + `state_file = STATE_DIR / "last-search"` | Both → `active_state_dir() / ...` |

### `.claude/tools/search.py`

Capture `sd = active_state_dir()` once in `main()` and once in `_write_last_search_ranges()`:
- `HISTORY_LOG = STATE_DIR / "search-history.log"` (module-level) → `active_state_dir() / ...`
- `(STATE_DIR / "last-search").write_text(...)` → `sd / "last-search"`
- `(STATE_DIR / "last-search.json").write_text(...)` → `sd / "last-search.json"`
- `STATE_DIR.mkdir(...)` → `sd.mkdir(...)`

### New test file

`.claude/tests/unit/test_search_config_agent.py` — 11 tests using `monkeypatch.setenv`. Verifies
`state_dir_for()`, `active_state_dir()`, backward compat (`STATE_DIR == CLAUDE_STATE_DIR`),
env-var priority order.

---

## PR 3: Installer `--agent` Selector

**Goal:** Add `--agent claude|codex|both` to `install.py`. Wire Claude + Codex installs.

### `install.py` changes

**`selected_agents()` helper** — add near top before `SOURCE`:
```python
def selected_agents(value: str) -> set[str]:
    if value == "both": return {"claude", "codex"}
    return {value}
```

**`--agent` argument** — add in `main()` after `--purge-index` (~line 1075):
```python
ap.add_argument("--agent", choices=["claude", "codex", "both"], default="claude")
```
Immediately after `args = ap.parse_args()`:
```python
agents = selected_agents(args.agent)
```

**`_dir_is_writable()` helper** — add before `_install_specs()` (line 799):
```python
def _dir_is_writable(target_root: Path, rel: str) -> bool:
    d = target_root / rel
    if d.is_dir(): return os.access(d, os.W_OK)
    parent = d.parent
    return parent.is_dir() and os.access(parent, os.W_OK)
```

**`_install_specs()` refactor** — change signature at line 799:
```python
def _install_specs(agents: set[str], caveman: bool, target_root: Path | None = None) -> list[...]:
    specs = [
        (".claude/tools",  ".claude/tools",  frozenset({"search_config.py"})),
        (".claude/schema", ".claude/schema", frozenset()),
    ]
    if "claude" in agents:
        specs.append((".claude/hooks", ".claude/hooks", frozenset()))
    if "codex" in agents:
        # shared tools/schema deployed to .less_tokens/ (no separate source dir needed)
        specs.append((".claude/tools",  ".less_tokens/tools",  frozenset({"search_config.py"})))
        specs.append((".claude/schema", ".less_tokens/schema", frozenset()))
        if target_root is not None and _dir_is_writable(target_root, ".codex"):
            specs.append(("agents/codex/hooks", ".codex/hooks", frozenset()))
        if target_root is not None:
            skill_tgt = ".agents/skills/less-tokens" if _dir_is_writable(target_root, ".agents") \
                        else ".less_tokens/skills/less-tokens"
        else:
            skill_tgt = ".less_tokens/skills/less-tokens"
        specs.append(("agents/codex/skills/less-tokens", skill_tgt, frozenset()))
    if caveman and "claude" in agents:
        specs.append((".claude/rules", ".claude/rules", frozenset()))
    return specs
```

Update all callers — add `agents` param to: `_foreign_files()` (line 810),
`_deployed_targets()` (line 844), `do_uninstall()` (line 968).

**`build_claude_hook_entries()` + alias** — rename `_build_hook_entries` (line 567):
```python
def build_claude_hook_entries(venv_py, target_root, args): ...  # body unchanged
_build_hook_entries = build_claude_hook_entries                  # backward compat
```

**`build_codex_hook_entries()`** — new function after the Claude one:
```python
def build_codex_hook_entries(venv_py: Path, target_root: Path, args) -> list[tuple[str, str, str]]:
    py = str(venv_py.relative_to(target_root)) if venv_py.is_relative_to(target_root) else str(venv_py)
    prefix = f"LESS_TOKENS_AGENT=codex {py}"
    entries = [
        ("PostToolUse", "apply_patch|Edit|Write", f"{prefix} .codex/hooks/index-refresh.py"),
        ("PreToolUse",  "mcp__filesystem__.*",    f"{prefix} .codex/hooks/search-first.py"),
    ]
    if getattr(args, "truncate", False):
        entries.append(("PostToolUse", "Bash|mcp__filesystem__.*",
                         f"{prefix} .codex/hooks/truncate-output.py"))
    if getattr(args, "compact", False):
        entries.append(("PostToolUse", ".*", f"{prefix} .codex/hooks/compact-trigger.py"))
    if getattr(args, "caveman", False):
        entries.append(("PostToolUse", ".*", f"{prefix} .codex/hooks/terse-reminder.py"))
    return entries
```

**`wire_claude_settings` alias** — add after `wire_settings()` (line 605):
```python
wire_claude_settings = wire_settings
```

**`wire_codex_hooks_json()`** — new function after `wire_settings()`. Same JSON structure and
idempotency logic as `wire_settings()`. Only writes when `added > 0`. Creates `.codex/` parent
with `mkdir(parents=True)`.

**`_our_hook_names()` update** — line 921: add `agents` param; also enumerate
`agents/codex/hooks/` filenames when `"codex" in agents`.

**`unwire_codex_hooks_json()`** — new function: mirror of `unwire_settings()` for
`.codex/hooks.json`.

**`handle_agents_md()`** — new function before `do_uninstall()`. HTML comment sentinels
`<!-- less_tokens: begin -->` / `<!-- less_tokens: end -->`. Source:
`agents/codex/instructions/AGENTS.md.fragment`. Idempotent.

**`do_uninstall()` update** — line 968: add `agents` param. Agent-conditional cleanup:
`.codex/hooks/`, `.less_tokens/tools/`, `.less_tokens/schema/`, `.less_tokens/skills/`.
Calls `unwire_codex_hooks_json()` for Codex.

**`_GI_PATHS` update** — line 860: add `"/.less_tokens/state/"`.

**`main()` Step 2 (copy)**: Guard `handle_search_config()` and `patch_venv_py()` for Claude
under `if "claude" in agents`. Add parallel block for Codex `search_config.py` (same functions,
target `.less_tokens/tools/search_config.py`).

**`main()` Step 5 (wire)**: Replace single-agent wiring with:
```python
if "claude" in agents:
    entries = build_claude_hook_entries(venv_py, target_root, args)
    wire_settings(settings_path, entries, dry_run=dry)

if "codex" in agents:
    if _dir_is_writable(target_root, ".codex"):
        entries = build_codex_hook_entries(venv_py, target_root, args)
        wire_codex_hooks_json(target_root / ".codex" / "hooks.json", entries, dry_run=dry)
    else:
        print("  · .codex/ not writable — hooks.json skipped; AGENTS.md + skill installed")
    fragment = SOURCE / "agents" / "codex" / "instructions" / "AGENTS.md.fragment"
    handle_agents_md(fragment, target_root, dry_run=dry)
```

### New test file

`.claude/tests/unit/test_install_specs_agent.py` — unit tests for `_install_specs()` with
different `agents` sets. Claude-only: no `.less_tokens/` entries. Codex-only: no `.claude/hooks/`
entries. Both: both present.

---

## PR 4: Codex Instructions and Skill

**Goal:** Create `AGENTS.md.fragment` and `SKILL.md`.

### New files to create

**`agents/codex/instructions/AGENTS.md.fragment`**

Short Markdown under `## Token Discipline`:
- Search before reading: `python .less_tokens/tools/search.py "query"`
- Symbol lookup: `python .less_tokens/tools/symbols.py <name>`
- Noisy-file guard: `python .less_tokens/tools/read_guard.py <path>`
- AGENTS.md audit: `python .less_tokens/tools/agentsmd_audit.py`
- Directory navigation: prefer `rg --files` over `find . -R`
- Response budget: direct findings, exact references, no filler

**`agents/codex/skills/less-tokens/SKILL.md`**

Front-matter with `name: less-tokens`. Body shows 4 script commands using `.less_tokens/tools/`
paths. `<venv-python>` placeholder replaced at install time (same `patch_venv_py`-style
substitution). No hooks described as mandatory.

### New test file

`.claude/tests/unit/test_agents_md.py` — tests for `handle_agents_md()`:
- Fresh `AGENTS.md`: fragment appended
- Existing file without block: fragment appended, existing content preserved
- Existing file with unchanged block: no-op (returns 0)
- Existing file with stale block: replaced in-place
- Dry-run: file not touched

---

## PR 5: Codex Adapter Hooks and Integration Tests

**Goal:** Create the 5 thin Codex adapter hook scripts. Add integration tests.

### New files to create

```
agents/codex/__init__.py
agents/codex/hooks/__init__.py
agents/codex/hooks/search-first.py
agents/codex/hooks/index-refresh.py
agents/codex/hooks/truncate-output.py
agents/codex/hooks/compact-trigger.py
agents/codex/hooks/terse-reminder.py
```

**Pattern for all Codex adapter hooks** (~20–25 lines each):
```python
#!/usr/bin/env python3
import json, os, sys
from pathlib import Path

def _resolve_repo() -> Path:
    # identical pattern to Claude hooks: LESS_TOKENS_REPO env, then walk up from __file__
    ...

REPO = _resolve_repo()
sys.path.insert(0, str(REPO / ".claude" / "tools"))
sys.path.insert(0, str(REPO / "agents" / "common" / "hooks"))

from search_config import active_state_dir, MAX_TOOL_OUTPUT_CHARS, ...
from payload import normalize_codex
from <module> import check_<function>

raw = json.loads(sys.stdin.read())
payload = normalize_codex(raw)
state_dir = active_state_dir()   # reads LESS_TOKENS_AGENT=codex from env
code, stdout, stderr = check_<function>(payload, repo=REPO, state_dir=state_dir, ...)
if stdout: print(stdout)
if stderr: print(stderr, file=sys.stderr)
sys.exit(code)
```

- **`index-refresh.py`** — calls `check_index_refresh()`. Accepts `apply_patch`, `Edit`, `Write`.
- **`truncate-output.py`** — calls `check_truncate_output()`. Accepts `Bash`, `mcp__filesystem__.*`.
- **`compact-trigger.py`** — calls `check_compact_trigger()`. Message: `"Session transcript is now {size:,} chars. Start a fresh/compacted Codex session if context pressure is high."`.
- **`search-first.py`** — calls `check_search_first()`. Accepts `mcp__filesystem__read_file`. Exit 0 for unknown tool names (best-effort, not a sandbox boundary).
- **`terse-reminder.py`** — standalone; mirrors `caveman-reminder.py` but with message `"Keep response concise. No filler."`. Uses `active_state_dir()` for state.

### New test files

**`.claude/tests/unit/test_codex_hooks.py`** — subprocess pattern from `test_hooks_protocol.py`.
Add `run_hook_with_env()` helper accepting extra env dict. Tests:
- `index-refresh.py` with `apply_patch` payload → exits 0
- `truncate-output.py` with large `tool_response` → exits 2
- `compact-trigger.py` with large transcript → exits 2 with Codex-specific message (not "/compact")
- `search-first.py` with unknown tool name → exits 0

**`.claude/tests/unit/test_hooks_state_dir.py`** — state dir isolation:
- `compact-trigger.py` with `LESS_TOKENS_AGENT=codex` writes state to `.less_tokens/state/`
- `search-first.py` with `LESS_TOKENS_STATE_DIR=<tmp>` reads sentinel from `<tmp>`
- Claude gate not satisfied by sentinel in `.less_tokens/state/`

**`.claude/tests/integration/test_install_codex.py`** — subprocess integration:
- `--agent codex` creates `.less_tokens/tools/` and `.less_tokens/schema/`
- `--agent codex` does not create `.claude/hooks/`
- `.claude/tools/search_config.py` contains `active_state_dir` after install
- Writability probe: `chmod 0o555` on `.codex/` → install exits 0, fallback skill path used
- `AGENTS.md` created at target root

**`.claude/tests/integration/test_install_both.py`** — both-mode:
- One `index.db` at `.claude/`; no `.codex/index.db`
- `--uninstall --agent claude` preserves `.codex/hooks/`
- `--uninstall --agent codex` preserves `.claude/hooks/`
- `--purge-index` deletes `index.db`; without it, `index.db` survives
- Second install is idempotent (no duplicate hook entries)

---

## PR 6: Docs

Update `README.md` and `documentation.md`:
- `--agent` flag documentation
- Compatibility matrix (Claude stable, Codex experimental → stable)
- Known limitations: Codex search-first is best-effort; `.codex/hooks.json` write is optional
- `CHANGELOG.md` entry under `[Unreleased]`
- Remove completed items from `BACKLOG.md`

---

## Verification

```bash
# All existing tests must stay green
pip install numpy pytest
pytest .claude/tests/unit/ -v
pytest .claude/tests/integration/ -v

# Backward compat — no --agent flag defaults to Claude
python3 install.py --target /tmp/lt_claude --yes --skip-deps --no-build --dry-run

# Codex-only install
python3 install.py --agent codex --target /tmp/lt_codex --yes --skip-deps --no-build --dry-run
# Expected: .less_tokens/tools/ created; no .claude/hooks/; AGENTS.md written

# Both-mode install
python3 install.py --agent both --target /tmp/lt_both --yes --skip-deps --no-build --dry-run
# Expected: .claude/hooks/ AND .codex/hooks/ (if writable); one search_config.py; no duplicate entries

# State dir isolation smoke test (after real install)
LESS_TOKENS_AGENT=codex python .less_tokens/tools/search.py "test query"
# last-search must appear in .less_tokens/state/, not .claude/state/

# Uninstall symmetry
python3 install.py --uninstall --agent claude --target /tmp/lt_both --dry-run
# Expected: only Claude artifacts listed; .codex/hooks/ untouched
```

---

## Critical Files

| File | What changes |
|---|---|
| `install.py` | 15 function changes/additions (see PR 3 section) |
| `.claude/tools/search_config.py:112` | Replace `STATE_DIR` line with full agent-aware block |
| `.claude/tools/search.py` | 4 locations: `HISTORY_LOG`, `last-search`, `last-search.json`, `mkdir` |
| `.claude/hooks/compact-trigger.py:46` | Hardcoded `.claude/state/` → `active_state_dir()` |
| `.claude/hooks/index-refresh.py:113` | Hardcoded `.claude/state/` → `active_state_dir()` |
| `.claude/hooks/search-first.py:52` | `STATE_DIR` → `active_state_dir()` |
| `.claude/hooks/auto-slice.py:45-50` | `STATE_DIR` fallback block → `active_state_dir()` |
| `.claude/hooks/context-cache.py` | Module-level `CACHE_FILE` → lazy `_cache_file()` |
| `.claude/hooks/post-edit-diff.py` | Module-level `LAST_EDIT_FILE` → inline in `_record_edit()` |
| `.claude/hooks/read-after-edit.py` | Module-level `LAST_EDIT_FILE` → inline in `_load_edits()` |
| `.claude/hooks/grep-first-read.py` | `RANGES_FILE` + `state_file` → `active_state_dir()` |

## New Files (25 total)

```
agents/__init__.py
agents/common/__init__.py
agents/common/hooks/__init__.py
agents/common/hooks/payload.py
agents/common/hooks/search_first.py
agents/common/hooks/index_refresh.py
agents/common/hooks/truncate_output.py
agents/common/hooks/compact_trigger.py
agents/codex/__init__.py
agents/codex/hooks/__init__.py
agents/codex/hooks/search-first.py
agents/codex/hooks/index-refresh.py
agents/codex/hooks/truncate-output.py
agents/codex/hooks/compact-trigger.py
agents/codex/hooks/terse-reminder.py
agents/codex/skills/less-tokens/SKILL.md
agents/codex/instructions/AGENTS.md.fragment
.claude/tests/unit/test_common_hooks.py
.claude/tests/unit/test_search_config_agent.py
.claude/tests/unit/test_hooks_state_dir.py
.claude/tests/unit/test_codex_hooks.py
.claude/tests/unit/test_install_specs_agent.py
.claude/tests/unit/test_agents_md.py
.claude/tests/integration/test_install_codex.py
.claude/tests/integration/test_install_both.py
```

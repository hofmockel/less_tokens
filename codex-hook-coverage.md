# Codex hook coverage

Date: 21 Jun 2026

Codex support uses the same local search/index tools as Claude through
`.less_tokens/tools/` compatibility shims, plus thin adapters under `.codex/hooks/`. Enforcement remains
best-effort because it depends on `.codex/hooks.json` being writable and on the
Codex runtime emitting the expected hook events.

## Installed runtime

| Path | Purpose |
|---|---|
| `.less_tokens/tools/` | Compatibility shims into the single `.claude/tools/` implementation |
| `.less_tokens/schema/` | SQLite schema copied from Claude runtime |
| `.less_tokens/hooks/` | Agent-neutral hook logic |
| `.less_tokens/bin/python` | Launcher pointing at the configured venv |
| `.codex/hooks/` | Codex-specific hook adapters |
| `AGENTS.md` | Always-loaded token-discipline block |

## Default hook coverage

| Strategy | Codex event | Matcher | Adapter | Shared logic |
|---|---|---|---|---|
| Search before read | `PreToolUse` | `mcp__filesystem__.*` | `.codex/hooks/search-first.py` | `agents/common/hooks/search_first.py` |
| Noisy-file read guard | `PreToolUse` | `mcp__filesystem__.*` | `.codex/hooks/read-guard.py` | `agents/common/hooks/read_guard.py` |
| Auto-slice after search | `PreToolUse` | `mcp__filesystem__.*` | `.codex/hooks/auto-slice.py` | `agents/common/hooks/auto_slice.py` |
| Grep/search before large read | `PreToolUse` | `mcp__filesystem__.*` | `.codex/hooks/grep-first-read.py` | `agents/common/hooks/grep_first_read.py` |
| Avoid reread after edit | `PreToolUse` | `mcp__filesystem__.*` | `.codex/hooks/read-after-edit.py` | `agents/common/hooks/read_after_edit.py` |
| Context cache | `PreToolUse` | `mcp__filesystem__.*` | `.codex/hooks/context-cache.py` | adapter-local pending shared extraction |
| Recursive listing guard | `PreToolUse` | `Bash` | `.codex/hooks/listing-guard.py` | adapter-local pending shared extraction |
| Structured CLI output | `PostToolUse` | `Bash` | `.codex/hooks/lean-output.py` | `.less_tokens/tools/parse.py` |
| Post-edit diff | `PostToolUse` | `apply_patch|Edit|Write` | `.codex/hooks/post-edit-diff.py` | adapter-local pending shared extraction |
| Index refresh | `PostToolUse` | `apply_patch|Edit|Write` | `.codex/hooks/index-refresh.py` | `agents/common/hooks/index_refresh.py` |
| AGENTS.md budget | `PostToolUse` | `Edit|Write` | `.codex/hooks/agentsmd-budget.py` | `.less_tokens/tools/claudemd_audit.py` |

## Optional hook coverage

| Flag | Strategy | Codex event | Matcher | Adapter |
|---|---|---|---|---|
| `--truncate` | Generic output truncation | `PostToolUse` | `Bash|mcp__filesystem__.*` | `.codex/hooks/truncate-output.py` |
| `--compact` | Long-session compaction nudge | `PostToolUse` | `.*` | `.codex/hooks/compact-trigger.py` |
| `--caveman` | Concise response reminder | `PostToolUse` | `.*` | `.codex/hooks/terse-reminder.py` |

## Known limits

- Hooks are skipped if `.codex/` is not writable during install.
- Coverage is strongest for `mcp__filesystem__read_file` and `Bash` events.
- Native Codex read/edit tools with different event names need explicit mapping.
- `apply_patch` payloads do not always expose touched files, so post-edit diff and index refresh fall back to conservative behavior.
- Terse-response enforcement is reminder-style for Codex; Claude has a stronger Stop hook.

## Verify

Run:

```bash
python3 less_tokens/install.py --agent codex --dry-run
```

Then inspect:

```bash
cat .codex/hooks.json
.less_tokens/bin/python .less_tokens/tools/search.py "query"
.less_tokens/bin/python .less_tokens/tools/agentsmd_audit.py
```

If `.codex/hooks.json` is missing or not writable, Codex still gets the
`.less_tokens/` runtime, the skill, and the `AGENTS.md` block, but enforcement
is advisory.

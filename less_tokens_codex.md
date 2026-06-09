# Porting `less_tokens` From Claude Code to Codex

This note evaluates the `less_tokens/` repo that was added inside this project and records findings for repurposing its Claude Code token-reduction ideas for Codex.

The short version: the core ideas are useful, but the Claude integration layer should not be copied directly. Codex needs a small adapter layer, AGENTS/skill-oriented instructions, and a more conservative stance on hooks because several Claude Code hook surfaces are not available as repo-controlled behavior in this Codex desktop environment.

## Context

`less_tokens` is designed to be cloned into a host project, installed, then removed. It targets Claude Code and installs artifacts under `.claude/`, including:

- vector search and embedding tools;
- Claude Code hook scripts;
- Claude slash-command docs;
- a `CLAUDE.md` output-style and search-before-read policy;
- optional truncation, compaction, context-cache, read-guard, and listing-guard behavior;
- savings/stat tracking.

This repository is a Codex project. Its always-loaded project instruction file is `AGENTS.md`, not `CLAUDE.md`. The repo also has trading-specific safety rules that must remain the top-level project contract.

## High-Level Verdict

The best portable asset is the deterministic search/indexing core. The most Claude-specific assets are hook wiring, hook payload parsing, slash commands, and `CLAUDE.md` management.

Recommended porting direction:

1. Keep one shared token-saving core.
2. Add thin agent adapters for Claude and Codex.
3. Treat `AGENTS.md` as a concise contract, not a dumping ground.
4. Use Codex skills for optional workflows.
5. Do not assume Claude Code hook semantics exist in Codex.
6. Prefer repo-local scripts and documented workflows over invisible enforcement until Codex provides a stable hook API.

## What Ports Well

### Vector Search

The search/indexing idea is directly useful in Codex. `less_tokens/.claude/tools/search.py`, `embeddings.py`, `db.py`, `symbols.py`, and `index.sql` are mostly agent-neutral.

For Codex, these should move out of `.claude/` or be made path-configurable:

```text
less_tokens_core/
  tools/
  schema/
  state/
```

or:

```text
.less_tokens/
  tools/
  schema/
  index.db
  state/
```

Codex can already use `rg`, `sed`, and file slicing efficiently, so vector search should be an additional precision tool, not a replacement for normal codebase exploration.

### Search-Before-Read Discipline

The principle ports well. The mechanism does not.

In Claude, `search-first.py` is enforced through `PreToolUse` on `Read`. In Codex, repo code cannot currently guarantee interception of every file read. A Codex port should document the discipline in `AGENTS.md` and provide a skill or script:

```bash
python .less_tokens/tools/search.py "trade scoring thresholds"
```

The Codex-specific instruction should be shorter than the Claude one:

```markdown
## Token Discipline

For large indexed files, search before reading the whole file:

    python .less_tokens/tools/search.py "query"

Prefer `rg`, targeted `sed -n`, and small slices over full-file dumps.
```

### Noise-File Guards

The denylist in `READ_DENY_GLOBS` is useful across agents:

- lockfiles;
- generated bundles;
- notebooks;
- binary media;
- large CSV/JSON data.

For Codex, this is best implemented first as a script and instruction, not a hard hook:

```bash
python .less_tokens/tools/read_guard.py path/to/file
```

If Codex later exposes stable tool hooks, the same logic can become a pre-read guard.

### Listing Guards

`listing-guard.py` and `lean-ls.py` map well to Codex habits because Codex often explores with shell commands. The useful rule is:

- avoid `find .`, `ls -R`, and `tree` on a large repo;
- prefer `rg --files`;
- summarize with depth and ignore rules.

Codex already has a project instruction to prefer `rg`/`rg --files`. A Codex port can ship `lean-ls.py`, but should not need to force it for small repositories.

### Post-Edit Diff

The idea behind `post-edit-diff.py` is agent-neutral: after an edit, show a tight diff instead of rereading the whole file.

Codex already has strong local edit tools and can run:

```bash
git diff -- path
```

So the Codex port should make this a documented verification habit and optional helper, not a mandatory hook.

### CLAUDE.md Pruning Becomes AGENTS.md Pruning

`claudemd.md` contains one of the strongest ideas: always-loaded instruction files are a fixed per-turn tax.

For Codex, rename and generalize it:

```text
agentsmd_audit.py
AGENTS_MD_TOKEN_BUDGET
AGENTS_MD_OVERFLOW_DOC
```

The rubric ports almost unchanged:

- keep hard rules and safety invariants in `AGENTS.md`;
- move architecture, examples, and long procedures into indexed docs;
- avoid stale line references;
- keep only instructions that must be known before action.

For this repo, trading safety belongs in `AGENTS.md`; detailed implementation notes belong in docs or indexed config files.

## What Needs a Codex Adapter

### Paths and Naming

The current repo assumes:

```text
.claude/
CLAUDE.md
.claude/settings.json
.claude/settings.local.json
.claude/hooks/
.claude/commands/
```

A Codex adapter should avoid writing Claude-specific paths into Codex projects. Better target:

```text
.less_tokens/
  tools/
  hooks/
  schema/
  state/
  index.db

AGENTS.md
Codex skill fragment, installed wherever the local Codex skill loader expects it
```

If Claude and Codex support are both needed, keep shared code in `.less_tokens/` and put only agent-specific wrappers in the agent's own integration directory.

### Installer

`install.py` should grow an explicit agent selector:

```bash
python3 less_tokens/install.py --agent claude
python3 less_tokens/install.py --agent codex
python3 less_tokens/install.py --agent both
```

Backward compatibility can keep `--agent claude` as the default.

For Codex, installation should:

- copy shared tools/schema/config into `.less_tokens/`;
- optionally build the index;
- append or print a minimal `AGENTS.md` fragment;
- install a Codex skill if a local skill location is known;
- avoid editing Claude settings;
- avoid claiming runtime hook enforcement unless available.

### Hook Payloads

Claude hook scripts parse payloads shaped like:

```python
payload["tool_name"]
payload["tool_input"]
payload["tool_result"]
payload["transcript_path"]
```

Codex should not reuse these scripts directly unless Codex emits the same payload. The right split is:

```text
common logic:
  is_indexed(path)
  should_block_read(path)
  truncate_result(tool, text)
  should_compact(transcript_size)

agent wrapper:
  parse payload
  call common logic
  format response
```

This is the central architectural change needed for a clean port.

### Slash Commands

Claude slash commands such as `/search`, `/build-index`, and `/def` do not map directly to Codex repo behavior.

Codex equivalent:

- scripts with clear commands;
- a local skill that teaches when to use them;
- maybe app/plugin integration later.

Example:

```bash
python .less_tokens/tools/search.py "query"
python .less_tokens/tools/embeddings.py refresh
python .less_tokens/tools/symbols.py SomeSymbol
```

## What Codex Already Does Differently

### Lazy Tool Discovery

`gap.md` identifies Tool/MCP schema overhead as a large fixed cost. Codex already has deferred tool discovery through `tool_search` in this environment. That means the Claude-specific `mcp-prune` direction is less important here.

Codex porting note: document this as a platform win, not a missing feature. A Codex adapter should avoid forcing every possible connector/tool into the context up front.

### Built-In Context Compaction

The Codex environment can compact context automatically when needed. A Claude-style `/compact` reminder may not be useful or available.

Codex porting note: keep transcript-size measurement as observability if available, but do not make `/compact` a central Codex strategy unless Codex exposes that command to the agent.

### Developer Instructions Already Encourage Token-Efficient Exploration

This Codex project environment already instructs the agent to:

- use `rg` before slower search tools;
- parallelize independent file reads;
- keep updates and final answers concise;
- use targeted file links and line references;
- avoid unnecessary full rewrites.

So Codex gains less from "caveman mode" than Claude Code does. It gains more from search/indexing, AGENTS.md hygiene, and noise-file avoidance.

## What Should Not Be Ported As-Is

### Caveman Mode

The exact "Talk like caveman" style is not a good Codex default. Codex has a collaborative coding persona and user-facing progress updates. Forcing primitive prose would conflict with expected behavior and may make engineering communication worse.

Codex-friendly replacement:

```markdown
## Response Budget

Be concise. Prefer direct findings, exact file references, and short verification notes. Avoid restating tool output unless the user asks.
```

The enforcement target should be response length and unnecessary repetition, not a roleplay style.

### Claude Stop Hooks

`caveman-reminder.py` depends on Claude Code Stop hooks and transcript access. Do not assume that exists in Codex.

If Codex exposes a response-review hook later, the portable logic should check:

- filler phrases;
- overlong prose;
- unnecessary full-file code blocks;
- repeated summaries.

Until then, keep it as a style rule or skill guidance.

### Tool Output Truncation Hook

`truncate-output.py` is valuable but depends on intercepting tool results before they enter context. In this Codex environment, normal shell output is already controlled by command choices and `max_output_tokens` parameters.

Codex porting note:

- keep the truncation functions;
- expose them for script wrappers;
- do not claim global tool-output interception unless Codex hook support exists.

### Claude Settings Writes

Do not write `.claude/settings.json` or `.claude/settings.local.json` during a Codex install. That surprises users and affects a different agent.

## Codex-Specific Recommendations

### 1. Create a Codex Skill

Ship a small skill:

```text
skills/less-tokens/SKILL.md
```

It should teach Codex to:

- run semantic search before reading large indexed files;
- use symbol lookup for definitions;
- use `rg --files` or `lean-ls.py` for broad navigation;
- avoid full reads of lockfiles, generated files, binaries, and large data;
- run tight diffs after edits.

The skill should be short. Long strategy docs should stay indexed.

### 2. Add AGENTS.md Fragment Support

The installer should print a proposed fragment instead of blindly editing:

```markdown
## Token Discipline

Use targeted context. Prefer `rg`, `rg --files`, semantic search, and file slices over full-file reads. Do not read generated, binary, lock, or large data files in full; summarize or sample them instead.
```

For projects with strict safety instructions, like this trading repo, automatic insertion needs care. The fragment should never dilute safety rules.

### 3. Make State Directory Agent-Neutral

Replace:

```python
CLAUDE_DIR = BASE / ".claude"
STATE_DIR = CLAUDE_DIR / "state"
```

with:

```python
LESS_TOKENS_DIR = BASE / ".less_tokens"
STATE_DIR = LESS_TOKENS_DIR / "state"
```

Claude wrappers can still point to `.claude/` if needed, but the shared core should not.

### 4. Split Common Logic From Agent Wrappers

Target structure:

```text
less_tokens/
  core/
    config.py
    db.py
    embeddings.py
    search.py
    symbols.py
    guards.py
    truncation.py
    stats.py
  adapters/
    claude/
      hooks/
      commands/
      instructions/
    codex/
      skills/
      instructions/
      hooks/
```

This prevents the Codex port from becoming a copy of Claude scripts with renamed paths.

### 5. Treat Hook Enforcement as Optional Capability

Each strategy should have three layers:

| Layer | Claude | Codex |
|---|---|---|
| Core logic | shared Python | shared Python |
| Workflow | `CLAUDE.md`, slash commands | `AGENTS.md`, skill, scripts |
| Enforcement | Claude hooks | optional Codex hooks if available |

This makes the project honest about what is enforced versus recommended.

## Strategy Mapping

| `less_tokens` Strategy | Claude Mechanism | Codex Port | Status |
|---|---|---|---|
| Vector search | `.claude/tools/search.py`, `/search` | `.less_tokens/tools/search.py`, skill instruction | Strong port |
| Build index | `/build-index`, embeddings tool | script command | Strong port |
| Search before Read | PreToolUse hook | skill + AGENTS rule; hook only if supported | Partial port |
| Caveman mode | `CLAUDE.md` + Stop hook | concise response budget | Adapt, do not copy |
| Tool output truncation | PostToolUse hook | command discipline, wrappers, `max_output_tokens` | Partial port |
| Compaction trigger | transcript hook + `/compact` | rely on Codex compaction unless API exists | Weak port |
| CLAUDE.md pruning | audit + budget hook | AGENTS.md audit + budget | Strong port |
| Symbol lookup | `/def`, `symbols.py` | `symbols.py` script + skill | Strong port |
| Read guard | PreToolUse Read hook | guard script + optional hook | Partial port |
| Listing guard | PreToolUse Bash hook | `rg --files`, `lean-ls.py`, optional wrapper | Partial port |
| Context cache | hook state | uncertain without hook API | Defer |
| MCP pruning | config-time Claude concern | mostly superseded by Codex `tool_search` | Do not prioritize |

## Findings From This Repo

This host repo is currently small and mostly documentation/config. Immediate wins are limited, but the patterns matter before the trading engine grows.

Good candidates for indexing:

- `README.md`
- `AGENTS.md`
- `BACKLOG.md`
- `CHANGELOG.md`
- `docs/**/*.md`
- `config/**/*.yml`

Do not index or dump future generated artifacts:

- market data snapshots;
- account exports;
- large news corpora;
- broker/API responses with sensitive fields;
- binary reports;
- notebooks.

Trading safety note: token-saving automation must never hide evidence needed for trade decisions. Every trade candidate still needs entry, stop/invalidation, target, risk/reward, sizing rationale, and source evidence. If truncation or search omits evidence, the engine should prefer no trade.

## Contribution Notes For `less_tokens`

Suggested upstream contribution:

1. Add a "Codex adapter" design doc based on `multi-agent.md`, but revise it to avoid assuming `.codex/hooks.json` exists.
2. Rename shared internals away from `.claude` paths.
3. Add `--agent codex` and `--agent both` installer modes.
4. Add `AGENTS.md` audit support alongside `CLAUDE.md`.
5. Replace "caveman" as the Codex default with "concise engineering response budget."
6. Document which strategies are enforced, recommended, or unsupported per agent.
7. Add tests that run shared core behavior without Claude hook payloads.

## Minimal Codex MVP

A useful first Codex-compatible release can be much smaller than the Claude install:

```text
.less_tokens/
  tools/search.py
  tools/embeddings.py
  tools/db.py
  tools/symbols.py
  tools/agentsmd_audit.py
  schema/index.sql
  search_config.py
  index.db
```

Plus:

```text
skills/less-tokens/SKILL.md
AGENTS.md fragment printed by installer
```

No hooks are required for the MVP. The MVP proves the shared core works in Codex and avoids misleading users about enforcement.

## Bottom Line

`less_tokens` should become a multi-agent toolkit, not a Claude repo with Codex path substitutions. The durable value is deterministic context selection: search, symbols, guards, audits, and concise outputs. The agent-specific value belongs in thin adapters.

For Codex, the strongest near-term port is:

- `.less_tokens` shared core;
- `AGENTS.md` hygiene;
- a `less-tokens` Codex skill;
- script-based search/symbol/read-guard workflows;
- optional hooks only when Codex exposes a stable hook interface.

## Implementation In This Repo

This project now includes a Codex-specific local port under `.less_tokens/`.

Implemented:

- `.less_tokens/tools/` shared search/index helpers copied from the Claude repo and patched to use `.less_tokens` state/schema paths.
- `.less_tokens/tools/agentsmd_audit.py` for AGENTS.md budget/ref/verbosity checks.
- `.less_tokens/tools/read_guard.py` for explicit noisy-file checks.
- `.less_tokens/tools/lean-ls.py` for compact directory listing.
- `.less_tokens/skills/less-tokens/SKILL.md` as the Codex workflow fragment.
- `AGENTS.md` token-discipline guidance.
- README/CHANGELOG pointers for setup and completed work.
- GitHub Actions and `tests/test_less_tokens_codex.py` coverage for CI-safe Codex port behavior.

Not implemented:

- Claude-style hooks or automatic tool-result interception.
- Automatic installation into a Codex skill loader path; `.codex/skills` was not writable in this workspace, so the skill fragment lives under `.less_tokens/skills/`.
- Default full semantic index refresh/search verification with `fastembed`; dependencies are declared in `.less_tokens/requirements.txt`, and an optional unittest round trip runs when `LESS_TOKENS_RUN_EMBEDDING_TESTS=1` with `numpy` and `fastembed` installed.

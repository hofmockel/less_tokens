# Backlog

## Purpose

This file is the single source of truth for planned work — new features, bug fixes, and improvements that have been identified but not yet started. It exists so that anyone (contributor, maintainer, or user) can see what's coming, understand priorities, and avoid duplicating effort.

## How to use it

**Reporting a bug or requesting a feature?**
Open a [GitHub Issue](../../issues) using the appropriate template. If the maintainer accepts it, it will be added here.

**Picking up work?**
Choose an item from High Priority, assign yourself in the corresponding Issue, and open a PR when ready. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.

**When work ships:**
Remove the item from this file and add an entry to [CHANGELOG.md](CHANGELOG.md) under `[Unreleased]`.

**Priority definitions:**

| Level | Meaning |
|---|---|
| **High** | Clear value, known implementation path — good first targets |
| **Medium** | Important but less urgent; may need more design thought |
| **Low / Ideas** | Worth tracking, no commitment to timeline |
---

## Model Strategy: Optimise for Specific Models, Work Everywhere

The project currently hardcodes one embedding model (`BAAI/bge-small-en-v1.5`, 384-dim) and has no awareness of which LLM is acting as the agent. The goal is a tiered approach: use the best available model when conditions allow, degrade gracefully when they don't.

### Current constraints

- `MODEL` and `DIM` are hardcoded constants in `tools/embeddings.py:39-40`.
- `search.py:44` reshapes all stored vectors using the hardcoded `DIM=384`. A model producing a different dimension silently corrupts results.
- The `embedding_model` column already exists per-row in `index.db` — the schema was designed for multi-model support but the code hasn't caught up.
- Changing the model invalidates every vector in the index and requires a `--full` refresh.

---

### Embedding model tier ladder

Define four tiers in priority order. The system selects the highest tier available at index-build time and stores the chosen model name in `embedding_model` per row.

| Tier | Model | Dim | Size | Requires |
|---|---|---|---|---|
| **0 — Keyword fallback** | BM25 / TF-IDF (stdlib) | — | 0 MB | Nothing — pure Python |
| **1 — Local small** *(current default)* | `BAAI/bge-small-en-v1.5` | 384 | ~130 MB | `fastembed` |
| **2 — Local large** | `BAAI/bge-large-en-v1.5` | 1024 | ~1.2 GB | `fastembed` |
| **3 — API** | Voyage `voyage-3-lite`, OpenAI `text-embedding-3-small`, Cohere `embed-v3` | 1024–1536 | 0 MB local | API key + network |

Work items:

- **Move `MODEL` and `DIM` to `search_config.py`** — replace the hardcoded constants in `embeddings.py:39-40` with config variables so users can select a tier without editing tool source. `search.py` must read `DIM` from config (or from the stored `embedding_model` row) rather than a hardcoded literal. (`tools/embeddings.py:39-40`, `tools/search.py:44`)

- **Keyword fallback (Tier 0)** — when `fastembed` is not installed or the model download fails, fall back to a stdlib BM25/TF-IDF search over raw chunk text. Quality is lower but the system remains usable in air-gapped environments, minimal Docker images, or first-run before the model cache is warm. Exit code and output format identical to normal search so hooks require no changes.

- **Pluggable API embedding backend (Tier 3)** — add a `EMBEDDING_BACKEND` config variable accepting `"fastembed"` (default), `"openai"`, `"voyage"`, or `"cohere"`. Each backend is a small adapter in `tools/backends/` that implements `embed(texts) -> np.ndarray`. API key read from environment variable; no keys stored in config files.

- **`embeddings.py switch-model`** — a subcommand that changes `EMBEDDING_MODEL` in `search_config.py` and immediately runs `refresh --full`, preventing the silent dimension mismatch that occurs when the model is changed manually. Prints a clear warning about re-index time before proceeding.

---

### Agent LLM context-window awareness

The optimal number of chunks to return (`k`) and the chunk character ceiling depend on how large the agent's context window is. A model with a 8K window needs different defaults than one with 200K.

- **`AGENT_MODEL` config variable** — add an optional `AGENT_MODEL` string to `search_config.py` (e.g. `"claude-sonnet-4-6"`, `"gpt-4o-mini"`). When set, `search.py` uses a lookup table to select default `k` and warn if chunks risk filling the window. When unset, current defaults apply unchanged.

- **Context-window lookup table** — ship a small `tools/model_profiles.py` mapping known model IDs to context window size and recommended `k` / `MAX_CHUNK_CHARS` values. Covers Claude (Haiku / Sonnet / Opus), GPT-4o family, and Gemini. Easily extended by users for new models.

- **Per-model caveman pattern tuning** — different LLMs have different verbosity signatures. `caveman-reminder.py` currently matches Claude-style filler phrases. The pattern list should be configurable in `search_config.py` so users running Copilot or GPT-based agents can add model-specific patterns without editing hook source.

---

### Graceful degradation

The system should never hard-block an agent when a component is unavailable. Defined degradation ladder:

| Condition | Current behaviour | Target behaviour |
|---|---|---|
| `fastembed` not installed | `RuntimeError`, refresh aborts | Fall back to Tier 0 keyword search with a one-time warning |
| Model download fails (offline) | Exception, index empty | Use last successfully cached model; warn if none cached |
| `index.db` missing or empty | `search-first` gate fires, no results | Gate lifts automatically; agent proceeds with `Read` and a one-time advisory |
| DB locked by concurrent refresh | `sqlite3.OperationalError` | Retry once with 500ms backoff; return stale results on second failure with a warning |
| API embedding backend unreachable | Unhandled exception | Fall back to next available tier, log the failure to `.less_tokens/state/embed-errors.log` |

- **Implement the degradation ladder** — each condition above needs an explicit handler in `tools/embeddings.py` and `tools/search.py` that catches the failure, emits a structured warning to stderr, and continues at the next tier rather than propagating an exception.

---
## Multi-Agent Expansion

### What is already agent-agnostic

Code inspection shows a clean split. Everything in `tools/` has zero Claude dependencies:

| Component | Claude-specific? | Notes |
|---|---|---|
| `tools/embeddings.py` | No | Pure Python chunking + fastembed + SQLite |
| `tools/search.py` | One line | Writes state to `.claude/state/last-search` — trivially abstracted |
| `tools/db.py` | No | Pure SQLite helper |
| `tools/search_config.py` | No | Config only; `.claude/` appears as an exclusion rule, not a dependency |
| `schema/index.sql` | No | Pure SQL |
| `caveman/caveman.md` | Format only | The instruction concept works in any LLM system prompt; only the filename/location is Claude-specific |
| `hooks/` (all three) | Yes | Entirely built on Claude Code's `PreToolUse`/`PostToolUse` protocol, stdin JSON, exit-code 2, and `.claude/settings.local.json` |
| `install.py` | Partially | Copies to `.claude/hooks/`; references `CLAUDE.md` and `settings.local.json` |

The `tools/` core is already a portable library. Only the hook layer is Claude-specific.

---

### Prerequisite: decouple state file from `.claude/`

Before any adapter can be built, `search.py` must stop writing to `.claude/state/last-search`. The state directory should move to a neutral location (e.g. `.less_tokens/state/`) configured in `search_config.py`, with `.claude/state/` as the default for backwards compatibility. This is the only code change needed to make `tools/` fully agent-agnostic. (`tools/search.py:73–75`, `hooks/search-first.py:43`)

---

### Adapter: Cursor

Cursor reads instruction rules from `.cursor/rules/*.mdc` and supports MCP servers. Two integration points:

- **Rules file** — `adapters/cursor/search-before-read.mdc`: equivalent of the CLAUDE.md "Search Before Read" section in Cursor's rules format. Instructs the agent to call `search.py` before opening indexed files.
- **MCP server** — wrap `search.py` as a one-tool MCP server (`adapters/cursor/mcp-search/`). Cursor can invoke it natively, removing the need for any hook machinery. The tool definition accepts a query string and returns the top-k chunks as JSON.
- **Caveman adapter** — `adapters/cursor/caveman.mdc`: terse output instruction in Cursor rules format.

**New files:** `adapters/cursor/search-before-read.mdc`, `adapters/cursor/caveman.mdc`, `adapters/cursor/mcp-search/server.py`

---

### Adapter: GitHub Copilot

Copilot reads a repository-level instruction file at `.github/copilot-instructions.md`. No hook system exists, so the integration is instruction-only:

- **Instructions file** — `adapters/copilot/copilot-instructions.md`: search-before-read and caveman instructions in Copilot's expected format. Users append or symlink into `.github/copilot-instructions.md`.
- **Limitation**: no equivalent of `PreToolUse` exists in Copilot, so the search-first gate cannot be enforced programmatically — it is advisory only.

**New files:** `adapters/copilot/copilot-instructions.md`

---

### Adapter: Cline / Roo

Cline and Roo read project rules from `.clinerules` (Cline) or `.roo/rules/*.md` (Roo). Both support custom tool definitions that can call local scripts:

- **Rules file** — `adapters/cline/clinerules`: search-before-read and caveman instructions.
- **Custom tool** — Cline supports MCP tool definitions; same MCP server built for Cursor can be reused.

**New files:** `adapters/cline/clinerules`, `adapters/roo/rules/search-before-read.md`

---

### Adapter: Continue.dev

Continue has a context provider system (`~/.continue/config.json`) that can call arbitrary scripts and inject their output into the prompt. This maps cleanly onto `search.py`:

- **Context provider** — `adapters/continue/search-provider.py`: a Continue custom context provider that calls `search.py` with the user's query and returns chunks. Users register it in `config.json`.
- **System message** — `adapters/continue/system-message.md`: caveman and search-before-read instructions for Continue's `systemMessage` field.

**New files:** `adapters/continue/search-provider.py`, `adapters/continue/system-message.md`, `adapters/continue/README.md`

---

### Adapter: Generic Python / LLM API

For teams calling the Anthropic, OpenAI, or Gemini API directly (LangChain, LlamaIndex, AutoGen, CrewAI, or raw SDK):

- **Importable library** — expose `from less_tokens import search` so any agent framework can call it as a tool without subprocess overhead. Requires packaging `tools/` as a proper module with `__init__.py`.
- **Tool definition templates** — `adapters/api/tool_definitions.py`: ready-made tool schemas in Anthropic, OpenAI, and Gemini function-calling formats so the search function can be registered as a callable tool in one line.
- **Caveman system prompt** — `adapters/api/system_prompts.py`: `CAVEMAN_PROMPT` string constant importable into any system prompt construction.

**New files:** `tools/__init__.py`, `adapters/api/tool_definitions.py`, `adapters/api/system_prompts.py`

---
## Bug-Hunt Protocol

How to decide when to run another hunt vs stop and fix. Eyeball-driven (no metric scripts); the rubric below keeps the eyeball calibrated.

### Severity rubric (assign per bug at intake)

| Tier | Definition | Example |
|---|---|---|
| **data-loss** | Wrong number lands in IRS-grade ledger, FIFO, wash-sale, or P&L. Real money at stake. | Lockouts dict collapse hides longer restriction; same-day rebuy missed by report adherence check. |
| **silent** | Behavior is wrong but no immediate money impact; numbers reported are misleading. | Correlation aligns by index not date; trailing_return falls back to earliest close on IPOs. |
| **ux** | Tool gives bad signal, false reassurance, or noise that trains the operator to ignore the gate. | parity-check baselines drift daily; universe.py refresh prints UPD on every row. |
| **cosmetic** | Wording / formatting / log-line issue. No functional impact. | (none documented yet — surface only if encountered.) |

### Three signals to assess after each hunt

1. **Severity slide** — what's the median tier of THIS round vs the previous? Going `data-loss → silent → ux → cosmetic` means the high-value surface is exhausted.
2. **Overlap rate** — when running a hunt, do NOT pre-exclude the existing bug list (let the agent rediscover). Then count: of the bugs surfaced, what fraction matches a bug already in the table by file:line or paraphrase? Rising overlap = saturated surface.
3. **File coverage** — cumulative distinct files where bugs have been found, vs the high-yield target list (`wash.py`, `add-fills.py`, `rh-sync.py`, `dataio.py`, `db.py`, `alerts.py`, `state.py`, `snapshot-state.py`, `refresh-prices.py`, `refresh-earnings.py`, `recalc-coverage.py`, `sell-check.py`, `pnl.py`, `report.py`, `pre-buy-check.py`, `momentum.py`, `stress.py`, `size.py`, `weekly-budget.py`, `universe.py`, `universe-coverage.py`, `discover.py`, `lockout-cost.py`, `journal*.py`, `parity-check.py`, `validate-ledger.py`, `backup.py`, `restore-check.py`, `embeddings.py`, `search.py`, `commit-hygiene.py`, `doc-drift.py`, `gen-tools-readme.py`, `secret-scan.py`, `app/scan.py`, `app/layers.py`, `schema/portfolio.sql`, `schema/migrations/*.sql`). When new hunts stop landing on new files, surface is covered.

### Stop rule (all three required)

- Median severity of last round ≤ `ux` (no `data-loss` or `silent` finds), AND
- Overlap rate with prior rounds ≥ 60% (mostly rediscovering known bugs), AND
- Cumulative file coverage ≥ 80% of the high-yield list above.

If 2 of 3 hold, run one more round. If ≤1 of 3, keep hunting.

### How to run a hunt (one-shot agent prompt template)

```
Find 10 real, undocumented bugs in /Users/michael/Documents/GitHub/AIPortfolio/.
- Read backlog.md ## Bugs section first; do NOT pre-exclude (overlap is a signal we want to measure).
- Bug definition: logic / silent failure / state / financial-logic / chain-ordering / docstring drift / schema / auth-UX / encoding.
- NOT bugs: features, refactors, "add tests", performance unless incorrect, anything in non-Bugs backlog sections, backup-section variants (deferred per memory), token instrumentation.
- Method: search-first for indexed files; read whole files for high-yield targets; verify each candidate by tracing or sqlite3 query; rank by severity tier.
- Output: 10 bugs in `**Bug N: title** (file:line)` + What/Why/Repro/Fix format, ≤6 lines each. If <10 solid, surface fewer + say so.
```

After the agent returns, the operator: (1) assigns each a tier, (2) checks each against the existing table for overlap, (3) scores the three signals, (4) applies the stop rule.
---

## Installer: Non-Destructive / Additive Behaviour

The installer currently has several places where re-running it or upgrading can clobber user work. All changes should be **additive by default** — existing customisation is never lost without an explicit opt-in. The six specific cases are documented below as individual work items.

- **`copy_tree --force` silently overwrites customised hook and tool files** — a user who has edited `search-first.py` or `search_config.py` has no warning before `--force` discards their changes. Fix: before overwriting any file that differs from the source, print a diff summary and require an explicit `--overwrite-modified` flag distinct from `--force` (which should only apply to unmodified files). (`install.py:55–76`)

- **`search_config.py` is replaced wholesale instead of merged** — on an upgrade, any new config variables added to the source `search_config.py` (e.g. `WINDOW_SECONDS`, `MAX_TOOL_OUTPUT_CHARS`) will never reach projects that already have the file, and `--force` would wipe user-set values. Fix: parse the existing file's variable names, inject only variables that are absent, leave existing values untouched. This is an upsert at the variable level, not the file level. (`install.py:145`, `tools/search_config.py`)

- **`init_db` has no schema migration path** — `db.py init` runs the full `index.sql` with `CREATE TABLE IF NOT EXISTS`, so it is safe on re-run, but any new columns or indexes added in a future schema version will silently not be applied to existing databases. Fix: introduce a `schema_version` table (already defined in `index.sql` but never written to), record the current version on init, and apply `ALTER TABLE` migration scripts on upgrade. (`tools/db.py:45–51`, `schema/index.sql:4–7`)

- **`.claude/settings.local.json` hook wiring is entirely manual** — the installer prints a block of JSON for the user to paste but does not check whether the hooks are already wired. A second install produces duplicate hook entries if the user pastes again. Fix: read the existing `settings.local.json` if present, merge each hook entry by `matcher + command` identity (upsert), and write the result back — or print "already wired" when the entry is found. (`install.py:192–194`)

- **`caveman/caveman.md` append instruction will duplicate the section on re-run** — the next-steps output tells the user to run `cat caveman/caveman.md >> CLAUDE.md`, but there is no guard against running that twice. Fix: the installer (or a companion `caveman-install.py` helper) should check whether the caveman section heading already appears in `CLAUDE.md` before appending; skip with "already present" if found. (`install.py:196–197`)

- **`--force` applies to all files uniformly with no granularity** — a user upgrading hook files while keeping their customised `search_config.py` has no way to do so; `--force` is all-or-nothing. Fix: replace `--force` with targeted flags: `--force-hooks` (overwrite `.claude/hooks/`), `--force-tools` (overwrite `tools/`), `--force-config` (overwrite `search_config.py`). Keep `--force` as a shorthand for all three but document the granular options prominently. (`install.py:119–120`, `install.py:144–150`)

---

## Bugs

Confirmed defects found by code inspection. Each has a specific file and line reference.

- **`schema/index.sql` comment describes wrong model and dimension** — line 17 reads `-- float32[1024], voyage-3-lite output` but the actual model is `BAAI/bge-small-en-v1.5` producing 384-dim vectors. Misleads anyone reading the schema. (`schema/index.sql:17`)

- **`chunk_changelog` regex won't match this repo's own CHANGELOG** — the splitter expects `## YYYY-MM-DD` but Keep a Changelog format (and our `CHANGELOG.md`) uses `## [0.2.0] - 2026-05-03`. Every version section silently falls back to `chunk_markdown`, losing the date-based key structure. (`tools/embeddings.py:147`)

- **`search.py` comment references `voyage_embed`** — line 45 reads `# Embeddings already normalized in storage; query normalized in voyage_embed.` — `voyage_embed` doesn't exist; the function is `embed`. Stale copy-paste from a previous implementation. (`tools/search.py:45`)

- **`search-first.py` docstring still shows `python3` in hook config** — the docstring example on lines 19–23 still uses `"command": "python3 .claude/hooks/search-first.py"` which breaks on Windows. The runtime message was fixed but the docstring was not. (`hooks/search-first.py:22`)

- **`is_indexed()` exclusion logic differs between `search-first.py` and `index-refresh.py`** — `search-first.py` uses `("/" + d) in ("/" + rel) or rel.startswith(d)` which matches excluded names anywhere in the path; `index-refresh.py` uses only `rel.startswith(d)`. The two hooks will disagree on whether mid-path excluded directories are blocked. (`hooks/search-first.py:49`, `hooks/index-refresh.py:37`)

- **`search_config.py` default `INDEXED_SOURCE_DIRS` includes `"app/"` which is never created by the installer** — fresh install targets will have `health` report a gap for every file under `app/` until the user edits the config. The default should only include directories the installer actually creates (`tools/`, `schema/`). (`tools/search_config.py:38`)

- **`db.py` `verify()` interpolates table name directly into SQL** — `f"SELECT COUNT(*) FROM {r[0]}"` constructs SQL from `sqlite_master` output without sanitization. Low real-world risk but bad practice; should use a whitelist or quoted identifier. (`tools/db.py:64`)

- **`index-refresh.py` imports `VENV_PY` with a needless alias** — `VENV_PY as _VENV_PY` is immediately re-assigned to `VENV_PY = _VENV_PY` on the next line. The alias serves no purpose and adds confusion. (`hooks/index-refresh.py:27–29`)

---

## Features

New capabilities identified as logical extensions of the current design.

- **`search.py --min-score`** — add a score threshold flag (e.g. `--min-score 0.5`) to filter out low-confidence results; prevents Claude from acting on semantically unrelated chunks that happen to rank in the top-k

- **`VIRTUAL_ENV` environment variable fallback in venv detection** — `detect_venv()` in `install.py` and `_venv_python()` in `search_config.py` should check the `VIRTUAL_ENV` env var first, since it's set by `activate` and reliably points to the active venv on all platforms

- **`embeddings.py refresh --dry-run`** — show which chunks would be added, updated, or deleted without writing to `index.db`; useful for verifying config changes before committing

- **`search.py` result deduplication** — when two top-k results come from the same `source_path`, collapse them into one entry and use the saved tokens for an additional unique file; avoids spending context budget on near-duplicate chunks

- **Expose `WINDOW_SECONDS` in `search_config.py`** — the 5-minute search-gate window is hardcoded in `search-first.py`; moving it to `search_config.py` lets users tune the aggressiveness of the gate without editing hook source code

- **`install.py` generates a ready-to-paste `settings.local.json` block** — after detecting the venv, print a complete, correctly-patched JSON snippet with the resolved python path substituted in, so users can paste it directly without manual editing

- **`embeddings.py` file-watcher mode** — a `watch` subcommand using `watchdog` that monitors `INDEXED_SOURCE_DIRS` and triggers incremental refresh automatically on save, as an alternative to the PostToolUse hook for non-Claude workflows

- **Multi-file chunk context** — when returning a function chunk, optionally prepend the containing class or module docstring so Claude has the structural context needed to understand the chunk without a follow-up Read

- **`search.py` query history log** — append each query and its top result score to `.claude/state/search-history.log` so maintainers can audit what Claude searched for and identify queries that consistently return poor results

- **`install.py --check`** — verify that a previous install is still valid: venv exists, fastembed is installed, `index.db` is present, hooks are wired in `settings.local.json`; exits non-zero with a specific message for each failure

---

## Documentation Improvements

Gaps and inaccuracies found in existing docs.

- **No troubleshooting section in README** — the three most common failure modes (fastembed download fails on first run, wrong venv path in `search_config.py`, empty index returning no results) have no documented recovery steps anywhere

- **README shows separate JSON blocks for each hook** — the wiring section presents the search hooks and the caveman hook in two separate `settings.local.json` snippets; users must manually merge them and JSON merging is a common source of errors; show one complete unified block

- **`index-refresh.log` is never mentioned** — background refresh writes to `.claude/state/index-refresh.log` but this path appears nowhere in the README or tool help text; users have no way to diagnose silent refresh failures without reading source code

- **`embeddings.py` module docstring uses `python3` in usage examples** — lines 13–16 show `python3 tools/embeddings.py refresh` which doesn't work on Windows and ignores the venv requirement; should use `<venv-python> tools/embeddings.py refresh`

- **CONTRIBUTING.md says "test manually" with no specifics** — the verification step doesn't describe what a passing manual test looks like; should list the four concrete commands to run (`install.py`, `search_config.py` edit, `refresh`, `search.py`, hook fire)

- **`search_config.py` inline comment for `EXCLUDED_DIR_PREFIXES` doesn't explain the difference from `EXCLUDED_DIR_NAMES`** — both variables exclude directories but via different mechanisms (prefix match on full path vs. bare name match on any path component); the distinction trips up new users when their exclusions don't work as expected

- **README doesn't document `WINDOW_SECONDS` or how to change it** — the 5-minute search-gate window is mentioned in passing ("a search ran in the last 5 minutes") but there's no explanation that it's hardcoded or where to change it

- **No explanation of what Claude does when `search.py` returns no results** — the README mentions the fallback conditions for using `Read` directly but doesn't explain whether the gate is automatically lifted or whether Claude must explicitly detect the empty result

- **CHANGELOG uses Keep a Changelog version format but `chunk_changelog` expects date-only headers** — there is no note in the CHANGELOG or in `embeddings.py` that the chunker's date-pattern regex won't match the `## [version] - date` format; developers adding changelog entries won't know the index is silently not splitting them correctly

- **README "Repository layout" section is missing `caveman/caveman.md` description** — the file tree lists `caveman/caveman.md` with the label `# CLAUDE.md snippet for terse output` but doesn't explain *how* it is activated (append to CLAUDE.md) the way the other files explain their purpose inline

---

## Proposed Strategies

Candidate token-reduction approaches not yet implemented. Each targets a different part of the token budget. Evaluate and promote to High Priority once design is agreed.

### Strategy 6 — Tiered Model + Effort

**Concept:** Token cost has two independent levers — the *model* chosen and the *effort* the agent applies (output length, reasoning depth, tool call count). These levers are orthogonal and compound: routing a mechanical task to a fast/cheap model *and* constraining effort multiplies the saving. The tier abstraction maps task complexity to the right combination of both, regardless of which provider or model family is in use.

**Three abstract tiers:**

| Tier | Effort | Trigger examples |
|---|---|---|
| **L1 Mechanical** | Minimal — one confirmation, no tables, no summaries | File operations, index refresh, status checks, renames |
| **L2 Rules** | Medium — result + brief reasoning, tables only if ≥3 rows | Search queries, config edits, doc updates, targeted bug fixes |
| **L3 Planning** | Full — analysis, options, tradeoffs | Architecture decisions, new strategies, refactors, reviews |

**Provider profiles** — each profile maps abstract tiers to concrete model IDs. Users set `PROVIDER_PROFILE` in `search_config.py`; the system resolves L1/L2/L3 to real model names at runtime:

| Tier | Anthropic | OpenAI | Google | Mistral | Local (Ollama) |
|---|---|---|---|---|---|
| L1 | `claude-haiku-4-5` | `gpt-4o-mini` | `gemini-2.0-flash` | `mistral-small` | `llama3.2:3b` |
| L2 | `claude-sonnet-4-6` | `gpt-4o` | `gemini-2.0-pro` | `mistral-medium` | `llama3.1:8b` |
| L3 | `claude-opus-4-7` | `o3` | `gemini-2.0-ultra` | `mistral-large` | `llama3.1:70b` |

**Proactive suggestion:** Before each task the agent emits one line stating the recommended tier — but only when it changes from the prior turn: `"L1 — recommend fast model, minimal effort."` Provider-neutral wording so the hint works regardless of which profile is active. Silence when the tier holds.

**Model-switching mechanism varies by provider/tool:**

| Environment | How to switch |
|---|---|
| Claude Code | `/model <alias>` slash command |
| Cursor | Model picker in UI; `model` field in `.cursor/rules` |
| OpenAI API | `model` parameter per request |
| Ollama | `model` parameter or env var |
| LangChain / LlamaIndex | Swap the `llm=` constructor argument |

**Implementation:**

- `tools/provider_profiles.py` — the canonical profile registry. Ships with Anthropic, OpenAI, Google, Mistral, and Ollama profiles. Users add custom profiles or override individual tier entries without editing the file (via `search_config.py` overrides).
- `caveman/tier-matrix.md` — task-type → tier mapping, provider-neutral. Appended to the agent's system prompt / `CLAUDE.md` like `caveman.md`.
- `search_config.py` additions — `PROVIDER_PROFILE: str = "anthropic"`, `AGENT_TIER_HINTS: bool = True`, plus an optional `TIER_OVERRIDES` dict for per-project customisation.
- Extends the `AGENT_MODEL` variable already proposed in the Model Strategy section — tier selection resolves both model and effort ceiling from a single L1/L2/L3 declaration.

**Expected savings:** L1 tasks on a fast model at minimal effort cost 10–20× less per turn than the equivalent on a flagship model at full effort. On a mixed session the blended reduction is 50–70%.

**New files:** `tools/provider_profiles.py`, `caveman/tier-matrix.md`
**Modified files:** `search_config.py`, `caveman/caveman.md` (cross-reference), `adapters/api/system_prompts.py` (tier hint prompt)

---

### Strategy 3 — Tool Output Truncation

**Problem:** Tool results (Bash output, file reads, web fetches) can dump thousands of tokens into the context even when only a few lines are relevant. Claude currently receives the full output every time.

**Approach:** A PostToolUse hook that intercepts tool results before they are appended to the conversation, measures character length, and truncates to a configurable ceiling (e.g. 2,000 chars) with a `[truncated — N chars omitted]` marker. For Bash, keep the first N lines and the last M lines (head+tail) so errors at the bottom are preserved. Users configure the ceiling in `search_config.py`.

**Expected savings:** 40–80% of tool-output tokens on verbose commands (`pip install`, `git log`, test runners). No model download required; pure string slicing.

**New files:** `hooks/truncate-output.py`, one new config variable `MAX_TOOL_OUTPUT_CHARS`.

---

### Strategy 4 — Prompt Caching

**Problem:** On every Claude Code session the system prompt, `CLAUDE.md`, and any large context blocks (architecture docs, schema files) are re-sent in full, consuming thousands of input tokens even though they haven't changed.

**Approach:** Structure the system prompt and `CLAUDE.md` to take advantage of [Anthropic's prompt caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching) — place stable, large blocks at the top of the context in the cacheable position. Provide a `cache-primer.py` script users run at session start to warm the cache with their most-read files, so subsequent calls hit the 5-minute cache window instead of re-encoding. Document the cache TTL and how to structure CLAUDE.md for maximum hit rate.

**Expected savings:** Up to 90% cost reduction on the cached portion of input tokens for sessions longer than one turn. Cache hits are also ~2× faster to process.

**New files:** `cache/cache-primer.py`, `cache/README.md` with CLAUDE.md structuring guidance.

---

### Strategy 5 — Conversation Compaction Trigger

**Problem:** As a Claude Code session grows, the conversation history accumulates and input tokens compound with every turn. Users typically don't compact until Claude starts degrading or they hit a wall — by which point thousands of tokens have already been wasted.

**Approach:** A PostToolUse hook that estimates the current conversation size by counting characters in `.claude/state/` session logs and comparing against a configurable threshold. When the threshold is crossed, it exits with code 2 and a message instructing Claude to run `/compact` before the next tool call. This turns compaction from a reactive emergency into a proactive, tunable maintenance step.

**Expected savings:** Highly variable — depends on session length and how much of the history is compactable — but typically 50–70% reduction in input tokens for sessions longer than ~30 turns.

**New files:** `hooks/compact-trigger.py`, one new config variable `MAX_SESSION_CHARS`.

---

## High Priority

### Vector Search

- **Multi-repo indexing** — support indexing across multiple project roots so a single search spans related repos (monorepo support)
- **Stale index warning** — detect when indexed files have changed since last refresh and surface a warning in `search.py` output before results
- **Configurable chunk size** — expose `MAX_CHUNK_CHARS` in `search_config.py` so users can tune for their model's context window
- **TypeScript / JavaScript chunking** — add a `chunk_js` strategy (function-level, like `chunk_python`) for projects with `.ts` / `.js` source

### Caveman Mode

- **Calibrated verbosity levels** — replace binary caveman on/off with a 1–5 verbosity dial in `search_config.py`; level 1 = full caveman, level 5 = normal prose
- **Per-task exemptions** — allow CLAUDE.md to declare specific task types (e.g., user-facing copy, PR descriptions) that bypass caveman mode

### Installer

- **Auto-update `search_config.py`** — after detecting the venv, patch `VENV_PY` and `INDEXED_SOURCE_DIRS` in place rather than just printing the line
- **`install.py --update`** — re-copy hook and tool files without touching `search_config.py` or `index.db` (safe upgrade path)

---

## Medium Priority

### Observability

- **Search quality metrics** — log query, top result score, and result count to `.claude/state/search.log` so users can audit what Claude is finding
- **Token savings estimate** — after each search, print an estimated token delta vs. reading all matched files in full
- **Dashboard command** — `embeddings.py stats --verbose` showing index age, chunk count by source type, and estimated coverage

### Developer Experience

- **`pytest` test suite** — unit tests for `chunk_python`, `chunk_markdown`, `is_indexed`, and the incremental refresh hash logic
- **CI: test on Python 3.9 / 3.11 / 3.12** — GitHub Actions matrix to catch version regressions early
- **`pre-commit` config** — add `ruff` and `pyright` hooks so contributors get linting feedback before pushing

### Documentation

- **Animated GIF demo** — screencast showing a before/after: full Read vs. search returning targeted chunks
- **"Porting guide" doc** — step-by-step walkthrough of adapting `search_config.py` for a new project type (Django, Next.js, Rust)
- **Token savings benchmarks** — documented measurements on a real codebase showing actual input/output token reduction

---

## Low Priority / Ideas

- **Embeddings model swap** — make the model name configurable in `search_config.py`; document the dimension change requirement
- **Remote index option** — store `index.db` in S3 / R2 for teams sharing an index across machines
- **VS Code extension** — surface `search.py` results in the editor sidebar as a complement to the Claude Code hook
- **`search.py` interactive REPL** — `search.py --interactive` for rapid exploratory querying during development
- **Automatic `INDEXED_SOURCE_DIRS` detection** — inspect the repo and suggest dirs based on file type distribution

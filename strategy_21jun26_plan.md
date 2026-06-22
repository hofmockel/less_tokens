# Token Budgeter + Relevance Gate Implementation Plan

## Goal

Build a new **budget-native context control system** for `less_tokens`.

The system should decide, before context reaches Claude or Codex:

- what context is worth paying for,
- how many tokens each context class may spend,
- which context candidates are relevant enough to include,
- what should be sliced, summarized, cached, deferred, or rejected,
- how Claude and Codex can run simultaneously without duplicating waste,
- how much was saved and what quality risk was introduced.

This is an innovation-first plan. Existing hooks, stats, layouts, and behaviors are inputs, not constraints. Keep pieces that are still the best path. Replace pieces that make the new system harder, weaker, or less measurable.

## Innovation Policy

1. **Best system wins**
   Prefer the cleanest budget/relevance architecture over backward compatibility. If an old hook, stats format, state file, or install layout fights the new model, replace it.

2. **Claude and Codex remain first-class**
   Innovation-first does not mean single-agent. The new design must support Claude, Codex, and `--agent both` as peers using one shared policy engine.

3. **Compatibility is optional, continuity is not**
   We do not need old report formats or old internal APIs. We do need installs to remain understandable, recoverable, and safe for users.

4. **Policy lives in one core**
   Claude and Codex adapters should translate payloads and messages only. Budget policy, relevance scoring, event schema, and enforcement rules live in shared code.

5. **Measure reality, not vanity**
   Stats should answer: what was considered, what was selected, what was rejected, what was saved, and whether the decision helped. Replace old savings counters with budget-native telemetry.

6. **Gate context before trimming output**
   Truncation remains useful, but the strategic win is deciding what context deserves entry before model calls and tool results inflate the transcript.

7. **Fail open, but record the failure**
   If scoring, token counting, locking, or state loading fails, allow the agent to continue and log the failure as a telemetry event.

## Target Architecture

### Core Package

Create a new shared package:

```text
agents/common/budget/
  __init__.py
  adapters.py
  candidates.py
  config.py
  decisions.py
  estimator.py
  events.py
  gate.py
  policy.py
  state.py
  summarizer.py
```

Responsibilities:

- `adapters.py`
  - Normalize Claude and Codex hook payloads.
  - Replace or supersede the current `agents/common/hooks/payload.py` if the new event model needs richer metadata.

- `candidates.py`
  - Define `ContextCandidate`.
  - Represent files, slices, search hits, diffs, tool outputs, summaries, instructions, and session state with one schema.

- `config.py`
  - Load budget config.
  - Resolve model, agent, project, and mode-specific settings.

- `decisions.py`
  - Define `BudgetDecision`.
  - Standardize `allow`, `warn`, `block`, `trim`, `summarize`, `defer`, and `replace`.

- `estimator.py`
  - Estimate tokens cheaply by default.
  - Allow optional provider tokenizers later.

- `events.py`
  - Own v2 telemetry schema.
  - Replace old performance stats event formats.

- `gate.py`
  - Score relevance.
  - Select candidates by budget.
  - Produce replacement suggestions.

- `policy.py`
  - Apply mode-specific enforcement.
  - Own the rules for budget pressure, category caps, and hard stops.

- `state.py`
  - Store per-agent session state and shared aggregate telemetry.
  - Handle locking, failure recovery, and stale state cleanup.

- `summarizer.py`
  - Deterministically summarize logs, diffs, directory listings, and session state where possible.
  - Defer LLM-generated summaries unless an agent explicitly performs them.

### Hooks As Transport

Existing hooks become transport points into the budget engine. They should be thin enough that replacing one does not change policy.

Hook categories:

- pre-read gate,
- pre-search gate,
- post-output gate,
- post-edit cache invalidation,
- compaction pressure trigger,
- report generation.

Existing files under `agents/common/hooks/` can either:

- call the new budget package,
- be replaced by wrappers,
- or be retired if their behavior is subsumed cleanly.

No special effort should be spent preserving old internal function names.

## Budget Model

### Token Estimation

Start with:

```text
estimated_tokens = ceil(character_count / 4)
```

Use conservative multipliers by content type:

```json
{
  "plain_text": 1.0,
  "code": 0.9,
  "json": 1.15,
  "logs": 1.2,
  "markdown": 1.0,
  "diff": 1.1
}
```

Reason: exact tokenizers add dependency and model-specific complexity. The first version needs fast, local, predictable gating.

### Default Budget

Default `.less_tokens/config/budget.json`:

```json
{
  "version": 2,
  "mode": "observe",
  "token_estimator": "chars_div_4",
  "total_context_tokens": 24000,
  "reserved_response_tokens": 4000,
  "relevance_threshold": 0.35,
  "replacement_required_for_blocks": true,
  "categories": {
    "instructions": 3000,
    "current_request": 2000,
    "session_summary": 3000,
    "retrieved_context": 10000,
    "tool_output": 4000,
    "diffs": 3000,
    "agent_state": 2000
  },
  "hard_caps": {
    "full_file_read": 3000,
    "single_tool_output": 2500,
    "directory_listing": 1000,
    "unscored_context": 1200
  },
  "agent_overrides": {
    "claude": {},
    "codex": {}
  }
}
```

Modes:

- `observe`: record decisions only.
- `advise`: print concise alternatives, no blocking.
- `enforce`: block high-confidence waste with replacement actions.
- `strict`: block over-budget context unless explicitly exempted.

Drop `off` as a core mode. A user can disable installation or hooks. The product should optimize for active token control.

## Relevance Gate

### Candidate Types

The gate ranks:

- exact file references,
- stack trace paths,
- current user-mentioned symbols,
- vector search hits,
- exact symbol matches,
- grep results,
- recent edited files,
- current diff,
- failing test output,
- prior tool output,
- session summary,
- instructions and project guidance.

### Scoring

Initial score:

```text
score =
  explicit_reference * 0.25
  + semantic_similarity * 0.25
  + lexical_match * 0.20
  + recency * 0.15
  + structural_importance * 0.10
  + failure_relevance * 0.05
```

Definitions:

- `explicit_reference`: file, symbol, or command named by user/tool output.
- `semantic_similarity`: vector search score when available.
- `lexical_match`: query/path/error overlap.
- `recency`: recently edited, read, searched, or failed.
- `structural_importance`: tests, configs, entrypoints, package files, symbols.
- `failure_relevance`: stack trace, failing assertion, lint error, type error.

### Selection

1. Convert incoming context into candidates.
2. Estimate token cost.
3. Score relevance.
4. Pin explicit references unless they exceed a hard cap.
5. Drop candidates below threshold.
6. Sort by usefulness per token.
7. Fill category budgets.
8. Transform oversized candidates:
   - full file to symbol slice,
   - symbol slice to line slice,
   - long output to structured summary,
   - repeated context to reference-only note,
   - low-relevance item to rejection event.

## Claude + Codex Simultaneous Usage

### New Runtime Layout

Use `.less_tokens/` as the shared control plane for both agents:

```text
.less_tokens/
  config/
    budget.json
  state/
    events.jsonl
    events.lock
    claude-session.json
    codex-session.json
    shared-project-state.json
  tools/
    budget_report.py
    budget_doctor.py
    search.py
  hooks/
    claude/
    codex/
```

Claude and Codex native directories remain only where their platforms require them:

```text
.claude/
  hooks/
  skills/
.codex/
  hooks/
  hooks.json
```

This is a deliberate shift: `.less_tokens/` becomes the product runtime. `.claude/` and `.codex/` become adapters.

### Agent State

Separate live sessions:

- `.less_tokens/state/claude-session.json`
- `.less_tokens/state/codex-session.json`

Shared project memory:

- `.less_tokens/state/shared-project-state.json`

Shared telemetry:

- `.less_tokens/state/events.jsonl`

Every event includes `agent`, `session_id`, and `run_id`. Claude and Codex can work at the same time without overwriting each other.

### Adapter Contract

Each adapter must:

- read native hook payload,
- produce normalized `BudgetInput`,
- call shared policy,
- print a native-compatible message,
- exit with the native-compatible code.

Each adapter must not:

- decide relevance policy,
- own token budgets,
- maintain private stats formats,
- duplicate config parsing.

## Enforcement Points

### Pre-Read

Decisions:

- allow small relevant reads,
- replace full-file reads with slices,
- block repeated unchanged reads,
- warn or block low-relevance reads depending on mode,
- ask for search first when no relevance signal exists.

Replacement must include exact action:

```text
Read only lines 120-198 from agents/common/hooks/auto_slice.py.
```

### Pre-Search

Decisions:

- allow targeted search,
- replace broad search with narrower query/glob,
- block exact repeat searches inside TTL,
- warn when search likely explodes output.

### Post-Output

Decisions:

- keep actionable failure lines,
- summarize passing output,
- collapse repetitive logs,
- preserve commands, file paths, stack traces, and assertion messages,
- trim output to remaining category budget.

### Post-Edit

Decisions:

- invalidate stale candidates for changed files,
- store compact diff metadata,
- avoid automatic full rereads,
- raise relevance of touched files for the active session.

### Compaction

Trigger based on budget pressure, not just transcript size.

Compact state should include:

- current objective,
- active files,
- decisions made,
- files changed,
- commands run,
- test status,
- open questions,
- next step.

The compact state itself must fit the `session_summary` budget.

## Telemetry And Performance Stats

Replace current stats with v2 telemetry.

### Event Schema

```json
{
  "version": 2,
  "timestamp": "2026-06-21T00:00:00Z",
  "agent": "claude",
  "session_id": "opaque-session-id",
  "run_id": "opaque-run-id",
  "phase": "pre_read",
  "tool_name": "Read",
  "category": "retrieved_context",
  "candidate_id": "file:/path/to/file.py",
  "strategy": "relevance_gate",
  "decision": "replace",
  "mode": "advise",
  "estimated_tokens_before": 5200,
  "estimated_tokens_after": 640,
  "estimated_tokens_saved": 4560,
  "budget_limit": 3000,
  "budget_used_before": 8100,
  "budget_used_after": 3740,
  "relevance_score": 0.82,
  "reason": "recent search matched precise line range",
  "replacement": "Read lines 120-198",
  "error": null
}
```

### Report

`budget_report.py` should produce:

```text
less_tokens budget report

Estimated saved: 73,900 tokens
Claude: 42,100 saved across 18 decisions
Codex: 31,800 saved across 14 decisions

Top savings:
1. relevance-gated reads: 28,400
2. dynamic output summaries: 19,700
3. repeated context suppression: 14,200
4. pressure-based compaction: 11,600

Top pressure:
1. retrieved_context: 86%
2. tool_output: 73%
3. diffs: 51%

Top rejected context:
1. low relevance: 11 events
2. repeated unchanged: 8 events
3. too large: 5 events
```

No old stats compatibility requirement.

## Implementation Phases

### Phase 1: New Core And Telemetry

Deliver:

- create `agents/common/budget/`,
- implement config, estimator, candidates, decisions, events, and state,
- implement v2 JSONL telemetry,
- add `budget_report.py`,
- route Claude and Codex hook payloads through the new adapter contract in observe mode.

Acceptance:

- `install.py --agent claude`, `--agent codex`, and `--agent both` install the new control plane,
- both agents write v2 events,
- old stats format is no longer the design target,
- budget failures log an event and fail open.

### Phase 2: Relevance Gate

Deliver:

- implement scoring,
- ingest search results, explicit references, stack traces, recent edits, and grep hits,
- produce candidate selections and replacement actions,
- store selected/rejected candidates in telemetry.

Acceptance:

- precise search hit beats full-file read,
- explicit user file reference beats generic relevance,
- failing test path gets high relevance,
- Claude and Codex receive equivalent decisions for equivalent payloads.

### Phase 3: Advise Mode

Deliver:

- print short native hook messages,
- include replacement actions,
- add `budget_doctor.py` to explain current config and recent pressure,
- support project and agent overrides.

Acceptance:

- no advise message exceeds 600 characters,
- every replacement is directly actionable,
- noisy advice is rate-limited.

### Phase 4: Enforce Mode

Deliver:

- block repeated unchanged reads,
- block full-file reads when precise slices exist,
- block huge low-value listings,
- block unscored context over cap,
- require replacement for every block.

Acceptance:

- all blocks produce v2 telemetry,
- all blocks include exact replacement,
- explicit escape hatch exists for intentional full context.

### Phase 5: Dynamic Output Summaries

Deliver:

- replace static output truncation with budget-aware summarization,
- keep failure lines, stack traces, paths, command summaries, and counts,
- summarize successful or repetitive output aggressively.

Acceptance:

- failing tests remain debuggable,
- passing logs shrink materially,
- report attributes savings to summary strategy.

### Phase 6: Pressure-Based Compaction

Deliver:

- trigger compaction from token pressure,
- generate compact session state template,
- keep separate Claude/Codex session summaries,
- maintain shared project state for facts both agents can reuse.

Acceptance:

- long sessions compact before budget exhaustion,
- compact state fits budget,
- simultaneous agents do not overwrite each other.

### Phase 7: Installer And Docs Redesign

Deliver:

- make `.less_tokens/` the primary runtime,
- update installer for the new control plane,
- update `README.md`, `documentation.md`, and `codex-hook-coverage.md`,
- document migration as replacement, not compatibility preservation,
- add `strategy_21jun26_results.md` after dogfooding.

Acceptance:

- docs explain innovation-first policy,
- docs explain `--agent both`,
- docs explain budget modes,
- docs explain v2 telemetry,
- installer protects user config while allowing old generated artifacts to be superseded.

## Test Plan

### Unit Tests

Test:

- token estimation by content type,
- category budgets,
- config overrides,
- candidate construction,
- relevance scoring,
- selection under budget,
- replacement generation,
- v2 event writing,
- lock failures,
- fail-open behavior.

### Integration Tests

Simulate:

- Claude read after search,
- Codex read after search,
- simultaneous Claude and Codex sessions,
- repeated unchanged reads,
- broad search replacement,
- failing pytest output,
- passing noisy output,
- pressure-based compaction,
- install with `--agent both`.

### Product Tests

Validate:

- budget report is useful,
- hook messages are short,
- blocked actions always have replacements,
- strict mode is tolerable on a real coding task,
- v2 telemetry can estimate savings by agent and strategy.

Do not write tests whose main purpose is preserving old stats shape or old private hook internals.

## Expected Savings

Compared to the current repo, expected additional savings:

- normal coding sessions: **15-35% fewer input tokens**,
- long tool-heavy sessions: **25-50% fewer input tokens**,
- simultaneous Claude + Codex work: **20-45% fewer duplicated/redundant tokens**.

Why:

- current hooks mostly catch local waste,
- the new gate makes context compete for budget globally,
- dynamic output summaries reduce transcript growth,
- shared project state prevents both agents from rediscovering the same context,
- v2 telemetry makes the next round of optimization obvious.

## Risks

Risk: relevance gate rejects needed context.
Mitigation: observe and advise before enforce; pin explicit references; provide escape hatch.

Risk: new runtime layout disrupts installs.
Mitigation: installer owns migration; user config is protected; generated artifacts may be replaced.

Risk: summaries hide important failure details.
Mitigation: deterministic preservation rules for stack traces, paths, assertions, commands, and nonzero exits.

Risk: scoring becomes opaque.
Mitigation: every decision logs score, budget, reason, and replacement.

Risk: Claude and Codex fight over state.
Mitigation: separate live session files, shared append-only telemetry, locked writes, fail-open logging.

## Suggested First PR

Scope:

- create `agents/common/budget/`,
- implement v2 event schema,
- implement token estimator,
- implement budget config,
- implement `budget_report.py`,
- update Claude and Codex adapters to emit observe-mode v2 events,
- update installer to create `.less_tokens/config/` and `.less_tokens/state/`.

Non-goals:

- preserving old stats output,
- preserving old private hook APIs,
- enforcing blocks,
- perfect relevance scoring.

Why first:

- establishes the new spine,
- supports Claude and Codex from day one,
- gives real data before enforcement,
- removes the old compatibility gravity early.

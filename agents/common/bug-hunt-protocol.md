# Bug-Hunt Protocol

How to decide when to run another hunt vs stop and fix. This protocol targets an arbitrary repo
— it started as less_tokens-only tooling and is delivered upstream as a portable Claude Code
skill — so it auto-detects which of two modes applies before picking a bug definition:

- **docs mode** — target repo has no test suite and is dominated by interlinked Markdown specs
  (e.g. a governance framework). A "bug" is a **cross-document inconsistency**, not a logic error.
- **code mode** — target repo has application code and a detectable test suite. A "bug" is a
  **logic / state / silent-failure error**.

The mode-detection heuristic below is generated from `.claude/tools/protocol_mode.py` — the same
source `bugfix-protocol.md` uses, so the two protocols can never disagree on what "docs mode" vs
"code mode" means. Code mode's severity tiers, target files, thresholds, and prompt template are
generated from `.claude/tools/bug_hunt_registry.py` — **this repo's own code-mode defaults**, not
generic across targets. There is no equivalent registry for docs-mode targets (a repo this one
has never seen has no target-Markdown-file list to regenerate from), so docs mode below is
hand-authored, repo-agnostic prose instead of generated content. Scoring a round in code mode is
mechanical (`hunt_round.py`/`hunt_score.py`); docs mode is eyeball-driven, no metric scripts.

Hunt statistics for **this repo's own hunts** (which always land in code mode — see below) are
recorded in `.claude/skills/bug-hunt/bughuntlog.jsonl`, one JSON record per round. A docs-mode
target keeps its own round log next to its own `BACKLOG.md`/`CHANGELOG.md`.

---

## Determine the repo root

Before anything else, run:
```
git rev-parse --show-toplevel
```
This is `$REPO_ROOT`. All paths below — in both modes — are relative to it.

---

## Mode detection

<!-- mode-detection: begin -->
Run against $REPO_ROOT (from `git rev-parse --show-toplevel`), in order, first match wins:

1. **Test runner detected -> code mode.** Any of: `pytest.ini`; `pyproject.toml` with a
   `[tool.pytest.ini_options]` table; `setup.cfg` with `[tool:pytest]`; `package.json` with a
   `test` script invoking `jest`/`mocha`/`vitest`/`ava`; a `Makefile`/`justfile` `test` target; or
   a `tests/`/`test/` directory containing `test_*.py`, `*_test.py`, `*.test.js`, or `*.spec.ts`
   files.
2. **No test runner, but `BACKLOG.md` or `backlog.md` exists and Markdown specs dominate ->
   docs mode.** Rough signal for "Markdown specs dominate": more tracked `*.md` files than
   source files at the repo root, or no conventional source directory (`src/`, `lib/`, `app/`,
   or the language-equivalent).
3. **Neither condition matches -> ambiguous.** Do not guess. State what was checked and ask the
   user which mode applies before running either protocol.

This is a heuristic, not a certainty. Print which branch fired and why as the first line of any
hunt/fix output.
<!-- mode-detection: end -->

For **this repo (less_tokens)**: branch 1 fires (a `tests/`-equivalent directory —
`.claude/tests/unit/` and `.claude/tests/integration/` — full of `test_*.py`, plus
`pyproject.toml`). less_tokens always lands in **code mode** against itself; the code-mode
section below carries this repo's own tuned defaults as a worked example.

---

## Docs mode

**Bug definition:** an internal inconsistency between coordinated Markdown documents in the
target repo — not a logic error, since there's no code to run.

- **Vocabulary drift** — a shared-verbatim term diverges between files (a defined term, a scale,
  a labeled taxonomy reworded in one file but not another).
- **Unenforced principle** — a rule stated in one doc with no corresponding enforcement/reference
  elsewhere the target repo's own conventions say it should have one.
- **Broken cross-link** — a relative Markdown link or cross-reference block points at a
  missing/renamed file, or is missing a member of a set it claims to enumerate.
- **Direct contradiction** — two documents state conflicting rules such that following one
  violates the other.

NOT bugs: stylistic rewordings that preserve meaning, proposed new content, "add a section"
requests.

**Severity rubric** (assign per bug at intake — same four tiers as code mode's data-loss/
silent/ux/cosmetic ladder, worded for docs):

| Tier | Definition | Example |
|---|---|---|
| **contradiction** | Two docs give conflicting instructions; following one breaks the other. | Two specs list a different precedence/priority order for the same decision. |
| **drift** | Shared-verbatim vocabulary diverges; same idea, mismatched wording. | A defined scale or label set spelled one way in one file, differently in another. |
| **gap** | A principle/rule/metric exists without its required counterpart. | A new rule with no corresponding enforcement or index entry. |
| **cosmetic** | Wording / formatting / link-label issue. No semantic impact. | Stale relative link label; trailing-section typo. |

**Three signals to assess after each hunt** (identical shape to code mode, no scorer script —
eyeball it):

1. **Severity slide** — median tier of this round vs the previous. `contradiction -> drift ->
   gap -> cosmetic` sliding down means the high-value surface is exhausted.
2. **Overlap rate** — do NOT pre-exclude the existing bug list (let the agent rediscover); of the
   bugs surfaced, what fraction matches one already known by file:line or paraphrase? Passes at
   >= 60%, the same threshold code mode enforces mechanically.
3. **File coverage** — cumulative distinct files where bugs have been found vs a target-file list
   **you build for this specific target repo** (read its README/CLAUDE.md/index doc for its own
   core-spec file list — there is no registry to generate this from generically). Passes at >=
   80%, matching code mode's threshold.

**Stop rule** (all three required): median severity of last round <= `gap`, overlap rate >= 60%,
cumulative file coverage >= 80%. If 2 of 3 hold, run one more round. If <= 1 of 3, keep hunting.

**Prompt template** (fill in the target repo's own core-spec file list before use):
```
Find up to 10 real, undocumented inconsistencies in $REPO_ROOT (a Markdown-spec-driven repo, no
test suite).
- Read BACKLOG.md (or backlog.md) first; do NOT pre-exclude (overlap is a signal we want to measure).
- Bug definition: vocabulary drift / unenforced principle / broken cross-link / direct
  contradiction across <list this target repo's own core spec files here>.
- NOT bugs: meaning-preserving rewordings, proposed new content, "add a section".
- Method: read the core spec files in full; verify each candidate by quoting the conflicting
  lines from both files; rank by severity tier.
- Output: up to 10 bugs in `**Bug N: title** (file:line)` + What/Why/Repro/Fix format, <= 6 lines
  each. If <10 solid, surface fewer and say so.
- Severity tier per bug: contradiction | drift | gap | cosmetic
```

**Operator steps:** (1) verify each candidate by reading the cited file:line, (2) assign each a
tier, (3) check each against the existing bug list for overlap, (4) score the three signals by
hand, (5) apply the stop rule, (6) append confirmed bugs to the target repo's backlog and a round
entry to its own hunt log (create one next to `BACKLOG.md` if none exists yet, same JSON-lines
shape as code mode's `bughuntlog.jsonl` — no mechanical validator, hand-check the required keys
against `hunt_round.ROUND_REQUIRED_KEYS`'s shape).

---

## Code mode

**Bug definition:** a logic / state / silent-failure error — a docstring/behavior mismatch,
schema drift, encoding bug, or hook/lifecycle ordering error confirmed by reading the code (and,
where a test suite exists, reproducible in one).

The severity rubric, target-file list, stop-rule thresholds, and agent prompt template below are
**this repo's (less_tokens) own registry-driven defaults** — generated from
`.claude/tools/bug_hunt_registry.py`. A different code-mode target repo needs its own tuned
values; regenerate this section from that repo's own registry copy rather than assuming these
transfer.

### Severity rubric (assign per bug at intake)

<!-- severity-rubric: begin -->
| Tier | Definition | Example |
|---|---|---|
| **data-loss** | Index corrupted or wrong results returned silently; token savings tracked incorrectly. | UPSERT collision clobbers a different file's embedding; duplicate source_key silently dropped. |
| **silent** | Behavior is wrong but no immediate data loss; results or counts are misleading. | search() returns stale-model rows; savings stats under-count due to off-by-one in char math. |
| **ux** | Hook gives bad signal, false block, or noise that trains the user to ignore it. | search-first blocks when a search did run; truncate hook logs savings when disabled. |
| **cosmetic** | Wording / formatting / log-line issue. No functional impact. | (none documented yet — surface only if encountered.) |
<!-- severity-rubric: end -->

Generated from `bug_hunt_registry.SEVERITY_TIERS` by `.claude/tools/bug_hunt_docs.py` — edit
the registry, not this table.

### Stop rule

After each round, append a JSON record to `bughuntlog.jsonl`, then run:

```
python .claude/tools/hunt_score.py
```

The scorer evaluates three signals against the log and prints `STOP`, `RUN ONE MORE`, or `KEEP HUNTING`.

Signal definitions (for filling in the record):
1. **Severity slide** — `median_severity` of this round (`data_loss` > `silent` > `ux` > `cosmetic`).
<!-- thresholds: begin -->
2. **Overlap** — of bugs surfaced, how many match a prior-round bug by file:line or paraphrase? Record as `{"matched": N, "total": N}`. Passes at >= 60%.
3. **File coverage** — list new files hit in `new_files`; scorer accumulates across all rounds vs the target file list. Passes at >= 80%.
<!-- thresholds: end -->

High-yield target files (cover as many as possible across rounds), matched against `new_files`
entries by bare filename:

<!-- target-files: begin -->
`budget-observer.py`, `caveman-reminder.py`, `compact-trigger.py`, `db.py`, `embeddings.py`, `hunt_score.py`, `index-refresh.py`, `install.py`, `model_profiles.py`, `savings_log.py`, `search-first.py`, `search.py`, `search_config.py`, `stats.py`, `truncate-output.py` (15 files).
<!-- target-files: end -->

### How to run a hunt (one-shot agent prompt template)

<!-- prompt-template: begin -->
```
Find 10 real, undocumented bugs in $REPO_ROOT (this repo — less_tokens).
- Read BACKLOG.md ## Bugs section first; do NOT pre-exclude (overlap is a signal we want to measure).
- Bug definition: logic / silent failure / state / docstring drift / schema / encoding / hook-ordering.
- NOT bugs: features, refactors, "add tests", performance unless incorrect, anything in non-Bugs backlog sections.
- Method: search-first for indexed files; read whole files for high-yield targets; verify each candidate by tracing or sqlite3 query; rank by severity tier.
- Output: 10 bugs in `**Bug N: title** (file:line)` + What/Why/Repro/Fix format, ≤6 lines each. If <10 solid, surface fewer + say so.
```
<!-- prompt-template: end -->

After the agent returns, the operator: (1) assigns each a tier, (2) checks each against the
existing table for overlap, (3) runs `python .claude/tools/hunt_round.py '<json record>'` —
validates the record (round number, severity tiers, overlap math), appends it to
`bughuntlog.jsonl`, and scores it in one step.

The severity rubric, target-file list, thresholds, and prompt template above are generated by
`.claude/tools/bug_hunt_docs.py` from `.claude/tools/bug_hunt_registry.py` — the single source
for all four (plus the shared mode-detection block above, sourced from `protocol_mode.py`). Edit
the registry (or `protocol_mode.py` for mode detection), then run
`python .claude/tools/bug_hunt_docs.py` to refresh this doc (a pre-commit hook enforces it's
already current).

---

## Rules (both modes)

- **Repo-agnostic root:** always detect the repo root with `git rev-parse --show-toplevel`.
  Never hardcode a path.
- **No pre-exclusion:** the agent reads the existing bug/backlog list but does not filter —
  rediscovery is signal.
- **Verify before adding:** never add a bug the agent surfaced without independently confirming
  it — read the cited file:line (docs mode) or trace/reproduce it (code mode).
- **No fixing here:** this skill logs bugs. Fixing is `bugfix-protocol.md`'s job — do not fix
  bugs found during a hunt.
- **One round per invocation:** don't chain multiple hunt rounds without user confirmation.
- **Operator owns tiers:** present a triage table and get confirmation before writing to the
  backlog/log.
- **Needs-human escape hatch:** if a candidate is too large, ambiguous, or cross-cutting to tier
  confidently, mark it `needs-human` instead of forcing a tier.

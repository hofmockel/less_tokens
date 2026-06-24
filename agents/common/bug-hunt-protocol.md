# Bug-Hunt Protocol

How to decide when to run another hunt vs stop and fix. Eyeball-driven (no metric scripts); the rubric below keeps the eyeball calibrated.

Hunt statistics are recorded in `.claude/skills/bug-hunt/bughuntlog.jsonl` — one JSON record per round.

---

## Severity rubric (assign per bug at intake)

| Tier | Definition | Example |
|---|---|---|
| **data-loss** | Index corrupted or wrong results returned silently; token savings tracked incorrectly. | UPSERT collision clobbers a different file's embedding; duplicate source_key silently dropped. |
| **silent** | Behavior is wrong but no immediate data loss; results or counts are misleading. | search() returns stale-model rows; savings stats under-count due to off-by-one in char math. |
| **ux** | Hook gives bad signal, false block, or noise that trains the user to ignore it. | search-first blocks when a search did run; truncate hook logs savings when disabled. |
| **cosmetic** | Wording / formatting / log-line issue. No functional impact. | (none documented yet — surface only if encountered.) |

---

## Stop rule

After each round, append a JSON record to `bughuntlog.jsonl`, then run:

```
python .claude/tools/hunt_score.py
```

The scorer evaluates three signals against the log and prints `STOP`, `RUN ONE MORE`, or `KEEP HUNTING`.

Signal definitions (for filling in the record):
1. **Severity slide** — `median_severity` of this round (`data_loss` > `silent` > `ux` > `cosmetic`).
2. **Overlap** — of bugs surfaced, how many match a prior-round bug by file:line or paraphrase? Record as `{"matched": N, "total": N}`.
3. **File coverage** — list new files hit in `new_files`; scorer accumulates across all rounds vs the 14-file target list.

High-yield target files (cover as many as possible across rounds):
`.claude/tools/embeddings.py`, `.claude/tools/search.py`, `.claude/hooks/search-first.py`,
`.claude/tools/index-refresh.py`, `.claude/hooks/truncate-output.py`, `.claude/tools/stats.py`,
`.claude/tools/savings_log.py`, `.claude/hooks/budget-observer.py`, `install.py`,
`.claude/tools/search_config.py`, `.claude/tools/chunkers.py`, `.claude/tools/hunt_score.py`,
`agents/common/budget/engine.py`, `.claude/hooks/compact-trigger.py`

---

## How to run a hunt (one-shot agent prompt template)

```
Find 10 real, undocumented bugs in /Users/michael/Documents/GitHub/less_tokens/.
- Read BACKLOG.md ## Bugs section first; do NOT pre-exclude (overlap is a signal we want to measure).
- Bug definition: logic / silent failure / state / docstring drift / schema / encoding / hook-ordering.
- NOT bugs: features, refactors, "add tests", performance unless incorrect, anything in non-Bugs backlog sections.
- Method: search-first for indexed files; read whole files for high-yield targets; verify each candidate by tracing or sqlite3 query; rank by severity tier.
- Output: 10 bugs in `**Bug N: title** (file:line)` + What/Why/Repro/Fix format, ≤6 lines each. If <10 solid, surface fewer + say so.
```

After the agent returns, the operator: (1) assigns each a tier, (2) checks each against the existing table for overlap, (3) appends a JSON record to `bughuntlog.jsonl`, (4) runs `hunt_score.py`.

# Bug-Hunt Protocol

How to decide when to run another hunt vs stop and fix. Eyeball-driven (no metric scripts); the rubric below keeps the eyeball calibrated.

Hunt statistics are recorded in [bughuntlog.md](bughuntlog.md) — one entry per round.

---

## Severity rubric (assign per bug at intake)

| Tier | Definition | Example |
|---|---|---|
| **data-loss** | Index corrupted or wrong results returned silently; token savings tracked incorrectly. | UPSERT collision clobbers a different file's embedding; duplicate source_key silently dropped. |
| **silent** | Behavior is wrong but no immediate data loss; results or counts are misleading. | search() returns stale-model rows; savings stats under-count due to off-by-one in char math. |
| **ux** | Hook gives bad signal, false block, or noise that trains the user to ignore it. | search-first blocks when a search did run; truncate hook logs savings when disabled. |
| **cosmetic** | Wording / formatting / log-line issue. No functional impact. | (none documented yet — surface only if encountered.) |

---

## Three signals to assess after each hunt

1. **Severity slide** — what's the median tier of THIS round vs the previous? Going `data-loss → silent → ux → cosmetic` means the high-value surface is exhausted.
2. **Overlap rate** — when running a hunt, do NOT pre-exclude the existing bug list (let the agent rediscover). Then count: of the bugs surfaced, what fraction matches a bug already in the table by file:line or paraphrase? Rising overlap = saturated surface.
3. **File coverage** — cumulative distinct files where bugs have been found, vs the high-yield target list (`embeddings.py`, `search.py`, `search_config.py`, `model_profiles.py`, `stats.py`, `savings_log.py`, `db.py`, `search-first.py`, `truncate-output.py`, `index-refresh.py`, `compact-trigger.py`, `caveman-reminder.py`, `install.py`, `index.sql`). When new hunts stop landing on new files, surface is covered.

---

## Stop rule (all three required)

- Median severity of last round ≤ `ux` (no `data-loss` or `silent` finds), AND
- Overlap rate with prior rounds ≥ 60% (mostly rediscovering known bugs), AND
- Cumulative file coverage ≥ 80% of the high-yield list above.

If 2 of 3 hold, run one more round. If ≤1 of 3, keep hunting.

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

After the agent returns, the operator: (1) assigns each a tier, (2) checks each against the existing table for overlap, (3) scores the three signals, (4) applies the stop rule, (5) appends a round entry to [bughuntlog.md](bughuntlog.md).

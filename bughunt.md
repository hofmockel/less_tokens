# Bug-Hunt Protocol

How to decide when to run another hunt vs stop and fix. Eyeball-driven (no metric scripts); the rubric below keeps the eyeball calibrated.

Hunt statistics are recorded in [bughuntlog.md](bughuntlog.md) — one entry per round.

---

## Severity rubric (assign per bug at intake)

| Tier | Definition | Example |
|---|---|---|
| **data-loss** | Wrong number lands in IRS-grade ledger, FIFO, wash-sale, or P&L. Real money at stake. | Lockouts dict collapse hides longer restriction; same-day rebuy missed by report adherence check. |
| **silent** | Behavior is wrong but no immediate money impact; numbers reported are misleading. | Correlation aligns by index not date; trailing_return falls back to earliest close on IPOs. |
| **ux** | Tool gives bad signal, false reassurance, or noise that trains the operator to ignore the gate. | parity-check baselines drift daily; universe.py refresh prints UPD on every row. |
| **cosmetic** | Wording / formatting / log-line issue. No functional impact. | (none documented yet — surface only if encountered.) |

---

## Three signals to assess after each hunt

1. **Severity slide** — what's the median tier of THIS round vs the previous? Going `data-loss → silent → ux → cosmetic` means the high-value surface is exhausted.
2. **Overlap rate** — when running a hunt, do NOT pre-exclude the existing bug list (let the agent rediscover). Then count: of the bugs surfaced, what fraction matches a bug already in the table by file:line or paraphrase? Rising overlap = saturated surface.
3. **File coverage** — cumulative distinct files where bugs have been found, vs the high-yield target list (`wash.py`, `add-fills.py`, `rh-sync.py`, `dataio.py`, `db.py`, `alerts.py`, `state.py`, `snapshot-state.py`, `refresh-prices.py`, `refresh-earnings.py`, `recalc-coverage.py`, `sell-check.py`, `pnl.py`, `report.py`, `pre-buy-check.py`, `momentum.py`, `stress.py`, `size.py`, `weekly-budget.py`, `universe.py`, `universe-coverage.py`, `discover.py`, `lockout-cost.py`, `journal*.py`, `parity-check.py`, `validate-ledger.py`, `backup.py`, `restore-check.py`, `embeddings.py`, `search.py`, `commit-hygiene.py`, `doc-drift.py`, `gen-tools-readme.py`, `secret-scan.py`, `app/scan.py`, `app/layers.py`, `schema/portfolio.sql`, `schema/migrations/*.sql`). When new hunts stop landing on new files, surface is covered.

---

## Stop rule (all three required)

- Median severity of last round ≤ `ux` (no `data-loss` or `silent` finds), AND
- Overlap rate with prior rounds ≥ 60% (mostly rediscovering known bugs), AND
- Cumulative file coverage ≥ 80% of the high-yield list above.

If 2 of 3 hold, run one more round. If ≤1 of 3, keep hunting.

---

## How to run a hunt (one-shot agent prompt template)

```
Find 10 real, undocumented bugs in /Users/michael/Documents/GitHub/AIPortfolio/.
- Read backlog.md ## Bugs section first; do NOT pre-exclude (overlap is a signal we want to measure).
- Bug definition: logic / silent failure / state / financial-logic / chain-ordering / docstring drift / schema / auth-UX / encoding.
- NOT bugs: features, refactors, "add tests", performance unless incorrect, anything in non-Bugs backlog sections, backup-section variants (deferred per memory), token instrumentation.
- Method: search-first for indexed files; read whole files for high-yield targets; verify each candidate by tracing or sqlite3 query; rank by severity tier.
- Output: 10 bugs in `**Bug N: title** (file:line)` + What/Why/Repro/Fix format, ≤6 lines each. If <10 solid, surface fewer + say so.
```

After the agent returns, the operator: (1) assigns each a tier, (2) checks each against the existing table for overlap, (3) scores the three signals, (4) applies the stop rule, (5) appends a round entry to [bughuntlog.md](bughuntlog.md).

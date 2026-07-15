# Continue: less_tokens

> **Next focus:** nothing blocked on engineering right now — pick up BACKLOG.md's next open item.

## Current state
HEAD is `35e234c`, working tree clean, pushed to `origin/main`.

## What happened this session
- Picked "Installer: make deployment spec executable, not duplicated prose-in-code" off
  BACKLOG.md (Architecture Simplification / High Priority). `main()`'s Step 2 previously
  re-declared every source/dest/exclude pair by hand across ~20 `copy_tree` calls, independently
  of `_install_specs()`, which already computed the same list for the foreign-file check. Added a
  `force_kind` field (`"hooks"` for the two top-level per-agent hook trees, `"tools"` for
  everything else) to each spec tuple and collapsed main()'s hand-written calls into one loop
  over `_install_specs(args.caveman, agents, target_root)`. `.less_tokens/config` still copies
  first and separately — `apply_codex_savings_profile()` must merge into an already-populated
  `budget.json`, not write a bare one a later same-tree copy would then skip. `search_config.py`
  merge handling and Codex tool-shim generation stay as separate calls (different write
  semantics, not directory copies).
- Verified byte-identical output (mod target path and install timestamp) against the
  pre-refactor installer: ran both versions into scratch targets via git stash, diffed the
  resulting trees. BACKLOG.md row removed — shipped.
- Full unit + integration suite: 923 passed, same 13 pre-existing unrelated failures
  (toolcost/stats/agentsmd-budget token-calibration tests) — unchanged by this session's changes.

## Open work
See [BACKLOG.md](BACKLOG.md) for the current list. Notable: bug-hunt protocol data-driven
conversion (High Priority, Prose to Code), and several Medium prose-to-code/doc-drift items
(skill manual generation, subagent guidance split, parity-doc generation, installer flag docs,
dev command shim, canonical-home rules). Cache-key widening for bash/grep stays parked until
Codex-side `"bash"`-kind near-miss data actually shows up in `.less_tokens/state/near_misses.jsonl`.

## Suggested skills
- `/bugfix` or a BACKLOG.md prose-to-code row — no bugs currently filed in the Bugs table.

## Start here
Check BACKLOG.md's remaining High Priority row (Prose to Code: bug-hunt protocol data-driven)
or a Medium prose-to-code/doc-drift item for the next pick.

---
_Last updated on 2026-07-14, HEAD `35e234c` (working tree clean, pushed)._

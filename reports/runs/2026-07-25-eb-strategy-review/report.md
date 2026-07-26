# EB Strategy Review — subagent strategies and general strategy roster, parity focus

**Date:** 2026-07-25
**Requested by:** repo owner, via the ever_better multi-agent roster (external reviewer of this repo)
**Reviewers:** `tect` (architecture/parity/over-engineering), `qa` (gap-hunting/verification), `exec` (synthesis and final call)
**Status:** Findings delivered; no code, config, or docs changed by this review — read-only audit only

## Why this exists

`less_tokens` tracks Claude/Codex parity for every shipped strategy in `parity.json`, and treats subagent strategies (SA1–SA6) as an evidence-gated roadmap. The repo owner asked the ever_better team to evaluate both — with particular attention to whether the parity mechanism itself is trustworthy, where the roadmap has gaps, and where designs are over-built relative to their payoff — from outside this codebase's own review loop.

## Method

Two independent specialist passes (`tect`, `qa`) reviewed the same material without seeing each other's work, then `exec` synthesized both into one ranked, decisive verdict. This mirrors the decorrelated-review pattern this repo itself documents for high-stakes changes. All findings below are evidence-based (file:line citations, direct command output) rather than inferred from documentation alone — both reviewers independently re-verified drift they observed on disk, ran `codex_parity_audit.py` and `install.py --self-refresh --dry-run` directly, and grepped live state (`.claude/settings.json`, `.codex/hooks.json`, `.claude/state/savings.jsonl`).

## Headline finding

**A single root cause — nobody has re-run `install.py --self-refresh` since the 2026-07-08 dogfood pass — produced three separate, independently-discoverable symptoms:** stale `parity.json` install copies, an orphaned hook still firing in `.codex/`, and SA1/SA2's hooks never actually wired into this repo's own `.claude/settings.json`. That last one means **the most recent benchmark report already drew a wrong conclusion from this exact hole**: [`reports/runs/2026-07-24-d4-token-savings-benchmark/report.md:115`](../2026-07-24-d4-token-savings-benchmark/report.md) attributes zero `subagent-cap` telemetry to "no subagent-heavy sessions observed." It isn't that. The hook is wired nowhere in this repo, so it structurally cannot fire, regardless of session mix. Waiting longer will not produce SA2 telemetry — the wiring gap has to close first.

## Ranked findings

### 1. CRITICAL — SA1/SA2 hooks unwired in this repo's own install; D4 report's attribution is wrong
- `grep -c "subagent-fanout\|subagent-cap" .claude/settings.json` → **0**, in a 215-line file with 46 other hook commands correctly wired.
- `.claude/state/savings.jsonl` has zero `subagent_fanout` events across 797 lines.
- `.claude/settings.json` was last regenerated 2026-07-16 09:43 — *before* SA1/SA2 shipped later that same day/next (`f4e7b9e`, `1abb6a8`).
- `install.py --agent claude --self-refresh --dry-run` confirms it *would* wire both hooks right now — the installer itself agrees they're currently missing.
- **Recommended action:** run `install.py --agent claude --self-refresh` (no version-gate blocker on the Claude side; git-tracked and reversible). Add a correction line to the D4 report now rather than waiting for a re-run — the false attribution is live and actionable today. Re-run the D4 benchmark once wiring lands to get real telemetry.
- This is a **human/repo-owner decision to execute**, not something this review implemented — it changes live hook wiring and an already-published report.

### 2. HIGH — Orphaned `truncate-output.py` still firing on the Codex side, contradicting 4 of 5 docs
- `.codex/hooks/truncate-output.py` exists (96 real lines, not a stub) and is wired in `.codex/hooks.json` `PostToolUse` — while canonical `parity.json`, README.md, DOCUMENTATION.md, and `DECISIONS.md:42` all say it's "missing"/"unwired." `DECISIONS.md`'s claim is false on disk right now.
- Root cause: commit `3c648b4` (CX28) updated canonical parity.json + manifest + docs but never removed the orphaned Codex hook file or its `.codex/hooks.json` entry. `install.py`'s orphan-sweep can't catch this on its own — the manifest no longer generates *any* Codex entry for truncate-output, so the cleanup logic never considers it.
- Compounding: a full automated fix is currently blocked — the installed `codex-cli` (`0.146.0-alpha.3`) is outside the verified hook-contract range (`0.142.3`–`0.145.0`), so `--self-refresh --dry-run` on the Codex side refuses to run at all.
- **Recommended action:** manually remove the file and its `.codex/hooks.json` entry as an interim patch (small, safe, reversible, doesn't require the blocked self-refresh path) — then still run a full Codex `--self-refresh` once a verified `codex-cli` version is confirmed, so the manual patch doesn't quietly become the permanent process.
- **Human gate:** whether to run `--self-refresh` against an unverified `codex-cli` version. Recommended call is **no, wait for a verified version** — overridable by whoever owns the Codex install if they knowingly accept the risk.

### 3. HIGH — `parity.json`'s "shipped" label conflates two different things
- Canonical `parity.json` marks `subagent-metrics`/`subagent-guidance` as `{"codex": "shipped"}`. Both are real: `agents/codex/hooks/subagent-metrics.py` and `subagent-guidance.py` exist, are registered in `hook_manifest.py`, and are covered by `test_codex_event_contract.py`/`test_codex_hooks.py`. But in *this repo's own* `.codex/` checkout, neither file is installed and `.codex/hooks.json` has zero subagent-related entries — matching README/DOCUMENTATION's (correct) "missing" and contradicting canonical parity.json's "shipped" for the same two keys.
- Both reviewers were right: the design/code genuinely exists and is tested ("shipped" as source), but was never deployed to this repo's own install ("shipped" ≠ "installed and active"). This is the same root cause as #1 — `install.py --self-refresh` hasn't run since 2026-07-08, nine canonical commits ago.
- **Recommended fix:** split `parity.json`'s vocabulary into two explicit states — `shipped (source)` vs. `installed (active)` — so this ambiguity can't recur, and add one explicit note cross-referencing the CX-numbered (Codex-verification) and SA-numbered (cross-platform roadmap) tracking schemes, since a reader of `BACKLOG.md`'s SA roadmap alone would currently and wrongly conclude Codex has zero subagent-boundary hooks.

### 4. HIGH — `parity.json`'s triple-copy distribution has no consumer and no drift check
- The same file is installed to `.claude/hooks/common/parity.json` and `.less_tokens/hooks/parity.json` via `copy_tree`, but nothing downstream ever reads either installed copy (`hook_parity_docs.py`, `test_hook_manifest_parity.py`, and `codex_parity_audit.py` all only touch the canonical `agents/common/hooks/parity.json` or compare against `.codex/`/manifest directly). Nothing fails if the copies diverge, and per #1 they already have.
- **Recommended fix:** exclude `parity.json` from `copy_tree`'s install specs (`install.py:1611,1628`) entirely, rather than building a diff-checker to keep two files in sync that nothing consumes. Canonical stays the sole source of truth. Cheaper and more correct than the alternative (a `--check` mode). Add one lightweight test asserting the exclusion holds.

### 5. MEDIUM — `codex_parity_audit.py` works but has no CI gate
- Running it directly against this repo (`python3 .claude/tools/codex_parity_audit.py --root .`) returns exit 1 and correctly flags both the `truncate-output` orphan and the `subagent-metrics`/`subagent-guidance` gap — right now, on this exact repo. It's exercised only against synthetic fixtures in its own unit test; nothing wires it into CI or pre-commit, so its real-world signal on this repo has never surfaced.
- **Recommended action:** wire it into CI/pre-commit alongside the existing `hook_parity_docs.py --check` gate. No blocker; do this in the same change as #1's fix.

### 6. MEDIUM — Test coverage gaps
- No test compares the (soon-to-be-eliminated, per #4) three `parity.json` copies against each other — the exact gap that let #1–#3 ship undetected. Once #4 lands, this test becomes moot (no second copy left to compare) rather than needed.
- Neither `test_subagent_cap.py` nor `test_subagent_fanout.py` asserts the hook is actually wired in this repo's own `.claude/settings.json` — the same class of gap that hid finding #1 for over a week. Add a hook-wiring assertion for both as part of #1's fix.

### 7. MEDIUM — SA5 should downgrade from Blocked to Later now
- SA5's own acceptance criteria already admit "role-keyed rules rot as the subagent roster changes, similar upkeep cost to a linter ruleset," and may be "parked indefinitely if SA1 alone proves sufficient." SA1's generic digest already preserves `Verdict:`/`Recommendation:`/`Summary:` fields verbatim regardless of subagent type — covering most of the benefit SA5 would add.
- **Recommended action:** move SA5 from **Blocked** to **Later** in `BACKLOG.md` now. This is a design judgment call (medium confidence on the reasoning), but the edit itself is low-risk and touches no code.

### 8. LOW — `.less_tokens/hooks/parity.json` staleness
- Gitignored, local, generated artifact — staleness here is expected behavior for something nobody has a reason to re-trigger outside an install refresh. No action needed beyond the general `--self-refresh` recommendation in #1/#2.

## Not covered / residual risk

`qa`'s sweep was a spot-check (`search-first`, `context-cache` verified clean as a baseline), not an exhaustive pass over all ~20 `parity.json` entries. `compact-trigger`, `terse-output`, and `savings-html` also showed as "unwired" in the live `codex_parity_audit.py` run during this review but were out of scope for deep verification — flagged as unverified, not cleared. A follow-up pass on those three would be needed before treating this audit as exhaustive.

## What's well-designed — left alone, not flagged for change

- The CX26–CX30 Codex hook-contract verification chain (`DECISIONS.md`) — rigorous, version-pinned, backed by live-verified negative results (e.g., CX28 proving Codex's `PostToolUse` cannot replace/suppress model-visible tool output). This is exactly why SA1/SA2's Claude-only design still holds architecturally, on stronger evidence than existed when they shipped.
- `truncate_output.py` and `subagent_fanout.py` themselves — small, single-purpose, well-tested, no speculative config surface. SA1's digest-then-fallback and SA2's FIFO content-hash pairing are both right-sized; don't extend either without telemetry showing the current mechanism actually falls short.
- SA4's `BACKLOG.md` entry — the best-calibrated item in the backlog: it names an unverified assumption, sequences a cheap verification step before the expensive build, and states an explicit downgrade path if verification fails. A model for how blocked items should be written.
- SA3's sequencing behind SA2 telemetry — proportionate as written, no changes needed.
- `install.py`'s force/overwrite-modified contract — sound mechanism (safe-by-default skip, explicit escalation, clear diff warnings). The drift documented in this report is a process failure (nobody invoked it), not a defect in the mechanism itself.

## Confidence

High on findings 1, 2, 4, 5 — independently reproduced by both reviewers against this repo's actual files, converging evidence. Medium on 3, 6, 7 — correct direction, but 3 and 7 carry a design/vocabulary judgment rather than a pure fact, and 6's remaining scope depends on how 4 lands. The residual-risk section above bounds how far this audit's coverage extends.

## Next steps (not executed by this review)

This review is read-only by design — no fixes were applied. The repo owner should decide, in order of urgency:
1. Run `install.py --agent claude --self-refresh` and correct the D4 report's attribution (#1).
2. Manually remove the orphaned Codex `truncate-output` hook (#2) — interim patch, not a substitute for a future full Codex self-refresh once a verified `codex-cli` version is available.
3. Split `parity.json`'s "shipped" vocabulary and exclude it from `copy_tree` (#3, #4).
4. Wire `codex_parity_audit.py` into CI (#5) and add the two named test gaps (#6).
5. Move SA5 to Later in `BACKLOG.md` (#7).

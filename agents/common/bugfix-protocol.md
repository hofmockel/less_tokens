# Bugfix Protocol

Atomic bug-fix workflow, companion to `bug-hunt-protocol.md`: that protocol finds and logs bugs,
this one fixes the next one off the backlog. Do NOT hunt inside this protocol and do NOT fix
inside the hunt protocol — they stay separate invocations.

This protocol targets an arbitrary repo — it started as less_tokens-only tooling and is delivered
upstream as a portable Claude Code skill — so it auto-detects which of two modes applies before
picking a fix workflow:

- **docs mode** — target repo has no test suite and is dominated by interlinked Markdown specs.
  A "bug" is a cross-document inconsistency; the fix is a doc edit, no test-writing step, verified
  by re-reading the affected sections.
- **code mode** — target repo has application code and a detectable test suite. A "bug" is a
  logic/state/silent-failure error; the fix requires a failing regression test written first, the
  minimal fix, then the repo's own lint/type/test commands.

The mode-detection heuristic below is generated from `.claude/tools/protocol_mode.py` — the same
source `bug-hunt-protocol.md` uses, so the two protocols can never disagree on what "docs mode"
vs "code mode" means. Code mode's severity vocabulary, verification-command list, and commit
template below are **this repo's (less_tokens) own registry-driven defaults**, generated from
`.claude/tools/bugfix_registry.py`. There is no equivalent registry for docs-mode targets (a repo
this one has never seen has no "lint/type/test command list" to regenerate from), so docs mode
below is hand-authored, repo-agnostic prose instead of generated content.

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

For **this repo (less_tokens)**: branch 1 fires (`.claude/tests/unit/` and
`.claude/tests/integration/` full of `test_*.py`, plus `pyproject.toml`). less_tokens always
lands in **code mode** against itself; the code-mode section below carries this repo's own tuned
defaults as a worked example.

---

## Docs mode

**Bug definition:** same as `bug-hunt-protocol.md`'s docs-mode section — an internal
inconsistency between coordinated Markdown documents (vocabulary drift, unenforced principle,
broken cross-link, direct contradiction). No test suite exists, so "fixed" is verified by
re-reading, not by running anything.

**Workflow (for each bug):**

1. **Read the target repo's backlog** — find the next unfixed bug (skip anything marked
   "Blocked" or "needs-human"; report which were skipped and why).
2. **Read the cited location** — open the file at the referenced line. Confirm the inconsistency
   is still present exactly as described. If it's already gone (fixed by prior work), skip to
   step 8 with a "confirmed fixed" note instead of guessing at a new fix.
3. **Identify all affected files** — coordinated specs often share vocabulary verbatim. A fix to
   one usually requires a matching change in others; find every location that must stay in sync
   (follow the target repo's own cross-link/index conventions to find them).
4. **Make the minimal edit** — fix only what the bug describes. Do not reword surrounding text,
   add new content, or improve adjacent wording. If fixing requires touching more than the
   described inconsistency, stop and mark the bug `needs-human`.
5. **Verify cross-document consistency** — after editing, read the relevant sections in every
   affected file and confirm: the shared vocabulary still matches verbatim, no new contradiction
   was introduced, and any reference to the fixed principle elsewhere is still accurate.
6. **Search for the same construct elsewhere** — grep the full repo for the root-cause construct
   (the exact term, cross-link pattern, or vocabulary that caused this bug), beyond the
   already-fixed files from step 3. For each additional hit, add a new backlog row describing it
   instead of fixing it inline — this fix stays scoped to the original bug. If the search finds
   nothing new, note that explicitly rather than skipping the search.
7. **Write the changelog entry first** — add a bullet to the target repo's own changelog
   (`CHANGELOG.md` under `## [Unreleased]`, or that repo's equivalent) describing what was wrong,
   what changed, and the file:line. Do this BEFORE touching the backlog. No changelog entry = do
   not proceed.
8. **Delete the backlog row** — remove the bug's row from the target repo's backlog. No
   strike-through, no "DONE" marker. The row must be gone. Only after the changelog entry is
   confirmed written.
9. **Commit atomically** — stage only the files you edited (no bulk `git add .`/`git add -A`).
   One bug = one commit; never batch two bugs into one commit.
10. **Report** — print the commit hash (or diff, if not committing) and a one-line summary. Loop
    to the next bug only if the user asked for more than one, and note any new backlog rows added
    by step 6.

**What counts as fixed:** the shared-verbatim term now reads identically everywhere it's used;
the previously-missing counterpart (enforcement row, index entry, cross-link) now exists; the two
documents now give consistent instructions; the relative link resolves correctly.

**Rules specific to docs mode:** no test-writing step exists (there's nothing to run); verify by
reading, not by assumption — actually open and re-read the sections after editing rather than
assuming the fix is sufficient.

---

## Code mode

**Bug definition:** same as `bug-hunt-protocol.md`'s code-mode section — a logic/state/
silent-failure error, confirmed by reading the code and reproducible in a test.

The severity vocabulary, verification-command list, and commit template below are **this repo's
(less_tokens) own registry-driven defaults** — generated from `.claude/tools/bugfix_registry.py`,
which re-exports `bug_hunt_registry.SEVERITY_TIERS` rather than redefining it (a bug is tiered
once, at hunt time; fixing it doesn't re-tier it). A different code-mode target repo needs its
own tuned verification commands and test convention; regenerate this section from that repo's own
registry copy rather than assuming these transfer.

### Severity rubric (as assigned during bug-hunt)

<!-- severity-rubric: begin -->
| Tier | Definition | Example |
|---|---|---|
| **data-loss** | Index corrupted or wrong results returned silently; token savings tracked incorrectly. | UPSERT collision clobbers a different file's embedding; duplicate source_key silently dropped. |
| **silent** | Behavior is wrong but no immediate data loss; results or counts are misleading. | search() returns stale-model rows; savings stats under-count due to off-by-one in char math. |
| **ux** | Hook gives bad signal, false block, or noise that trains the user to ignore it. | search-first blocks when a search did run; truncate hook logs savings when disabled. |
| **cosmetic** | Wording / formatting / log-line issue. No functional impact. | (none documented yet — surface only if encountered.) |
<!-- severity-rubric: end -->

Same table `bug-hunt-protocol.md` renders from `bug_hunt_registry.SEVERITY_TIERS` — bugfix
consumes the tier a bug was already assigned, it does not re-tier.

### Workflow (for each bug)

1. **Read `BACKLOG.md`** — find the next unfixed bug (skip anything "Blocked"; report which were
   skipped and why).
2. **Write a failing regression test first** — following this repo's naming/location convention
   below, before touching the fix. The test must fail against the current (buggy) code and
   demonstrate the exact defect.
3. **Implement the minimal fix** — the smallest change that makes the regression test pass
   without breaking other behavior. Do not refactor, expand scope, or "improve while you're in
   there".
4. **Run verification** — the commands below, in order. All must pass before proceeding.
5. **Search for the same construct elsewhere** — grep the full repo for the root-cause construct
   (the exact API call, pattern, or literal that caused this bug) beyond the file(s) just fixed.
   For each additional hit, add a new `BACKLOG.md` row describing it instead of fixing it inline —
   this fix stays scoped to the regression test written in step 2. If the search finds nothing
   new, note that explicitly rather than skipping the search.
6. **Write the `CHANGELOG.md` entry first** — one bullet under `## [Unreleased]`: what was wrong,
   what changed, file:line, and the regression test's name. Do this BEFORE touching `BACKLOG.md`.
7. **Delete the backlog row** — remove the bug's row from `BACKLOG.md`. No strike-through, no
   "DONE" marker. Only after the changelog entry is confirmed written.
8. **Commit atomically** — stage only the files you edited. One bug = one commit.
9. **Report** — print the commit hash, the regression test's nodeid, and a one-line summary. Note
   any new backlog rows added by step 5.

### Verification commands

<!-- verification-commands: begin -->
Regression test convention: `test_bug<id>_<short_description>.py` in `.claude/tests/unit/`.

Run in order after the minimal fix, before changelog/backlog/commit:

1. **lint** — `ruff check .`
2. **format check** — `ruff format --check .`
3. **regression test** — `.claude/.venv-tokens/bin/python .claude/tools/dev.py single <nodeid>`
4. **full unit suite** — `.claude/.venv-tokens/bin/python .claude/tools/dev.py unit`
<!-- verification-commands: end -->

### Commit message template

<!-- commit-template: begin -->
```
fix: <one-line summary>

<what was wrong, what changed, file:line>. Regression test: <test file>.

Co-Authored-By: <agent name> <noreply@anthropic.com>
```
<!-- commit-template: end -->

---

## Rules (both modes)

- **Repo-agnostic root:** always detect the repo root with `git rev-parse --show-toplevel`.
  Never hardcode a path.
- **Changelog before backlog:** write the changelog entry before deleting the backlog row.
  Always. The changelog entry is the receipt.
- **Minimal scope:** fix only the described bug. Do not refactor, expand, or improve. Three
  words changed is better than a rewritten paragraph.
- **No partial fixes:** if resolving one bug would introduce or leave open a new inconsistency,
  mark it `needs-human` rather than guessing at the resolution.
- **Verify by running (code mode) or reading (docs mode), not by assumption:** actually execute
  the verification commands, or actually re-read the edited sections. Don't assume the fix is
  sufficient because it "looks right".
- **Atomic commits:** one bug = one commit. Never batch two bugs into one commit.
- **Already-fixed bugs still need cleanup:** if the described bug is already gone, write a
  "confirmed fixed" changelog entry and delete the row. Never leave stale backlog items.
- **No hunting here:** this skill fixes bugs already logged. Finding new ones is
  `bug-hunt-protocol.md`'s job — do not go looking for unrelated bugs while fixing one.
- **Propagate the root-cause search:** after the fix (docs mode step 6, code mode step 5), grep
  the repo for the same construct and log any other hit as a new backlog row instead of fixing it
  inline. This is a targeted search for the exact construct just fixed, not a hunt for unrelated
  bugs.
- **Needs-human escape hatch:** anything too large, ambiguous, or cross-cutting to fix minimally
  gets marked `needs-human` instead of forced through.

## Parameters

- **Bug ID / description** — if the user names a specific bug, fix that one instead of reading
  the backlog top-to-bottom.
- **`--max-bugs N`** — fix at most N bugs before stopping (default: 1 per invocation unless the
  user says otherwise).

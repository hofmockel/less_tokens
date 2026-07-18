# Continue: less_tokens

> **Next focus:** land CX23 (verify or rule out cross-event hook misfires in Codex's single matcher-group `hooks.json` wiring).

## Current state
`main` is clean at `ae0c3b7`, matches `origin/main`. No open PRs. Working tree currently has **uncommitted doc edits** from this session (not yet committed/PR'd): `DECISIONS.md` (new CX18 entry), `BACKLOG.md` (CX18 row/prose replaced with CX23), `CHANGELOG.md` (new `[Unreleased]` entry citing CX18/CX23). No source code changed.

## What happened this session
- Picked up CX21 per the prior handoff, found it (and CX22, CX17, two docs-sync PRs) had already shipped in PRs [#72](https://github.com/hofmockel/less_tokens/pull/72)/[#75](https://github.com/hofmockel/less_tokens/pull/75)/[#70](https://github.com/hofmockel/less_tokens/pull/70)/[#73](https://github.com/hofmockel/less_tokens/pull/73)/[#74](https://github.com/hofmockel/less_tokens/pull/74) since the handoff was written — that handoff was stale by 4 commits.
- User chose to promote **CX18** (top of `BACKLOG.md`'s Next table by order/priority) since Ready-now was empty.
- Investigated CX18 (does Codex have a real end-of-turn/`Stop` hook contract). Found the vendored native `codex-cli 0.142.3` binary (`/opt/homebrew/lib/node_modules/@openai/codex/node_modules/@openai/codex-darwin-arm64/vendor/aarch64-apple-darwin/bin/codex`) embeds a full JSON Schema (`codex_app_server_protocol`) including a real `Stop` event (`hook_event_name: "Stop"`, `last_assistant_message`, `stop_hook_active` — structurally identical to Claude's `Stop` payload), plus `SessionStart`/`SubagentStart`/`SubagentStop`/`UserPromptSubmit`/`PreCompact`/`PostCompact`/`PermissionRequest`.
- Live-tested in a scratch dir (`codex exec -m gpt-5.5 --dangerously-bypass-hook-trust --dangerously-bypass-approvals-and-sandbox`): a bare `Stop` hook (sole entry, own matcher group) was accepted with no parse error but **never fired** on a clean tool-free single turn — same "schema-defined, CLI-accepted, silent no-op in headless `exec`" shape CX17 already found for `PostToolUse`.
- Closed CX18 as a research item with a recorded verdict (implementation not viable — `Stop` doesn't fire in `codex exec`; interactive TUI still untested, same gap CX17 left open). Full writeup in `DECISIONS.md`.
- While testing, stumbled onto something more urgent: `codex_hooks_json_value()` (CX21's shipped writer, `agents/common/hooks/hook_manifest.py`) always nests **every** hook entry into one matcher-group array regardless of declared `event`. Putting a `Stop`/`matcher:""` entry and a `PreToolUse`/`matcher:".*"` entry in one such group and firing only `PreToolUse` caused the `Stop`-labeled script to run too, with a `PreToolUse` payload — suggesting the CLI may not gate strictly on the declared `event` field within a shared group, and an empty matcher may act as a group-wide wildcard. This is exactly the shape every real shipped install uses (~20 entries in one group). Filed as **CX23**, P0, Research (bounded — not enough evidence yet to design a fix; a follow-up test isolating entries into separate groups timed out before completing, so it's inconclusive, not confirmed).
- Recorded the CX18 verdict in `DECISIONS.md`, replaced its `BACKLOG.md` row/prose with CX23's, renumbered the Next table, and added a `CHANGELOG.md [Unreleased]` entry. **Not yet committed or PR'd.**

## Open work
1. **Commit and PR this session's doc changes** (`DECISIONS.md`, `BACKLOG.md`, `CHANGELOG.md`) — `main` is a protected branch, branch+PR required (learned last session, still true).
2. **CX23** (P0, top of BACKLOG.md's Next table) — reproduce or rule out the cross-event hook misfire at realistic scale (real `HOOK_SPECS` entry counts/matchers, not just 2 entries), then design and verify a fix to `codex_hooks_json_value()`'s grouping if confirmed. Full repro steps and acceptance criteria in `BACKLOG.md`.
3. Reopen **CX17**/**CX18** together once an interactive `codex` TUI test becomes feasible (both are blocked on the same "not scriptable for unattended live testing" gap).
4. **CN1** (P2, still just filed) — resolve its open design questions (hard-block vs warn push; what "update" means in a bare git hook), then implement the pre-push freshness gate.
5. Third `parity.json` status value question (from two sessions ago) — still open, low priority, revisit only if it resurfaces naturally.

## Notes for next session
- `codex` CLI is installed locally (`codex-cli 0.142.3`, `which codex` → `/opt/homebrew/bin/codex`) and works for live testing. Use `-m gpt-5.5` explicitly — the bare default model slug errors ("requires a newer version of Codex"). Use `-c model_reasoning_effort=low` to keep test turns fast; some runs otherwise exceed a 170s tool timeout.
- Scratch test harness from this session (hooks.json + logging scripts) is in the session scratchpad, not the repo — not preserved across sessions. Rebuild it fresh for CX23 (see `BACKLOG.md`'s CX23 acceptance criteria for the exact repro shape needed).

## Suggested skills
- `$bugfix` is not quite right for CX23 — it's a research spike, not a scoped single-cause fix, until the misfire is confirmed at scale.

## Start here
Commit/PR the pending doc changes first (`git status` will show the three modified files), then start CX23 by reading its `BACKLOG.md` row and `DECISIONS.md`'s CX18 entry for the exact repro that surfaced it.

---
_Last updated at HEAD `ae0c3b7` on 2026-07-17 (doc changes above are uncommitted on top of this HEAD)._

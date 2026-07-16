---
name: continue
description: >
  Write a handoff document (continue.md) so a fresh agent can pick up exactly where this session
  left off. Invoke this skill when the user says "write a continue doc", "create a handoff",
  "hand off to the next agent", "save my progress", "prepare for the next session", or "/continue",
  and also whenever a session is clearly wrapping up and context needs to be preserved.
  If the user passes arguments, treat them as a description of what the next session will focus on.
argument-hint: "What will the next session be used for?"
trigger: /continue
---

# /continue

Shipped with less_tokens (`agents/claude/skills/continue/`), not a personal global skill — every
project less_tokens is installed into gets its own copy, paired with the `continue-freshness`
PreToolUse hook (`agents/common/hooks/continue_freshness.py`, wired in `hook_manifest.py`). That
hook blocks a raw `Read` of a stale `continue.md` even when this skill was never invoked — Phase 1
below is what an agent should do when writing a *new* handoff; the hook is what stops a *fresh*
agent from silently trusting an old one it just opened directly.

## Phase 1 — Staleness check (always run first)

Before writing anything, check whether an existing `continue.md` is still accurate.

1. Does `continue.md` exist in the project root? If not, skip to Phase 2.
2. Extract the recorded hash from its footer: `_Last updated at HEAD \`<hash>\`_`.
3. Run `git rev-list --count <hash>..HEAD`. Zero means fresh; nonzero means stale by that many
   commits — this is exactly what `continue-freshness.py` checks on every `Read` of the file, so
   a plain `Read(continue.md)` earlier in this session may already have surfaced (and blocked on)
   the same drift. Don't re-derive it by hand if it already told you.
4. If stale, run `git log --oneline <hash>..HEAD` to see what actually happened.

**Report the result in one of two ways before doing anything else:**

- **Fresh** — 0 commits since the recorded hash: `> continue.md is current (HEAD matches).` Read
  the full document and execute the **Start here** action as if the user had typed it themselves.
  Do not ask for confirmation — the document is the instruction. Only fall through to Phase 2 if
  the user explicitly asked to rewrite the handoff.
- **Stale** — N newer commits exist: show a compact table:

  ```
  > continue.md is stale — N commit(s) landed since it was written:
  | hash    | message |
  |---------|---------|
  | abc1234 | … |
  ```

  Then tell the agent: "Read these commits and the current `BACKLOG.md`/`backlog.md` before
  trusting the open-work section." Proceed to Phase 2 to rewrite.

If no commit hash is found in `continue.md` at all, treat the document as **potentially stale**:
report the file's last-modified timestamp vs. the most recent commit date and let the agent judge.

---

## Phase 2 — Write the handoff

Write `continue.md` in the project root — a lean handoff document that lets a fresh agent resume
this session without re-deriving context from scratch.

### If the user passed arguments

Treat the argument as the next session's focus area. Emphasise the context, open work, and
suggested next steps that are most relevant to that focus. De-emphasise or omit things the next
agent won't need.

### What to write

**Current state** — one paragraph. What is working, what is broken, and where things stand right now.

**What happened this session** — bullet list of key decisions, changes, or discoveries. Capture
the *why* behind choices, since a fresh agent can read the git log for the *what*.

**Open work** — what still needs doing, prioritised. Reference [BACKLOG.md](../../../BACKLOG.md)
rather than copying its content. If the session touched a shipped item, note whether its
`CHANGELOG.md` entry and `BACKLOG.md` deletion (see repo's backlog/changelog lifecycle rule) are
done or still pending — that's exactly the kind of loose end a fresh agent needs flagged.

**Suggested skills** — which skills the next agent should invoke, with a one-line reason each.
Draw from this repo's own skills (`/bug-hunt`, `/claudemd`, `/less-tokens`) plus user-level ones
that came up in this session (e.g. `/bugfix`), and any that would be useful for the next focus.

**Start here** — one clear first action for the next agent, so they're not paralysed by options.

### What NOT to include

The goal is a lean document, not a transcript.

- **No duplication** — if content exists in another artifact (README, DOCUMENTATION.md,
  BACKLOG.md, DECISIONS.md, CHANGELOG.md, commit message, PR description, issue), reference it by
  relative path or URL instead of copying it.
- **No journey logs** — mention outcomes, not everything that was tried and failed.
- **No sensitive data** — redact API keys, tokens, passwords, personal email addresses, phone
  numbers, and any other PII. Replace with a placeholder like `<API_KEY>` or `<USER_EMAIL>`.
- **No filler** — every sentence should earn its place. Caveman output style applies
  (`.claude/rules/caveman.md`) — short, direct, no padding.
- **Always embed the current HEAD commit hash** somewhere in the doc, using the exact anchor
  format `_Last updated at HEAD \`<7-char hash>\`_` — the `continue-freshness` hook regexes for
  this literal pattern, so a different phrasing means the enforced check silently does nothing. Note
  explicitly if the working tree is dirty — this repo often has uncommitted tracked changes at
  handoff time.

### Format

```markdown
# Continue: <project-name>

> **Next focus:** <one-line summary of what comes next, or the user's argument if provided>

## Current state
<paragraph — what is working and what is not>

## What happened this session
- <key decision or change, with the why>
- ...

## Open work
<prioritised list, or a reference like "See [backlog.md](backlog.md)">

## Suggested skills
- `/skill-name` — reason
- `/skill-name` — reason

## Start here
<single, concrete next action>

---
_Last updated at HEAD `<7-char hash>` on <date>._
```

Keep the whole document under ~300 words unless the session was unusually complex. A fresh agent
should be able to read it in under a minute and know exactly what to do next.

---

## Why this is enforced, not just documented

A 2026-07-16 session read a `continue.md` that was 12 commits stale and nearly re-built a
`docs-site/` from scratch over already-shipped work — Phase 1 above existed the whole time, but
nothing forced it to run, because the agent never invoked `/continue` at all; it just read the file
directly, as any fresh agent normally does. `continue-freshness.py` closes that gap at the tool-call
level instead of relying on an agent to remember and follow Phase 1 unprompted. Keep both: the hook
catches unprompted reads, Phase 1 is what to actually do once staleness is confirmed (rewrite,
don't just note it and proceed).

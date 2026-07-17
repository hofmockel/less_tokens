---
name: continue
description: Write or use a project-root continue.md handoff so a fresh Codex session can resume exactly where the current one left off. Use when the user asks to write a continue doc, create a handoff, hand off to the next agent, save progress, prepare for the next session, resume from continue.md, run /continue, or when a session is clearly wrapping up and durable context should be preserved. If the user provides extra text, treat it as the next session's focus.
---

# Continue handoffs

Pair this skill with the installed `continue-freshness` PreToolUse hook. The hook blocks a direct
filesystem read of a stale `continue.md`; this workflow explains how to assess, use, or replace it.

## Resume from an existing handoff

1. Extract the footer anchor `_Last updated at HEAD \`<hash>\`_` without trusting the body.
2. Run `git rev-list --count <hash>..HEAD`.
3. If the count is zero, read the document and execute its **Start here** action as the user's
   instruction.
4. If the count is nonzero, run `git log --oneline <hash>..HEAD`, inspect the relevant commits and
   current backlog, and rewrite the handoff before acting on stale open-work claims.
5. If no valid anchor exists, treat the handoff as potentially stale and compare its modification
   time with the latest commit.

## Write a handoff

Create or replace project-root `continue.md` with only durable resumption context:

- `Next focus`: one concrete objective, using any user-supplied argument.
- `Current state`: branch, clean/dirty state, and important constraints.
- `What happened`: outcomes and decisions; let commits carry implementation detail.
- `Open work`: prioritized remaining work or a pointer to the canonical backlog.
- `Suggested skills`: only skills likely to matter next session.
- `Start here`: one executable first action.
- Footer: `_Last updated at HEAD \`<7-40 character hash>\` on <date>._`

Keep the handoff under about 300 words unless complexity requires more. Reference existing specs,
issues, commits, and docs instead of duplicating them. Record whether the working tree is dirty.
Exclude secrets, credentials, personal data, failed-attempt journals, and conversational filler.

Use this skeleton:

```markdown
# Continue: <project-name>

> **Next focus:** <one-line objective>

## Current state
<branch, working-tree state, constraints>

## What happened
- <outcome or decision>

## Open work
<remaining work or canonical backlog link>

## Suggested skills
- `$skill-name` — <reason>

## Start here
<one concrete action>

---
_Last updated at HEAD `<hash>` on <date>._
```

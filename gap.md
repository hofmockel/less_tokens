# gap.md — Unaddressed token attack surfaces

What less_tokens does not yet attack. Excludes surfaces already covered (Strategies 1–5) or already in [BACKLOG.md](BACKLOG.md) (S6–S13, claudemd). These are the remaining holes.

## Coverage map

| Surface | Bucket | Status |
|---|---|---|
| Whole-file Read | input | covered (search) + backlog S9/S13 |
| Verbose prose | output | covered (caveman) + backlog S11 |
| Oversized tool dumps | tool | covered (truncation S3) |
| Long-session history | history | covered (compaction S5) |
| CLAUDE.md always-loaded | fixed | **built (claudemd skill)** |
| Symbol locate via grep | input | backlog S8 |
| Re-read after edit | input | backlog S10 |
| Structured test/lint output | tool | backlog S12 |
| Model tier routing | output | backlog S6 |
| **Tool / MCP schema overhead** | fixed | **GAP G1** |
| **In-session re-read / re-search** | input | **GAP G2** |
| **Directory & listing dumps** | tool | **GAP G3** |
| **Noise-file reads** | input | **GAP G4** |
| **WebFetch full-page dumps** | tool | **GAP G5** |
| **Live token governor** | meta | **GAP G6** |
| **Subagent context re-derivation** | input | **GAP G7** |
| **Reprinting files in output** | output | **GAP G8** |
| **Always-loaded beyond CLAUDE.md** | fixed | **GAP G9** |
| **Search-result redundancy** | input | **GAP G10** |

The whole toolkit lives in the input/output/tool buckets. The **fixed per-turn** bucket (paid every turn, no matter what) is barely touched — only claudemd. That bucket is the biggest blind spot.

---

## G1 — Tool / MCP schema overhead (fixed, every turn) — HIGH

**Cost.** Every tool definition sits in context on every turn. A few MCP servers with fat JSON schemas can add thousands of tokens per turn before Claude does anything. This is the single largest untouched fixed cost — it dwarfs CLAUDE.md on a connector-heavy setup.

**Why unaddressed.** less_tokens only thinks about files. Tool defs are invisible to it.

**Direction.** Lazy tool exposure: load only the tools a task needs, fetch the rest on demand (the deferred-tool / search-for-schema pattern). For Claude Code, an `mcp-prune` config + a `.toolignore` that drops unused servers from the session. Audit tool: `tools/toolcost.py` estimates per-server schema tokens so the user sees the tax. Enforcement is config-time (what gets loaded), not a runtime hook.

**Impact.** Often the biggest single win on real setups. Fixed cost × every turn.

---

## G2 — In-session re-read / re-search — HIGH

**Cost.** Claude reads the same file or runs the same search twice in a session. Each repeat re-injects the full payload. Compaction (S5) only fires late; nothing stops the duplicate before it lands.

**Direction.** A PreToolUse content cache keyed on `(tool, args, file-mtime)`. On a repeat with unchanged inputs, block and return `"already in context (turn N) — unchanged since"` instead of re-injecting. Deterministic; the state already half-exists (`STATE_DIR/last-search`). Note: evaluate.md cut a "query cache" as an embedding-compute saver — this is a different lever: stop re-injecting identical results into context.

**Impact.** High on iterative sessions where Claude circles the same files.

---

## G3 — Directory & listing dumps — MED/HIGH

**Cost.** `ls -R`, `find`, `tree`, `git status` on a big tree, and `Glob` returning hundreds of paths. Truncation (S3) caps the size but keeps random head/tail — the listing is still mostly noise.

**Direction.** A scoped lister skill/tool that returns a depth-limited, `.gitignore`-aware, summarized tree (counts per dir, not every file). PreToolUse on `Bash` detects bare `ls -R`/`find .`/`tree` and routes to it. Cap `Glob` result count with a "N more" tail.

**Impact.** Medium-high; these commands are reflexive and dump a lot.

---

## G4 — Noise-file reads — HIGH

**Cost.** Reading lockfiles (`package-lock.json`, `poetry.lock`), generated/minified bundles, large data files (CSV/JSON), notebooks, and binaries is near-pure waste — thousands of tokens of content Claude rarely needs in full. `.claudeignore` scopes the *project file list* but does not stop an explicit `Read` of these paths.

**Direction.** PreToolUse on `Read`: match a noise-glob list (config `READ_DENY_GLOBS`); block with `"<file> is a lockfile/generated/data file — read a slice or summarize, don't load whole."` For data files, point to `head`/`wc`/a column-summary instead. Binary detection (null bytes) → hard block.

**Impact.** High and easy; one mis-Read of a lockfile is a whole budget.

---

## G5 — WebFetch full-page dumps — MED

**Cost.** WebFetch returns the whole page; truncation cuts it blindly, often dropping the part that mattered. Web search results carry boilerplate.

**Direction.** A main-content extractor (readability-style: strip nav/footer/script) applied PostToolUse on `WebFetch` before the result reaches context. Returns the article body, not the chrome.

**Impact.** Medium; depends how much web work the host does.

---

## G6 — Live token governor — MED (meta)

**Cost.** `stats.py` measures savings *after the fact* and is opt-in. Nothing watches the live session and *adapts*. Budgets (truncation ceiling, search `k`, compaction threshold) are static.

**Direction.** A running session-token estimate (transcript size is already read by compact-trigger) that tightens knobs as budget depletes: smaller `MAX_TOOL_OUTPUT_CHARS`, lower `k`, earlier compaction, stricter caveman. One PostToolUse governor reading the same `transcript_path`, writing a live tier to state that the other hooks consult.

**Impact.** Medium; multiplies the existing strategies instead of adding a new one.

---

## G7 — Subagent context re-derivation — MED

**Cost.** Each spawned agent starts cold and re-reads/re-searches the same files the parent already had. Parallel agents multiply the same input cost. (The platform itself warns this is the expensive path.)

**Direction.** A discipline + helper: parent writes a compact context pack (the relevant slices/search hits) to `STATE_DIR`, agents read that instead of re-deriving. A skill documenting "pass results, don't re-discover." Hard to hook-enforce; mostly rule + helper.

**Impact.** Medium, spiky — large when subagents are used heavily.

---

## G8 — Reprinting whole files in output — MED

**Cost.** Caveman governs prose, not code. Claude still pastes entire files / large blocks into the response instead of using `Edit`, paying full output tokens for content already on disk.

**Direction.** Stop-hook check (pairs with S11): flag responses containing a large code block whose content closely matches an existing file — nudge `"use Edit, don't reprint <file>."` Deterministic via substring/line-overlap against the named file.

**Impact.** Medium; common in edit-heavy work.

---

## G9 — Always-loaded surfaces beyond CLAUDE.md — MED

**Cost.** claudemd prunes CLAUDE.md, but `.claude/rules/*` is also appended every turn, and **every installed skill's description is always-loaded**. As skills accumulate, their descriptions become a silent growing fixed tax — the same disease claudemd treats, one level over.

**Direction.** Extend the audit: `claudemd_audit.py --rules` covers `.claude/rules/*`; a `skilldesc_audit` flags bloated/overlapping skill descriptions and enforces a per-description word cap. Same budget mechanism, wider scope.

**Impact.** Medium and grows with skill count — worth it before a skill library gets large.

---

## G10 — Search-result redundancy — MED/LOW

**Cost.** `search.py` returns `k` chunks that can overlap or near-duplicate (adjacent chunks of the same function, the same heading echoed across docs). Pay for the same content more than once per query.

**Direction.** Dedupe in `search.py`: drop a hit whose cosine to an already-selected hit exceeds a threshold, backfill the next distinct one. Pure post-processing on vectors already in hand.

**Impact.** Low-medium; sharpens an existing strategy rather than adding cost elsewhere.

---

## Priority

1. **G1** (tool/MCP schema) and **G4** (noise-file reads) — biggest unaddressed cost, G4 is also the cheapest to ship.
2. **G2** (re-read cache) and **G3** (listing dumps) — frequent, deterministic.
3. **G6** (live governor) and **G9** (always-loaded beyond CLAUDE.md) — multiply/extend what exists.
4. **G5, G7, G8, G10** — narrower or harder to enforce.

The headline: less_tokens owns the input/output/tool buckets but has barely touched **fixed per-turn cost** (G1, G9) — the tax paid on every single turn regardless of the task. That is where the next big win is.

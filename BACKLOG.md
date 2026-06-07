# Backlog

Planned work not yet started. Maintainer: add `CHANGELOG.md` entry + delete item here before merging. See [.claude/skills/bug-hunt/SKILL.md](.claude/skills/bug-hunt/SKILL.md) / [.claude/skills/bug-hunt/bughuntlog.md](.claude/skills/bug-hunt/bughuntlog.md) for the bug-hunt protocol.

---

## Bugs

Confirmed defects found by code inspection. Each has a specific file and line reference.

- **Bug 27: REPO resolution in hooks is broken in dev environment** (.claude/hooks/search-first.py:15)
- **Bug 28: model_profiles.py inconsistent heuristics for Opus models** (.claude/tools/model_profiles.py:25)
- **Bug 29: stats.py _load_records silent on JSON decode errors** (.claude/tools/stats.py:65)
- **Bug 30: bughunt.md coverage list is for a different project (AIPortfolio)** (.claude/skills/bug-hunt/SKILL.md:28)

---

## Vector Search & Indexing

### High Priority

- **Multi-repo indexing** — support indexing across multiple project roots so a single search spans related repos (monorepo support)
- **Configurable chunk size** — expose `MAX_CHUNK_CHARS` in `.claude/tools/search_config.py` so users can tune for their Claude model's context window
- **TypeScript / JavaScript chunking** — add a `chunk_js` strategy (function-level, like `chunk_python`) for projects with `.ts` / `.js` source

### Medium Priority

- **Keyword fallback** — when `fastembed` is not installed or the model download fails, fall back to a stdlib BM25/TF-IDF search over raw chunk text. Quality is lower but the system remains usable before the model cache is warm. Exit code and output format identical to normal search so hooks require no changes.
- **Implement graceful degradation** — explicit handlers in `.claude/tools/embeddings.py` and `.claude/tools/search.py` for each failure condition; each catches the failure, emits a structured warning to stderr, and continues rather than propagating an exception.

### Low Priority

- **Remote index option** — store `index.db` in S3 / R2 for teams sharing an index across machines
- **`search.py` interactive REPL** — `search.py --interactive` for rapid exploratory querying during development
- **`embeddings.py` file-watcher mode** — a `watch` subcommand using `watchdog` that monitors `INDEXED_SOURCE_DIRS` and triggers incremental refresh automatically on save, as an alternative to the PostToolUse hook

---

## Installer

### High Priority

- **`install.py --check`** — verify that a previous install is still valid: venv exists, fastembed is installed, `index.db` is present and has ≥1 row, `VENV_PY` resolves to a real interpreter, `.claude/hooks/*.py` exist and are executable, hooks are wired in `.claude/settings.json` (the file the installer actually writes — `install.py:1004`), and a `.claude/tools/search.py "test"` smoke query returns without error. Print `[✓]`/`[✗]` per check and exit non-zero with a specific message for each failure.
- **Auto-append caveman prompt to a resolved `CLAUDE.md` target** — `--caveman` copies `.claude/rules/` and wires the reminder hook, but appending the prompt to `CLAUDE.md` is left as a printed `cat .claude/rules/caveman.md >> CLAUDE.md` next-step (`install.py:1069-1070`). The reminder hook nags for terse output from the first turn even though the style spec it references is not yet in context. `_caveman_in_claude_md()` (`install.py:566`) already detects the duplicate — extend it to perform an idempotent append using guarded block markers (like the `.gitignore` block). Also resolve the ambiguous target: in a clone-into-host layout there are two `CLAUDE.md` files (host root vs `less_tokens/CLAUDE.md`), and `cat >>` against a missing host root file silently creates one containing only the caveman section with no `# CLAUDE.md` header. The installer should name the absolute target path and create a minimal valid `CLAUDE.md` (standard header) when absent. (`install.py:566`, `install.py:1064-1070`)

### Medium Priority

---

## Hooks & Caveman Mode

### High Priority

- **Calibrated verbosity levels** — replace binary caveman on/off with a 1–5 verbosity dial in `.claude/tools/search_config.py`; level 1 = full caveman, level 5 = normal prose
- **Per-task exemptions** — allow CLAUDE.md to declare specific task types (e.g., user-facing copy, PR descriptions) that bypass caveman mode

---

## Observability

### Medium Priority

- **Search quality metrics** — log query, top result score, and result count to `.claude/state/search.log` so users can audit what Claude is finding
- **`search.py` query history log** — append each query and its top result score to `.claude/state/search-history.log` so maintainers can audit what Claude searched for and identify queries that consistently return poor results
- **Dashboard command** — `embeddings.py stats --verbose` showing index age, chunk count by source type, and estimated coverage

---

## Developer Experience

### Medium Priority

- **Consider GitHub self-hosted runners for the perf job** — the `perf` CI job downloads the fastembed model (~130 MB `BAAI/bge-small-en-v1.5`) and relies on `actions/cache` for subsequent runs; a cold cache miss adds significant wall-clock time and introduces network variance into timing results. A self-hosted runner with the model pre-installed in `~/.cache/huggingface` would eliminate both the download and the cache-restore step, and would provide stable CPU baselines so reduction-percentage regressions aren't masked by runner noise. Trade-off: self-hosted runners require infrastructure maintenance and the runner must be registered to the repo; only worth the overhead if perf run times become a bottleneck or timing variance starts producing false failures.

---

## Proposed Strategies

### Strategy 7 — Grep-before-Read

**Problem.** Claude reads whole files to find one function or symbol. A 400-line file read for one target costs ~400 lines of tokens. Happens constantly.

**Goal.** Force line-number lookup before full Read. Then use `Read` with `offset`+`limit` to fetch only the relevant slice.

**Three pieces:**

1. **CLAUDE.md instruction** (free, immediate) — add rule: "Never Read a file without first knowing the target line. Use `grep -n` to find it, then Read with offset+limit."

2. **`.claude/hooks/grep-first.py` — PreToolUse on `Read`** (enforcement)
   - Fire when `Read` called with no `offset`
   - Check file line count
   - If lines > threshold (default 150): block with message `"<file> has N lines. grep -n first, then Read with offset+limit."`
   - If lines ≤ threshold: pass (small files fine to read whole)
   - Exempt files already gated by search-first (indexed files) — redundant
   - Exempt `CLAUDE.md`, `settings.json` — always small

3. **Savings tracking** (optional) — log blocked Reads + estimated lines saved into existing `.claude/tools/stats.py` pipeline

**Sketch of hook:**
```python
# .claude/hooks/grep-first.py  — PreToolUse: Read
import json, sys
from pathlib import Path

payload = json.load(sys.stdin)
if payload.get("tool_name") != "Read":
    sys.exit(0)

inp = payload.get("tool_input", {})
if inp.get("offset"):          # already targeted — pass
    sys.exit(0)

path = inp.get("file_path", "")
try:
    lines = Path(path).read_text(errors="ignore").count("\n")
except OSError:
    sys.exit(0)

THRESHOLD = 150
if lines > THRESHOLD:
    print(json.dumps({
        "decision": "block",
        "reason": f"{Path(path).name} has {lines} lines. grep -n first, then Read with offset+limit."
    }))
    sys.exit(0)

sys.exit(0)
```

**Effort:** ~1h (hook + CLAUDE.md rule + wire into `.claude/settings.json`). Stats integration optional.

### Strategy 6 — Tiered Effort

Route each task to the cheapest Claude model + effort level it needs. Three tiers: **L1 Mechanical** (Haiku, one confirmation, no summaries), **L2 Rules** (Sonnet, result + brief reasoning), **L3 Planning** (Opus, full analysis). Before each task the agent emits one line with the recommended tier only when it changes from the prior turn. Implementation: `.claude/rules/tier-matrix.md` appended to `CLAUDE.md` + `AGENT_TIER_HINTS: bool` config flag. Expected savings: 50–70% blended reduction.

### Strategy 4 — Prompt Caching *(deferred — likely redundant with Claude Code defaults)*

Claude Code already caches the system prompt and `CLAUDE.md` automatically. Revisit if measurement on a real session shows the auto-cache is missing large doc files Claude reads every turn.

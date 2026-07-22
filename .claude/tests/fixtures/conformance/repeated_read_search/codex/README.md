# `repeated_read_search` — Codex bounded live capture

Captured 2026-07-22 against installed `codex-cli 0.145.0` (standalone), replayed against the
release-tagged `0.144.6` hook schema (same field set as
`.claude/tests/fixtures/codex-hooks/0.144.6/pre-tool-use-bash.json`) since `0.145.0` currently
falls outside `install.py`'s verified `0.142.3–0.144.6` window (CX26) and `install.py --dry-run`
correctly refused to wire hooks against it — a real, separate finding worth its own backlog row,
not silently worked around.

## Method

`agents/codex/hooks/context-cache.py` was invoked directly, twice per probe (`PostToolUse` to
record, `PreToolUse` to check), via its real stdin JSON contract, with `LESS_TOKENS_STATE_DIR`
pointed at a disposable temp state dir so the probes don't touch this repo's own dogfooded state.
Three probes, because reading `context_cache.py`'s source (`agents/codex/hooks/context-cache.py`
+ `agents/common/hooks/context_cache.py`) turned up a real asymmetry before any live call was
made: the hook imports `map_read_or_search` (`_codex_runtime.py`), which only rewrites the opt-in
`mcp__filesystem__read_*` tool shape into a synthetic `Read` — unlike `search-first.py`,
`grep-first-read.py`, `read-guard.py`, `continue-freshness.py`, `read-after-edit.py`, and
`auto-slice.py`, it never calls `map_bash_read` (added by CX25, whose fix list explicitly named
those six hooks and not this one). So a default Codex install's dominant real read path — `cat`/
`head`/`tail`/`sed -n` over `Bash` — never reaches `context_cache.py`'s `Read` branch at all, and
its `Bash` branch only recognizes `pwd`, `git status`, `rg`, and `pytest` as cacheable
(`cacheable_bash_command`, `agents/common/hooks/context_cache.py`) — `cat` isn't among them.
Net effect: the *search* half of this workload is genuinely enforced on a default install; the
*read* half is currently dead there, and only reachable through the opt-in `mcp__filesystem__`
server path.

## Results

| Probe | Input | Output |
| --- | --- | --- |
| `rg add src/example.py` (search, `Bash`) | Post: record; Pre: same command again | **Blocked**: `context-cache: Bash \`rg add .../src/example.py\` already ran (call #1, 0s ago). Output is already in context — skip repeat.` via the native `permissionDecision: deny` contract |
| `cat src/example.py` (read, `Bash`, default-install path) | Post: "record"; Pre: same command again | **Not blocked** — exit 0, no `hookSpecificOutput`, no denial. `map_read_or_search` never rewrites the `Bash` `cat` shape, so `check_context_cache` never enters its `Read` branch, and the `Bash` branch's `cacheable_bash_command` allowlist excludes `cat`. The file re-enters context uncached. |
| `mcp__filesystem__read_text_file(path=src/example.py)` (read, opt-in MCP path) | Post: record; Pre: same call again | **Blocked**: `context-cache: example.py already in context (call #N, 0s ago) — file unchanged. Skip this Read; content is still valid in context.` — proves the `Read`-branch logic itself works; it just isn't reachable from a default install's `Bash`-only read surface |

Fixture payloads (sanitized): `0.144.6/post-tool-use-bash-rg.json` +
`0.144.6/pre-tool-use-bash-rg-repeat-blocked.json` (search, enforced);
`0.144.6/post-tool-use-bash-cat.json` + `0.144.6/pre-tool-use-bash-cat-repeat-not-blocked.json`
(read, default install, not enforced); `0.144.6/post-tool-use-mcp-read.json` +
`0.144.6/pre-tool-use-mcp-read-repeat-blocked.json` (read, opt-in MCP install, enforced).

`event_fired: true` for all three probes (the hook always runs and returns cleanly).
`action_enforced: true` only for the search (`rg`) and opt-in-MCP-read probes; the default-install
`cat`/`head`/`tail`/`sed` read path is `action_enforced: false` — an honest split rather than a
single workload-wide boolean, matching the caveat pattern already used for `repeated_read_search:claude`
(Bash-fallback gap) and CX25/CX28's existing enforcement-boundary disclosures.

Schema provenance: same as `.claude/tests/fixtures/codex-hooks/README.md`.

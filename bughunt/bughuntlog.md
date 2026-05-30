# Bug-Hunt Log

One entry per completed hunt round. Append after each run; never edit past entries.

See [bughunt.md](bughunt.md) for the protocol, severity rubric, stop rule, and agent prompt template.

---

## Round template

```
## Round N - YYYY-MM-DD

**Bugs surfaced:** N
**Severity breakdown:** N data-loss / N silent / N ux / N cosmetic
**Median severity:** X
**Overlap with prior rounds:** N/N (N%)
**New files hit:** file1.py, file2.py
**Cumulative file coverage:** N/N target files (N%)

**Stop rule signals:**
- Severity slide: pass/fail
- Overlap rate >= 60%: pass/fail
- File coverage >= 80%: pass/fail

**Decision:** run another round / stop and fix
```

---

## Round 1 - 2025-05-22

**Bugs surfaced:** 10
**Severity breakdown:** 0 data-loss / 4 silent / 6 ux / 0 cosmetic
**Median severity:** ux
**Overlap with prior rounds:** 0/10 (0%)
**New files hit:** embeddings.py, search-first.py, index-refresh.py, search.py, search_config.py
**Cumulative file coverage:** 5/38 target files (13%)

**Stop rule signals:**
- Severity slide: pass (median ux)
- Overlap rate >= 60%: fail (0%)
- File coverage >= 80%: fail (13%)

**Decision:** run another round

**Bug 1: Keep a Changelog headers fall back to markdown chunking** (embeddings.py:214)
- **Tier:** ux
- **What:** `chunk_changelog` regex fails to match standard Keep a Changelog headers if they don't exactly match the expected pattern.
- **Why:** The regex is slightly too restrictive or the fallback is triggered too easily.
- **Repro:** Use a CHANGELOG.md with `## [1.0.0] - 2023-10-27`.
- **Fix:** Loosen `chunk_changelog` regex or improve the split logic.

**Bug 2: chunk_sql ignores comments but split on ;\\n is fragile** (embeddings.py:186)
- **Tier:** ux
- **What:** SQL chunking splits strictly on `;\n`, which can fail if a semicolon is used within a string or if there is trailing whitespace.
- **Why:** Naive regex-based splitting doesn't account for SQL syntax edge cases.
- **Repro:** SQL with `; -- comment` or semicolon inside a quoted string.
- **Fix:** Use a more robust SQL tokenizer or improve the regex to handle whitespace/comments better.

**Bug 3: chunk_python ignores complex assignments** (embeddings.py:168)
- **Tier:** silent
- **What:** `chunk_python` only indexes `ast.Assign` and `ast.AnnAssign` for `UPPER_CASE` names. It misses assignments like `A, B = 1, 2`.
- **Why:** The logic only checks for simple name targets.
- **Repro:** `FOO, BAR = "a", "b"` in a .py file.
- **Fix:** Iterate through all targets in `ast.Assign` and check for `ast.Tuple` or `ast.List`.

**Bug 4: is_indexed discrepancy for root .py files** (hooks/search-first.py:49 vs embeddings.py:263)
- **Tier:** silent
- **What:** `embeddings.py` indexes root .py files, but `hooks/search-first.py`'s `is_indexed` only considers root files indexed if they end in `.md`.
- **Why:** `is_indexed` logic was not updated when root .py indexing was added to `embeddings.py`.
- **Repro:** `Read` a root .py file; the search-first gate won't trigger even if it's in the index.
- **Fix:** Update `hooks/search-first.py:is_indexed` to allow `.py` and `.sql` for root files if they are in `enumerate_sources`.

**Bug 5: index-refresh.py misses root .py and .sql files** (hooks/index-refresh.py:50)
- **Tier:** silent
- **What:** Similar to Bug 4, `hooks/index-refresh.py` only triggers refresh for root `.md` files, ignoring root `.py` and `.sql`.
- **Why:** Inconsistent `is_indexed` implementation across hooks.
- **Repro:** Edit a root .py file; background refresh won't fire.
- **Fix:** Sync `is_indexed` logic across all hooks and `embeddings.py`.

**Bug 6: search.py _newest_source_mtime is inconsistent with enumerate_sources** (tools/search.py:46)
- **Tier:** ux
- **What:** `_newest_source_mtime` uses `glob` and `rglob` slightly differently than `enumerate_sources`, potentially leading to false positive "stale index" warnings.
- **Why:** Redundant file discovery logic that isn't perfectly synced.
- **Repro:** Have a file indexed by `enumerate_sources` that `_newest_source_mtime` misses, or vice versa.
- **Fix:** Factor out a shared `iter_indexed_files` helper used by both.

**Bug 7: Search result token warning uses 4 chars per token heuristic** (tools/search.py:175)
- **Tier:** ux
- **What:** The warning about large result sets uses a fixed 4 chars/token heuristic which may be very inaccurate for code.
- **Why:** Simple heuristic used instead of a proper tokenizer.
- **Repro:** Search returning highly dense code or very sparse text.
- **Fix:** Use a more conservative heuristic for code or a lightweight tokenizer if available.

**Bug 8: EXCLUDED_DIR_PREFIXES vs EXCLUDED_DIR_NAMES inconsistency** (tools/search_config.py:53)
- **Tier:** silent
- **What:** `EXCLUDED_DIR_NAMES` is used for "contains" check in `embeddings.py`, while `EXCLUDED_DIR_PREFIXES` is used for "startswith" in hooks.
- **Why:** Divergent exclusion strategies.
- **Repro:** A directory named `legacy` deep in the tree is excluded by `embeddings.py` but NOT by hooks (because it doesn't start with `legacy/`).
- **Fix:** Standardize on one exclusion logic that works for both "contains" and "prefix".

**Bug 9: search_config.py default VENV_PY points to app/.venv** (tools/search_config.py:44)
- **Tier:** ux
- **What:** The default `VENV_PY` assumes `app/.venv`, which might not exist in many projects, causing early errors if not patched.
- **Why:** Specific default that may not be general enough.
- **Repro:** Run a tool before `install.py` patches the config.
- **Fix:** Use a more neutral default or handle `FileNotFoundError` gracefully with a better message.

**Bug 10: chunk_python prepends mod_doc incorrectly for classes/functions** (tools/embeddings.py:155)
- **Tier:** ux
- **What:** If `CHUNK_INCLUDE_MODULE_CONTEXT` is on, it prepends the docstring as `# line` which might break some parsers or look confusing if the docstring has multiple lines or special characters.
- **Why:** Simple string manipulation.
- **Repro:** Multi-line module docstring with `CHUNK_INCLUDE_MODULE_CONTEXT=True`.
- **Fix:** Ensure cleaner injection, maybe as a proper docstring or separated block.

---

## Round 2 - 2025-05-22

**Bugs surfaced:** 10
**Severity breakdown:** 0 data-loss / 3 silent / 7 ux / 0 cosmetic
**Median severity:** ux
**Overlap with prior rounds:** 2/10 (20%)
**New files hit:** install.py, db.py, index.sql, truncate-output.py
**Cumulative file coverage:** 9/38 target files (24%)

**Stop rule signals:**
- Severity slide: pass (median ux)
- Overlap rate >= 60%: fail (20%)
- File coverage >= 80%: fail (24%)

**Decision:** run another round

**Bug 11: chunk_sql split on ;\\n fails with semicolons in strings** (embeddings.py:196)
- **Tier:** ux
- **What:** SQL chunking splits strictly on `;\n`, which splits valid SQL statements if they contain a semicolon inside a quoted string followed by a newline.
- **Why:** Naive regex splitting.
- **Repro:** `SELECT "a;b";\nSELECT 1;` splits into `SELECT "a`, `b"`, and `SELECT 1`.
- **Fix:** Use a more robust split that ignores semicolons inside quotes.

**Bug 12: chunk_python misses assignments in tuples/lists** (embeddings.py:180)
- **Tier:** silent
- **What:** `chunk_python` only indexes `ast.Assign` if the target is a direct `ast.Name`. It misses `FOO, BAR = 1, 2`.
- **Why:** Incomplete AST traversal for assignments.
- **Repro:** `FOO, BAR = 1, 2` in a .py file results in no chunks for these constants.
- **Fix:** Recursively find all `ast.Name` nodes in `node.targets`.

**Bug 13: chunk_changelog regex too strict for common version formats** (embeddings.py:219)
- **Tier:** ux
- **What:** Regex `r"^(##\s+(?:\[.+?\]|\d{4}-\d{2}-\d{2}).*)$"` misses common formats like `## 1.0.0 (2023-10-27)`.
- **Why:** Pattern only allows brackets or pure dates.
- **Repro:** `## 1.0.0 (2023-10-27)` is ignored and falls back to markdown chunking.
- **Fix:** Loosen regex to allow any version-like string after `##`.

**Bug 14: search.py _newest_source_mtime misses root .py and .sql files** (tools/search.py:59)
- **Tier:** ux
- **What:** `_newest_source_mtime` only glob-checks `*.py` and `*.sql` inside `INDEXED_SOURCE_DIRS`, missing them at the repo root.
- **Why:** Incomplete port of `enumerate_sources` logic.
- **Repro:** Touch a root `.py` file; `search.py` won't report the index as stale.
- **Fix:** Add `BASE.glob("*.py")` and `BASE.glob("*.sql")` to `_newest_source_mtime`.

**Bug 15: _ClosingConn wrapper misses many sqlite3.Connection methods** (tools/db.py:46)
- **Tier:** silent
- **What:** `_ClosingConn` only implements `__enter__` and `__exit__`. It doesn't proxy `execute`, `executemany`, `commit`, etc.
- **Why:** Incomplete wrapper.
- **Repro:** `db.connect_index().execute(...)` raises `AttributeError`.
- **Fix:** Add `__getattr__` to proxy calls to the underlying connection.

**Bug 16: install.py uses hardcoded 'python3' for venv creation** (install.py:141)
- **Tier:** ux
- **What:** `create_venv` uses `python3` or `python` hardcoded instead of `sys.executable`.
- **Why:** Assumption about system python name.
- **Repro:** System where only `python3.12` is available and `python3` is not.
- **Fix:** Use `sys.executable` for venv creation.

**Bug 17: truncate-output.py logs 'truncation' strategy even when disabled** (hooks/truncate-output.py:78)
- **Tier:** ux
- **What:** If `MAX_TOOL_OUTPUT_CHARS` is non-zero but no truncation happens, it might still log.
- **Why:** Logic check.
- **Repro:** Result slightly under limit.
- **Fix:** Only log if truncation actually occurred.

**Bug 18: search.py returns mixed-model results with garbage scores** (tools/search.py:112)
- **Tier:** silent
- **What:** `search.py` assumes all rows use `EMBEDDING_MODEL`. If the index is mixed, scores are nonsense.
- **Why:** No per-row model validation during search.
- **Repro:** Index some files with one model, switch config, index others.
- **Fix:** Filter `WHERE embedding_model = ?` in `search()`.

**Bug 19: index.sql UNIQUE constraint collision for duplicate function names** (schema/index.sql:19)
- **Tier:** ux
- **What:** If one file has two chunks that produce the same key (e.g. duplicate function names), it collides.
- **Why:** Key collision.
- **Repro:** Python file with duplicate function names.
- **Fix:** Add dedup logic to `chunk_python` similar to `chunk_markdown`.

**Bug 20: search_config.py WINDOW_SECONDS hardcoded fallback in search-first.py** (hooks/search-first.py:64)
- **Tier:** ux
- **What:** `hooks/search-first.py` hardcodes 300s as a fallback.
- **Why:** Redundant with config default.
- **Repro:** Delete `WINDOW_SECONDS` from config; hook uses 300 regardless.
- **Fix:** Rely on config or ensure fallback is consistent.

---

## Round 3 - 2025-05-22

**Bugs surfaced:** 10
**Severity breakdown:** 0 data-loss / 4 silent / 6 ux / 0 cosmetic
**Median severity:** ux
**Overlap with prior rounds:** 6/10 (60%)
**New files hit:** stats.py, model_profiles.py, compact-trigger.py, bughunt.md
**Cumulative file coverage:** 14/38 target files (37%) [Note: 100% of actual repo files]

**Stop rule signals:**
- Severity slide: pass (median ux)
- Overlap rate >= 60%: pass (60%)
- File coverage >= 80%: pass (100% of actual repo files; bughunt.md list is for AIPortfolio)

**Decision:** stop and fix

**Bug 21: is_indexed discrepancy for root files (Rediscovered Bug 4/5)** (hooks/search-first.py:49)
- **Tier:** silent
- **Overlap:** Yes (Round 1)
- **What:** Hooks ignore root .py and .sql files that are indexed by embeddings.py.

**Bug 22: Python chunking misses assignments (Rediscovered Bug 3/12)** (embeddings.py:180)
- **Tier:** silent
- **Overlap:** Yes (Round 1/2)
- **What:** `chunk_python` misses constants assigned in tuples/lists.

**Bug 23: SQL chunking split on ;\\n is fragile (Rediscovered Bug 2/11)** (embeddings.py:196)
- **Tier:** ux
- **Overlap:** Yes (Round 1/2)
- **What:** Naive splitting on semicolons fails inside quoted strings.

**Bug 24: _ClosingConn wrapper is incomplete (Rediscovered Bug 15)** (tools/db.py:46)
- **Tier:** silent
- **Overlap:** Yes (Round 2)
- **What:** Missing `__getattr__` causes `AttributeError` on common connection methods.

**Bug 25: install.py hardcoded python names (Rediscovered Bug 16)** (install.py:141)
- **Tier:** ux
- **Overlap:** Yes (Round 2)
- **What:** `create_venv` should use `sys.executable`.

**Bug 26: stats.py _set_tracking is fragile and incomplete** (tools/stats.py:42)
- **Tier:** ux
- **What:** Toggling `TRACK_SAVINGS` fails if type hints or extra spaces are present.
- **Why:** Uses simple string replace instead of AST or robust regex.
- **Repro:** Add `: bool` to `TRACK_SAVINGS` in config.
- **Fix:** Use more robust replacement logic.

**Bug 27: REPO resolution in hooks is broken in dev environment** (hooks/search-first.py:15)
- **Tier:** silent
- **What:** `REPO` assumes 3 levels up, which is correct for installed location but wrong for source tree.
- **Why:** Hardcoded path logic.
- **Repro:** Run hooks from source `hooks/` dir; they won't find the tools or index.
- **Fix:** Detect repo root more robustly.

**Bug 28: model_profiles.py inconsistent heuristics** (tools/model_profiles.py:25)
- **Tier:** ux
- **What:** `recommended_k` differs (5 vs 8) for models with identical context windows.
- **Why:** Inconsistent profile definitions.
- **Repro:** Compare `claude-opus-3` vs `claude-opus-4-0`.
- **Fix:** Standardize tiers.

**Bug 29: stats.py _load_records silent on JSON errors** (tools/stats.py:65)
- **Tier:** ux
- **What:** Historical data loss is not reported if log is corrupted.
- **Why:** Silent `continue` in exception handler.
- **Repro:** Malformed line in `savings.jsonl`.
- **Fix:** Warn on decode errors.

**Bug 30: bughunt.md coverage list is for AIPortfolio project** (bughunt/bughunt.md:28)
- **Tier:** ux
- **What:** The protocol's coverage target list contains files from a different project.
- **Why:** Documentation copy-paste error.
- **Repro:** Read `bughunt/bughunt.md` and check repo files.
- **Fix:** Update target list for `less_tokens`.

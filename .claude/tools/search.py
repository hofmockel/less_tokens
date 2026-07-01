#!/usr/bin/env python3
"""Vector search over index.db. Mandatory first lookup before Read for indexed files.

Usage:
  python3 tools/search.py "wash sale procedure"
  python3 tools/search.py "where is latent_risks_today defined" --source-type code
  python3 tools/search.py "rationale for COPX trim" --source-type journal -k 3
  python3 tools/search.py "cash floor" --json
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

def _find_base() -> Path:
    """Project root: cwd when it contains .claude/tools/search_config.py, else __file__ ancestor."""
    cwd = Path.cwd().resolve()
    if (cwd / ".claude" / "tools" / "search_config.py").exists():
        return cwd
    return Path(__file__).resolve().parent.parent.parent


BASE = _find_base()
CLAUDE_DIR = BASE / ".claude"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import connect_index  # noqa: E402
from embeddings import DIM, embed, unpack_vectors  # noqa: E402
import search_config  # noqa: E402
from model_profiles import profile as _model_profile  # noqa: E402
from search_config import (  # noqa: E402
    INDEXED_DOC_GLOBS,
    INDEXED_ROOT_GLOBS,
    INDEXED_SOURCE_DIRS,
    active_state_dir,
)
from savings_log import append as _log_savings  # noqa: E402
from savings_log import resolve_session as _resolve_session  # noqa: E402
from savings_log import STRATEGY_SEARCH  # noqa: E402

DEFAULT_K = 3
CODEX_DEFAULT_K = 2
DEFAULT_SNIPPET_CHARS = 600
CODEX_DEFAULT_SNIPPET_CHARS = 400

# db module owns INDEX_DB; resolve it lazily so test monkeypatches are seen.
_DB_MOD = sys.modules[connect_index.__module__]


def _newest_source_mtime() -> float:
    """Newest mtime across the files enumerate_sources() would index.

    Heuristic only — mirrors embeddings.enumerate_sources file selection
    (root/doc-glob markdown + *.py rglob / *.sql under INDEXED_SOURCE_DIRS)
    without reading or chunking content, so it stays cheap on every query.
    """
    newest = 0.0
    for pattern in (*INDEXED_ROOT_GLOBS, *INDEXED_DOC_GLOBS):
        for f in BASE.glob(pattern):
            try:
                newest = max(newest, f.stat().st_mtime)
            except OSError:
                pass
    for dir_str in INDEXED_SOURCE_DIRS:
        d = BASE / dir_str.rstrip("/")
        if not d.exists():
            continue
        for finder in (lambda: d.rglob("*.py"), lambda: d.glob("*.sql")):
            try:
                for f in finder():
                    try:
                        newest = max(newest, f.stat().st_mtime)
                    except OSError:
                        pass
            except OSError:
                pass
    for pattern in ("*.py", "*.sql"):
        for f in BASE.glob(pattern):
            try:
                newest = max(newest, f.stat().st_mtime)
            except OSError:
                pass
    return newest


def _index_is_stale() -> bool:
    """True if an indexed source file is newer than index.db.

    A missing index is handled downstream (empty results + hint), not here.
    """
    try:
        idx_mtime = _DB_MOD.INDEX_DB.stat().st_mtime
    except OSError:
        return False
    return _newest_source_mtime() > idx_mtime


def _source_type_choices() -> list[str] | None:
    """Distinct source_type values actually in the index, or None if unknown.

    Deriving --source-type choices from the index keeps argparse in sync with
    reality: it accepts every value the current index contains (even ones a
    newer/older indexer produced) and never advertises a value that returns
    zero rows. None means the index is unavailable — leave --source-type
    unconstrained rather than blocking on a stale static list.
    """
    try:
        with connect_index() as c:
            rows = c.execute(
                "SELECT DISTINCT source_type FROM documents "
                "WHERE source_type IS NOT NULL ORDER BY source_type"
            ).fetchall()
    except sqlite3.OperationalError:
        return None
    return [r[0] for r in rows] or None


def _log_history(query: str, results: list[dict]) -> None:
    """Append one JSONL record so maintainers can audit what was searched."""
    try:
        sd = active_state_dir()
        sd.mkdir(parents=True, exist_ok=True)
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "query": query,
            "top_score": round(results[0]["score"], 6) if results else None,
            "results": len(results),
        }
        with (sd / "search-history.log").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
    except OSError:
        pass


def search(
    query: str,
    k: int = DEFAULT_K,
    source_type: str | None = None,
    min_score: float | None = None,
) -> list[dict]:
    try:
        qvec = embed([query], input_type="query")[0]
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return []

    try:
        with connect_index() as c:
            sql = (
                "SELECT id, source_type, source_path, source_key, text, embedding "
                "FROM documents WHERE embedding_model = ?"
            )
            params: tuple = (search_config.EMBEDDING_MODEL,)
            if source_type:
                sql += " AND source_type = ?"
                params = (search_config.EMBEDDING_MODEL, source_type)
            rows = c.execute(sql, params).fetchall()
    except sqlite3.OperationalError as e:
        print(f"ERROR: index unavailable ({e}); run `tools/embeddings.py refresh`", file=sys.stderr)
        return []

    if not rows:
        return []

    vecs = unpack_vectors(b"".join(r[5] for r in rows), DIM)
    # Stored vectors and query vector are both L2-normalized in `embed()`, so dot product = cosine similarity.
    scores = vecs @ qvec
    # Collapse multiple chunks from the same file to the single best-scoring
    # one and spend the freed budget on the next distinct file, so k results
    # cover k files instead of near-duplicate chunks. Scores are sorted
    # descending, so the first chunk seen per path is its best.
    results: list[dict] = []
    seen_paths: set[str] = set()
    # Unit vectors of already-selected hits, for cross-file dedup below.
    selected_units: list[np.ndarray] = []
    dedup_sim = search_config.SEARCH_DEDUP_SIM
    for i in np.argsort(-scores):
        if min_score is not None and scores[i] < min_score:
            break
        path = rows[i][2]
        if path in seen_paths:
            continue
        # Cross-file semantic dedup: when this file's best chunk is near-identical
        # to an already-selected hit, both would spend budget on the same content.
        # Drop the whole file and let the freed slot backfill the next distinct hit.
        cand = vecs[i]
        cand_unit = cand / (np.linalg.norm(cand) or 1.0)
        if dedup_sim < 1.0 and selected_units:
            if float(np.max(np.array(selected_units) @ cand_unit)) >= dedup_sim:
                seen_paths.add(path)
                continue
        seen_paths.add(path)
        selected_units.append(cand_unit)
        results.append({
            "score": float(scores[i]),
            "source_type": rows[i][1],
            "source_path": path,
            "source_key": rows[i][3],
            "text": rows[i][4],
        })
        if len(results) >= k:
            break
    return results


def _locate_range(file_text: str, chunk_text: str) -> tuple[int, int] | None:
    """Best-effort 1-based (start, end) line span of a chunk within its file.

    Matches the chunk's first non-blank line, and confirms with the last line
    when the span fits. Returns None if not found. Used to turn a search hit
    into a Read(offset, limit) slice (Strategy S9).
    """
    flines = file_text.splitlines()
    clines = chunk_text.splitlines()
    while clines and not clines[0].strip():
        clines.pop(0)
    while clines and not clines[-1].strip():
        clines.pop()
    if not clines:
        return None
    first, last, n = clines[0], clines[-1], len(clines)
    fallback: tuple[int, int] | None = None
    for i, ln in enumerate(flines):
        if ln == first:
            end_idx = i + n - 1
            if end_idx < len(flines) and flines[end_idx] == last:
                return (i + 1, end_idx + 1)
            if fallback is None:
                fallback = (i + 1, min(i + n, len(flines)))
    return fallback


def _write_last_search_ranges(results: list[dict]) -> None:
    """Write STATE_DIR/last-search.json: {source_path: [[start, end], ...]}.

    Lets the auto-slice hook (S9) suggest a Read(offset, limit) for a file the
    last search matched, instead of a whole-file read. Best-effort; never raises.
    """
    ranges: dict[str, list[list[int]]] = {}
    for r in results:
        path = r.get("source_path", "")
        if not path:
            continue
        try:
            text = (BASE / path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        span = _locate_range(text, r.get("text", ""))
        if span:
            ranges.setdefault(path, []).append([span[0], span[1]])
    try:
        sd = active_state_dir()
        sd.mkdir(parents=True, exist_ok=True)
        (sd / "last-search.json").write_text(
            json.dumps(ranges), encoding="utf-8")
    except OSError:
        pass


def _is_codex_agent() -> bool:
    return os.environ.get("LESS_TOKENS_AGENT", "").lower() == "codex"


def _resolve_k(explicit_k: int | None, prof: dict | None) -> int:
    if explicit_k is not None:
        return explicit_k
    if _is_codex_agent():
        return CODEX_DEFAULT_K
    if prof and "recommended_k" in prof:
        return prof["recommended_k"]
    return DEFAULT_K


def _resolve_snippet_chars(explicit_chars: int | None) -> int:
    if explicit_chars is not None:
        return explicit_chars
    if _is_codex_agent():
        return CODEX_DEFAULT_SNIPPET_CHARS
    return DEFAULT_SNIPPET_CHARS


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    # Default k=3 keeps lookups under ~300 tokens for the common case;
    # the long tail (rank 4+) is rarely informative. Pass -k 5/8 explicitly
    # for broad-research queries where you want the wider funnel.
    ap.add_argument("-k", type=int, default=None,
                    help="Number of chunks to return "
                         "(default: Codex 2, else AGENT_MODEL profile, else 3)")
    ap.add_argument("--snippet-chars", type=int, default=None,
                    help="Characters to print per hit (default: Codex 400, else 600)")
    ap.add_argument("--source-type", choices=_source_type_choices())
    ap.add_argument("--min-score", type=float, default=None,
                    help="Drop results with cosine score below this floor")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if _index_is_stale():
        print(
            "WARN: index may be stale — an indexed source file is newer than "
            "index.db; run `tools/embeddings.py refresh`",
            file=sys.stderr,
        )

    # Touch state file so the search-first hook knows a search just ran.
    sd = active_state_dir()
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "last-search").write_text(args.query + "\n", encoding="utf-8")

    # Resolve k: explicit -k wins; Codex gets a tighter default; Claude keeps
    # the model profile/default behavior.
    prof = _model_profile(getattr(search_config, "AGENT_MODEL", None))
    k = _resolve_k(args.k, prof)
    snippet_chars = _resolve_snippet_chars(args.snippet_chars)
    results = search(args.query, k=k, source_type=args.source_type,
                     min_score=args.min_score)
    # Warn if returned chunks would consume a large fraction of the
    # configured model's window.
    if prof and results:
        approx_tokens = int(sum(len(r["text"]) for r in results) / search_config.CHARS_PER_TOKEN)
        window = prof.get("context_window", 0)
        if window and approx_tokens > window // 4:
            print(
                f"WARN: returned chunks ≈ {approx_tokens} tokens; "
                f"{prof.get('context_window')}-token window may fill quickly. "
                "Lower -k or raise --min-score.",
                file=sys.stderr,
            )
    _log_history(args.query, results)
    if results:
        chunk_chars = sum(len(r["text"]) for r in results)
        unique_paths = {r["source_path"] for r in results}
        full_file_chars = 0
        for fp in unique_paths:
            try:
                full_file_chars += (BASE / fp).stat().st_size
            except OSError:
                pass
        sid, ssrc = _resolve_session(None)
        _log_savings({
            "strategy": STRATEGY_SEARCH,
            "basis": "upper_bound",
            "kept_chars": chunk_chars,
            "elided_chars": max(0, full_file_chars - chunk_chars),
            "content_kind": "search_result",
            "where": args.query,
            "session_id": sid,
            "session_source": ssrc,
        })

    _write_last_search_ranges(results)

    if args.json:
        print(json.dumps(results, indent=2))
        return 0
    if not results:
        print("(no results — index may be empty; run `tools/embeddings.py refresh`)")
        return 0
    for r in results:
        print(f"\n[{r['score']:.3f}] {r['source_path']}::{r['source_key']}  ({r['source_type']})")
        snippet = r["text"][:snippet_chars]
        print(snippet + ("…" if len(r["text"]) > snippet_chars else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

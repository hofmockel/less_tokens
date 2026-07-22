#!/usr/bin/env python3
"""HS1 benchmark: vector-only vs lexical-only (FTS5/BM25) vs RRF-fused retrieval.

Run from the target repo root with that repo's own venv-tokens interpreter, e.g.:
  .claude/.venv-tokens/bin/python3 \
    reports/runs/2026-07-22-hs1-hybrid-retrieval-benchmark/bench.py \
    --queries reports/runs/2026-07-22-hs1-hybrid-retrieval-benchmark/queries_less_tokens.json \
    --out reports/runs/2026-07-22-hs1-hybrid-retrieval-benchmark/results_less_tokens.json

Ranks are computed at chunk granularity (source_path, source_key), not
collapsed to one-per-file, because the correctness-relevant question is
whether the exact right chunk surfaces, not just the right file.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

BASE = Path.cwd().resolve()
sys.path.insert(0, str(BASE / ".claude" / "tools"))
from db import connect_index  # noqa: E402
from embeddings import DIM, embed, unpack_vectors  # noqa: E402
import search_config  # noqa: E402

RRF_K = 60
TOP_K = 5
SNIPPET_CHARS = 600  # matches search.py DEFAULT_SNIPPET_CHARS


def load_rows():
    with connect_index() as c:
        rows = c.execute(
            "SELECT id, source_path, source_key, text, embedding, length(text) "
            "FROM documents WHERE embedding_model = ?",
            (search_config.EMBEDDING_MODEL,),
        ).fetchall()
    return rows


def build_fts(rows):
    con = sqlite3.connect(":memory:")
    con.execute("CREATE VIRTUAL TABLE fts USING fts5(text, content='')")
    con.executemany(
        "INSERT INTO fts(rowid, text) VALUES (?, ?)",
        [(i, r[3]) for i, r in enumerate(rows)],
    )
    return con


def vector_ranking(qvec, vecs):
    scores = vecs @ qvec
    order = np.argsort(-scores)
    return [int(i) for i in order]  # row indices, best first


def lexical_ranking(fts_con, query):
    # FTS5 MATCH needs quoted terms for identifiers containing punctuation
    # (leading underscore, dots, dashes) that would otherwise be parsed as
    # FTS5 query-syntax operators.
    # OR across terms (standard BM25 bag-of-words), not FTS5's implicit AND —
    # an AND join would require every token (including stopwords) to co-occur
    # in one chunk, which almost never happens for multi-word natural queries.
    terms = query.replace('"', ' ').split()
    match_expr = " OR ".join(f'"{t}"' for t in terms) if terms else '""'
    try:
        cur = fts_con.execute(
            "SELECT rowid FROM fts WHERE fts MATCH ? ORDER BY bm25(fts)",
            (match_expr,),
        )
        return [int(r[0]) for r in cur.fetchall()]
    except sqlite3.OperationalError:
        return []


def rrf_fuse(*rankings, k=RRF_K):
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, idx in enumerate(ranking, start=1):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank)
    return [idx for idx, _ in sorted(scores.items(), key=lambda kv: -kv[1])]


def rank_of_first(ranking, accept_idx: set[int]) -> int | None:
    for pos, idx in enumerate(ranking, start=1):
        if idx in accept_idx:
            return pos
    return None


def tokens_to_find(ranking, accept_idx: set[int], rows, full_file_chars: dict[str, int]) -> int:
    """Approx chars an agent reads to reach the first correct chunk: sum of
    printed-snippet chars (capped at SNIPPET_CHARS) for every result before
    and including the hit; a miss within TOP_K falls back to a full-file
    read of the (first) ground-truth file."""
    pos = rank_of_first(ranking[:TOP_K], accept_idx)
    if pos is not None:
        return sum(min(len(rows[i][3]), SNIPPET_CHARS) for i in ranking[:pos])
    scanned = sum(min(len(rows[i][3]), SNIPPET_CHARS) for i in ranking[:TOP_K])
    fallback_path = rows[next(iter(accept_idx))][1] if accept_idx else None
    fallback = full_file_chars.get(fallback_path, 0)
    return scanned + fallback


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = load_rows()
    if not rows:
        print("ERROR: no indexed rows for current EMBEDDING_MODEL", file=sys.stderr)
        return 1
    vecs = unpack_vectors(b"".join(r[4] for r in rows), DIM)
    index_by_key = {(r[1], r[2]): i for i, r in enumerate(rows)}

    full_file_chars: dict[str, int] = {}
    for r in rows:
        full_file_chars[r[1]] = full_file_chars.get(r[1], 0) + len(r[3])

    t0 = time.perf_counter()
    fts_con = build_fts(rows)
    fts_build_s = time.perf_counter() - t0

    queries = json.loads(Path(args.queries).read_text())["queries"]

    per_query = []
    for q in queries:
        if q["type"] == "exact":
            term = q["match_contains"].lower()
            accept_idx = {i for i, r in enumerate(rows) if term in r[3].lower()}
        else:
            accept_idx = set()
            key = (q["gt_path"], q["gt_key"])
            if key in index_by_key:
                accept_idx = {index_by_key[key]}
        if not accept_idx:
            print(f"WARN: {q['id']} has no ground-truth rows in this index — skipping", file=sys.stderr)
            continue

        t0 = time.perf_counter()
        qvec = embed([q["query"]], input_type="query")[0]
        embed_s = time.perf_counter() - t0

        t0 = time.perf_counter()
        vec_rank = vector_ranking(qvec, vecs)
        vec_search_s = time.perf_counter() - t0

        t0 = time.perf_counter()
        lex_rank = lexical_ranking(fts_con, q["query"])
        lex_search_s = time.perf_counter() - t0

        t0 = time.perf_counter()
        fused_rank = rrf_fuse(vec_rank, lex_rank)
        fuse_s = time.perf_counter() - t0

        methods = {
            "vector": (vec_rank, embed_s + vec_search_s),
            "lexical": (lex_rank, lex_search_s),
            "fused": (fused_rank, embed_s + vec_search_s + lex_search_s + fuse_s),
        }
        result = {"id": q["id"], "type": q["type"], "query": q["query"]}
        for name, (ranking, latency_s) in methods.items():
            rank = rank_of_first(ranking, accept_idx)
            result[name] = {
                "rank": rank,
                "hit_at_5": bool(rank is not None and rank <= TOP_K),
                "reciprocal_rank": (1.0 / rank) if rank else 0.0,
                "latency_ms": round(latency_s * 1000, 3),
                "chars_to_find": tokens_to_find(ranking, accept_idx, rows, full_file_chars),
            }
        per_query.append(result)

    # Index-size overhead: vector blobs already shipped vs FTS5 index added.
    vector_bytes = sum(len(r[4]) for r in rows)
    fts_pages = fts_con.execute("PRAGMA page_count").fetchone()[0]
    fts_page_size = fts_con.execute("PRAGMA page_size").fetchone()[0]
    fts_bytes = fts_pages * fts_page_size

    summary = {}
    for method in ("vector", "lexical", "fused"):
        for qtype in ("semantic", "exact", "all"):
            subset = [r for r in per_query if qtype == "all" or r["type"] == qtype]
            if not subset:
                continue
            n = len(subset)
            summary[f"{method}/{qtype}"] = {
                "n": n,
                "recall_at_5": round(sum(r[method]["hit_at_5"] for r in subset) / n, 3),
                "mrr": round(sum(r[method]["reciprocal_rank"] for r in subset) / n, 3),
                "mean_latency_ms": round(sum(r[method]["latency_ms"] for r in subset) / n, 3),
                "mean_chars_to_find": round(sum(r[method]["chars_to_find"] for r in subset) / n, 1),
            }

    out = {
        "repo": BASE.name,
        "n_documents": len(rows),
        "fts_build_s": round(fts_build_s, 4),
        "index_overhead_bytes": {"vector_blobs": vector_bytes, "fts5_index": fts_bytes,
                                   "fts5_over_vector_ratio": round(fts_bytes / vector_bytes, 3) if vector_bytes else None},
        "summary": summary,
        "per_query": per_query,
    }
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

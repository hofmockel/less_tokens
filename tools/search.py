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
import sqlite3
import sys
from pathlib import Path

import numpy as np

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "tools"))
from db import connect_index  # noqa: E402
from embeddings import DIM, embed  # noqa: E402
from search_config import SOURCE_TYPES, STATE_DIR  # noqa: E402
from savings_log import append as _log_savings  # noqa: E402

DEFAULT_K = 3


def search(query: str, k: int = DEFAULT_K, source_type: str | None = None) -> list[dict]:
    try:
        qvec = embed([query], input_type="query")[0]
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return []

    try:
        with connect_index() as c:
            sql = "SELECT id, source_type, source_path, source_key, text, embedding FROM documents"
            params: tuple = ()
            if source_type:
                sql += " WHERE source_type = ?"
                params = (source_type,)
            rows = c.execute(sql, params).fetchall()
    except sqlite3.OperationalError as e:
        print(f"ERROR: index unavailable ({e}); run `tools/embeddings.py refresh`", file=sys.stderr)
        return []

    if not rows:
        return []

    vecs = np.frombuffer(b"".join(r[5] for r in rows), dtype=np.float32).reshape(-1, DIM)
    # Stored vectors and query vector are both L2-normalized in `embed()`, so dot product = cosine similarity.
    scores = vecs @ qvec
    top = np.argsort(-scores)[:k]
    return [
        {
            "score": float(scores[i]),
            "source_type": rows[i][1],
            "source_path": rows[i][2],
            "source_key": rows[i][3],
            "text": rows[i][4],
        }
        for i in top
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    # Default k=3 keeps lookups under ~300 tokens for the common case;
    # the long tail (rank 4+) is rarely informative. Pass -k 5/8 explicitly
    # for broad-research queries where you want the wider funnel.
    ap.add_argument("-k", type=int, default=3,
                    help="Number of chunks to return (default 3)")
    ap.add_argument("--source-type", choices=SOURCE_TYPES)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    # Touch state file so the search-first hook knows a search just ran.
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    (STATE_DIR / "last-search").write_text(args.query + "\n", encoding="utf-8")

    results = search(args.query, k=args.k, source_type=args.source_type)
    if results:
        chunk_chars = sum(len(r["text"]) for r in results)
        unique_paths = {r["source_path"] for r in results}
        full_file_chars = 0
        for fp in unique_paths:
            try:
                full_file_chars += (BASE / fp).stat().st_size
            except OSError:
                pass
        _log_savings({
            "strategy": "search",
            "query": args.query,
            "chunk_chars": chunk_chars,
            "full_file_chars": full_file_chars,
            "saved_chars": max(0, full_file_chars - chunk_chars),
        })

    if args.json:
        print(json.dumps(results, indent=2))
        return 0
    if not results:
        print("(no results — index may be empty; run `tools/embeddings.py refresh`)")
        return 0
    for r in results:
        print(f"\n[{r['score']:.3f}] {r['source_path']}::{r['source_key']}  ({r['source_type']})")
        snippet = r["text"][:600]
        print(snippet + ("…" if len(r["text"]) > 600 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

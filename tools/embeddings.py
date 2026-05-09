#!/usr/bin/env python3
"""Build/refresh index.db from repo sources.

Sources (everything indexable):
  - All files matching INDEXED_ROOT_GLOBS in repo root (default: *.md)
  - All *.py and *.sql under INDEXED_SOURCE_DIRS (default: tools/, app/, schema/)

Embedding: local fastembed BAAI/bge-small-en-v1.5 (384 dim). Self-contained;
model downloads to ~/.cache/huggingface on first run (~130MB).
Storage: index.db documents.embedding (BLOB, float32 raw bytes, normalized).

Usage:
  python3 tools/embeddings.py refresh         # incremental rebuild
  python3 tools/embeddings.py refresh --full  # delete-all and rebuild
  python3 tools/embeddings.py stats           # row counts by source_type
  python3 tools/embeddings.py health          # verify every expected source has chunks
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "tools"))
from db import connect_index  # noqa: E402
from search_config import (  # noqa: E402
    EXCLUDED_DIR_NAMES,
    INDEXED_ROOT_GLOBS,
    INDEXED_SOURCE_DIRS,
)

MODEL = "BAAI/bge-small-en-v1.5"
DIM = 384
BATCH = 32

_model = None


def _get_model():
    global _model
    if _model is None:
        try:
            from fastembed import TextEmbedding
        except ImportError as e:
            raise RuntimeError(
                "fastembed not installed. Install with: pip install fastembed"
            ) from e
        _model = TextEmbedding(model_name=MODEL)
    return _model


def _excluded(path: Path) -> bool:
    parts = set(path.relative_to(BASE).parts)
    return bool(parts & EXCLUDED_DIR_NAMES)


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# ----- chunking -------------------------------------------------------------

def chunk_markdown(path: Path) -> list[tuple[str, str]]:
    """Split a markdown file by H1/H2/H3 headings."""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    chunks: list[tuple[str, list[str]]] = []
    current_key = "preamble"
    current: list[str] = []
    for ln in lines:
        m = re.match(r"^(#{1,3})\s+(.+?)\s*$", ln)
        if m:
            if current:
                chunks.append((current_key, current))
            current_key = m.group(2).strip()
            current = [ln]
        else:
            current.append(ln)
    if current:
        chunks.append((current_key, current))
    out: list[tuple[str, str]] = []
    key_counts: dict[str, int] = {}
    for k, ls in chunks:
        body = "\n".join(ls).strip()
        if not body:
            continue
        if k in key_counts:
            key_counts[k] += 1
            out.append((f"{k}_{key_counts[k]}", body))
        else:
            key_counts[k] = 1
            out.append((k, body))
    return out


def chunk_python(path: Path) -> list[tuple[str, str]]:
    """One chunk per top-level def/class/UPPER_CASE constant."""
    src = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return [("__file__", src)]
    lines = src.splitlines()
    out: list[tuple[str, str]] = []
    mod_doc = ast.get_docstring(tree)
    if mod_doc:
        out.append(("__module__", mod_doc))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = node.lineno - 1
            end = getattr(node, "end_lineno", start + 1)
            out.append((node.name, "\n".join(lines[start:end])))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    start = node.lineno - 1
                    end = getattr(node, "end_lineno", start + 1)
                    out.append((target.id, "\n".join(lines[start:end])))
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id.isupper():
                start = node.lineno - 1
                end = getattr(node, "end_lineno", start + 1)
                out.append((node.target.id, "\n".join(lines[start:end])))
    return out


def chunk_sql(path: Path) -> list[tuple[str, str]]:
    src = path.read_text(encoding="utf-8", errors="replace")
    src_no_comments = re.sub(r"--[^\n]*", "", src)
    blocks = re.split(r";\s*\n", src_no_comments)
    out: list[tuple[str, str]] = []
    for b in blocks:
        b = b.strip()
        if not b:
            continue
        m = re.search(
            r"CREATE\s+(?:TABLE|VIEW|INDEX)\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)",
            b, re.IGNORECASE,
        )
        key = m.group(1) if m else f"stmt:{_sha256(b)[:8]}"
        out.append((key, b))
    return out


def chunk_changelog(path: Path) -> list[tuple[str, str]]:
    """Split CHANGELOG.md on version/date headings.

    Matches both date-only headers (## YYYY-MM-DD) and Keep-a-Changelog
    headers (## [version] - date, ## [Unreleased]).
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    parts = re.split(
        r"^(##\s+(?:\[.+?\]|\d{4}-\d{2}-\d{2}).*)$", text, flags=re.MULTILINE
    )
    out: list[tuple[str, str]] = []
    for i in range(1, len(parts), 2):
        head = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        out.append((head.lstrip("#").strip(), (head + "\n" + body).strip()))
    if not out:
        return chunk_markdown(path)
    return out


# ----- source enumeration ---------------------------------------------------

def enumerate_sources() -> list[tuple[str, str, str, str]]:
    """Return [(source_type, source_path, source_key, text), ...]."""
    out: list[tuple[str, str, str, str]] = []

    # Root-level globs (default: *.md)
    for glob in INDEXED_ROOT_GLOBS:
        for f in sorted(BASE.glob(glob)):
            if _excluded(f):
                continue
            if f.suffix == ".md":
                st = "changelog" if f.name == "CHANGELOG.md" else "doc"
                chunks = chunk_changelog(f) if st == "changelog" else chunk_markdown(f)
                for k, t in chunks:
                    out.append((st, f.name, k, t))
            else:
                print(f"  WARN: unsupported root glob extension {f.suffix!r} — {f.name} skipped",
                      file=sys.stderr)

    # Python from indexed subdirs + root .py
    py_paths: list[Path] = []
    for dir_str in INDEXED_SOURCE_DIRS:
        d = BASE / dir_str.rstrip("/")
        if d.exists():
            py_paths.extend(d.rglob("*.py"))
    py_paths.extend(BASE.glob("*.py"))
    for py in sorted(set(py_paths)):
        if _excluded(py):
            continue
        rel = py.relative_to(BASE).as_posix()
        for k, t in chunk_python(py):
            out.append(("code", rel, k, t))

    # SQL from indexed subdirs
    for dir_str in INDEXED_SOURCE_DIRS:
        d = BASE / dir_str.rstrip("/")
        if not d.exists():
            continue
        for sq in sorted(d.glob("*.sql")):
            rel = sq.relative_to(BASE).as_posix()
            for k, t in chunk_sql(sq):
                out.append(("code", rel, k, t))

    return out


# ----- local embed ---------------------------------------------------------

def embed(texts: list[str], input_type: str = "document") -> np.ndarray:
    """Local fastembed encode. Returns (N, DIM) float32 normalized."""
    model = _get_model()
    if input_type == "query":
        gen = model.query_embed(texts)
    else:
        gen = model.embed(texts)
    vecs = np.array(list(gen), dtype=np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9
    return vecs / norms


# ----- refresh --------------------------------------------------------------

def refresh(full: bool = False) -> int:
    try:
        _get_model()
    except RuntimeError as e:
        print(f"WARN: {e} — skipping refresh", file=sys.stderr)
        return 0

    sources = enumerate_sources()
    print(f"Enumerated {len(sources)} chunks from sources")

    with connect_index() as conn:
        if full:
            conn.execute("DELETE FROM documents")
            conn.commit()

        existing = {
            (r[0], r[1]): r[2]
            for r in conn.execute(
                "SELECT source_path, source_key, content_hash FROM documents"
            ).fetchall()
        }
        seen: set[tuple[str, str]] = set()

        to_embed: list[tuple[str, str, str, str, str]] = []
        for st, sp, sk, text in sources:
            seen.add((sp, sk))
            h = _sha256(text)
            if existing.get((sp, sk)) == h:
                continue
            to_embed.append((st, sp, sk, text, h))

        deleted = 0
        for sp, sk in set(existing) - seen:
            conn.execute(
                "DELETE FROM documents WHERE source_path=? AND source_key=?",
                (sp, sk),
            )
            deleted += 1
        conn.commit()

        unchanged = len(seen) - len(to_embed)
        print(f"  to embed: {len(to_embed)}  "
              f"unchanged: {unchanged}  "
              f"deleted: {deleted}")

        embedded = 0
        for i in range(0, len(to_embed), BATCH):
            batch = to_embed[i:i + BATCH]
            texts = [b[3] for b in batch]
            try:
                vecs = embed(texts)
            except Exception as e:
                print(f"  embed batch {i // BATCH} failed: {e}", file=sys.stderr)
                conn.commit()
                return 1
            now = datetime.now(timezone.utc).isoformat()
            for (st, sp, sk, text, h), v in zip(batch, vecs):
                conn.execute(
                    """INSERT INTO documents (source_type, source_path, source_key, text,
                                              content_hash, embedding, embedding_model, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(source_path, source_key) DO UPDATE SET
                         source_type=excluded.source_type,
                         text=excluded.text,
                         content_hash=excluded.content_hash,
                         embedding=excluded.embedding,
                         embedding_model=excluded.embedding_model,
                         updated_at=excluded.updated_at""",
                    (st, sp, sk, text, h, v.tobytes(), MODEL, now),
                )
            embedded += len(batch)
            conn.commit()
            print(f"  embedded {embedded}/{len(to_embed)}")

        print(f"Done. embedded={embedded} deleted={deleted}")
    return 0


def expected_source_paths() -> set[str]:
    """File-only enumeration. Mirrors enumerate_sources() globs without chunking."""
    out: set[str] = set()
    for glob in INDEXED_ROOT_GLOBS:
        for f in sorted(BASE.glob(glob)):
            if _excluded(f):
                continue
            out.add(f.name)
    py_paths: list[Path] = []
    for dir_str in INDEXED_SOURCE_DIRS:
        d = BASE / dir_str.rstrip("/")
        if d.exists():
            py_paths.extend(d.rglob("*.py"))
    py_paths.extend(BASE.glob("*.py"))
    for py in sorted(set(py_paths)):
        if _excluded(py):
            continue
        out.add(py.relative_to(BASE).as_posix())
    for dir_str in INDEXED_SOURCE_DIRS:
        d = BASE / dir_str.rstrip("/")
        if d.exists():
            for sq in sorted(d.glob("*.sql")):
                out.add(sq.relative_to(BASE).as_posix())
    return out


def _produces_no_chunks(rel_path: str) -> bool:
    """True iff the file at rel_path has no indexable content.

    Empty marker files (e.g. blank `__init__.py`) and files whose chunker
    returns nothing should not be flagged as gaps — they are correctly
    skipped by the indexer, not failures.
    """
    abs_path = BASE / rel_path
    try:
        text = abs_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    if not text.strip():
        return True
    suffix = abs_path.suffix.lower()
    try:
        if suffix == ".py":
            chunks = chunk_python(abs_path)
        elif suffix == ".sql":
            chunks = chunk_sql(abs_path)
        elif suffix == ".md":
            chunks = (chunk_changelog(abs_path)
                      if abs_path.name == "CHANGELOG.md"
                      else chunk_markdown(abs_path))
        else:
            return False
    except Exception:
        return False
    return not chunks


def health() -> int:
    """Verify every expected source has ≥1 chunk in index.db.

    Files with no indexable content (empty `__init__.py`, files whose
    chunker yields zero chunks) are not counted as gaps.
    """
    expected = expected_source_paths()
    with connect_index() as c:
        counts = dict(c.execute(
            "SELECT source_path, COUNT(*) FROM documents GROUP BY source_path"
        ).fetchall())

    candidate = [src for src in sorted(expected) if counts.get(src, 0) == 0]
    missing = [src for src in candidate if not _produces_no_chunks(src)]
    skipped_empty = len(candidate) - len(missing)

    if not missing:
        total = sum(counts.values())
        suffix = f" ({skipped_empty} empty file(s) ignored)" if skipped_empty else ""
        print(f"OK — {len(expected)} expected sources covered "
              f"({total} chunks total){suffix}.")
        return 0

    print(f"⚠ {len(missing)} index gap(s):")
    for m in missing:
        print(f"  missing: {m}")
    print("\nRun: python3 tools/embeddings.py refresh --full")
    return 1


def stats() -> int:
    with connect_index() as c:
        rows = c.execute(
            "SELECT source_type, COUNT(*) FROM documents "
            "GROUP BY source_type ORDER BY source_type"
        ).fetchall()
        total = c.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    print(f"index.db documents: {total}")
    for st, n in rows:
        print(f"  {st:<12} {n}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("refresh")
    r.add_argument("--full", action="store_true", help="delete-all and rebuild")
    sub.add_parser("stats")
    sub.add_parser("health")
    sub.add_parser("savings")
    args = ap.parse_args()
    if args.cmd == "refresh":
        return refresh(full=args.full)
    if args.cmd == "health":
        return health()
    if args.cmd == "savings":
        from stats import main as _savings_main  # noqa: PLC0415
        return _savings_main()
    return stats()


if __name__ == "__main__":
    sys.exit(main())

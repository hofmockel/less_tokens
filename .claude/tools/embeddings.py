#!/usr/bin/env python3
"""Build/refresh index.db from repo sources.

Sources (everything indexable):
  - All files matching INDEXED_ROOT_GLOBS in repo root (default: *.md)
  - All *.py and *.sql under INDEXED_SOURCE_DIRS (default: tools/, app/, schema/)

Embedding: local fastembed BAAI/bge-small-en-v1.5 (384 dim). Self-contained;
model downloads to ~/.cache/huggingface on first run (~130MB).
Storage: index.db documents.embedding (BLOB, little-endian float32 raw bytes,
normalized).

Usage:
  python3 tools/embeddings.py refresh         # incremental rebuild
  python3 tools/embeddings.py refresh --full  # delete-all and rebuild
  python3 tools/embeddings.py refresh --dry-run  # preview, write nothing
  python3 tools/embeddings.py stats           # row counts by source_type
  python3 tools/embeddings.py stats --verbose # + index age, files, coverage
  python3 tools/embeddings.py health          # verify every expected source has chunks
  python3 tools/embeddings.py switch-model <model> --dim <N>  # atomic model+reindex swap
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import re
import sqlite3
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

# fastembed pulls in urllib3, which on macOS system Python (LibreSSL) emits a
# benign NotOpenSSLWarning at import. It pollutes stderr on every search.py run
# and any captured hook output. Filter the known message process-wide here;
# search.py imports this module at load, so both entrypoints are covered.
warnings.filterwarnings(
    "ignore",
    message=r"urllib3 v2 only supports OpenSSL",
    category=Warning,
)

import numpy as np  # noqa: E402

def _find_base() -> Path:
    """Project root: cwd when it contains .claude/tools/search_config.py, else __file__ ancestor.

    Lets the global install (tools living in the less_tokens source tree) operate on a
    per-project index by running with cwd set to the target project root.
    """
    cwd = Path.cwd().resolve()
    if (cwd / ".claude" / "tools" / "search_config.py").exists():
        return cwd
    return Path(__file__).resolve().parent.parent.parent


BASE = _find_base()
CLAUDE_DIR = BASE / ".claude"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import search_config  # noqa: E402
from db import connect_index, ensure_current_schema  # noqa: E402
from search_config import (  # noqa: E402
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    EXCLUDED_DIR_NAMES,
    EXCLUDED_DIR_PREFIXES,
    INDEXED_DOC_GLOBS,
    INDEXED_ROOT_GLOBS,
    INDEXED_SOURCE_DIRS,
)

MODEL = EMBEDDING_MODEL
DIM = EMBEDDING_DIM
BATCH = 32

# Embeddings are stored as raw float32 bytes. Pin little-endian at the single
# (de)serialization point so an index.db built on one host stays correct when
# read on a host of different endianness (native bytes silently corrupt scores
# cross-endian).
VEC_DTYPE = np.dtype("<f4")

# On-disk vector layout marker, stored in `PRAGMA user_version`. Bump
# whenever the embedding byte layout changes (see VEC_DTYPE). An index.db
# written before this marker existed reports user_version 0 — its blobs may
# be host-native (pre little-endian pin) and would decode as garbage now, so
# refresh() rebuilds such an index once and then stamps the marker.
VEC_FORMAT = 1


def pack_vector(v: np.ndarray) -> bytes:
    return np.asarray(v, dtype=VEC_DTYPE).tobytes()


def unpack_vectors(blob: bytes, dim: int) -> np.ndarray:
    return np.frombuffer(blob, dtype=VEC_DTYPE).reshape(-1, dim)


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
    try:
        rel = path.relative_to(BASE).as_posix()
    except ValueError:
        return True
    parts = set(Path(rel).parts)
    if bool(parts & EXCLUDED_DIR_NAMES):
        return True
    return any(rel.startswith(p) for p in EXCLUDED_DIR_PREFIXES)


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
    bodies = [(k, "\n".join(ls).strip()) for k, ls in chunks]
    bodies = [(k, b) for k, b in bodies if b]
    # Pre-scan every literal heading key in this file so a generated
    # `f"{k}_{n}"` dedup suffix can never collide with a real `## k_n`
    # heading (or an already-emitted key): a collision would make two chunks
    # share (source_path, source_key) and the UPSERT would silently drop one.
    literal_keys = {k for k, _ in bodies}
    out: list[tuple[str, str]] = []
    emitted: set[str] = set()
    for k, body in bodies:
        key = k
        if key in emitted:
            n = 2
            while f"{k}_{n}" in literal_keys or f"{k}_{n}" in emitted:
                n += 1
            key = f"{k}_{n}"
        emitted.add(key)
        out.append((key, body))
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
    add_ctx = bool(
        mod_doc and search_config.CHUNK_INCLUDE_MODULE_CONTEXT
    )

    def _ctx(code: str) -> str:
        # Prefix the module docstring as a comment so the chunk still reads
        # as the original source, just with the file's purpose attached.
        header = "\n".join(f"# {ln}" if ln else "#" for ln in mod_doc.splitlines())
        return f"{header}\n\n{code}"

    def _get_upper_names(node: ast.AST) -> list[str]:
        if isinstance(node, ast.Name) and node.id.isupper():
            return [node.id]
        if isinstance(node, (ast.Tuple, ast.List)):
            names = []
            for elt in node.elts:
                names.extend(_get_upper_names(elt))
            return names
        return []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = node.lineno - 1
            end = getattr(node, "end_lineno", start + 1)
            code = "\n".join(lines[start:end])
            out.append((node.name, _ctx(code) if add_ctx else code))
        elif isinstance(node, ast.Assign):
            names = []
            for target in node.targets:
                names.extend(_get_upper_names(target))
            for name in names:
                start = node.lineno - 1
                end = getattr(node, "end_lineno", start + 1)
                out.append((name, "\n".join(lines[start:end])))
        elif isinstance(node, ast.AnnAssign):
            for name in _get_upper_names(node.target):
                start = node.lineno - 1
                end = getattr(node, "end_lineno", start + 1)
                out.append((name, "\n".join(lines[start:end])))
    # Dedup source_key values: same name defined twice in one file (valid Python)
    # would produce two chunks with identical keys; the UPSERT would silently
    # drop the first.  Append a _N suffix for subsequent duplicates, same as
    # chunk_markdown does for repeated headings.
    literal_keys = {k for k, _ in out}
    deduped: list[tuple[str, str]] = []
    emitted: set[str] = set()
    for k, body in out:
        key = k
        if key in emitted:
            n = 2
            while f"{k}_{n}" in literal_keys or f"{k}_{n}" in emitted:
                n += 1
            key = f"{k}_{n}"
        emitted.add(key)
        deduped.append((key, body))
    return deduped


def chunk_sql(path: Path) -> list[tuple[str, str]]:
    src = path.read_text(encoding="utf-8", errors="replace")
    # Basic SQL statement splitter that respects single/double quoted strings
    # and ignores semicolons within them. Heuristic-based, better than split(;).
    blocks: list[str] = []
    current: list[str] = []
    in_string: str | None = None
    lines = src.splitlines(keepends=True)
    for line in lines:
        stripped = re.sub(r"--[^\n]*", "", line)
        for i, char in enumerate(stripped):
            if char in ("'", '"'):
                if in_string == char:
                    in_string = None
                elif in_string is None:
                    in_string = char
            elif char == ";" and in_string is None:
                # Check if this semicolon is followed by a newline or EOF
                # (allowing for trailing whitespace)
                after = stripped[i + 1 :].strip()
                if not after:
                    current.append(line[: i + 1])
                    blocks.append("".join(current))
                    current = []
                    line = line[i + 1 :]
                    break
        if line:
            current.append(line)
    if current:
        final = "".join(current).strip()
        if final:
            blocks.append(final)

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
        r"^(##\s+(?:\[.+?\]|v?\d+\.\d+\.\d+|\d{4}-\d{2}-\d{2}).*)$",
        text,
        flags=re.MULTILINE,
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

def enumerate_sources() -> tuple[list[tuple[str, str, str, str]], bool]:
    """Return ([(source_type, source_path, source_key, text), ...], incomplete).

    `incomplete` is True if any indexed source dir could not be fully
    traversed (e.g. a permission-denied subtree). Callers that prune the
    index from this list must not delete rows when it is True — the missing
    sources are unreadable, not gone.
    """
    out: list[tuple[str, str, str, str]] = []
    incomplete = False

    # Markdown globs: repo root (INDEXED_ROOT_GLOBS) + extra dirs
    # (INDEXED_DOC_GLOBS). Keyed by path relative to BASE so a root
    # CLAUDE.md and a subdir CLAUDE.md don't collide on source_path.
    for glob in (*INDEXED_ROOT_GLOBS, *INDEXED_DOC_GLOBS):
        for f in sorted(BASE.glob(glob)):
            if _excluded(f):
                continue
            rel = f.relative_to(BASE).as_posix()
            if f.suffix == ".md":
                st = "changelog" if f.name == "CHANGELOG.md" else "doc"
                chunks = chunk_changelog(f) if st == "changelog" else chunk_markdown(f)
                for k, t in chunks:
                    out.append((st, rel, k, t))
            else:
                print(f"  WARN: unsupported glob extension {f.suffix!r} — {rel} skipped",
                      file=sys.stderr)

    # Python from indexed subdirs + root .py
    py_paths: list[Path] = []
    for dir_str in INDEXED_SOURCE_DIRS:
        d = BASE / dir_str.rstrip("/")
        if not d.exists():
            continue
        try:
            py_paths.extend(d.rglob("*.py"))
        except OSError as e:
            # One unreadable subtree must not abort the whole refresh and
            # leave the index stale — skip it and keep the other sources.
            # Flag the run incomplete so refresh() does not prune the rows
            # belonging to the part we could not read.
            incomplete = True
            print(f"  WARN: skipping unreadable paths under {dir_str} — {e}",
                  file=sys.stderr)
    py_paths.extend(BASE.glob("*.py"))
    for py in sorted(set(py_paths)):
        if _excluded(py):
            continue
        rel = py.relative_to(BASE).as_posix()
        for k, t in chunk_python(py):
            out.append(("code", rel, k, t))

    # SQL from indexed subdirs + root .sql
    sql_paths: list[Path] = []
    for dir_str in INDEXED_SOURCE_DIRS:
        d = BASE / dir_str.rstrip("/")
        if not d.exists():
            continue
        try:
            sql_paths.extend(d.glob("*.sql"))
        except OSError as e:
            incomplete = True
            print(f"  WARN: skipping unreadable SQL dir {dir_str} — {e}",
                  file=sys.stderr)
            continue
    sql_paths.extend(BASE.glob("*.sql"))
    for sq in sorted(set(sql_paths)):
        if _excluded(sq):
            continue
        rel = sq.relative_to(BASE).as_posix()
        for k, t in chunk_sql(sq):
            out.append(("code", rel, k, t))

    return out, incomplete


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

def _dry_run_report(full: bool) -> int:
    """Print add/update/unchanged/delete counts without touching index.db.

    Writes nothing (no schema migration, no model load) so it previews a
    refresh safely and works even when fastembed isn't installed.
    """
    sources, incomplete = enumerate_sources()
    print(f"Enumerated {len(sources)} chunks from sources")

    db_path = sys.modules[connect_index.__module__].INDEX_DB
    existing: dict[tuple[str, str], str] = {}
    if db_path.exists():
        with connect_index() as conn:
            try:
                existing = {
                    (r[0], r[1]): r[2]
                    for r in conn.execute(
                        "SELECT source_path, source_key, content_hash "
                        "FROM documents"
                    ).fetchall()
                }
            except sqlite3.OperationalError:
                existing = {}

    seen: set[tuple[str, str]] = set()
    added = updated = 0
    for _st, sp, sk, text in sources:
        seen.add((sp, sk))
        cur = existing.get((sp, sk))
        if cur is None:
            added += 1
        elif cur != _sha256(text):
            updated += 1
    unchanged = len(seen) - added - updated
    if full and not incomplete:
        deleted = len(existing)
    elif incomplete:
        deleted = 0
    else:
        deleted = len(set(existing) - seen)

    print("DRY RUN — no changes written")
    print(f"  add: {added}  update: {updated}  "
          f"unchanged: {unchanged}  delete: {deleted}")
    return 0


def refresh(full: bool = False, dry_run: bool = False) -> int:
    if dry_run:
        return _dry_run_report(full)

    # Bring the schema current first (fresh init or pending migration). The
    # v1->v2 migration drops stale native-endian rows so they get re-embedded
    # little-endian; this must run even when the model is unavailable, hence
    # before the _get_model() check.
    ensure_current_schema()

    try:
        _get_model()
    except RuntimeError as e:
        print(f"WARN: {e} — skipping refresh", file=sys.stderr)
        return 0

    sources, incomplete = enumerate_sources()
    print(f"Enumerated {len(sources)} chunks from sources")

    with connect_index() as conn:
        uv = conn.execute("PRAGMA user_version").fetchone()[0]
        stale_format = uv < VEC_FORMAT

        if full and not incomplete:
            conn.execute("DELETE FROM documents")
            conn.commit()
        elif full and incomplete:
            print("  WARN: enumeration incomplete (unreadable source dir) — "
                  "downgrading --full to incremental so existing rows are "
                  "not wiped", file=sys.stderr)

        if stale_format and incomplete:
            print(f"  WARN: index.db predates the current vector layout "
                  f"(user_version {uv} < {VEC_FORMAT}) but enumeration was "
                  f"incomplete — deferring the forced re-embed until a "
                  f"clean refresh", file=sys.stderr)
        elif stale_format:
            n = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            if n:
                print(f"  WARN: index.db predates the current vector layout "
                      f"(user_version {uv} < {VEC_FORMAT}) — re-embedding all "
                      f"{n} rows so search scores aren't silently corrupt",
                      file=sys.stderr)
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
        if incomplete:
            print("  WARN: enumeration incomplete — skipping prune; "
                  "stale-but-usable rows kept until a clean refresh "
                  "reconciles them", file=sys.stderr)
        else:
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
                    (st, sp, sk, text, h, pack_vector(v), MODEL, now),
                )
            embedded += len(batch)
            conn.commit()
            print(f"  embedded {embedded}/{len(to_embed)}")

        if not incomplete:
            conn.execute(f"PRAGMA user_version = {VEC_FORMAT}")  # noqa: S608

        print(f"Done. embedded={embedded} deleted={deleted}")

        if embedded == 0 and deleted == 0 and not incomplete:
            # Nothing changed — touch index.db so search.py's mtime-based stale
            # check doesn't fire until a source file actually changes again.
            import os as _os
            db_path = sys.modules[connect_index.__module__].INDEX_DB
            _os.utime(db_path, None)

    return 0


def expected_source_paths() -> set[str]:
    """File-only enumeration. Mirrors enumerate_sources() globs without chunking."""
    out: set[str] = set()
    for glob in (*INDEXED_ROOT_GLOBS, *INDEXED_DOC_GLOBS):
        for f in sorted(BASE.glob(glob)):
            if _excluded(f):
                continue
            out.add(f.relative_to(BASE).as_posix())
    py_paths: list[Path] = []
    for dir_str in INDEXED_SOURCE_DIRS:
        d = BASE / dir_str.rstrip("/")
        if not d.exists():
            continue
        try:
            py_paths.extend(d.rglob("*.py"))
        except OSError as e:
            # One unreadable subtree must not crash health/verify and
            # report a false coverage gap — skip it and keep the rest.
            print(f"  WARN: skipping unreadable paths under {dir_str} — {e}",
                  file=sys.stderr)
    py_paths.extend(BASE.glob("*.py"))
    for py in sorted(set(py_paths)):
        if _excluded(py):
            continue
        out.add(py.relative_to(BASE).as_posix())
    sql_paths: list[Path] = []
    for dir_str in INDEXED_SOURCE_DIRS:
        d = BASE / dir_str.rstrip("/")
        if not d.exists():
            continue
        try:
            sql_paths.extend(d.glob("*.sql"))
        except OSError as e:
            print(f"  WARN: skipping unreadable SQL dir {dir_str} — {e}",
                  file=sys.stderr)
            continue
    sql_paths.extend(BASE.glob("*.sql"))
    for sq in sorted(set(sql_paths)):
        if _excluded(sq):
            continue
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


def _config_path() -> Path:
    return BASE / ".claude" / "tools" / "search_config.py"


def switch_model(model: str, dim: int) -> int:
    """Atomically switch EMBEDDING_MODEL / EMBEDDING_DIM and re-index.

    Prevents the silent dimension mismatch that occurs when a user edits
    the model by hand but forgets to bump DIM and run `refresh --full`.
    Refuses a no-op (same model + same dim) so a misclick doesn't trigger
    a full re-index for nothing.
    """
    if model == MODEL and dim == DIM:
        print(f"switch-model: EMBEDDING_MODEL is already {model!r} "
              f"with DIM {dim}; nothing to do.", file=sys.stderr)
        return 2

    cfg = _config_path()
    text = cfg.read_text()
    new = re.sub(
        r'^(EMBEDDING_MODEL\s*:\s*str\s*=\s*)"[^"]*"',
        lambda m: f'{m.group(1)}"{model}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    new = re.sub(
        r"^(EMBEDDING_DIM\s*:\s*int\s*=\s*)\d+",
        lambda m: f"{m.group(1)}{dim}",
        new,
        count=1,
        flags=re.MULTILINE,
    )
    if new == text:
        print("switch-model: could not locate EMBEDDING_MODEL / EMBEDDING_DIM "
              "in search_config.py — edit manually then run "
              "`embeddings.py refresh --full`.", file=sys.stderr)
        return 1
    cfg.write_text(new)
    print(f"switch-model: set EMBEDDING_MODEL={model!r}, EMBEDDING_DIM={dim}.")
    print("Running `refresh --full` — every chunk is re-embedded; this may "
          "take a while and downloads the new model on first use.")
    return refresh(full=True)


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


def _format_age(seconds: float) -> str:
    if seconds < 90:
        return f"{int(seconds)}s"
    if seconds < 5400:
        return f"{int(seconds // 60)}m"
    if seconds < 172800:
        return f"{int(seconds // 3600)}h"
    return f"{int(seconds // 86400)}d"


def stats(verbose: bool = False) -> int:
    with connect_index() as c:
        rows = c.execute(
            "SELECT source_type, COUNT(*) FROM documents "
            "GROUP BY source_type ORDER BY source_type"
        ).fetchall()
        total = c.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        newest = c.execute(
            "SELECT MAX(updated_at) FROM documents"
        ).fetchone()[0]
        files = c.execute(
            "SELECT COUNT(DISTINCT source_path) FROM documents"
        ).fetchone()[0]
    print(f"index.db documents: {total}")
    for st, n in rows:
        print(f"  {st:<12} {n}")
    if not verbose:
        return 0

    print(f"indexed files: {files}")
    if newest:
        try:
            age = (datetime.now(timezone.utc)
                   - datetime.fromisoformat(newest)).total_seconds()
            print(f"index age: {_format_age(max(0.0, age))} "
                  f"(newest chunk {newest})")
        except ValueError:
            print(f"index age: unknown (newest chunk {newest})")
    else:
        print("index age: empty index")

    expected = expected_source_paths()
    with connect_index() as c:
        indexed = {
            r[0] for r in c.execute(
                "SELECT DISTINCT source_path FROM documents"
            ).fetchall()
        }
    covered = len(expected & indexed)
    pct = (100.0 * covered / len(expected)) if expected else 0.0
    print(f"coverage: {covered}/{len(expected)} expected sources "
          f"({pct:.0f}%)")
    missing = sorted(expected - indexed)
    if missing:
        print(f"  missing: {', '.join(missing[:10])}"
              + (" …" if len(missing) > 10 else ""))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("refresh")
    r.add_argument("--full", action="store_true", help="delete-all and rebuild")
    r.add_argument("--dry-run", action="store_true",
                   help="show add/update/delete counts without writing")
    s = sub.add_parser("stats")
    s.add_argument("--verbose", action="store_true",
                   help="also show index age, file count, and coverage")
    sub.add_parser("health")
    sub.add_parser("savings")
    sm = sub.add_parser(
        "switch-model",
        help="rewrite EMBEDDING_MODEL/DIM in search_config.py and reindex",
    )
    sm.add_argument("model", help="new fastembed model id, e.g. BAAI/bge-base-en-v1.5")
    sm.add_argument("--dim", type=int, required=True,
                    help="embedding dimension of the new model (e.g. 768)")
    args = ap.parse_args()
    if args.cmd == "refresh":
        return refresh(full=args.full, dry_run=args.dry_run)
    if args.cmd == "health":
        return health()
    if args.cmd == "savings":
        from stats import main as _savings_main  # noqa: PLC0415
        return _savings_main()
    if args.cmd == "switch-model":
        return switch_model(args.model, dim=args.dim)
    return stats(verbose=getattr(args, "verbose", False))


if __name__ == "__main__":
    sys.exit(main())

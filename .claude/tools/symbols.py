#!/usr/bin/env python3
"""Symbol index — exact `file:line` for top-level defs/classes/constants.

AST-only (no embeddings, no fastembed): locating a symbol is a fact, not a
search. `/def foo` returns one line instead of dumping a grep. Mirrors the node
selection in embeddings.chunk_python so a symbol hit lines up with a search chunk.

Usage:
  python .claude/tools/symbols.py <name>        # exact location(s)
  python .claude/tools/symbols.py <name> --json
  python .claude/tools/symbols.py refresh [--full]
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
import time
from pathlib import Path
from typing import Iterator


def _find_base() -> Path:
    cwd = Path.cwd().resolve()
    if (cwd / ".claude" / "tools" / "search_config.py").exists():
        return cwd
    return Path(__file__).resolve().parent.parent.parent


BASE = _find_base()
sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import connect_index  # noqa: E402

try:
    import search_config as _cfg  # noqa: E402
    EXCLUDED_NAMES = set(_cfg.EXCLUDED_DIR_NAMES)
    EXCLUDED_PREFIXES = tuple(_cfg.EXCLUDED_DIR_PREFIXES)
    INDEXED_SOURCE_DIRS = tuple(_cfg.INDEXED_SOURCE_DIRS)
    STATE_DIR = _cfg.STATE_DIR
except Exception:
    EXCLUDED_NAMES = {".git", "__pycache__", ".venv", "node_modules", ".claude"}
    EXCLUDED_PREFIXES = ()
    INDEXED_SOURCE_DIRS = ()
    STATE_DIR = BASE / ".claude" / "state"

_MARKER = STATE_DIR / "last-symbols-refresh"


def _upper_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Name) and node.id.isupper():
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        out: list[str] = []
        for elt in node.elts:
            out.extend(_upper_names(elt))
        return out
    return []


def extract_symbols(path: Path) -> list[tuple[str, str, int, int]]:
    """Return (name, kind, start_line, end_line) for top-level definitions.

    Lines are 1-based (ready for Read offset). Mirrors chunk_python selection.
    """
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    out: list[tuple[str, str, int, int]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append((node.name, "func", node.lineno,
                        getattr(node, "end_lineno", node.lineno)))
        elif isinstance(node, ast.ClassDef):
            out.append((node.name, "class", node.lineno,
                        getattr(node, "end_lineno", node.lineno)))
        elif isinstance(node, ast.Assign):
            names: list[str] = []
            for t in node.targets:
                names.extend(_upper_names(t))
            for n in names:
                out.append((n, "const", node.lineno,
                            getattr(node, "end_lineno", node.lineno)))
        elif isinstance(node, ast.AnnAssign):
            for n in _upper_names(node.target):
                out.append((n, "const", node.lineno,
                            getattr(node, "end_lineno", node.lineno)))
    return out


def _excluded(rel: str) -> bool:
    parts = set(Path(rel).parts)
    if parts & EXCLUDED_NAMES:
        return True
    return any(rel.startswith(p) for p in EXCLUDED_PREFIXES)


def _iter_py_files() -> Iterator[Path]:
    for f in BASE.glob("*.py"):
        if not _excluded(f.relative_to(BASE).as_posix()):
            yield f
    for d in INDEXED_SOURCE_DIRS:
        root = BASE / d.rstrip("/")
        if not root.exists():
            continue
        for f in root.rglob("*.py"):
            rel = f.relative_to(BASE).as_posix()
            if not _excluded(rel):
                yield f


def _ensure_table(c) -> None:
    c.execute(
        "CREATE TABLE IF NOT EXISTS symbols ("
        "name TEXT NOT NULL, kind TEXT NOT NULL, source_path TEXT NOT NULL, "
        "start_line INTEGER NOT NULL, end_line INTEGER NOT NULL, "
        "PRIMARY KEY (name, source_path, start_line))"
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name)")


def refresh(full: bool = False) -> int:
    rows: list[tuple[str, str, str, int, int]] = []
    for f in _iter_py_files():
        rel = f.relative_to(BASE).as_posix()
        for name, kind, s, e in extract_symbols(f):
            rows.append((name, kind, rel, s, e))
    with connect_index() as c:
        _ensure_table(c)
        c.execute("DELETE FROM symbols")
        c.executemany(
            "INSERT OR IGNORE INTO symbols "
            "(name, kind, source_path, start_line, end_line) VALUES (?,?,?,?,?)",
            rows,
        )
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        _MARKER.write_text(str(time.time()))
    except OSError:
        pass
    return len(rows)


def _newest_source_mtime() -> float:
    newest = 0.0
    for f in _iter_py_files():
        try:
            newest = max(newest, f.stat().st_mtime)
        except OSError:
            pass
    return newest


def _is_stale() -> bool:
    try:
        marker = _MARKER.stat().st_mtime
    except OSError:
        return True
    return _newest_source_mtime() > marker


def has_symbol(name: str) -> bool:
    """Cheap existence check for hooks. Never refreshes; False on any error."""
    try:
        with connect_index() as c:
            row = c.execute(
                "SELECT 1 FROM symbols WHERE name=? LIMIT 1", (name,)
            ).fetchone()
        return row is not None
    except Exception:
        return False


def lookup(name: str) -> list[dict]:
    if _is_stale():
        refresh()
    try:
        with connect_index() as c:
            _ensure_table(c)
            rows = c.execute(
                "SELECT name, kind, source_path, start_line, end_line "
                "FROM symbols WHERE name=? ORDER BY source_path, start_line",
                (name,),
            ).fetchall()
    except Exception:
        return []
    return [dict(r) for r in rows]


def main() -> int:
    ap = argparse.ArgumentParser(description="Symbol index lookup")
    ap.add_argument("name", help="symbol name, or 'refresh'")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.name == "refresh":
        n = refresh(full=args.full)
        print(f"symbols: indexed {n} definitions")
        return 0

    hits = lookup(args.name)
    if args.json:
        print(json.dumps(hits, indent=2))
        return 0
    if not hits:
        print(f"no symbol '{args.name}'. Try search.py for fuzzy matches.",
              file=sys.stderr)
        return 1
    for h in hits:
        print(f"{h['source_path']}:{h['start_line']}-{h['end_line']}  "
              f"({h['kind']} {h['name']})  "
              f"-> Read(offset={h['start_line']}, limit={h['end_line']-h['start_line']+1})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

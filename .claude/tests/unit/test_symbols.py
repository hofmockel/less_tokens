"""Unit tests for the symbol index (S8)."""
from __future__ import annotations

from pathlib import Path


import sys
TOOLS = Path(__file__).resolve().parent.parent.parent / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
import symbols  # noqa: E402
import db  # noqa: E402

SAMPLE = '''\
"""mod doc"""
CONST_A = 1
X, Y = 2, 3


def top_func(a):
    return a


class TopClass:
    def method(self):  # not a top-level symbol
        return 1


async def afunc():
    return 0
'''


def test_extract_symbols_selects_top_level(tmp_path):
    f = tmp_path / "m.py"
    f.write_text(SAMPLE)
    got = {(n, k) for n, k, _, _ in symbols.extract_symbols(f)}
    assert ("top_func", "func") in got
    assert ("TopClass", "class") in got
    assert ("afunc", "func") in got
    assert ("CONST_A", "const") in got
    assert ("X", "const") in got and ("Y", "const") in got
    assert ("method", "func") not in got  # nested, not top-level


def test_extract_line_ranges_are_1_based(tmp_path):
    f = tmp_path / "m.py"
    f.write_text(SAMPLE)
    by_name = {n: (s, e) for n, _, s, e in symbols.extract_symbols(f)}
    s, e = by_name["top_func"]
    assert s == 6 and e >= s  # def on line 6


def test_extract_js_ts_symbols(tmp_path):
    f = tmp_path / "component.ts"
    f.write_text("""\
export interface Props {
  name: string
}

export type Mode = "a" | "b"

export const Widget = () => {
  return null
}

export class Store {
}

async function loadThing() {
}

enum Flavor {
  One
}
""")
    got = {(n, k) for n, k, _, _ in symbols.extract_symbols(f)}
    assert ("Props", "interface") in got
    assert ("Mode", "type") in got
    assert ("Widget", "const") in got
    assert ("Store", "class") in got
    assert ("loadThing", "func") in got
    assert ("Flavor", "enum") in got


def test_syntax_error_returns_empty(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text("def (:\n")
    assert symbols.extract_symbols(f) == []


def test_refresh_and_lookup_roundtrip(tmp_path, monkeypatch):
    src = tmp_path / "sample.py"
    src.write_text(SAMPLE)
    monkeypatch.setattr(symbols, "_iter_py_files", lambda: iter([src]))
    monkeypatch.setattr(symbols, "BASE", tmp_path)
    monkeypatch.setattr(db, "INDEX_DB", tmp_path / "index.db")
    monkeypatch.setattr(symbols, "_MARKER", tmp_path / "marker")

    n = symbols.refresh()
    assert n >= 6
    hits = symbols.lookup("top_func")
    assert hits and hits[0]["source_path"].endswith("sample.py")
    assert symbols.has_symbol("TopClass") is True
    assert symbols.has_symbol("nope_nope") is False


def test_refresh_and_lookup_js_ts_roundtrip(tmp_path, monkeypatch):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    src = src_dir / "component.ts"
    src.write_text("export const Widget = () => null\n")
    monkeypatch.setattr(symbols, "_iter_py_files", lambda: iter(()))
    monkeypatch.setattr(symbols, "_iter_js_files", lambda: iter([src]))
    monkeypatch.setattr(symbols, "BASE", tmp_path)
    monkeypatch.setattr(db, "INDEX_DB", tmp_path / "index.db")
    monkeypatch.setattr(symbols, "_MARKER", tmp_path / "marker")

    n = symbols.refresh(full=True)
    assert n == 1
    hits = symbols.lookup("Widget")
    assert hits and hits[0]["source_path"] == "src/component.ts"


def test_refresh_full_flag_skips_unchanged_files(tmp_path, monkeypatch):
    """refresh(full=False) must not wipe rows for files unchanged since the marker.

    Bug: the full parameter was never checked; refresh always ran
    DELETE FROM symbols regardless, erasing rows for files not re-scanned.
    """
    import os
    import time as _time

    src = tmp_path / "sample.py"
    src.write_text(SAMPLE)
    marker = tmp_path / "marker"
    monkeypatch.setattr(symbols, "_iter_py_files", lambda: iter([src]))
    monkeypatch.setattr(symbols, "BASE", tmp_path)
    monkeypatch.setattr(db, "INDEX_DB", tmp_path / "index.db")
    monkeypatch.setattr(symbols, "_MARKER", marker)

    # Initial full refresh to populate the DB
    symbols.refresh(full=True)

    # Insert a sentinel row for a file NOT returned by _iter_py_files
    with db.connect_index() as c:
        c.execute(
            "INSERT OR IGNORE INTO symbols "
            "(name, kind, source_path, start_line, end_line) "
            "VALUES ('sentinel_func', 'func', 'ghost.py', 1, 10)"
        )

    # Set marker mtime to future so src appears older than marker (unchanged)
    marker.write_text("")
    future = _time.time() + 3600
    os.utime(marker, (future, future))

    # Incremental refresh — no file is newer than the marker, so nothing should change
    symbols.refresh(full=False)

    with db.connect_index() as c:
        row = c.execute(
            "SELECT name FROM symbols WHERE source_path = 'ghost.py'"
        ).fetchone()
    assert row is not None, (
        "refresh(full=False) must preserve rows for files unchanged since the marker"
    )

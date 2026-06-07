"""Unit tests for the symbol index (S8)."""
from __future__ import annotations

from pathlib import Path

import pytest

import importlib, sys
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

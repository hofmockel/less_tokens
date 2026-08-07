"""P3 regression: search-first and index-refresh must agree on is_indexed.

Both hooks delegate to the single shared `is_indexed` in
`agents/common/hooks/search_first.py`. This test pins that they pass the
*same* config so mid-path excluded dirs can never diverge again — the
divergence that the old CLAUDE.md "Known bugs worth avoiding" note warned about.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_both_hooks_use_one_shared_is_indexed():
    sf = _load("sf_hook", ".claude/hooks/search-first.py")
    ir = _load("ir_hook", ".claude/hooks/index-refresh.py")
    # Same function object backs both wrappers — no second implementation.
    assert sf._common_is_indexed is ir._common_is_indexed


def test_indexed_decision_matches_across_hooks():
    sf = _load("sf_hook2", ".claude/hooks/search-first.py")
    ir = _load("ir_hook2", ".claude/hooks/index-refresh.py")
    sf._load_config()  # search-first reads its config lazily

    cases = [
        REPO / "CLAUDE.md",
        REPO / "DOCUMENTATION.md",
        REPO / ".claude" / "tools" / "search.py",
        REPO / ".claude" / "node_modules" / "pkg" / "mod.py",  # mid-path excluded
        REPO / "build" / "out.py",
        REPO / "random.txt",
    ]
    for p in cases:
        assert sf.is_indexed(p) == ir.is_indexed(p), f"divergence on {p}"

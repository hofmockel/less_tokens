from __future__ import annotations

import importlib.util
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
BUILD_DOCS = REPO / "docs-site" / "scripts" / "build_docs.py"


def _load_build_docs():
    spec = importlib.util.spec_from_file_location("build_docs", BUILD_DOCS)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hook_matrix_is_generated_from_manifest():
    build_docs = _load_build_docs()

    names = {row["name"] for row in build_docs.hook_matrix()}

    assert "search-first" in names
    assert "budget-observer" in names
    assert "terse-output" in names


def test_installer_flags_are_parsed_from_argparse_metadata():
    build_docs = _load_build_docs()

    flags = {flag for row in build_docs.installer_flags() for flag in row["flags"]}

    assert "--agent" in flags
    assert "--codex-savings" in flags
    assert "--no-compact" in flags


def test_strategy_matrix_links_to_strategy_pages():
    build_docs = _load_build_docs()

    slugs = {row["slug"] for row in build_docs.strategy_matrix()}

    assert "search-first" in slugs
    assert "budget-control-plane" in slugs
    assert "lean-output-truncation" in slugs

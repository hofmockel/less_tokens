"""Recursive-glob guidance for doc-heavy repos.

1. search_config.py comments INDEXED_ROOT_GLOBS as supporting `**`.
2. NEXT STEPS output mentions INDEXED_ROOT_GLOBS (the .md knob) so
   users of non-Python repos know which variable to edit.
3. _maybe_suggest_recursive_globs() nudges when subdir markdown
   dominates and no root .py is present.
"""
from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
import install  # noqa: E402


def test_config_comment_mentions_recursive_pattern():
    text = (REPO / ".claude" / "tools" / "search_config.py").read_text()
    assert "**" in text
    assert "INDEXED_ROOT_GLOBS" in text


def test_install_next_steps_mentions_indexed_root_globs():
    src = (REPO / "install.py").read_text()
    # The NEXT STEPS branch should mention the .md knob explicitly so
    # non-Python repos know which variable to tune.
    assert "INDEXED_ROOT_GLOBS" in src


def test_suggest_recursive_globs_fires_for_doc_heavy_repo(tmp_path):
    # Doc-heavy: 0 .py, 6 .md spread across subdirs, 1 .md at root.
    (tmp_path / "README.md").write_text("root\n")
    for i in range(6):
        d = tmp_path / f"docs{i}"
        d.mkdir()
        (d / f"page{i}.md").write_text(f"# page {i}\n")
    buf = io.StringIO()
    with redirect_stdout(buf):
        install._maybe_suggest_recursive_globs(tmp_path)
    out = buf.getvalue()
    assert "**/*.md" in out
    assert "INDEXED_ROOT_GLOBS" in out


def test_suggest_recursive_globs_silent_for_python_repo(tmp_path):
    # Python repo: lots of .py, no subdir .md — should NOT print.
    for i in range(5):
        (tmp_path / f"module{i}.py").write_text("x = 1\n")
    (tmp_path / "README.md").write_text("root\n")
    buf = io.StringIO()
    with redirect_stdout(buf):
        install._maybe_suggest_recursive_globs(tmp_path)
    assert buf.getvalue() == ""

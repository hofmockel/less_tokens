"""Regression: a single permission-denied directory must not abort the whole
index refresh.

`enumerate_sources()` collected Python files with `d.rglob("*.py")` for each
`INDEXED_SOURCE_DIRS` entry. `rglob` propagates `PermissionError` (an
`OSError`) the moment it descends into one unreadable subtree, so a single
locked-down directory killed the entire run and left `index.db` stale - even
though every other source dir was readable. The fix wraps each per-source
enumeration in `try/except OSError`, logs a warning, and continues so the
readable sources are still indexed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))
from tools import embeddings  # noqa: E402


@pytest.fixture()
def two_source_dirs(tmp_path, monkeypatch):
    """A fake repo with one readable source dir and one that raises
    PermissionError on traversal (simulating a chmod 000 subtree).
    """
    (tmp_path / "good").mkdir()
    (tmp_path / "good" / "ok.py").write_text("def f():\n    return 1\n")
    (tmp_path / "bad").mkdir()

    monkeypatch.setattr(embeddings, "BASE", tmp_path)
    # "bad" is listed first so a pre-fix run aborts before "good" is ever
    # reached - the strongest form of the bug.
    monkeypatch.setattr(embeddings, "INDEXED_SOURCE_DIRS", ("bad/", "good/"))
    monkeypatch.setattr(embeddings, "INDEXED_ROOT_GLOBS", ())
    monkeypatch.setattr(embeddings, "_excluded", lambda p: False)

    orig_rglob = Path.rglob

    def fake_rglob(self, pattern):
        if self.name == "bad":
            raise PermissionError(13, "Permission denied", str(self))
        return orig_rglob(self, pattern)

    monkeypatch.setattr(Path, "rglob", fake_rglob)
    return tmp_path


def test_unreadable_dir_does_not_abort_refresh(two_source_dirs, capsys):
    # Pre-fix this raises PermissionError out of enumerate_sources().
    sources, _ = embeddings.enumerate_sources()

    paths = {row[1] for row in sources}
    assert "good/ok.py" in paths, "readable source must still be indexed"


def test_unreadable_dir_emits_warning(two_source_dirs, capsys):
    embeddings.enumerate_sources()
    err = capsys.readouterr().err
    assert "WARN" in err
    assert "bad" in err

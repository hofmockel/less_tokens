"""Installer does not create or maintain a second semantic index."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import install  # noqa: E402


def _configure_external(tmp_path: Path) -> None:
    config = tmp_path / ".claude" / "tools" / "search_config.py"
    config.parent.mkdir(parents=True)
    config.write_text('SEARCH_BACKEND: str = "command"\n')


def test_reads_annotated_backend_assignment(tmp_path):
    _configure_external(tmp_path)
    assert install.configured_search_backend(tmp_path) == "command"


def test_external_backend_skips_sqlite_init(tmp_path, monkeypatch):
    _configure_external(tmp_path)
    monkeypatch.setattr(
        install.subprocess,
        "check_call",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not init SQLite")),
    )

    assert install.init_db(Path("/unused/python"), tmp_path) == (0, False)
    assert not (tmp_path / ".claude" / "index.db").exists()


def test_external_backend_skips_local_embedding_build(tmp_path, monkeypatch):
    _configure_external(tmp_path)
    monkeypatch.setattr(
        install.subprocess,
        "check_call",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not embed locally")),
    )

    assert install.build_index(Path("/unused/python"), tmp_path) == 0

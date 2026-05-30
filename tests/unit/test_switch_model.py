"""`embeddings.py switch-model` rewrites search_config.py + reindexes.

Prevents the silent dimension mismatch that occurs when a user edits
EMBEDDING_MODEL by hand but forgets to bump EMBEDDING_DIM and re-run
`refresh --full` (scores quietly become wrong against an existing index).
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))


def _setup_fake_config(tmp_path, monkeypatch):
    """Create a search_config.py-like file in a tmp dir + put it on sys.path."""
    cfg = tmp_path / "search_config.py"
    cfg.write_text(
        'EMBEDDING_MODEL: str = "old/model"\n'
        "EMBEDDING_DIM: int = 384\n"
    )
    return cfg


def test_switch_model_rewrites_config_and_triggers_full_refresh(tmp_path, monkeypatch):
    cfg = _setup_fake_config(tmp_path, monkeypatch)
    import embeddings
    importlib.reload(embeddings)

    monkeypatch.setattr(embeddings, "_config_path", lambda: cfg)
    refresh_calls: list[dict] = []
    monkeypatch.setattr(
        embeddings, "refresh",
        lambda **kw: refresh_calls.append(kw) or 0,
    )

    rc = embeddings.switch_model("new/big-model", dim=768)
    assert rc == 0
    text = cfg.read_text()
    assert 'EMBEDDING_MODEL: str = "new/big-model"' in text
    assert "EMBEDDING_DIM: int = 768" in text
    assert "old/model" not in text
    assert refresh_calls == [{"full": True}]


def test_switch_model_rejects_unchanged_model(tmp_path, monkeypatch):
    cfg = _setup_fake_config(tmp_path, monkeypatch)
    import embeddings
    importlib.reload(embeddings)
    monkeypatch.setattr(embeddings, "_config_path", lambda: cfg)
    monkeypatch.setattr(embeddings, "refresh", lambda **kw: 0)

    rc = embeddings.switch_model("old/model", dim=384)
    # No-op: same model, same dim - refuse so the user doesn't trigger a
    # gratuitous full re-index.
    assert rc != 0


def test_switch_model_preserves_surrounding_lines(tmp_path, monkeypatch):
    cfg = tmp_path / "search_config.py"
    cfg.write_text(
        "# leading comment\n"
        'EMBEDDING_MODEL: str = "old/model"\n'
        "EMBEDDING_DIM: int = 384\n"
        "OTHER_VAR = 42\n"
    )
    import embeddings
    importlib.reload(embeddings)
    monkeypatch.setattr(embeddings, "_config_path", lambda: cfg)
    monkeypatch.setattr(embeddings, "refresh", lambda **kw: 0)

    embeddings.switch_model("new/model", dim=512)
    text = cfg.read_text()
    assert text.startswith("# leading comment\n")
    assert "OTHER_VAR = 42" in text

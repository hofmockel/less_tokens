"""Codex-specific search.py output-budget defaults."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))
from tools import search  # noqa: E402


@pytest.fixture()
def stubbed_main(monkeypatch, tmp_path):
    captured = {}

    def fake_search(query, *, k, source_type=None, min_score=None):
        captured.update(
            {
                "query": query,
                "k": k,
                "source_type": source_type,
                "min_score": min_score,
            }
        )
        return [
            {
                "score": 0.9,
                "source_type": "code",
                "source_path": "src/app.py",
                "source_key": "demo",
                "text": "x" * 800,
            }
        ]

    monkeypatch.setattr(search, "_source_type_choices", lambda: None)
    monkeypatch.setattr(search, "_index_is_stale", lambda: False)
    monkeypatch.setattr(search, "active_state_dir", lambda: tmp_path / "state")
    monkeypatch.setattr(search, "_log_history", lambda *a, **k: None)
    monkeypatch.setattr(search, "_log_savings", lambda *a, **k: None)
    monkeypatch.setattr(search, "_write_last_search_ranges", lambda *a, **k: None)
    monkeypatch.setattr(search, "search", fake_search)
    return captured


def test_codex_env_uses_tighter_default_k_and_snippet_chars(
    stubbed_main, monkeypatch, capsys
):
    monkeypatch.setenv("LESS_TOKENS_AGENT", "codex")
    monkeypatch.setattr(sys, "argv", ["search.py", "query"])

    assert search.main() == 0

    out = capsys.readouterr().out
    assert stubbed_main["k"] == search.CODEX_DEFAULT_K
    assert "x" * search.CODEX_DEFAULT_SNIPPET_CHARS in out
    assert "x" * (search.CODEX_DEFAULT_SNIPPET_CHARS + 1) not in out


def test_claude_env_keeps_existing_default_k_and_snippet_chars(
    stubbed_main, monkeypatch, capsys
):
    monkeypatch.setenv("LESS_TOKENS_AGENT", "claude")
    monkeypatch.setattr(sys, "argv", ["search.py", "query"])

    assert search.main() == 0

    out = capsys.readouterr().out
    assert stubbed_main["k"] == search.DEFAULT_K
    assert "x" * search.DEFAULT_SNIPPET_CHARS in out
    assert "x" * (search.DEFAULT_SNIPPET_CHARS + 1) not in out


def test_explicit_limits_override_codex_defaults(stubbed_main, monkeypatch, capsys):
    monkeypatch.setenv("LESS_TOKENS_AGENT", "codex")
    monkeypatch.setattr(
        sys, "argv", ["search.py", "query", "-k", "5", "--snippet-chars", "50"]
    )

    assert search.main() == 0

    out = capsys.readouterr().out
    assert stubbed_main["k"] == 5
    assert "x" * 50 in out
    assert "x" * 51 not in out

"""AGENT_MODEL + model_profiles drive default k in search.py.

Unset AGENT_MODEL keeps current behavior (DEFAULT_K = 3). Set to a
known model id, the search CLI picks up the model's recommended k
without the user passing -k.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / ".claude" / "tools"))


def test_profile_returns_none_when_unset():
    from model_profiles import profile
    assert profile(None) is None
    assert profile("") is None
    assert profile("not-a-real-model") is None


def test_profile_has_known_claude_ids():
    from model_profiles import MODEL_PROFILES, profile
    # At least one Sonnet and one Opus should be present.
    assert any("sonnet" in k for k in MODEL_PROFILES)
    assert any("opus" in k for k in MODEL_PROFILES)
    p = profile("claude-sonnet-4-6")
    assert p is not None
    assert p["recommended_k"] > 0
    assert p["context_window"] > 0


def test_search_config_exposes_agent_model_none_by_default():
    import search_config
    assert hasattr(search_config, "AGENT_MODEL")
    assert search_config.AGENT_MODEL is None


def test_search_cli_uses_profile_k_when_unset(monkeypatch):
    import search as search_mod
    import search_config
    captured: dict = {}

    def fake_search(query, k, source_type=None, min_score=None):
        captured["k"] = k
        return []

    monkeypatch.setattr(search_mod, "search", fake_search)
    monkeypatch.delenv("LESS_TOKENS_AGENT", raising=False)
    monkeypatch.setattr(search_config, "AGENT_MODEL", "claude-opus-4-7")
    monkeypatch.setattr(search_mod, "_index_is_stale", lambda: False)
    monkeypatch.setattr(sys, "argv", ["search.py", "anything"])
    search_mod.main()
    # Opus profile recommends >3.
    assert captured["k"] >= 5


def test_search_cli_explicit_k_overrides_profile(monkeypatch):
    import search as search_mod
    import search_config
    captured: dict = {}
    monkeypatch.setattr(
        search_mod, "search",
        lambda query, k, source_type=None, min_score=None: captured.update({"k": k}) or [],
    )
    monkeypatch.delenv("LESS_TOKENS_AGENT", raising=False)
    monkeypatch.setattr(search_config, "AGENT_MODEL", "claude-opus-4-7")
    monkeypatch.setattr(search_mod, "_index_is_stale", lambda: False)
    monkeypatch.setattr(sys, "argv", ["search.py", "anything", "-k", "2"])
    search_mod.main()
    assert captured["k"] == 2

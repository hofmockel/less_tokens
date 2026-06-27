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

from tests.conftest import REPO_ROOT, load_hook  # noqa: E402


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


def test_model_profiles_scale_claude_hook_thresholds():
    from model_profiles import scaled_compact_chars, scaled_tool_output_chars

    assert scaled_tool_output_chars(4000, None) == 4000
    assert scaled_tool_output_chars(4000, "unknown-model") == 4000
    assert scaled_tool_output_chars(0, "claude-haiku-4-5") == 0
    assert scaled_tool_output_chars(4000, "claude-haiku-4-5") == 3000
    assert scaled_tool_output_chars(4000, "claude-sonnet-4-5") == 4000
    assert scaled_tool_output_chars(4000, "claude-opus-4-8") == 5000
    assert scaled_compact_chars(500_000, "claude-sonnet-4-6") == 750_000


def test_claude_hooks_apply_model_scaled_thresholds(monkeypatch):
    import search_config

    monkeypatch.setattr(search_config, "AGENT_MODEL", "claude-haiku-4-5")
    truncate = load_hook(REPO_ROOT / ".claude" / "hooks" / "truncate-output.py")
    compact = load_hook(REPO_ROOT / ".claude" / "hooks" / "compact-trigger.py")

    assert truncate.MAX_TOOL_OUTPUT_CHARS == 3000
    assert compact.MAX_SESSION_CHARS == 375_000


def test_codex_hooks_do_not_use_claude_model_thresholds():
    codex_hooks = [
        REPO_ROOT / "agents" / "codex" / "hooks" / "truncate-output.py",
        REPO_ROOT / "agents" / "codex" / "hooks" / "compact-trigger.py",
    ]

    for hook in codex_hooks:
        src = hook.read_text(encoding="utf-8")
        assert "model_profiles" not in src
        assert "AGENT_MODEL" not in src

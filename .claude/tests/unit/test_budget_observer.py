from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "agents" / "common" / "hooks"))

from budget_observer import budget_hook_outcome, observe_budget_payload  # noqa: E402


def test_observer_returns_advice_only_in_advise_mode(tmp_path):
    cfg = tmp_path / ".less_tokens" / "config"
    cfg.mkdir(parents=True)
    (cfg / "budget.json").write_text(json.dumps({"mode": "advise"}), encoding="utf-8")
    target = tmp_path / "big.py"
    target.write_text("x" * 20000, encoding="utf-8")
    raw = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Read",
        "tool_input": {"file_path": str(target)},
        "session_id": "s1",
        "run_id": "r1",
    }
    advice = observe_budget_payload(raw, repo=tmp_path, agent="claude")
    assert advice is not None
    assert len(advice) <= 600
    assert "less_tokens budget" in advice


def test_observer_stays_silent_in_observe_mode(tmp_path):
    target = tmp_path / "big.py"
    target.write_text("x" * 20000, encoding="utf-8")
    raw = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Read",
        "tool_input": {"file_path": str(target)},
    }
    assert observe_budget_payload(raw, repo=tmp_path, agent="codex") is None


def test_observer_blocks_in_enforce_mode(tmp_path):
    cfg = tmp_path / ".less_tokens" / "config"
    cfg.mkdir(parents=True)
    (cfg / "budget.json").write_text(json.dumps({"mode": "enforce"}), encoding="utf-8")
    target = tmp_path / "big.py"
    target.write_text("x" * 20000, encoding="utf-8")
    raw = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Read",
        "tool_input": {"file_path": str(target)},
    }
    outcome = budget_hook_outcome(raw, repo=tmp_path, agent="claude")
    assert outcome is not None
    assert outcome.exit_code == 2
    assert outcome.stream == "stderr"
    assert outcome.message and "less_tokens budget" in outcome.message


def test_observer_bypass_disables_enforce_block(tmp_path):
    cfg = tmp_path / ".less_tokens" / "config"
    cfg.mkdir(parents=True)
    (cfg / "budget.json").write_text(json.dumps({"mode": "enforce"}), encoding="utf-8")
    target = tmp_path / "big.py"
    target.write_text("x" * 20000, encoding="utf-8")
    raw = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Read",
        "tool_input": {"file_path": str(target), "less_tokens_bypass": True},
    }
    outcome = budget_hook_outcome(raw, repo=tmp_path, agent="claude")
    assert outcome is not None
    assert outcome.exit_code == 0
    assert outcome.message is None

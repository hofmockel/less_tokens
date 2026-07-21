from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "agents" / "common" / "hooks"))

from budget_observer import budget_hook_outcome, observe_budget_payload  # noqa: E402
from agents.common.budget import load_events  # noqa: E402


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


def test_observer_rate_limits_repeated_advice(tmp_path):
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

    first = budget_hook_outcome(raw, repo=tmp_path, agent="claude")
    second = budget_hook_outcome(raw, repo=tmp_path, agent="claude")

    assert first is not None
    assert first.message and "less_tokens budget" in first.message
    assert second is not None
    assert second.exit_code == 0
    assert second.message is None


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


def test_observer_records_retry_safe_pretool_measurement_for_codex_and_claude(tmp_path):
    for agent in ("codex", "claude"):
        root = tmp_path / agent
        root.mkdir()
        target = root / "big.py"
        target.write_text("x" * 20000, encoding="utf-8")
        tool_input = {"file_path": str(target)}
        raw = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Read",
            "tool_input": tool_input,
            "tool_use_id": f"{agent}-tool-use-1",
            "session_id": f"{agent}-session",
        }
        canonical_input = json.dumps(
            tool_input,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

        assert budget_hook_outcome(raw, repo=root, agent=agent) is not None
        first_events = load_events(root)
        assert first_events
        first_ids = {event["event_id"] for event in first_events}
        assert budget_hook_outcome(raw, repo=root, agent=agent) is not None

        events = load_events(root)
        assert first_ids <= {event["event_id"] for event in events}
        assert len({event["event_id"] for event in events}) == len(events)
        assert {event["agent"] for event in events} == {agent}
        assert "pre_read" in {event["phase"] for event in events}
        assert {event["invocation_id"] for event in events} == {raw["tool_use_id"]}
        measured = [event for event in events if event["input_characters"]]
        assert len(measured) == 1
        assert measured[0]["phase"] == "pre_read"
        assert measured[0]["input_characters"] == len(canonical_input)
        assert measured[0]["estimated_input_tokens"] > 0

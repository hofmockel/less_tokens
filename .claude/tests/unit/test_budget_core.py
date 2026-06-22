from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from agents.common.budget import (  # noqa: E402
    ContextCandidate,
    evaluate_budget_input,
    load_budget_config,
    load_events,
    normalize_budget_input,
    score_candidates,
    select_candidates,
)
from agents.common.budget.advice import advice_for_mode, enforcement_decision, format_advice, outcome_for_mode  # noqa: E402
from agents.common.budget.decisions import BudgetDecision  # noqa: E402
from agents.common.budget.signals import build_budget_signals, grep_cache_key  # noqa: E402
from agents.common.budget.config import default_budget_config_text  # noqa: E402
from agents.common.budget.estimator import estimate_tokens  # noqa: E402


def test_estimator_uses_chars_div_4_with_multiplier():
    assert estimate_tokens("a" * 40) == 10
    assert estimate_tokens("a" * 40, content_type="logs") == 12


def test_default_budget_config_is_v2_json():
    data = json.loads(default_budget_config_text())
    assert data["version"] == 2
    assert data["mode"] == "observe"
    assert data["categories"]["retrieved_context"] == 10000


def test_load_budget_config_merges_project_file(tmp_path):
    cfg_dir = tmp_path / ".less_tokens" / "config"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "budget.json").write_text(
        json.dumps({"mode": "advise", "categories": {"tool_output": 1234}}),
        encoding="utf-8",
    )
    cfg = load_budget_config(tmp_path, agent="claude")
    assert cfg.mode == "advise"
    assert cfg.category_limit("tool_output") == 1234
    assert cfg.category_limit("retrieved_context") == 10000


def test_score_explicit_path_beats_unmentioned_path():
    candidates = [
        ContextCandidate(candidate_id="file:a.py", category="retrieved_context", candidate_type="file", path="a.py", text="x"),
        ContextCandidate(candidate_id="file:b.py", category="retrieved_context", candidate_type="file", path="b.py", text="x"),
    ]
    scored = score_candidates(candidates, query="please inspect a.py")
    scores = {c.path: c.relevance_score for c in scored}
    assert scores["a.py"] > scores["b.py"]


def test_select_candidates_replaces_oversized_relevant_file(tmp_path):
    cfg = load_budget_config(tmp_path)
    candidate = ContextCandidate(
        candidate_id="file:big.py",
        category="retrieved_context",
        candidate_type="file",
        path="big.py",
        text="x" * 20000,
        relevance_score=0.9,
    )
    decision = select_candidates([candidate], cfg)[0]
    assert decision.action == "replace"
    assert decision.replacement
    assert decision.estimated_tokens_saved > 0


def test_evaluate_budget_input_writes_v2_event(tmp_path):
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Read",
        "tool_input": {"file_path": str(tmp_path / "README.md")},
        "session_id": "s1",
        "run_id": "r1",
    }
    (tmp_path / "README.md").write_text("# hello\n", encoding="utf-8")
    budget_input = normalize_budget_input(payload, agent="claude")
    decisions = evaluate_budget_input(tmp_path, budget_input, load_budget_config(tmp_path))
    events = load_events(tmp_path)
    assert decisions
    assert events[0]["version"] == 2
    assert events[0]["agent"] == "claude"
    assert events[0]["phase"] == "pre_read"


def test_search_range_boosts_file_and_produces_exact_replacement(tmp_path):
    state = tmp_path / ".less_tokens" / "state"
    state.mkdir(parents=True)
    (state / "last-search.json").write_text(json.dumps({"agents/common/budget/gate.py": [[12, 20]]}), encoding="utf-8")
    cfg = load_budget_config(tmp_path)
    candidate = ContextCandidate(
        candidate_id="file:agents/common/budget/gate.py",
        category="retrieved_context",
        candidate_type="file",
        path="agents/common/budget/gate.py",
        text="x" * 20000,
    )
    signals = build_budget_signals(tmp_path, query="budget gate")
    scored = score_candidates([candidate], query="budget gate", signals=signals)
    assert scored[0].relevance_score >= cfg.relevance_threshold
    decision = select_candidates(scored, cfg, signals=signals)[0]
    assert decision.action == "replace"
    assert "lines 12-20" in (decision.replacement or "")


def test_failing_test_path_gets_high_relevance(tmp_path):
    output = "FAILED tests/test_budget_core.py::test_gate - AssertionError\nE assert 1 == 2\n"
    payload = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "pytest"},
        "tool_response": output,
    }
    budget_input = normalize_budget_input(payload, agent="codex")
    signals = build_budget_signals(tmp_path, query="pytest", text=output)
    scored = score_candidates(budget_input.candidates, query=budget_input.query, signals=signals)
    by_path = {candidate.path: candidate for candidate in scored if candidate.path}
    assert by_path["tests/test_budget_core.py"].relevance_score >= 0.35
    assert "failure output" in by_path["tests/test_budget_core.py"].reason


def test_recent_edit_path_increases_relevance(tmp_path):
    edited = tmp_path / "app.py"
    state = tmp_path / ".less_tokens" / "state"
    state.mkdir(parents=True)
    (state / "last-edit.json").write_text(json.dumps({str(edited.resolve()): __import__("time").time()}), encoding="utf-8")
    candidate = ContextCandidate(
        candidate_id=f"file:{edited}",
        category="retrieved_context",
        candidate_type="file",
        path=str(edited),
        text="def changed(): pass",
    )
    signals = build_budget_signals(tmp_path, query="verify recent edit")
    scored = score_candidates([candidate], query="verify recent edit", signals=signals)[0]
    assert scored.relevance_score > 0
    assert "recent path" in scored.reason


def test_advice_is_capped_and_mode_gated():
    decision = BudgetDecision(
        action="replace",
        category="retrieved_context",
        candidate_id="file:big.py",
        estimated_tokens_before=5000,
        estimated_tokens_after=100,
        budget_limit=3000,
        replacement="Read only " + ("specific lines " * 80),
    )
    assert advice_for_mode([decision], mode="observe") is None
    advice = advice_for_mode([decision], mode="advise")
    assert advice is not None
    assert len(advice) <= 600
    assert "saves ~4,900 tokens" in advice


def test_enforce_mode_blocks_actionable_decision():
    decision = BudgetDecision(
        action="replace",
        category="retrieved_context",
        candidate_id="file:big.py",
        estimated_tokens_before=5000,
        estimated_tokens_after=100,
        budget_limit=3000,
        replacement="Read a targeted slice from big.py with limit 200.",
    )
    assert enforcement_decision([decision], mode="advise") is None
    outcome = outcome_for_mode([decision], mode="enforce")
    assert outcome.exit_code == 2
    assert outcome.stream == "stderr"
    assert outcome.message and "Read a targeted slice" in outcome.message


def test_budget_doctor_smoke(tmp_path):
    cfg_dir = tmp_path / ".less_tokens" / "config"
    state_dir = tmp_path / ".less_tokens" / "state"
    cfg_dir.mkdir(parents=True)
    state_dir.mkdir(parents=True)
    (cfg_dir / "budget.json").write_text(json.dumps({"mode": "advise"}), encoding="utf-8")
    (state_dir / "events.jsonl").write_text(json.dumps({
        "version": 2,
        "decision": "replace",
        "category": "retrieved_context",
        "budget_used_after": 1000,
        "budget_limit": 2000,
    }) + "\n", encoding="utf-8")
    tool = Path(__file__).parent.parent.parent.parent / ".less_tokens" / "tools" / "budget_doctor.py"
    result = subprocess.run(
        [sys.executable, str(tool), "--limit", "5"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent.parent.parent)},
        timeout=10,
    )
    assert result.returncode == 0
    assert "Mode: advise" in result.stdout
    assert "retrieved_context: 50%" in result.stdout


def test_repeated_read_blocks_in_enforce_mode(tmp_path):
    target = tmp_path / "big.py"
    target.write_text("x" * 20000, encoding="utf-8")
    state = tmp_path / ".less_tokens" / "state"
    state.mkdir(parents=True)
    key = f"{target}::None::None"
    (state / "context-cache.json").write_text(json.dumps({
        "reads": {key: {"ts": __import__("time").time()}},
        "greps": {},
    }), encoding="utf-8")
    (tmp_path / ".less_tokens" / "config").mkdir(parents=True)
    (tmp_path / ".less_tokens" / "config" / "budget.json").write_text(json.dumps({"mode": "enforce"}), encoding="utf-8")
    budget_input = normalize_budget_input({
        "hook_event_name": "PreToolUse",
        "tool_name": "Read",
        "tool_input": {"file_path": str(target)},
    }, agent="claude")
    decisions = evaluate_budget_input(tmp_path, budget_input, load_budget_config(tmp_path))
    assert decisions[0].action == "block"
    assert "repeated unchanged read" in decisions[0].reason


def test_repeated_search_blocks_in_enforce_mode(tmp_path):
    state = tmp_path / ".less_tokens" / "state"
    state.mkdir(parents=True)
    (state / "context-cache.json").write_text(json.dumps({
        "reads": {},
        "greps": {grep_cache_key(pattern="needle"): {"ts": __import__("time").time()}},
    }), encoding="utf-8")
    (tmp_path / ".less_tokens" / "config").mkdir(parents=True)
    (tmp_path / ".less_tokens" / "config" / "budget.json").write_text(json.dumps({"mode": "enforce"}), encoding="utf-8")
    budget_input = normalize_budget_input({
        "hook_event_name": "PreToolUse",
        "tool_name": "Grep",
        "tool_input": {"pattern": "needle"},
    }, agent="claude")
    decisions = evaluate_budget_input(tmp_path, budget_input, load_budget_config(tmp_path))
    assert decisions[0].action == "block"
    assert "repeated search" in decisions[0].reason


def test_broad_directory_listing_blocks_in_enforce_mode(tmp_path):
    (tmp_path / ".less_tokens" / "config").mkdir(parents=True)
    (tmp_path / ".less_tokens" / "config" / "budget.json").write_text(json.dumps({"mode": "enforce"}), encoding="utf-8")
    budget_input = normalize_budget_input({
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "find ."},
    }, agent="codex")
    decisions = evaluate_budget_input(tmp_path, budget_input, load_budget_config(tmp_path))
    assert decisions[0].action == "block"
    assert "directory listing" in decisions[0].reason
    assert "narrower glob" in (decisions[0].replacement or "")


def test_strict_blocks_oversized_unscored_context(tmp_path):
    cfg = load_budget_config(tmp_path)
    cfg = type(cfg)(
        version=cfg.version,
        mode="strict",
        token_estimator=cfg.token_estimator,
        total_context_tokens=cfg.total_context_tokens,
        reserved_response_tokens=cfg.reserved_response_tokens,
        relevance_threshold=cfg.relevance_threshold,
        replacement_required_for_blocks=cfg.replacement_required_for_blocks,
        categories=cfg.categories,
        hard_caps={**cfg.hard_caps, "unscored_context": 10},
        agent_overrides=cfg.agent_overrides,
    )
    candidate = ContextCandidate(
        candidate_id="tool_output:unknown",
        category="tool_output",
        candidate_type="tool_output",
        text="x" * 1000,
        relevance_score=0,
    )
    decision = select_candidates([candidate], cfg)[0]
    assert decision.action == "block"
    assert "unscored context" in decision.reason

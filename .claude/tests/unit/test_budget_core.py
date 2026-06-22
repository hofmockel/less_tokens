from __future__ import annotations

import json
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

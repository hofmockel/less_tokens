from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).parent.parent.parent.parent


def _read(name: str) -> str:
    return (REPO / name).read_text(encoding="utf-8")


def test_readme_describes_budget_control_plane():
    text = _read("README.md")
    assert "budget-native context control plane" in text
    assert ".less_tokens/config/budget.json" in text
    assert ".less_tokens/tools/budget_report.py" in text
    assert ".less_tokens/tools/budget_doctor.py" in text
    for mode in ("observe", "advise", "enforce", "strict"):
        assert mode in text


def test_documentation_describes_budget_runtime_and_escape_hatch():
    text = _read("documentation.md")
    assert "Budget control plane" in text
    assert ".less_tokens/state/events.jsonl" in text
    assert ".less_tokens/state/claude-session.json" in text
    assert ".less_tokens/state/codex-session.json" in text
    assert "less_tokens_bypass" in text
    assert "less_tokens: allow" in text
    assert "less_tokens: bypass" in text


def test_changelog_mentions_budget_control_plane():
    text = _read("CHANGELOG.md")
    assert "Budget-native context control plane" in text
    assert "budget_report.py" in text
    assert "budget_doctor.py" in text


def test_codex_coverage_mentions_budget_observer():
    text = _read("codex-hook-coverage.md")
    assert ".codex/hooks/budget-observer.py" in text
    assert ".less_tokens/config/budget.json" in text
    assert ".less_tokens/state/events.jsonl" in text
    assert "observe" in text
    assert "strict" in text


def test_strategy_results_capture_budget_verification():
    text = _read("strategy_21jun26_results.md")
    assert "Full unit and integration suite: 699 passed." in text
    assert "budget_report.py" in text
    assert "budget_doctor.py" in text
    assert "Live savings numbers require actual hook-delivered events" in text

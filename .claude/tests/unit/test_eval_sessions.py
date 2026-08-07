"""Tests for the deterministic session-style evaluation harness."""

from __future__ import annotations

from pathlib import Path
import sys


TOOLS = Path(__file__).resolve().parent.parent.parent / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import eval_sessions  # noqa: E402


def test_eval_sessions_reports_savings():
    result = eval_sessions.run_eval()
    assert result["tasks"]
    assert result["totals"]["baseline_chars"] > result["totals"]["less_tokens_chars"]
    assert result["totals"]["approx_tokens_saved"] > 0


def test_markdown_report_contains_totals():
    report = eval_sessions.markdown_report(eval_sessions.run_eval())
    assert "Total baseline chars" in report
    assert "Reduction:" in report

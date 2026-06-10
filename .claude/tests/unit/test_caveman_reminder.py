"""Unit tests for the caveman-reminder Stop hook."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.conftest import load_hook

HOOK = Path(__file__).resolve().parent.parent.parent / "hooks" / "caveman-reminder.py"


@pytest.fixture(scope="module")
def hook():
    return load_hook(HOOK)


def _transcript(tmp_path, *turns) -> str:
    p = tmp_path / "t.jsonl"
    lines = []
    for role, text in turns:
        lines.append(json.dumps({
            "type": role,
            "message": {"role": role, "content": [{"type": "text", "text": text}]},
        }))
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p)


def test_last_assistant_text_picks_last_assistant(hook, tmp_path):
    t = _transcript(tmp_path, ("user", "hi"),
                    ("assistant", "first"), ("user", "more"),
                    ("assistant", "second"))
    assert hook.last_assistant_text(t) == "second"


def test_terse_is_clean(hook):
    assert hook.analyze("File not found. Check path.") == []


def test_filler_is_flagged(hook):
    problems = hook.analyze("I apologize, but I'd be happy to help.")
    assert any("filler" in p for p in problems)


def test_code_fence_is_exempt(hook):
    # filler inside a code fence must not trip the check
    assert hook.analyze("```\nI apologize for the error\n```") == []


def test_word_budget_flagged(hook):
    long = "word " * (hook.MAX_RESPONSE_WORDS + 50)
    assert any("budget" in p for p in hook.analyze(long))


def test_missing_transcript_is_empty(hook):
    assert hook.last_assistant_text("/nonexistent/path.jsonl") == ""


def test_unclosed_fence_not_counted_as_prose(hook):
    """Filler inside an unclosed code fence must not trigger a violation.

    Bug: _FENCE required a closing ```; unclosed fence left its content
    in the prose word count, causing false filler and word-budget alerts.
    """
    # filler word inside an unclosed fence — should be stripped, not flagged
    text = "Short note.\n```python\nI apologize for the error\n"
    problems = hook.analyze(text)
    assert problems == [], f"unclosed fence leaked into prose: {problems}"


def test_unclosed_fence_words_not_counted(hook, monkeypatch):
    """Words in an unclosed code fence must not count toward the word budget."""
    monkeypatch.setattr(hook, "MAX_RESPONSE_WORDS", 5)
    # 100 words inside an unclosed fence — should not exceed the 5-word budget
    many_words = " ".join(["word"] * 100)
    text = f"Ok.\n```\n{many_words}\n"
    problems = hook.analyze(text)
    assert not any("budget" in p for p in problems), (
        f"unclosed fence words counted against prose budget: {problems}"
    )

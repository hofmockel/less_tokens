"""Regression test: _strip_code must remove unclosed code fences from prose."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))
import claudemd_audit as audit_mod


def test_unclosed_fence_stripped():
    """Unclosed ``` fence: content must not appear in stripped output."""
    body = "Some prose.\n```python\ndef foo(): pass\n# no closing fence"
    result = audit_mod._strip_code(body)
    assert "def foo" not in result, (
        f"Unclosed fence content leaked into prose: {result!r}"
    )
    assert "no closing fence" not in result


def test_balanced_fence_stripped():
    """Balanced fences still removed correctly."""
    body = "Intro.\n```python\ndef bar(): pass\n```\nOutro."
    result = audit_mod._strip_code(body)
    assert "def bar" not in result
    assert "Intro." in result
    assert "Outro." in result


def test_mixed_fences():
    """One balanced fence followed by one unclosed fence: both stripped."""
    body = "A.\n```\ncode1\n```\nB.\n```\ncode2 no end"
    result = audit_mod._strip_code(body)
    assert "code1" not in result
    assert "code2" not in result
    assert "A." in result
    assert "B." in result

"""Regression: truncate_bash omitted_lines<=0 branch must use assembled result.

When head+tail covers all lines (omitted_lines=0), the old code called
truncate_chars(text, ceiling) on the *original* text — which includes any
trailing newline — instead of the assembled head+tail result. This caused
a 1-char drift in the char-based tail window and unconditionally invoked
truncate_chars even when the text fit within ceiling.
"""
from __future__ import annotations

from pathlib import Path
from tests.conftest import load_hook

HOOK = Path(__file__).resolve().parent.parent.parent / "hooks" / "truncate-output.py"


def _hook():
    return load_hook(HOOK)


def test_no_omission_banner_when_head_tail_covers_all(tmp_path):
    """omitted_lines=0 → no '[... N lines omitted ...]' marker in output."""
    hook = _hook()
    text = "\n".join(f"line{i}" for i in range(8))  # 8 lines, head+tail=10 covers all
    result = hook.truncate_bash(text, head=5, tail=5, ceiling=10_000)
    assert "[... " not in result
    assert "line0" in result
    assert "line7" in result


def test_omitted_zero_returns_assembled_result_not_original_text(tmp_path):
    """When omitted_lines=0 and text fits in ceiling, returns assembled
    head+tail (no trailing newline) rather than the original text verbatim."""
    hook = _hook()
    text = "alpha\nbeta\ngamma\n"  # trailing newline in original
    # head=5, tail=5 covers all 3 lines → omitted_lines=0
    result = hook.truncate_bash(text, head=5, tail=5, ceiling=10_000)
    # Assembled result uses "\n".join(...) → no trailing newline
    assert result == "alpha\nbeta\ngamma"


def test_omitted_zero_over_ceiling_still_truncates(tmp_path):
    """When omitted_lines=0 but content exceeds ceiling, char truncation applies."""
    hook = _hook()
    # 2 lines of 10 chars each = 21 chars with newline; ceiling=10
    text = "AAAAAAAAAA\nBBBBBBBBBB\n"
    result = hook.truncate_bash(text, head=5, tail=5, ceiling=10)
    assert "[... " in result

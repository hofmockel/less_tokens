"""Regression test: a panel's total_tokens must come from its total_chars, not
the sum of per-row truncated values.

Post-Phase-3 the report renders measured and upper-bound in separate panels and
never cross-sums them, so this guard stays *within one basis* — both fixtures use
measured strategies (truncation, compaction) and read the measured (first) Total.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "tools"))
import stats as stats_mod


def _make_records(strategy: str, saved_chars: int, count: int = 1) -> list[dict]:
    return [{"strategy": strategy, "saved_chars": saved_chars} for _ in range(count)]


def _measured_total_tokens(records: list[dict]) -> int:
    lines = stats_mod._build_table_lines("Test", records)
    # The measured panel is rendered first, so its Total is the first **Total** row.
    total_line = next(ln for ln in lines if "**Total**" in ln)
    token_matches = re.findall(r"\*\*([0-9,]+)\*\*", total_line)
    return int(token_matches[-1].replace(",", ""))


def test_total_tokens_not_truncated_per_row():
    """10 measured rows saving 1 char each = 10 chars combined; each row's own
    saved_chars is below one token's worth (floors to 0 individually), so a
    per-row-summed total would give 0 — the correct total comes from summing
    chars first, then converting once. Calibration-agnostic: derives the
    expected token count from the real divisor instead of hardcoding one."""
    records = _make_records("truncation", 1, count=5) + _make_records("compaction", 1, count=5)
    total_tokens = _measured_total_tokens(records)
    assert stats_mod._to_tokens(1) == 0, "fixture assumption broke: 1 char must floor to 0 tokens"
    expected = stats_mod._to_tokens(10)
    assert expected > 0, "fixture assumption broke: 10 chars must floor to >0 tokens"
    assert total_tokens == expected, f"Expected {expected} tokens (10 chars, single conversion), got {total_tokens}"


def test_total_tokens_exact_divisible():
    """Sanity: total_tokens for 8 measured chars matches a direct single-shot
    conversion of the combined char count (calibration-agnostic)."""
    records = _make_records("truncation", 4) + _make_records("compaction", 4)
    assert _measured_total_tokens(records) == stats_mod._to_tokens(8)

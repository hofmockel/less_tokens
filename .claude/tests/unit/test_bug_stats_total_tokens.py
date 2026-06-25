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
    """Two measured rows saving 3 chars each = 6 chars = 1 token; per-row sum gives 0."""
    records = _make_records("truncation", 3) + _make_records("compaction", 3)
    total_tokens = _measured_total_tokens(records)
    # 6 chars // 4 = 1 token; per-row sum of (3//4 + 3//4) = 0
    assert total_tokens == 1, f"Expected 1 token (6 chars // 4), got {total_tokens}"


def test_total_tokens_exact_divisible():
    """Sanity: 8 measured chars across 2 rows of 4 chars each = 2 tokens both ways."""
    records = _make_records("truncation", 4) + _make_records("compaction", 4)
    assert _measured_total_tokens(records) == 2

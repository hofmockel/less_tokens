"""Regression test: total_tokens must be computed from total_chars, not sum of per-row truncated values."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / ".claude" / "tools"))
import stats as stats_mod


def _make_records(strategy: str, saved_chars: int, count: int = 1) -> list[dict]:
    return [{"strategy": strategy, "saved_chars": saved_chars} for _ in range(count)]


def test_total_tokens_not_truncated_per_row():
    """3 strategies each saving 3 chars = 9 total chars = 2 tokens; per-row sum gives 0."""
    records = (
        _make_records("search", 3)
        + _make_records("compaction", 3)
        + _make_records("truncation", 3)
    )
    lines = stats_mod._build_table_lines("Test", records)
    total_line = next(ln for ln in lines if "**Total**" in ln)
    # Extract token count from the total row: last **N** group
    import re
    token_matches = re.findall(r"\*\*([0-9,]+)\*\*", total_line)
    total_tokens = int(token_matches[-1].replace(",", ""))
    # 9 chars // 4 = 2 tokens; per-row sum of (3//4 + 3//4 + 3//4) = 0
    assert total_tokens == 2, f"Expected 2 tokens (9 chars // 4), got {total_tokens}"


def test_total_tokens_exact_divisible():
    """Sanity: 8 chars across 2 rows of 4 chars each = 2 tokens both ways."""
    records = _make_records("search", 4) + _make_records("truncation", 4)
    lines = stats_mod._build_table_lines("Test", records)
    total_line = next(ln for ln in lines if "**Total**" in ln)
    import re
    token_matches = re.findall(r"\*\*([0-9,]+)\*\*", total_line)
    total_tokens = int(token_matches[-1].replace(",", ""))
    assert total_tokens == 2

"""Bug 29: stats._load_records was silent on JSON decode errors.

Malformed JSONL records in the savings log were skipped without any indication,
making it hard to diagnose a corrupted log.  The fix emits a WARN to stderr for
each skipped line so users can investigate the corruption.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / ".claude" / "tools"))


def _import_stats():
    import stats

    return importlib.reload(stats)


def test_malformed_record_emits_warn(tmp_path, capsys):
    """_load_records must print a WARN to stderr for each malformed line."""
    stats = _import_stats()
    log = tmp_path / "savings.jsonl"
    log.write_text(
        "not-json-at-all\n"
        '{"strategy": "truncation", "saved_chars": 100, "ts": 9999999999}\n'
    )
    with patch("stats.LOG_FILE", log):
        records = stats._load_records(all_time=True)

    # Valid record is still returned.
    assert len(records) == 1

    # A warning must be emitted for the malformed line.
    err = capsys.readouterr().err
    assert "WARN" in err or "warn" in err.lower(), (
        "No warning emitted for malformed JSON record (Bug 29)"
    )

"""Unit tests for tools/savings_log.py and tools/stats.py."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

# Ensure tools/ is importable before any patch() calls reference module names.
_TOOLS = Path(__file__).parent.parent.parent / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import savings_log  # noqa: E402  (must follow sys.path setup)


# ---------------------------------------------------------------------------
# savings_log
# ---------------------------------------------------------------------------

def test_append_noop_when_disabled(tmp_path):
    log = tmp_path / "savings.jsonl"
    with (
        patch("savings_log.TRACK_SAVINGS", False),
        patch("savings_log._LOG_FILE", log),
    ):
        import savings_log
        savings_log.append({"strategy": "truncation", "saved_chars": 100})
    assert not log.exists()


def test_append_writes_when_enabled(tmp_path):
    log = tmp_path / "savings.jsonl"
    with (
        patch("savings_log.TRACK_SAVINGS", True),
        patch("savings_log.STATE_DIR", tmp_path),
        patch("savings_log._LOG_FILE", log),
    ):
        import savings_log
        savings_log.append({"strategy": "truncation", "saved_chars": 500})

    assert log.exists()
    record = json.loads(log.read_text())
    assert record["strategy"] == "truncation"
    assert record["saved_chars"] == 500
    assert "ts" in record


def test_append_adds_timestamp_if_missing(tmp_path):
    log = tmp_path / "savings.jsonl"
    before = time.time()
    with (
        patch("savings_log.TRACK_SAVINGS", True),
        patch("savings_log.STATE_DIR", tmp_path),
        patch("savings_log._LOG_FILE", log),
    ):
        import savings_log
        savings_log.append({"strategy": "compaction", "saved_chars": 0})
    after = time.time()
    record = json.loads(log.read_text())
    assert before <= record["ts"] <= after


def test_append_respects_existing_timestamp(tmp_path):
    log = tmp_path / "savings.jsonl"
    with (
        patch("savings_log.TRACK_SAVINGS", True),
        patch("savings_log.STATE_DIR", tmp_path),
        patch("savings_log._LOG_FILE", log),
    ):
        import savings_log
        savings_log.append({"strategy": "truncation", "saved_chars": 0, "ts": 12345.0})
    record = json.loads(log.read_text())
    assert record["ts"] == 12345.0


# ---------------------------------------------------------------------------
# stats._summarize
# ---------------------------------------------------------------------------

def _import_stats():
    import importlib, sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tools"))
    import stats
    return importlib.reload(stats)


def test_summarize_empty():
    stats = _import_stats()
    result = stats._summarize([])
    for key in ("truncation", "search-blocked", "search", "compaction"):
        assert result[key]["events"] == 0
        assert result[key]["saved_chars"] == 0


def test_summarize_aggregates():
    stats = _import_stats()
    records = [
        {"strategy": "truncation", "saved_chars": 1000},
        {"strategy": "truncation", "saved_chars": 2000},
        {"strategy": "search", "saved_chars": 500},
        {"strategy": "unknown", "saved_chars": 999},  # should be ignored
    ]
    result = stats._summarize(records)
    assert result["truncation"]["events"] == 2
    assert result["truncation"]["saved_chars"] == 3000
    assert result["search"]["events"] == 1
    assert result["search"]["saved_chars"] == 500
    assert result["compaction"]["events"] == 0


# ---------------------------------------------------------------------------
# stats._build_table_lines
# ---------------------------------------------------------------------------

def test_build_table_lines_returns_list_of_strings():
    stats = _import_stats()
    lines = stats._build_table_lines("Test heading", [])
    assert isinstance(lines, list)
    assert all(isinstance(l, str) for l in lines)
    assert any("Test heading" in l for l in lines)
    assert any("Total" in l for l in lines)


def test_build_table_lines_shows_savings():
    stats = _import_stats()
    records = [{"strategy": "truncation", "saved_chars": 4000}]
    lines = stats._build_table_lines("Session", records)
    joined = "\n".join(lines)
    assert "4,000" in joined
    assert "1,000" in joined  # 4000 // 4 tokens


# ---------------------------------------------------------------------------
# stats._load_records
# ---------------------------------------------------------------------------

def test_load_records_session_filter(tmp_path):
    stats = _import_stats()
    log = tmp_path / "savings.jsonl"
    now = time.time()
    old = {"strategy": "truncation", "saved_chars": 100, "ts": now - 86400}  # 24h ago
    recent = {"strategy": "search", "saved_chars": 200, "ts": now - 60}       # 1m ago
    log.write_text(json.dumps(old) + "\n" + json.dumps(recent) + "\n")

    with patch("stats.LOG_FILE", log):
        session = stats._load_records(all_time=False)
        all_time = stats._load_records(all_time=True)

    assert len(session) == 1
    assert session[0]["strategy"] == "search"
    assert len(all_time) == 2


def test_load_records_missing_file(tmp_path):
    stats = _import_stats()
    with patch("stats.LOG_FILE", tmp_path / "nonexistent.jsonl"):
        result = stats._load_records()
    assert result == []


def test_load_records_skips_malformed_lines(tmp_path):
    stats = _import_stats()
    log = tmp_path / "savings.jsonl"
    log.write_text('not json\n{"strategy": "compaction", "saved_chars": 0, "ts": 1}\n')
    with patch("stats.LOG_FILE", log):
        result = stats._load_records(all_time=True)
    assert len(result) == 1


# ---------------------------------------------------------------------------
# stats._write_report
# ---------------------------------------------------------------------------

def test_write_report_creates_file(tmp_path):
    stats = _import_stats()
    report = tmp_path / "savings-report.md"
    records = [{"strategy": "truncation", "saved_chars": 8000, "ts": time.time()}]
    with patch("stats.REPORT_FILE", report):
        path = stats._write_report(records, records)
    assert path == report
    content = report.read_text()
    assert "# Token Savings Report" in content
    assert "Generated:" in content
    assert "8,000" in content
    # methodology prose explains how each number is derived
    assert "How these numbers are measured" in content
    assert "counterfactual upper bound" in content


# ---------------------------------------------------------------------------
# stats._set_tracking
# ---------------------------------------------------------------------------

def test_set_tracking_enables(tmp_path):
    stats = _import_stats()
    cfg = tmp_path / "search_config.py"
    cfg.write_text("TRACK_SAVINGS = False   # comment\n")
    with patch("stats.CONFIG_FILE", cfg):
        stats._set_tracking(True)
    assert "TRACK_SAVINGS = True" in cfg.read_text()


def test_set_tracking_disables(tmp_path):
    stats = _import_stats()
    cfg = tmp_path / "search_config.py"
    cfg.write_text("TRACK_SAVINGS = True\n")
    with patch("stats.CONFIG_FILE", cfg):
        stats._set_tracking(False)
    assert "TRACK_SAVINGS = False" in cfg.read_text()


def test_set_tracking_missing_key(tmp_path, capsys):
    stats = _import_stats()
    cfg = tmp_path / "search_config.py"
    cfg.write_text("# no tracking variable here\n")
    with patch("stats.CONFIG_FILE", cfg):
        stats._set_tracking(True)
    err = capsys.readouterr().err
    assert "Could not find" in err

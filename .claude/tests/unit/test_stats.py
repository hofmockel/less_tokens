"""Unit tests for tools/savings_log.py and tools/stats.py.

These guard the measurement *pipe*, never a savings magnitude: arithmetic
identities, basis classification, session-id fallback order, the always-on
write path, and the legacy-tolerant loader. No fixture asserts that a made-up
input "saves" a made-up amount.
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

# Ensure tools/ is importable before any patch() calls reference module names.
_TOOLS = Path(__file__).parent.parent.parent / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import savings_log  # noqa: E402  (must follow sys.path setup)

_ENABLED = {"LESS_TOKENS_NO_STATS": "0"}


# ---------------------------------------------------------------------------
# savings_log.append — always on, local-only, env opt-out
# ---------------------------------------------------------------------------

def test_append_noop_when_opted_out(tmp_path):
    log = tmp_path / "savings.jsonl"
    with (
        patch.dict(os.environ, {"LESS_TOKENS_NO_STATS": "1"}),
        patch("savings_log._LOG_FILE", log),
    ):
        savings_log.append({"strategy": "truncation", "elided_chars": 100})
    assert not log.exists()


def test_append_writes_when_on_by_default(tmp_path):
    log = tmp_path / "savings.jsonl"
    with (
        patch.dict(os.environ, _ENABLED),
        patch("savings_log.STATE_DIR", tmp_path),
        patch("savings_log._LOG_FILE", log),
    ):
        savings_log.append({"strategy": "truncation", "elided_chars": 500})

    assert log.exists()
    record = json.loads(log.read_text())
    assert record["strategy"] == "truncation"
    assert record["elided_chars"] == 500
    assert "ts" in record


def test_append_adds_timestamp_if_missing(tmp_path):
    log = tmp_path / "savings.jsonl"
    before = time.time()
    with (
        patch.dict(os.environ, _ENABLED),
        patch("savings_log.STATE_DIR", tmp_path),
        patch("savings_log._LOG_FILE", log),
    ):
        savings_log.append({"strategy": "compaction", "elided_chars": 0})
    after = time.time()
    record = json.loads(log.read_text())
    assert before <= record["ts"] <= after


def test_append_respects_existing_timestamp(tmp_path):
    log = tmp_path / "savings.jsonl"
    with (
        patch.dict(os.environ, _ENABLED),
        patch("savings_log.STATE_DIR", tmp_path),
        patch("savings_log._LOG_FILE", log),
    ):
        savings_log.append({"strategy": "truncation", "elided_chars": 0, "ts": 12345.0})
    record = json.loads(log.read_text())
    assert record["ts"] == 12345.0


# ---------------------------------------------------------------------------
# savings_log.resolve_session — fallback order
# ---------------------------------------------------------------------------

def test_resolve_session_prefers_payload_field():
    with patch.dict(os.environ, {"LESS_TOKENS_SESSION_ID": "envval"}):
        sid, src = savings_log.resolve_session(
            {"session_id": "abc", "transcript_path": "/t/x.jsonl"}
        )
    assert (sid, src) == ("abc", "payload")


def test_resolve_session_hashes_transcript_path():
    sid, src = savings_log.resolve_session({"transcript_path": "/home/u/x.jsonl"})
    assert src == "transcript_path"
    assert len(sid) == 12 and sid.isalnum()
    # stable: same path → same id
    assert savings_log.resolve_session({"transcript_path": "/home/u/x.jsonl"})[0] == sid


def test_resolve_session_falls_back_to_env():
    with patch.dict(os.environ, {"LESS_TOKENS_SESSION_ID": "envval"}):
        sid, src = savings_log.resolve_session({})
    assert (sid, src) == ("envval", "env")


def test_resolve_session_last_resort_local():
    env = dict(os.environ)
    env.pop("LESS_TOKENS_SESSION_ID", None)
    with patch.dict(os.environ, env, clear=True):
        sid, src = savings_log.resolve_session(None)
    assert (sid, src) == ("local-session", "local")


# ---------------------------------------------------------------------------
# stats._normalize_record — basis classification + legacy mapping
# ---------------------------------------------------------------------------

def _import_stats():
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))
    import stats
    return importlib.reload(stats)


def test_normalize_legacy_truncation_is_measured():
    stats = _import_stats()
    r = stats._normalize_record({"strategy": "truncation", "saved_chars": 100})
    assert r["basis"] == "measured"
    assert r["elided_chars"] == 100
    assert r["content_kind"] == "legacy"
    assert r["saved_chars"] == 100  # alias preserved for summing


def test_normalize_legacy_search_is_upper_bound():
    stats = _import_stats()
    r = stats._normalize_record({"strategy": "search", "saved_chars": 50})
    assert r["basis"] == "upper_bound"
    assert r["content_kind"] == "legacy"


def test_normalize_folds_glob_cap_into_truncation():
    stats = _import_stats()
    r = stats._normalize_record({"strategy": "glob-cap", "saved_chars": 30})
    assert r["strategy"] == "truncation"
    assert r["basis"] == "measured"


def test_normalize_preserves_new_schema_record():
    stats = _import_stats()
    rec = {
        "strategy": "truncation", "basis": "measured",
        "kept_chars": 5, "elided_chars": 20, "content_kind": "tool_output",
    }
    r = stats._normalize_record(rec)
    assert r["basis"] == "measured"
    assert r["elided_chars"] == 20
    assert r["saved_chars"] == 20  # alias of elided


def test_elided_is_original_minus_kept_identity():
    # The arithmetic identity each emitter relies on — deterministic, no fixtures.
    original = "x" * 4000
    kept = "x" * 137
    elided = max(0, len(original) - len(kept))
    rec = {"strategy": "truncation", "basis": "measured",
           "kept_chars": len(kept), "elided_chars": elided}
    assert rec["elided_chars"] == len(original) - len(kept)


# ---------------------------------------------------------------------------
# stats._summarize
# ---------------------------------------------------------------------------

def test_summarize_empty():
    stats = _import_stats()
    result = stats._summarize([])
    for key in ("truncation", "search-blocked", "search", "compaction"):
        assert result[key]["events"] == 0
        assert result[key]["saved_chars"] == 0


def test_summarize_aggregates():
    stats = _import_stats()
    records = [
        {"strategy": "truncation", "elided_chars": 1000},
        {"strategy": "truncation", "elided_chars": 2000},
        {"strategy": "search", "elided_chars": 500},
        {"strategy": "unknown", "elided_chars": 999},  # should be ignored
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
    records = [{"strategy": "truncation", "elided_chars": 4000}]
    lines = stats._build_table_lines("Session", records)
    joined = "\n".join(lines)
    assert "4,000" in joined
    assert "1,000" in joined  # 4000 // 4 tokens


# ---------------------------------------------------------------------------
# stats._load_records — legacy-tolerant loader
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
    # loader normalizes legacy records on the way out
    assert session[0]["basis"] == "upper_bound"
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
    records = [{"strategy": "truncation", "elided_chars": 8000, "ts": time.time()}]
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
    # always-on / local-only framing, not the old opt-in flag
    assert "LESS_TOKENS_NO_STATS" in content


# ---------------------------------------------------------------------------
# Phase 3 — session_id grouping (real session, wall-clock only as legacy)
# ---------------------------------------------------------------------------

def test_load_records_groups_by_current_session(tmp_path):
    stats = _import_stats()
    log = tmp_path / "savings.jsonl"
    now = time.time()
    rows = [
        {"strategy": "truncation", "basis": "measured", "elided_chars": 100,
         "session_id": "old-sess", "session_source": "payload", "ts": now - 7200},
        {"strategy": "truncation", "basis": "measured", "elided_chars": 200,
         "session_id": "cur-sess", "session_source": "payload", "ts": now - 60},
        {"strategy": "search", "basis": "upper_bound", "elided_chars": 300,
         "session_id": "cur-sess", "session_source": "payload", "ts": now - 30},
    ]
    log.write_text("".join(json.dumps(r) + "\n" for r in rows))
    with patch("stats.LOG_FILE", log):
        session = stats._load_records(all_time=False)
        all_time = stats._load_records(all_time=True)
    # current session = the most recent real session, not an 8h wall-clock window
    assert {r["session_id"] for r in session} == {"cur-sess"}
    assert len(session) == 2
    assert len(all_time) == 3


def test_load_records_explicit_session_id(tmp_path):
    stats = _import_stats()
    log = tmp_path / "savings.jsonl"
    now = time.time()
    rows = [
        {"strategy": "truncation", "basis": "measured", "elided_chars": 1,
         "session_id": "a", "session_source": "payload", "ts": now},
        {"strategy": "truncation", "basis": "measured", "elided_chars": 1,
         "session_id": "b", "session_source": "payload", "ts": now},
    ]
    log.write_text("".join(json.dumps(r) + "\n" for r in rows))
    with patch("stats.LOG_FILE", log):
        only_a = stats._load_records(session_id="a")
    assert {r["session_id"] for r in only_a} == {"a"}


def test_load_records_legacy_falls_back_to_wall_clock(tmp_path):
    # No real session_id anywhere → the wall-clock window is the legacy view.
    stats = _import_stats()
    log = tmp_path / "savings.jsonl"
    now = time.time()
    old = {"strategy": "truncation", "saved_chars": 100, "ts": now - 86400}
    recent = {"strategy": "search", "saved_chars": 200, "ts": now - 60}
    log.write_text(json.dumps(old) + "\n" + json.dumps(recent) + "\n")
    with patch("stats.LOG_FILE", log):
        session = stats._load_records(all_time=False)
    assert len(session) == 1
    assert session[0]["strategy"] == "search"


# ---------------------------------------------------------------------------
# Phase 3 — measured vs upper-bound never cross-summed
# ---------------------------------------------------------------------------

def test_report_separates_measured_and_upper_bound(tmp_path):
    stats = _import_stats()
    records = [
        {"strategy": "truncation", "basis": "measured", "elided_chars": 1000},
        {"strategy": "search", "basis": "upper_bound", "elided_chars": 9000},
    ]
    lines = stats._build_table_lines("Block", records)
    joined = "\n".join(lines)
    # two distinct panels
    assert "Measured" in joined
    assert "Upper bound" in joined
    # measured total is 1,000 — the 9,000 upper-bound is NEVER folded in
    assert "**1,000**" in joined
    assert "10,000" not in joined  # 1000 + 9000 would be a cross-sum
    # upper-bound magnitudes are flagged optimistic with the ≤ prefix
    assert "≤9,000" in joined


def test_panel_lines_sums_only_its_strategies(tmp_path):
    stats = _import_stats()
    records = [
        {"strategy": "truncation", "basis": "measured", "elided_chars": 400},
        {"strategy": "compaction", "basis": "measured", "elided_chars": 600},
        {"strategy": "search", "basis": "upper_bound", "elided_chars": 5000},
    ]
    measured = "\n".join(
        stats._panel_lines("m", records, stats._MEASURED_STRATEGIES)
    )
    upper = "\n".join(
        stats._panel_lines("u", records, stats._UPPER_BOUND_STRATEGIES, prefix="≤")
    )
    assert "**1,000**" in measured  # 400 + 600, search excluded
    assert "5,000" not in measured
    assert "≤5,000" in upper
    assert "1,000" not in upper


def test_token_footer_is_uncalibrated():
    stats = _import_stats()
    assert "uncalibrated" in stats.TOKEN_FOOTER
    assert "chars÷4" in stats.TOKEN_FOOTER


# ---------------------------------------------------------------------------
# Phase 4 — self-contained HTML page
# ---------------------------------------------------------------------------

def test_write_html_creates_file(tmp_path):
    stats = _import_stats()
    html = tmp_path / "savings.html"
    records = [{"strategy": "truncation", "elided_chars": 8000, "ts": time.time()}]
    with patch("stats.HTML_FILE", html):
        path = stats._write_html_report(records, records)
    assert path == html
    content = html.read_text()
    assert content.startswith("<!DOCTYPE html>")
    assert "<title>Token Savings Report</title>" in content
    assert "8,000" in content
    assert "LESS_TOKENS_NO_STATS" in content


def test_html_is_self_contained(tmp_path):
    """No external resources — opens straight from file:// and never phones home."""
    stats = _import_stats()
    html = stats._render_html([], [])
    # style is inlined, not linked; no remote fetches of any kind
    assert "<style>" in html
    assert "http://" not in html and "https://" not in html
    assert "<link" not in html and "src=" not in html
    assert "<script" not in html


def test_html_separates_measured_and_upper_bound(tmp_path):
    stats = _import_stats()
    records = [
        {"strategy": "truncation", "basis": "measured", "elided_chars": 1000},
        {"strategy": "search", "basis": "upper_bound", "elided_chars": 9000},
    ]
    html = stats._html_block("Block", records)
    assert "Measured" in html
    assert "Upper bound" in html
    # the 9,000 upper bound is never folded into the measured total
    assert "10,000" not in html
    assert "≤9,000" in html


def test_html_escapes_session_id(tmp_path):
    """A session_id is rendered as text, never as live markup."""
    stats = _import_stats()
    records = [{
        "strategy": "truncation", "basis": "measured", "elided_chars": 10,
        "session_id": "<img src=x>", "session_source": "payload", "ts": time.time(),
    }]
    html = stats._render_html(records, records)
    assert "<img src=x>" not in html
    assert "&lt;img" in html


# --- Phase 5 surfacing helpers ---------------------------------------------

def test_fmt_tokens_scales():
    stats = _import_stats()
    assert stats._fmt_tokens(0) == "0"
    assert stats._fmt_tokens(999) == "999"
    assert stats._fmt_tokens(1500) == "1.5k"
    assert stats._fmt_tokens(122_000) == "122k"


def test_measured_saved_chars_excludes_upper_bound():
    stats = _import_stats()
    records = [
        {"strategy": "truncation", "basis": "measured", "elided_chars": 400},
        {"strategy": "compaction", "basis": "measured", "elided_chars": 400},
        {"strategy": "search", "basis": "upper_bound", "elided_chars": 9999},
    ]
    # only the two measured rows count toward the headline number
    assert stats._measured_saved_chars(records) == 800


def test_measured_oneliner_format_and_honesty():
    stats = _import_stats()
    records = [
        {"strategy": "truncation", "basis": "measured", "elided_chars": 8000},
        {"strategy": "search", "basis": "upper_bound", "elided_chars": 1_000_000},
    ]
    line = stats._measured_oneliner(records)
    assert line == "↓ ~2.0k tok saved (measured) · session"
    assert "measured" in line
    # upper-bound magnitude must never leak into the glanceable line
    assert "250" not in line and "1000" not in line


def test_savings_link_is_file_uri():
    stats = _import_stats()
    link = stats._savings_link()
    assert link.startswith("file://")
    assert link.endswith("savings.html")

"""Unit tests for measure_compaction (Phase 2 of the stats rewrite).

Guards the measurement pipe only: peak tracking, compaction detection, the
both-sides arithmetic identity, and the "fire only on a real shrink" rule. No
test asserts a savings magnitude from a fabricated transcript.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from agents.common.hooks.compact_trigger import measure_compaction

THRESHOLD = 500_000


def _payload(transcript):
    return SimpleNamespace(transcript_path=transcript)


def _write(path, size):
    path.write_bytes(b"x" * size)
    return path


def _run(tmp_path, transcript, *, peak_state=None, threshold=THRESHOLD):
    peak_file = tmp_path / "compact-peak"
    if peak_state is not None:
        peak_file.write_text(json.dumps(peak_state))
    events = []
    measure_compaction(
        _payload(transcript),
        state_dir=tmp_path,
        max_session_chars=threshold,
        log=events.append,
        session=("sess-1", "payload"),
        peak_file=peak_file,
    )
    saved = json.loads(peak_file.read_text()) if peak_file.exists() else {}
    return events, saved


def test_new_transcript_just_starts_tracking(tmp_path):
    t = _write(tmp_path / "t.jsonl", 120_000)
    events, peak = _run(tmp_path, t)
    assert events == []
    assert peak == {"transcript": str(t), "peak": 120_000}


def test_growth_updates_peak_without_emitting(tmp_path):
    t = _write(tmp_path / "t.jsonl", 300_000)
    events, peak = _run(tmp_path, t, peak_state={"transcript": str(t), "peak": 200_000})
    assert events == []
    assert peak["peak"] == 300_000


def test_compaction_emits_measured_event(tmp_path):
    t = _write(tmp_path / "t.jsonl", 40_000)  # post-compaction summary
    events, peak = _run(tmp_path, t, peak_state={"transcript": str(t), "peak": 700_000})
    assert len(events) == 1
    e = events[0]
    assert e["strategy"] == "compaction"
    assert e["basis"] == "measured"
    assert e["kept_chars"] == 40_000
    assert e["elided_chars"] == 700_000 - 40_000
    assert e["content_kind"] == "transcript"
    assert e["session_id"] == "sess-1"
    # peak resets to the post-compaction size
    assert peak["peak"] == 40_000


def test_elided_is_peak_minus_kept_identity(tmp_path):
    t = _write(tmp_path / "t.jsonl", 50_000)
    events, _ = _run(tmp_path, t, peak_state={"transcript": str(t), "peak": 900_000})
    e = events[0]
    assert e["elided_chars"] == 900_000 - e["kept_chars"]


def test_drop_below_threshold_peak_does_not_emit(tmp_path):
    # peak never exceeded the compaction threshold → not a real compaction
    t = _write(tmp_path / "t.jsonl", 10_000)
    events, _ = _run(tmp_path, t, peak_state={"transcript": str(t), "peak": 200_000})
    assert events == []


def test_small_shrink_does_not_emit(tmp_path):
    # cur >= peak/2 → within-session noise, not a compaction
    t = _write(tmp_path / "t.jsonl", 400_000)
    events, _ = _run(tmp_path, t, peak_state={"transcript": str(t), "peak": 700_000})
    assert events == []


def test_new_session_path_resets_without_emitting(tmp_path):
    # different transcript path, even though small vs the old peak
    t = _write(tmp_path / "new.jsonl", 30_000)
    events, peak = _run(
        tmp_path, t, peak_state={"transcript": str(tmp_path / "old.jsonl"), "peak": 800_000}
    )
    assert events == []
    assert peak == {"transcript": str(t), "peak": 30_000}


def test_missing_transcript_path_is_noop(tmp_path):
    events, _ = _run(tmp_path, None)
    assert events == []


# ---------------------------------------------------------------------------
# Near-miss instrumentation (Strategy 4 Phase 0) — additive only, no behavior
# change. Compaction fired once in this repo's entire history; this samples
# every invocation's transcript size so a real distribution exists before any
# threshold decision is made.
# ---------------------------------------------------------------------------

from agents.common.hooks.compact_trigger import check_compact_trigger, record_session_size_sample  # noqa: E402


def test_record_session_size_sample_appends_jsonl(tmp_path):
    record_session_size_sample(tmp_path, size=12345, threshold=THRESHOLD)
    log = (tmp_path / "near_misses.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(log) == 1
    entry = json.loads(log[0])
    assert entry == {"kind": "session_size", "size": 12345, "threshold": THRESHOLD, "ts": entry["ts"]}


def test_check_compact_trigger_samples_size_even_when_under_threshold(tmp_path):
    transcript = _write(tmp_path / "t.jsonl", 1000)
    code, _, _ = check_compact_trigger(
        _payload(str(transcript)), state_dir=tmp_path,
        max_session_chars=THRESHOLD, message="compact now",
    )
    assert code == 0
    log = (tmp_path / "near_misses.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(log) == 1
    entry = json.loads(log[0])
    assert entry["size"] == 1000 and entry["threshold"] == THRESHOLD


def test_check_compact_trigger_samples_size_when_over_threshold_too(tmp_path):
    transcript = _write(tmp_path / "t.jsonl", THRESHOLD + 1000)
    code, _, _ = check_compact_trigger(
        _payload(str(transcript)), state_dir=tmp_path,
        max_session_chars=THRESHOLD, message="compact now",
    )
    assert code == 2
    log = (tmp_path / "near_misses.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(log) == 1
    assert json.loads(log[0])["size"] == THRESHOLD + 1000

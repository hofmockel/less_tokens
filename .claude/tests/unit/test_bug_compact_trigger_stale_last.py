"""Bug: compact-trigger stale last-size silences trigger in new sessions.

`last-size` persists across sessions; after a large session the new-session
transcript starts small but `size < last + hysteresis` holds true, preventing
the nudge from ever firing. The fix requires `last <= size` before suppressing,
so a new (smaller) session always fires when it exceeds the threshold.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


from tests.conftest import REPO_ROOT, load_hook


def _make_payload(transcript_path: Path) -> bytes:
    return json.dumps({"transcript_path": str(transcript_path)}).encode()


def test_stale_last_does_not_suppress_new_session(tmp_path, monkeypatch):
    """New session transcript above threshold must fire even when last > size."""
    mod = load_hook(REPO_ROOT / ".claude" / "hooks" / "compact-trigger.py")

    threshold = 500_000

    # Simulate previous large session: last recorded size was 700_000
    state_file = tmp_path / "compact-trigger-last"
    state_file.write_text("700000")
    monkeypatch.setattr(mod, "STATE_FILE", state_file)
    monkeypatch.setattr(mod, "MAX_SESSION_CHARS", threshold)
    # active_state_dir() also feeds near_misses.jsonl (session_size telemetry);
    # left unpatched this test's fixture sizes leak into the repo's real
    # production log instead of a synthetic tmp_path one.
    monkeypatch.setattr(mod, "active_state_dir", lambda: tmp_path)

    # New session transcript: 600_000 chars — above threshold, but below last+hysteresis
    # (600_000 < 700_000 + 125_000 = 825_000), so the stale guard would suppress it.
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_bytes(b"x" * 600_000)

    payload = json.dumps({"transcript_path": str(transcript)})
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(payload))

    result = mod.main()
    assert result == 2, (
        "compact-trigger must fire when transcript exceeds threshold, "
        "even if new-session size is smaller than the stale last-size"
    )


def test_hysteresis_still_suppresses_within_same_session(tmp_path, monkeypatch):
    """Hysteresis should still prevent rapid re-firing within a growing session."""
    mod = load_hook(REPO_ROOT / ".claude" / "hooks" / "compact-trigger.py")

    threshold = 500_000

    # last triggered at 600_000; now at 650_000 — growth < hysteresis
    state_file = tmp_path / "compact-trigger-last"
    state_file.write_text("600000")
    monkeypatch.setattr(mod, "STATE_FILE", state_file)
    monkeypatch.setattr(mod, "MAX_SESSION_CHARS", threshold)
    monkeypatch.setattr(mod, "active_state_dir", lambda: tmp_path)

    transcript = tmp_path / "transcript.jsonl"
    transcript.write_bytes(b"x" * 650_000)

    payload = json.dumps({"transcript_path": str(transcript)})
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(payload))

    result = mod.main()
    assert result == 0, (
        "compact-trigger must NOT re-fire when growth since last trigger < hysteresis"
    )

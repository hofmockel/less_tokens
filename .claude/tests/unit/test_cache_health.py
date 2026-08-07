"""Unit tests for agents.common.cache_health (PC1).

Guards: version-window gating, transcript discovery (Claude deterministic
path + fallback, Codex cwd-grep + subagent-skip), native usage parsing for
both platforms, and the abrupt-miss-window heuristic. No test asserts a
savings magnitude — this module reports native counters, not estimates.
"""

from __future__ import annotations

import json
import sys

from agents.common.cache_health import (
    claude_cache_read_share,
    claude_transcript_path,
    claude_version_supported,
    codex_cache_read_share,
    codex_version_supports_reads,
    codex_version_supports_writes,
    compute_cache_health,
    detect_abrupt_miss_windows,
    find_claude_transcript_fallback,
    find_codex_transcript,
    parse_claude_cache_usage,
    parse_codex_cache_usage,
    parse_version,
    slugify_cwd,
)


def test_parse_version():
    assert parse_version("2.1.200 (Claude Code)") == (2, 1, 200)
    assert parse_version("codex-cli 0.144.6") == (0, 144, 6)
    assert parse_version("nonsense") is None


def test_claude_version_window():
    assert claude_version_supported((2, 1, 181)) is True
    assert claude_version_supported((2, 1, 215)) is True
    assert claude_version_supported((2, 1, 216)) is False
    assert claude_version_supported((2, 1, 180)) is False
    assert claude_version_supported(None) is False


def test_codex_version_windows():
    assert codex_version_supports_reads((0, 142, 3)) is True
    assert codex_version_supports_reads((0, 142, 2)) is False
    assert codex_version_supports_writes((0, 144, 6)) is False
    assert codex_version_supports_writes((0, 145, 0)) is True


def test_slugify_cwd_matches_observed_convention():
    from pathlib import Path

    assert slugify_cwd(Path("/Users/michael/Documents/GitHub/ever_better")) == (
        "-Users-michael-Documents-GitHub-ever-better"
    )


def test_claude_transcript_path_is_deterministic(tmp_path):
    p = claude_transcript_path(
        tmp_path / "repo", "sess-123", claude_home=tmp_path / "home"
    )
    assert (
        p
        == tmp_path
        / "home"
        / "projects"
        / slugify_cwd(tmp_path / "repo")
        / "sess-123.jsonl"
    )


def test_find_claude_transcript_fallback_picks_newest(tmp_path):
    import os
    import time

    cwd = tmp_path / "repo"
    home = tmp_path / "home"
    proj = home / "projects" / slugify_cwd(cwd)
    proj.mkdir(parents=True)
    old = proj / "old.jsonl"
    new = proj / "new.jsonl"
    old.write_text("{}\n")
    time.sleep(0.01)
    new.write_text("{}\n")
    os.utime(old, (time.time() - 100, time.time() - 100))
    assert find_claude_transcript_fallback(cwd, claude_home=home) == new


def test_find_claude_transcript_fallback_missing_dir(tmp_path):
    assert (
        find_claude_transcript_fallback(
            tmp_path / "nope", claude_home=tmp_path / "home"
        )
        is None
    )


def _write_jsonl(path, records):
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def test_find_codex_transcript_matches_cwd_and_skips_subagents(tmp_path):
    home = tmp_path / "codex_home"
    day = home / "sessions" / "2026" / "07" / "20"
    day.mkdir(parents=True)

    subagent = day / "rollout-2026-07-20T10-00-00-aaa.jsonl"
    _write_jsonl(
        subagent,
        [
            {
                "type": "session_meta",
                "payload": {"cwd": "/repo", "thread_source": "subagent"},
            }
        ],
    )

    other_cwd = day / "rollout-2026-07-20T11-00-00-bbb.jsonl"
    _write_jsonl(
        other_cwd,
        [
            {
                "type": "session_meta",
                "payload": {"cwd": "/other-repo"},
            }
        ],
    )

    match = day / "rollout-2026-07-20T12-00-00-ccc.jsonl"
    _write_jsonl(
        match,
        [
            {
                "type": "session_meta",
                "payload": {"cwd": "/repo"},
            }
        ],
    )

    from pathlib import Path

    found = find_codex_transcript(Path("/repo"), codex_home=home)
    assert found == match


def test_find_codex_transcript_no_match(tmp_path):
    from pathlib import Path

    home = tmp_path / "codex_home"
    (home / "sessions").mkdir(parents=True)
    assert find_codex_transcript(Path("/nowhere"), codex_home=home) is None


def test_parse_claude_cache_usage(tmp_path):
    transcript = tmp_path / "t.jsonl"
    _write_jsonl(
        transcript,
        [
            {"type": "queue-operation"},  # no usage — skipped
            {
                "timestamp": "2026-07-20T00:00:00Z",
                "message": {
                    "usage": {
                        "input_tokens": 2,
                        "cache_creation_input_tokens": 100,
                        "cache_read_input_tokens": 900,
                    }
                },
            },
            {"message": {"usage": {"input_tokens": 5}}},  # missing fields — skipped
        ],
    )
    turns = parse_claude_cache_usage(transcript)
    assert len(turns) == 1
    assert turns[0]["cache_read_input_tokens"] == 900


def test_parse_claude_cache_usage_missing_file(tmp_path):
    assert parse_claude_cache_usage(tmp_path / "missing.jsonl") == []


def test_parse_codex_cache_usage(tmp_path):
    transcript = tmp_path / "r.jsonl"
    _write_jsonl(
        transcript,
        [
            {"payload": {"type": "session_meta"}},
            {
                "timestamp": "2026-07-20T00:00:00Z",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "total_token_usage": {
                            "input_tokens": 1000,
                            "cached_input_tokens": 800,
                        }
                    },
                },
            },
        ],
    )
    turns = parse_codex_cache_usage(transcript)
    assert len(turns) == 1
    assert turns[0]["cached_input_tokens"] == 800
    assert turns[0]["cache_write_input_tokens"] is None


def test_claude_cache_read_share():
    assert (
        claude_cache_read_share(
            {
                "input_tokens": 0,
                "cache_creation_input_tokens": 100,
                "cache_read_input_tokens": 900,
            }
        )
        == 0.9
    )
    assert (
        claude_cache_read_share(
            {
                "input_tokens": 0,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            }
        )
        is None
    )


def test_codex_cache_read_share():
    assert (
        codex_cache_read_share({"input_tokens": 1000, "cached_input_tokens": 800})
        == 0.8
    )
    assert codex_cache_read_share({"input_tokens": 0, "cached_input_tokens": 0}) is None


def test_detect_abrupt_miss_windows_flags_sharp_drop():
    shares = [0.9, 0.9, 0.9, 0.9, 0.9, 0.1]
    flagged = detect_abrupt_miss_windows(shares, window=5)
    assert len(flagged) == 1
    assert flagged[0]["index"] == 5
    assert flagged[0]["baseline"] == 0.9


def test_detect_abrupt_miss_windows_ignores_cold_start():
    # Low share from turn 0 is the normal ramp-up, not a "drop" — no baseline yet.
    shares = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    assert detect_abrupt_miss_windows(shares, window=5) == []


def test_detect_abrupt_miss_windows_ignores_low_baseline():
    # Baseline never got warm (< 0.70), so a drop off it isn't "abrupt miss".
    shares = [0.5, 0.5, 0.5, 0.5, 0.5, 0.1]
    assert detect_abrupt_miss_windows(shares, window=5) == []


def test_compute_cache_health_unavailable_outside_version_window():
    from pathlib import Path

    result = compute_cache_health(
        agent="claude",
        cwd=Path("/repo"),
        session_id="s1",
        session_source="payload",
        cli_version="1.0.0",
    )
    assert result == {
        "available": False,
        "agent": "claude",
        "reason": ("cli_version '1.0.0' outside verified window 2.1.181-2.1.215"),
    }


def test_compute_cache_health_claude_end_to_end(tmp_path, monkeypatch):
    from pathlib import Path

    cwd = Path("/repo")
    home = tmp_path / "home"
    transcript_dir = home / "projects" / slugify_cwd(cwd)
    transcript_dir.mkdir(parents=True)
    transcript = transcript_dir / "sess-1.jsonl"
    _write_jsonl(
        transcript,
        [
            {
                "message": {
                    "usage": {
                        "input_tokens": 0,
                        "cache_creation_input_tokens": 100,
                        "cache_read_input_tokens": 900,
                    }
                },
            }
        ],
    )
    monkeypatch.setattr(
        sys.modules[compute_cache_health.__module__],
        "claude_transcript_path",
        lambda c, sid, claude_home=None: transcript,
    )

    result = compute_cache_health(
        agent="claude",
        cwd=cwd,
        session_id="sess-1",
        session_source="payload",
        cli_version="2.1.200",
    )
    assert result["available"] is True
    assert result["cache_read_share_avg"] == 0.9
    assert result["abrupt_miss_windows"] == []


def test_compute_cache_health_codex_unsupported_agent():
    from pathlib import Path

    result = compute_cache_health(
        agent="mystery",
        cwd=Path("/repo"),
        session_id=None,
        session_source=None,
        cli_version=None,
    )
    assert result["available"] is False

"""Unit tests for the context-cache PreToolUse hook (G2)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.conftest import load_hook

HOOK = Path(__file__).resolve().parent.parent.parent / "hooks" / "context-cache.py"


@pytest.fixture(scope="module")
def hook():
    return load_hook(HOOK)


# ---------------------------------------------------------------------------
# Read cache — allow on first call
# ---------------------------------------------------------------------------

def test_read_first_call_allowed(hook, tmp_path):
    p = tmp_path / "foo.py"
    p.write_text("x = 1")
    state = {"session": "", "call": 1, "reads": {}, "greps": {}}
    assert hook.check_read(state, str(p), None, None) is None


# ---------------------------------------------------------------------------
# Read cache — block on repeat with unchanged mtime
# ---------------------------------------------------------------------------

def test_read_repeat_blocked(hook, tmp_path):
    p = tmp_path / "bar.py"
    p.write_text("x = 1")
    state = {"session": "", "call": 5, "reads": {}, "greps": {}}
    hook.record_read(state, str(p), None, None)
    # same call, same file, unchanged
    msg = hook.check_read(state, str(p), None, None)
    assert msg is not None
    assert "already in context" in msg
    assert "bar.py" in msg


# ---------------------------------------------------------------------------
# Read cache — allow after file changes (mtime differs)
# ---------------------------------------------------------------------------

def test_read_allowed_after_file_change(hook, tmp_path):
    p = tmp_path / "changed.py"
    p.write_text("x = 1")
    state = {"session": "", "call": 2, "reads": {}, "greps": {}}
    hook.record_read(state, str(p), None, None)
    # Mutate mtime to simulate file change
    entry_key = hook._read_key(str(p), None, None)
    state["reads"][entry_key]["mtime"] -= 1.0
    assert hook.check_read(state, str(p), None, None) is None


# ---------------------------------------------------------------------------
# Read cache — mtime-preserving write that changes content must not be served
# as "unchanged" (BACKLOG.md: context-cache trusts mtime as proof of unchanged)
# ---------------------------------------------------------------------------

def test_read_same_mtime_different_size_not_blocked(hook, tmp_path):
    p = tmp_path / "resized.py"
    p.write_text("x = 1")
    state = {"session": "", "call": 4, "reads": {}, "greps": {}}
    hook.record_read(state, str(p), None, None)
    entry_key = hook._read_key(str(p), None, None)
    original_mtime = state["reads"][entry_key]["mtime"]
    # Simulate a mtime-preserving write (cp -p, rsync --times, coarse fs
    # granularity) that changes the file's content/size but not its mtime.
    p.write_text("x = 1\ny = 2\nz = 3\n")
    os.utime(p, (original_mtime, original_mtime))
    assert hook.check_read(state, str(p), None, None) is None


# ---------------------------------------------------------------------------
# Read cache — different offset = different key, allowed
# ---------------------------------------------------------------------------

def test_read_different_offset_allowed(hook, tmp_path):
    p = tmp_path / "sliced.py"
    p.write_text("\n".join(f"line{i}" for i in range(50)))
    state = {"session": "", "call": 3, "reads": {}, "greps": {}}
    hook.record_read(state, str(p), None, None)
    # A sliced read with offset=10 is a distinct key
    assert hook.check_read(state, str(p), 10, 20) is None


# ---------------------------------------------------------------------------
# Read cache — missing file passes through (let Read surface the error)
# ---------------------------------------------------------------------------

def test_read_missing_file_passes(hook, tmp_path):
    state = {"session": "", "call": 1, "reads": {}, "greps": {}}
    assert hook.check_read(state, str(tmp_path / "ghost.py"), None, None) is None


# ---------------------------------------------------------------------------
# Grep cache — allow on first call
# ---------------------------------------------------------------------------

def test_grep_first_call_allowed(hook):
    state = {"session": "", "call": 1, "reads": {}, "greps": {}}
    inp = {"pattern": "def foo", "path": "src/", "glob": "*.py", "type": ""}
    assert hook.check_grep(state, inp, ttl=300) is None


# ---------------------------------------------------------------------------
# Grep cache — block on repeat within TTL
# ---------------------------------------------------------------------------

def test_grep_repeat_blocked(hook):
    state = {"session": "", "call": 3, "reads": {}, "greps": {}}
    inp = {"pattern": "def foo", "path": "src/", "glob": "*.py", "type": ""}
    hook.record_grep(state, inp)
    msg = hook.check_grep(state, inp, ttl=300)
    assert msg is not None
    assert "def foo" in msg
    assert "already ran" in msg


# ---------------------------------------------------------------------------
# Grep cache — allow after TTL expires
# ---------------------------------------------------------------------------

def test_grep_expired_allowed(hook):
    state = {"session": "", "call": 3, "reads": {}, "greps": {}}
    inp = {"pattern": "import sys", "path": "", "glob": "", "type": ""}
    hook.record_grep(state, inp)
    key = hook._grep_key(inp)
    state["greps"][key]["ts"] -= 400  # push past TTL=300
    assert hook.check_grep(state, inp, ttl=300) is None


# ---------------------------------------------------------------------------
# Grep cache — different pattern = different key, allowed
# ---------------------------------------------------------------------------

def test_grep_different_pattern_allowed(hook):
    state = {"session": "", "call": 2, "reads": {}, "greps": {}}
    inp1 = {"pattern": "class Foo", "path": "", "glob": "", "type": ""}
    inp2 = {"pattern": "class Bar", "path": "", "glob": "", "type": ""}
    hook.record_grep(state, inp1)
    assert hook.check_grep(state, inp2, ttl=300) is None


# ---------------------------------------------------------------------------
# Session boundary clears cache
# ---------------------------------------------------------------------------

def test_new_session_clears_cache(hook, tmp_path):
    p = tmp_path / "persistent.py"
    p.write_text("y = 2")
    state = hook._get_state("transcript_A")
    hook.record_read(state, str(p), None, None)
    hook._save(state)

    # New session key — cache should be empty
    fresh = hook._get_state("transcript_B")
    assert fresh["reads"] == {}
    assert fresh["call"] == 0


# ---------------------------------------------------------------------------
# Blocked repeat read emits a full-schema measured savings record
# ---------------------------------------------------------------------------

def test_blocked_read_emits_measured_savings_schema(hook, tmp_path):
    p = tmp_path / "cached.py"
    p.write_text("z = 3" * 50)
    captured = []
    base = {"tool_name": "Read", "tool_input": {"file_path": str(p)},
            "transcript_path": "t1"}

    # First call records the read (allowed, no savings event).
    code, _, _ = hook.check_context_cache(
        hook.normalize_claude(base), state_dir=tmp_path, enabled=True,
        grep_ttl=300, log=captured.append, session=("sess-1", "payload"))
    assert code == 0 and captured == []

    # Repeat call is blocked and must log the new schema.
    code, _, msg = hook.check_context_cache(
        hook.normalize_claude(base), state_dir=tmp_path, enabled=True,
        grep_ttl=300, log=captured.append, session=("sess-1", "payload"))
    assert code == 2 and "already in context" in msg
    assert len(captured) == 1
    rec = captured[0]
    assert rec["strategy"] == "context-cache-read"
    assert rec["basis"] == "measured"
    assert rec["kept_chars"] == 0
    assert rec["elided_chars"] == p.stat().st_size
    assert rec["session_id"] == "sess-1"
    assert rec["session_source"] == "payload"


def test_blocked_partial_read_credits_only_the_slice(hook, tmp_path):
    # A partial re-read re-injects only its line slice, so the saving is the slice
    # size — not the whole file. Crediting st_size would overstate it.
    p = tmp_path / "big.py"
    lines = [f"line {i}\n" for i in range(100)]
    p.write_text("".join(lines))
    slice_chars = len("".join(lines[9:19]))  # offset=10 (1-based), limit=10
    assert slice_chars < p.stat().st_size

    captured = []
    base = {"tool_name": "Read",
            "tool_input": {"file_path": str(p), "offset": 10, "limit": 10},
            "transcript_path": "t1"}
    for _ in range(2):
        _, _, _ = hook.check_context_cache(
            hook.normalize_claude(base), state_dir=tmp_path, enabled=True,
            grep_ttl=300, log=captured.append, session=("s", "payload"))
    assert len(captured) == 1
    assert captured[0]["elided_chars"] == slice_chars


def test_blocked_read_chars_full_file_is_exact(hook, tmp_path):
    p = tmp_path / "whole.py"
    p.write_text("a = 1\nb = 2\n")
    assert hook.blocked_read_chars(str(p), None, None) == p.stat().st_size


# ---------------------------------------------------------------------------
# Bash cache — Codex-only wiring, shared logic
# ---------------------------------------------------------------------------

def test_bash_repeat_blocks_with_measured_savings(hook, tmp_path):
    captured = []
    post = {
        "tool_name": "Bash",
        "tool_input": {"command": "git status --short"},
        "tool_result": " M app.py\n",
        "transcript_path": "t1",
    }
    pre = {
        "tool_name": "Bash",
        "tool_input": {"command": "git status --short"},
        "transcript_path": "t1",
    }

    code, _, _ = hook.check_context_cache(
        hook.normalize_claude(post), state_dir=tmp_path, enabled=True,
        grep_ttl=300, bash_ttl=120, event_name="PostToolUse",
        log=captured.append, session=("sess-1", "payload"))
    assert code == 0 and captured == []

    code, _, msg = hook.check_context_cache(
        hook.normalize_claude(pre), state_dir=tmp_path, enabled=True,
        grep_ttl=300, bash_ttl=120, event_name="PreToolUse",
        log=captured.append, session=("sess-1", "payload"))
    assert code == 2
    assert "Bash `git status --short` already ran" in msg
    assert captured[0]["strategy"] == "context-cache-bash"
    assert captured[0]["elided_chars"] == len(" M app.py\n")
    assert captured[0]["where"] == "git status --short"


def test_bash_non_cacheable_command_is_not_blocked(hook, tmp_path):
    post = {
        "tool_name": "Bash",
        "tool_input": {"command": "ls -la"},
        "tool_result": "total 0\n",
        "transcript_path": "t1",
    }
    pre = {
        "tool_name": "Bash",
        "tool_input": {"command": "ls -la"},
        "transcript_path": "t1",
    }
    hook.check_context_cache(
        hook.normalize_claude(post), state_dir=tmp_path, enabled=True,
        grep_ttl=300, bash_ttl=120, event_name="PostToolUse")
    code, _, msg = hook.check_context_cache(
        hook.normalize_claude(pre), state_dir=tmp_path, enabled=True,
        grep_ttl=300, bash_ttl=120, event_name="PreToolUse")
    assert code == 0
    assert msg == ""


# ---------------------------------------------------------------------------
# Near-miss instrumentation (Strategy 3 Phase 0) — additive only, no behavior
# change, never read by any hook.
# ---------------------------------------------------------------------------

def test_near_miss_signature_is_first_token():
    hook = load_hook(HOOK)
    assert hook.near_miss_signature("pytest -v tests/foo.py") == "pytest"
    assert hook.near_miss_signature("pytest tests/bar.py") == "pytest"
    assert hook.near_miss_signature("") == ""
    assert hook.near_miss_signature("   ") == ""


def test_record_near_miss_appends_jsonl_without_reading_it_back(tmp_path):
    hook = load_hook(HOOK)
    hook.record_near_miss(tmp_path, kind="bash", signature="pytest")
    hook.record_near_miss(tmp_path, kind="grep", signature="foo bar")
    log = tmp_path / "near_misses.jsonl"
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    import json as _json
    first = _json.loads(lines[0])
    assert first["kind"] == "bash" and first["signature"] == "pytest" and "ts" in first


def test_record_near_miss_is_a_noop_for_empty_signature(tmp_path):
    hook = load_hook(HOOK)
    hook.record_near_miss(tmp_path, kind="bash", signature="")
    assert not (tmp_path / "near_misses.jsonl").exists()


def test_bash_miss_records_near_miss_by_signature(tmp_path):
    hook = load_hook(HOOK)
    pre = {
        "tool_name": "Bash",
        "tool_input": {"command": "pytest tests/unit/test_x.py -v"},
        "transcript_path": "t1",
    }
    code, _, msg = hook.check_context_cache(
        hook.normalize_claude(pre), state_dir=tmp_path, enabled=True,
        grep_ttl=300, bash_ttl=120, event_name="PreToolUse")
    assert code == 0 and msg == ""
    log = (tmp_path / "near_misses.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(log) == 1
    import json as _json
    assert _json.loads(log[0])["signature"] == "pytest"


def test_grep_miss_records_near_miss_by_pattern(tmp_path):
    hook = load_hook(HOOK)
    pre = {
        "tool_name": "Grep",
        "tool_input": {"pattern": "def check_bash"},
        "transcript_path": "t1",
    }
    code, _, msg = hook.check_context_cache(
        hook.normalize_claude(pre), state_dir=tmp_path, enabled=True,
        grep_ttl=300, bash_ttl=120, event_name="PreToolUse")
    assert code == 0 and msg == ""
    log = (tmp_path / "near_misses.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(log) == 1
    import json as _json
    entry = _json.loads(log[0])
    assert entry["kind"] == "grep" and entry["signature"] == "def check_bash"


# ---------------------------------------------------------------------------
# None transcript_path must not share state across sessions
# ---------------------------------------------------------------------------

def test_none_transcript_path_does_not_share_state(hook, tmp_path):
    """_get_state(None) must return a fresh state even when a prior None
    session saved entries — two sessions both with transcript_path=None
    are indistinguishable, so the cache must not bleed across them."""
    p = tmp_path / "shared.py"
    p.write_text("x = 1")

    # Simulate session 1: get state, record a read, save
    state1 = hook._get_state(None)
    hook.record_read(state1, str(p), None, None)
    hook._save(state1)

    # Simulate session 2 (new session, also transcript_path=None):
    # must see empty reads, not the stale entry from session 1
    state2 = hook._get_state(None)
    assert state2["reads"] == {}, (
        "_get_state(None) returned stale reads from a previous None-keyed session"
    )

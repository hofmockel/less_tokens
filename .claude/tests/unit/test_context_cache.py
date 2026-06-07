"""Unit tests for the context-cache PreToolUse hook (G2)."""
from __future__ import annotations

import json
import time
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

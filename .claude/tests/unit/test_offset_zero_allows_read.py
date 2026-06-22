"""Regression test: offset=0 should be treated as a deliberate slice, not absent.

Both read-guard.py and read-after-edit.py used `inp.get("offset")` which is
falsy for 0, incorrectly blocking Read(offset=0, limit=N) as if it were an
unsliced whole-file read.
"""
from __future__ import annotations

import io
import json
import time
from pathlib import Path

import pytest

from tests.conftest import load_hook

HOOK_READ_GUARD = Path(__file__).resolve().parent.parent.parent / "hooks" / "read-guard.py"
HOOK_READ_AFTER_EDIT = (
    Path(__file__).resolve().parent.parent.parent / "hooks" / "read-after-edit.py"
)


@pytest.fixture(scope="module")
def read_guard():
    return load_hook(HOOK_READ_GUARD)


@pytest.fixture(scope="module")
def read_after_edit():
    return load_hook(HOOK_READ_AFTER_EDIT)


def _make_payload(file_path: str, offset=None, limit=None) -> str:
    inp: dict = {"file_path": file_path}
    if offset is not None:
        inp["offset"] = offset
    if limit is not None:
        inp["limit"] = limit
    return json.dumps({"tool_name": "Read", "tool_input": inp})


# ---------------------------------------------------------------------------
# read-guard: offset=0 should bypass the block
# ---------------------------------------------------------------------------


def test_read_guard_offset_zero_bypasses_block(read_guard, tmp_path, monkeypatch):
    """Read(offset=0, limit=N) on a large data file must be allowed."""
    big_csv = tmp_path / "big.csv"
    big_csv.write_text(
        "\n".join(f"{i},x" for i in range(read_guard.READ_DENY_DATA_MAX_LINES + 5))
    )
    # confirm the file is blocked without offset
    assert read_guard.check(str(big_csv)) is not None, "setup: file should be blockable"

    payload = _make_payload(str(big_csv), offset=0, limit=50)
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(payload.encode())))
    result = read_guard.main()
    assert result == 0, "offset=0 must bypass the large-file block in read-guard"


def test_read_guard_no_offset_still_blocked(read_guard, tmp_path, monkeypatch):
    """Whole-file Read on a large data file without offset is still blocked."""
    big_csv = tmp_path / "big2.csv"
    big_csv.write_text(
        "\n".join(f"{i},x" for i in range(read_guard.READ_DENY_DATA_MAX_LINES + 5))
    )
    payload = _make_payload(str(big_csv))
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(payload.encode())))
    result = read_guard.main()
    assert result == 2, "whole-file Read on large data must still be blocked"


# ---------------------------------------------------------------------------
# read-after-edit: offset=0 should bypass the block
# ---------------------------------------------------------------------------


def test_read_after_edit_offset_zero_bypasses_block(
    read_after_edit, tmp_path, monkeypatch
):
    """Read(offset=0, limit=N) on a recently-edited file must be allowed."""
    target = tmp_path / "edited.py"
    target.write_text("x = 1\n")
    abs_path = str(target.resolve())

    state_dir = tmp_path / "state"
    state_dir.mkdir()
    last_edit = state_dir / "last-edit.json"
    last_edit.write_text(json.dumps({abs_path: time.time()}))

    monkeypatch.setattr(read_after_edit, "_active_state_dir", lambda: state_dir)

    payload = _make_payload(abs_path, offset=0, limit=20)
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(payload.encode())))
    result = read_after_edit.main()
    assert result == 0, "offset=0 must bypass the recent-edit block in read-after-edit"


def test_read_after_edit_no_offset_still_blocked(
    read_after_edit, tmp_path, monkeypatch
):
    """Whole-file Read on a recently-edited file without offset is still blocked."""
    target = tmp_path / "edited2.py"
    target.write_text("x = 1\n")
    abs_path = str(target.resolve())

    state_dir = tmp_path / "state2"
    state_dir.mkdir()
    last_edit = state_dir / "last-edit.json"
    last_edit.write_text(json.dumps({abs_path: time.time()}))

    monkeypatch.setattr(read_after_edit, "_active_state_dir", lambda: state_dir)

    payload = _make_payload(abs_path)
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(payload.encode())))
    result = read_after_edit.main()
    assert result == 2, "whole-file Read on recently-edited file must still be blocked"

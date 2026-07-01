"""Regression: wire_settings(dry_run=True) must not mutate the in-memory settings dict.

Bug: event_list.append(...) ran before the `if not dry_run:` guard, so a dry-run call
mutated the hooks list in memory. A second wire_settings call against the same
settings dict in the same process saw the hook as already wired and skipped it,
even though nothing was actually written to disk.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from install import wire_settings


def test_dry_run_does_not_mutate_and_second_call_still_adds(tmp_path):
    settings_path = tmp_path / "settings.json"
    entries = [("PreToolUse", "Read", "echo hi")]

    added1, present1 = wire_settings(settings_path, entries, dry_run=True)
    assert added1 == 1
    assert present1 == 0
    assert not settings_path.exists()

    added2, present2 = wire_settings(settings_path, entries, dry_run=True)
    assert added2 == 1
    assert present2 == 0


def test_dry_run_does_not_self_mutate_within_one_call(tmp_path):
    """Duplicate entries in one dry-run call must each report as 'would add',
    not have the first self-mutation make the second look already-wired."""
    settings_path = tmp_path / "settings.json"
    entries = [
        ("PreToolUse", "Read", "echo hi"),
        ("PreToolUse", "Read", "echo hi"),
    ]

    added, present = wire_settings(settings_path, entries, dry_run=True)
    assert added == 2
    assert present == 0

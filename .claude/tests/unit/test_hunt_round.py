"""Unit tests for tools/hunt_round.py — bug-hunt round validator/appender."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]


def _load(name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


hunt_round = _load("hunt_round", ".claude/tools/hunt_round.py")


def _record(**overrides):
    base = {
        "round": 1,
        "date": "2026-07-14",
        "bugs_surfaced": 2,
        "severity": {"ux": 1, "silent": 1},
        "median_severity": "ux",
        "overlap": {"matched": 0, "total": 0},
        "new_files": ["stats.py"],
    }
    base.update(overrides)
    return base


def test_validate_accepts_well_formed_first_round():
    hunt_round.validate(_record(), prior_records=[])


def test_validate_rejects_missing_key():
    record = _record()
    del record["median_severity"]
    with pytest.raises(hunt_round.ValidationError, match="missing keys"):
        hunt_round.validate(record, prior_records=[])


def test_validate_rejects_non_sequential_round():
    with pytest.raises(hunt_round.ValidationError, match="round must be 1"):
        hunt_round.validate(_record(round=2), prior_records=[])
    with pytest.raises(hunt_round.ValidationError, match="round must be 2"):
        hunt_round.validate(_record(round=3), prior_records=[{"round": 1}])


def test_validate_rejects_unknown_severity_tier():
    record = _record(severity={"typo_tier": 2})
    with pytest.raises(hunt_round.ValidationError, match="unknown severity tiers"):
        hunt_round.validate(record, prior_records=[])


def test_validate_rejects_severity_sum_mismatch():
    record = _record(severity={"ux": 1}, bugs_surfaced=5)
    with pytest.raises(hunt_round.ValidationError, match="sum to"):
        hunt_round.validate(record, prior_records=[])


def test_validate_rejects_bad_median_severity():
    with pytest.raises(hunt_round.ValidationError, match="median_severity must be"):
        hunt_round.validate(_record(median_severity="terrible"), prior_records=[])


def test_validate_rejects_matched_exceeding_total():
    record = _record(overlap={"matched": 5, "total": 2})
    with pytest.raises(hunt_round.ValidationError, match="cannot exceed"):
        hunt_round.validate(record, prior_records=[])


def test_append_round_writes_and_is_sequential(tmp_path):
    log = tmp_path / "log.jsonl"
    log.write_text("# header comment\n")
    hunt_round.append_round(_record(), path=log)
    hunt_round.append_round(_record(round=2), path=log)
    lines = [
        json.loads(line)
        for line in log.read_text().splitlines()
        if not line.startswith("#")
    ]
    assert [r["round"] for r in lines] == [1, 2]


def test_append_round_rejects_second_call_with_stale_round(tmp_path):
    log = tmp_path / "log.jsonl"
    log.write_text("")
    hunt_round.append_round(_record(), path=log)
    with pytest.raises(hunt_round.ValidationError):
        hunt_round.append_round(_record(round=1), path=log)


def test_load_record_accepts_inline_json_and_file(tmp_path):
    assert hunt_round._load_record(json.dumps(_record())) == _record()

    path = tmp_path / "record.json"
    path.write_text(json.dumps(_record()))
    assert hunt_round._load_record(str(path)) == _record()


def test_load_record_raises_on_garbage():
    with pytest.raises(hunt_round.ValidationError):
        hunt_round._load_record("not json and not a real path")

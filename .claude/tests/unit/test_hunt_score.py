"""Unit tests for tools/hunt_score.py — bug-hunt stop-rule scorer."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def _load(name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


hunt_score = _load("hunt_score", ".claude/tools/hunt_score.py")


def test_target_files_sourced_from_registry_and_exist_on_disk():
    known_dirs = (REPO / ".claude" / "tools", REPO / ".claude" / "hooks", REPO)
    for name in hunt_score.TARGET_FILES:
        assert any((d / name).is_file() for d in known_dirs), (
            f"target file {name!r} not found in .claude/tools, .claude/hooks, or repo root"
        )


def test_severity_index_unknown_treated_as_worst():
    assert hunt_score._severity_index("not-a-tier") == 0
    assert hunt_score._severity_index("cosmetic") == len(hunt_score.SEVERITY_ORDER) - 1


def test_parse_records_skips_comments_and_blanks(tmp_path):
    log = tmp_path / "log.jsonl"
    log.write_text('# comment\n\n{"round": 1}\n{"round": 2}\n')
    records = hunt_score._parse_records(log)
    assert [r["round"] for r in records] == [1, 2]


def test_score_stop_when_all_three_signals_pass(tmp_path, capsys):
    covered = list(hunt_score.TARGET_FILES)
    records = [
        {
            "round": 1,
            "date": "2026-07-14",
            "median_severity": "cosmetic",
            "overlap": {"matched": 6, "total": 10},
            "new_files": covered,
        }
    ]
    hunt_score.score(records)
    assert "STOP" in capsys.readouterr().out


def test_score_keep_hunting_when_no_signals_pass(capsys):
    records = [
        {
            "round": 1,
            "date": "2026-07-14",
            "median_severity": "data_loss",
            "overlap": {"matched": 0, "total": 10},
            "new_files": [],
        }
    ]
    hunt_score.score(records)
    assert "KEEP HUNTING" in capsys.readouterr().out

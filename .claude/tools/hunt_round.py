#!/usr/bin/env python3
"""Validate and append one bug-hunt round record, then score it.

Replaces the hand-done "(3) append JSON, (4) run hunt_score.py" steps in
agents/common/bug-hunt-protocol.md's operator checklist with one command.

Usage:
    python .claude/tools/hunt_round.py '<json record>'
    python .claude/tools/hunt_round.py path/to/record.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bug_hunt_registry import ROUND_REQUIRED_KEYS, SEVERITY_ORDER  # noqa: E402
from hunt_score import DEFAULT_LOG_PATH, _parse_records, score  # noqa: E402


class ValidationError(ValueError):
    pass


def _load_record(arg: str) -> dict:
    try:
        return json.loads(arg)
    except json.JSONDecodeError:
        pass
    path = Path(arg)
    if not path.exists():
        raise ValidationError(f"not valid JSON and no such file: {arg}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate(record: dict, prior_records: list[dict]) -> None:
    missing = [k for k in ROUND_REQUIRED_KEYS if k not in record]
    if missing:
        raise ValidationError(f"missing keys: {missing}")

    if not isinstance(record["round"], int):
        raise ValidationError("round must be an int")
    expected_round = (prior_records[-1]["round"] + 1) if prior_records else 1
    if record["round"] != expected_round:
        raise ValidationError(f"round must be {expected_round}, got {record['round']}")

    if record["median_severity"] not in SEVERITY_ORDER:
        raise ValidationError(
            f"median_severity must be one of {SEVERITY_ORDER}, got {record['median_severity']!r}"
        )

    severity = record["severity"]
    unknown_tiers = set(severity) - set(SEVERITY_ORDER)
    if unknown_tiers:
        raise ValidationError(f"unknown severity tiers: {sorted(unknown_tiers)}")
    if sum(severity.values()) != record["bugs_surfaced"]:
        raise ValidationError(
            f"severity counts sum to {sum(severity.values())}, "
            f"bugs_surfaced says {record['bugs_surfaced']}"
        )

    overlap = record["overlap"]
    if overlap["matched"] > overlap["total"]:
        raise ValidationError("overlap.matched cannot exceed overlap.total")

    if not isinstance(record["new_files"], list):
        raise ValidationError("new_files must be a list")


def append_round(record: dict, path: Path = DEFAULT_LOG_PATH) -> None:
    prior_records = _parse_records(path)
    validate(record, prior_records)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    try:
        record = _load_record(sys.argv[1])
        append_round(record)
    except ValidationError as exc:
        print(f"Invalid round record: {exc}", file=sys.stderr)
        sys.exit(1)
    score(_parse_records(DEFAULT_LOG_PATH))


if __name__ == "__main__":
    main()

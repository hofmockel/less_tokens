#!/usr/bin/env python3
"""Score the bug-hunt stop rule against bughuntlog.jsonl.

Reads all round records, evaluates the three stop signals for the latest
round, and prints GO or STOP with a signal breakdown.

Usage:
    python .claude/tools/hunt_score.py [path/to/bughuntlog.jsonl]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SEVERITY_ORDER = ["data_loss", "silent", "ux", "cosmetic"]
TARGET_FILES = {
    "embeddings.py", "search.py", "search_config.py", "model_profiles.py",
    "stats.py", "savings_log.py", "db.py", "search-first.py",
    "truncate-output.py", "index-refresh.py", "compact-trigger.py",
    "caveman-reminder.py", "install.py", "index.sql",
}
OVERLAP_THRESHOLD = 0.60
COVERAGE_THRESHOLD = 0.80


def _parse_records(path: Path) -> list[dict]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        records.append(json.loads(line))
    return records


def _severity_index(s: str) -> int:
    try:
        return SEVERITY_ORDER.index(s)
    except ValueError:
        return 0  # unknown = treat as worst


def score(records: list[dict]) -> None:
    if not records:
        print("No rounds recorded yet. Cannot score.")
        sys.exit(1)

    last = records[-1]

    # Signal 1: median severity of last round <= "ux"
    med = last.get("median_severity", "data_loss")
    sig1 = _severity_index(med) >= _severity_index("ux")

    # Signal 2: overlap rate >= 60%
    overlap = last.get("overlap", {})
    matched, total = overlap.get("matched", 0), overlap.get("total", 0)
    overlap_rate = matched / total if total else 0.0
    sig2 = overlap_rate >= OVERLAP_THRESHOLD

    # Signal 3: cumulative file coverage >= 80% of target list
    covered: set[str] = set()
    for r in records:
        covered.update(r.get("new_files", []))
    hit_targets = covered & TARGET_FILES
    coverage_rate = len(hit_targets) / len(TARGET_FILES)
    sig3 = coverage_rate >= COVERAGE_THRESHOLD

    signals = [sig1, sig2, sig3]
    passed = sum(signals)

    print(f"Round {last.get('round', '?')}  ({last.get('date', '?')})")
    print(f"  Severity slide   (median <= ux):      {'PASS' if sig1 else 'FAIL'}  [{med}]")
    print(f"  Overlap rate     (>= 60%):             {'PASS' if sig2 else 'FAIL'}  [{matched}/{total} = {overlap_rate:.0%}]")
    print(f"  File coverage    (>= 80% of targets): {'PASS' if sig3 else 'FAIL'}  [{len(hit_targets)}/{len(TARGET_FILES)} = {coverage_rate:.0%}]")
    print()

    if passed == 3:
        print("STOP — all three signals met.")
    elif passed == 2:
        print("RUN ONE MORE — 2 of 3 signals met.")
    else:
        print(f"KEEP HUNTING — only {passed} of 3 signals met.")


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path(__file__).parent.parent / "skills" / "bug-hunt" / "bughuntlog.jsonl"
    )
    if not path.exists():
        print(f"Not found: {path}", file=sys.stderr)
        sys.exit(1)
    score(_parse_records(path))


if __name__ == "__main__":
    main()

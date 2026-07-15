#!/usr/bin/env python3
"""Measured-vs-asserted label consistency gate for README.md's strategy table.

Modeled directly on changelog_gate.py's precedent: scan a doc, cross-reference
an artifact, fail CI on drift, name the exact violation. Here the artifact is
savings_log._KNOWN_STRATEGIES (the canonical registry every telemetry emitter
writes against — see stats.py). Any row in README.md's strategy table with a
magnitude claim (a percentage or "N×") must either:

  1. name a strategy with a real _KNOWN_STRATEGIES entry (a savings.jsonl
     category actually exists for it), or
  2. carry an explicit "not telemetry-backed"-style marker in its Savings cell.

This is what stops a future contributor from adding a new unverified savings
percentage the way "Terse output mode" (30-60%) and "Lean tool output"
(40-90%) shipped without one.

Row -> registry-key mapping comes from strategy_registry.STRATEGIES, the same
source strategy_table_docs.py renders README.md's table from: add or change a
row there once and both the doc and this gate stay in sync. An unmapped row
(one present in README.md's text but absent from the registry) fails loudly
rather than silently passing.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

README = "README.md"

STRATEGY_ROW = re.compile(r"^\|\s*\*\*(?P<name>[^*]+)\*\*\s*\|[^|]*\|(?P<savings>[^|]*)\|", re.MULTILINE)
MAGNITUDE = re.compile(r"\d+(?:\s*[\-–]\s*\d+)?\s*%|\d+\s*×")
UNVERIFIED_MARKERS = ("not telemetry-backed", "not measured", "asserted only", "no telemetry")

_tools_dir = Path(__file__).resolve().parent
if str(_tools_dir) not in sys.path:
    sys.path.insert(0, str(_tools_dir))
from strategy_registry import STRATEGIES  # noqa: E402

# README strategy display name -> savings_log strategy key, or None if the
# strategy is real but has no savings.jsonl category by design.
README_STRATEGY_REGISTRY_MAP: dict[str, str | None] = {
    row.name: row.registry_key for row in STRATEGIES
}


def find_unbacked_claims(readme_text: str, known_strategies: set[str]) -> list[str]:
    """Rows with a magnitude claim, no registry backing, and no honesty marker."""
    problems = []
    for m in STRATEGY_ROW.finditer(readme_text):
        name = m.group("name").strip()
        savings = m.group("savings").strip()
        if not MAGNITUDE.search(savings):
            continue
        if name not in README_STRATEGY_REGISTRY_MAP:
            problems.append(
                f"{name!r}: not in README_STRATEGY_REGISTRY_MAP — add a mapping "
                f"(a savings_log strategy key, or None if intentionally unmeasured)"
            )
            continue
        key = README_STRATEGY_REGISTRY_MAP[name]
        if key and key in known_strategies:
            continue
        if not any(marker in savings.lower() for marker in UNVERIFIED_MARKERS):
            problems.append(
                f"{name!r}: claims {savings!r} with no savings.jsonl registry entry "
                f"and no honesty marker (e.g. 'not telemetry-backed')"
            )
    return problems


def _known_strategies() -> set[str]:
    tools_dir = Path(__file__).resolve().parent
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    try:
        from savings_log import _KNOWN_STRATEGIES
        return set(_KNOWN_STRATEGIES)
    except Exception:
        return {
            "truncation", "compaction", "context-cache-read",
            "context-cache-grep", "context-cache-bash", "search-blocked", "search",
        }


def main(argv: list[str]) -> int:
    repo = Path(__file__).resolve().parents[2]
    readme_path = repo / README
    text = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

    problems = find_unbacked_claims(text, _known_strategies())
    if problems:
        for p in problems:
            print(f"label-consistency-gate: {p}", file=sys.stderr)
        return 1
    print("label-consistency-gate: ok (every magnitude claim is registry-backed or marked unverified)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

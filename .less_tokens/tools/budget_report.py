#!/usr/bin/env python3
"""Print a v2 less_tokens budget telemetry report."""
from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path


def _resolve_repo() -> Path:
    curr = Path.cwd().resolve()
    for _ in range(8):
        if (curr / ".less_tokens").exists() or (curr / ".git").exists():
            return curr
        if curr == curr.parent:
            break
        curr = curr.parent
    return Path.cwd().resolve()


REPO = _resolve_repo()
sys.path[:0] = [str(REPO), str(REPO / ".less_tokens" / "hooks")]

try:
    from agents.common.budget.events import load_events  # noqa: E402
    from agents.common.budget.state import resolve_state_root  # noqa: E402
except Exception:
    from budget.events import load_events  # type: ignore[no-redef]  # noqa: E402
    from budget.state import resolve_state_root  # type: ignore[no-redef]  # noqa: E402


def _int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _pct(used: int, limit: int) -> str:
    if limit <= 0:
        return "n/a"
    return f"{min(999, round((used / limit) * 100))}%"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=1000, help="read the most recent N events")
    args = parser.parse_args()

    events = load_events(resolve_state_root(REPO), limit=args.limit)
    if not events:
        print("less_tokens budget report\n")
        print("No v2 budget telemetry found yet.")
        return 0

    saved_total = sum(_int(e.get("estimated_tokens_saved")) for e in events)
    by_agent: collections.Counter[str] = collections.Counter()
    by_strategy: collections.Counter[str] = collections.Counter()
    pressure: dict[str, tuple[int, int]] = {}
    rejected: collections.Counter[str] = collections.Counter()
    risk: collections.Counter[str] = collections.Counter()
    compactions = 0

    for event in events:
        saved = _int(event.get("estimated_tokens_saved"))
        agent = str(event.get("agent") or "unknown")
        by_agent[agent] += saved
        decision = str(event.get("decision") or "unknown")
        strategy = str(event.get("strategy") or decision)
        by_strategy[f"{strategy}: {decision}"] += saved
        category = str(event.get("category") or "unknown")
        used = _int(event.get("budget_used_after") or event.get("budget_used_before"))
        limit = _int(event.get("budget_limit"))
        prev = pressure.get(category, (0, limit))
        pressure[category] = (max(prev[0], used), limit or prev[1])
        if decision in {"block", "defer", "replace", "trim"}:
            reason = str(event.get("reason") or "unspecified")
            rejected[reason] += 1
        if decision in {"block", "defer"}:
            risk["context omitted"] += 1
        if decision in {"replace", "trim", "summarize"}:
            risk["context transformed"] += 1
        if event.get("error"):
            risk["budget failure"] += 1
        if str(event.get("phase") or "") == "compaction":
            compactions += 1

    print("less_tokens budget report\n")
    print(f"Estimated saved: {saved_total:,} tokens")
    for agent, saved in by_agent.most_common():
        count = sum(1 for e in events if str(e.get("agent") or "unknown") == agent)
        print(f"{agent.title()}: {saved:,} saved across {count} decisions")

    print("\nTop savings:")
    for idx, (name, saved) in enumerate(by_strategy.most_common(5), start=1):
        print(f"{idx}. {name}: {saved:,}")

    print("\nTop pressure:")
    pressure_rows = sorted(
        pressure.items(),
        key=lambda item: (item[1][0] / item[1][1]) if item[1][1] else 0,
        reverse=True,
    )
    for idx, (category, (used, limit)) in enumerate(pressure_rows[:5], start=1):
        print(f"{idx}. {category}: {_pct(used, limit)}")

    print("\nTop rejected context:")
    if rejected:
        for idx, (reason, count) in enumerate(rejected.most_common(5), start=1):
            print(f"{idx}. {reason}: {count} events")
    else:
        print("1. none: 0 events")

    print("\nQuality risk:")
    if risk:
        for idx, (label, count) in enumerate(risk.most_common(), start=1):
            print(f"{idx}. {label}: {count} events")
    else:
        print("1. none: 0 events")
    print(f"\nCompactions: {compactions}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

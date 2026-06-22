#!/usr/bin/env python3
"""Explain less_tokens budget config and recent pressure."""
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
    from agents.common.budget import load_budget_config, load_events  # noqa: E402
except Exception:
    from budget import load_budget_config, load_events  # type: ignore[no-redef]  # noqa: E402


def _int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _pct(used: int, limit: int) -> str:
    if limit <= 0:
        return "n/a"
    return f"{round((used / limit) * 100)}%"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", choices=["claude", "codex"], default=None)
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    config = load_budget_config(REPO, agent=args.agent)
    events = load_events(REPO, limit=args.limit)
    pressure: dict[str, tuple[int, int]] = {}
    decisions: collections.Counter[str] = collections.Counter()
    risk: collections.Counter[str] = collections.Counter()
    compactions = 0
    errors = 0
    for event in events:
        category = str(event.get("category") or "unknown")
        used = _int(event.get("budget_used_after") or event.get("budget_used_before"))
        limit = _int(event.get("budget_limit")) or config.category_limit(category)
        previous = pressure.get(category, (0, limit))
        pressure[category] = (max(previous[0], used), limit or previous[1])
        decisions[str(event.get("decision") or "unknown")] += 1
        decision = str(event.get("decision") or "unknown")
        if decision in {"block", "defer"}:
            risk["context omitted"] += 1
        if decision in {"replace", "trim", "summarize"}:
            risk["context transformed"] += 1
        if str(event.get("phase") or "") == "compaction":
            compactions += 1
        if event.get("error"):
            errors += 1
            risk["budget failure"] += 1

    who = f" ({args.agent})" if args.agent else ""
    print(f"less_tokens budget doctor{who}\n")
    print(f"Mode: {config.mode}")
    print(f"Estimator: {config.token_estimator}")
    print(f"Total context: {config.total_context_tokens:,}")
    print(f"Reserved response: {config.reserved_response_tokens:,}")
    print(f"Relevance threshold: {config.relevance_threshold:.2f}")

    print("\nCategory budgets:")
    for category, limit in sorted(config.categories.items()):
        print(f"- {category}: {limit:,}")

    print("\nRecent pressure:")
    if pressure:
        for category, (used, limit) in sorted(
            pressure.items(),
            key=lambda item: (item[1][0] / item[1][1]) if item[1][1] else 0,
            reverse=True,
        )[:5]:
            print(f"- {category}: {_pct(used, limit)} ({used:,}/{limit:,})")
    else:
        print("- none recorded")

    print("\nRecent decisions:")
    if decisions:
        for decision, count in decisions.most_common():
            print(f"- {decision}: {count}")
    else:
        print("- none recorded")
    print(f"\nCompactions: {compactions}")
    print("\nQuality risk:")
    if risk:
        for label, count in risk.most_common():
            print(f"- {label}: {count}")
    else:
        print("- none recorded")
    if errors:
        print(f"\nFailures logged: {errors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

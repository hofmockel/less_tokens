#!/usr/bin/env python3
"""Deterministic session-style token evaluation for less_tokens.

This is not a live Claude/Codex runner. It is a repeatable fixture harness that
compares broad baseline context collection against less_tokens-style targeted
context for representative coding tasks.

Usage:
  python .claude/tools/eval_sessions.py
  python .claude/tools/eval_sessions.py --json
  python .claude/tools/eval_sessions.py --report .claude/state/session-eval.md
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


BASE = Path(__file__).resolve().parent.parent.parent
FIXTURE = BASE / ".claude" / "tests" / "fixtures" / "sample_project"
CHARS_PER_TOKEN = 4


@dataclass(frozen=True)
class EvalTask:
    name: str
    files: tuple[str, ...]
    needles: tuple[str, ...]
    description: str


TASKS: tuple[EvalTask, ...] = (
    EvalTask(
        "locate_function",
        ("tools/sample.py",),
        ("simple_function", "return x * 2"),
        "Locate and inspect a small function.",
    ),
    EvalTask(
        "diagnose_schema",
        ("schema/tables.sql",),
        ("CREATE TABLE", "audit"),
        "Find the relevant schema statement.",
    ),
    EvalTask(
        "summarize_config_docs",
        ("docs/guide.md",),
        ("Configuration", "Advanced"),
        "Answer a docs/configuration question.",
    ),
    EvalTask(
        "inspect_changelog",
        ("CHANGELOG.md",),
        ("Changed", "Fixed"),
        "Find a changelog entry without reading every doc.",
    ),
    EvalTask(
        "small_refactor",
        ("tools/sample.py", "docs/guide.md"),
        ("class", "configuration"),
        "Gather focused context across code and docs.",
    ),
)


def _read(rel: str) -> str:
    return (FIXTURE / rel).read_text(encoding="utf-8", errors="replace")


def _all_fixture_chars() -> int:
    return sum(len(p.read_text(encoding="utf-8", errors="replace")) for p in FIXTURE.rglob("*") if p.is_file())


def _targeted_chars(task: EvalTask, radius: int = 2) -> int:
    total = 0
    for rel in task.files:
        lines = _read(rel).splitlines()
        keep: set[int] = set()
        for idx, line in enumerate(lines):
            lower = line.lower()
            if any(needle.lower() in lower for needle in task.needles):
                for j in range(max(0, idx - radius), min(len(lines), idx + radius + 1)):
                    keep.add(j)
        if not keep and lines:
            keep.update(range(min(len(lines), 8)))
        total += sum(len(lines[i]) + 1 for i in sorted(keep))
    return total


def run_eval() -> dict:
    baseline_per_task = _all_fixture_chars()
    rows = []
    baseline_total = 0
    targeted_total = 0
    for task in TASKS:
        targeted = _targeted_chars(task)
        baseline_total += baseline_per_task
        targeted_total += targeted
        rows.append({
            "task": task.name,
            "description": task.description,
            "baseline_chars": baseline_per_task,
            "less_tokens_chars": targeted,
            "saved_chars": max(0, baseline_per_task - targeted),
            "reduction_pct": round((1 - targeted / baseline_per_task) * 100, 1)
            if baseline_per_task else 0.0,
        })
    return {
        "tasks": rows,
        "totals": {
            "baseline_chars": baseline_total,
            "less_tokens_chars": targeted_total,
            "saved_chars": max(0, baseline_total - targeted_total),
            "approx_tokens_saved": max(0, baseline_total - targeted_total) // CHARS_PER_TOKEN,
            "reduction_pct": round((1 - targeted_total / baseline_total) * 100, 1)
            if baseline_total else 0.0,
        },
    }


def markdown_report(result: dict) -> str:
    lines = [
        "# Session-style token evaluation",
        "",
        "Deterministic fixture benchmark. Baseline reads the fixture corpus for each task; less_tokens uses targeted slices around task-relevant lines.",
        "",
        "| Task | Baseline chars | less_tokens chars | Reduction |",
        "|---|---:|---:|---:|",
    ]
    for row in result["tasks"]:
        lines.append(
            f"| {row['task']} | {row['baseline_chars']:,} | "
            f"{row['less_tokens_chars']:,} | {row['reduction_pct']}% |"
        )
    totals = result["totals"]
    lines.extend([
        "",
        f"Total baseline chars: {totals['baseline_chars']:,}",
        f"Total less_tokens chars: {totals['less_tokens_chars']:,}",
        f"Approx tokens saved: {totals['approx_tokens_saved']:,}",
        f"Reduction: {totals['reduction_pct']}%",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    result = run_eval()
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(markdown_report(result), encoding="utf-8")
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(markdown_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

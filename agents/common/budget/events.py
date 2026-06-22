"""v2 budget telemetry events."""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .decisions import BudgetDecision


@dataclass(frozen=True)
class BudgetEvent:
    version: int
    timestamp: str
    agent: str
    session_id: str
    run_id: str
    phase: str
    tool_name: str
    category: str
    candidate_id: str
    strategy: str
    decision: str
    mode: str
    estimated_tokens_before: int
    estimated_tokens_after: int
    estimated_tokens_saved: int
    budget_limit: int
    budget_used_before: int
    budget_used_after: int
    relevance_score: float
    reason: str
    replacement: str | None
    error: str | None


def iso_timestamp(now: float | None = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now or time.time()))


def event_from_decision(
    decision: BudgetDecision,
    *,
    agent: str,
    session_id: str,
    run_id: str,
    phase: str,
    tool_name: str,
    mode: str,
    strategy: str = "relevance_gate",
) -> BudgetEvent:
    return BudgetEvent(
        version=2,
        timestamp=iso_timestamp(),
        agent=agent,
        session_id=session_id,
        run_id=run_id,
        phase=phase,
        tool_name=tool_name,
        category=decision.category,
        candidate_id=decision.candidate_id,
        strategy=strategy,
        decision=decision.action,
        mode=mode,
        estimated_tokens_before=decision.estimated_tokens_before,
        estimated_tokens_after=decision.estimated_tokens_after,
        estimated_tokens_saved=decision.estimated_tokens_saved,
        budget_limit=decision.budget_limit,
        budget_used_before=decision.budget_used_before,
        budget_used_after=decision.budget_used_after,
        relevance_score=decision.relevance_score,
        reason=decision.reason,
        replacement=decision.replacement,
        error=decision.error,
    )


def events_path(root: Path) -> Path:
    return root / ".less_tokens" / "state" / "events.jsonl"


def append_event(root: Path, event: BudgetEvent) -> None:
    path = events_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(asdict(event), sort_keys=True) + "\n"
    with path.open("a", encoding="utf-8") as f:
        try:
            if hasattr(os, "lockf"):
                os.lockf(f.fileno(), os.F_LOCK, 0)
            f.write(line)
        finally:
            if hasattr(os, "lockf"):
                os.lockf(f.fileno(), os.F_ULOCK, 0)


def append_failure_event(
    root: Path,
    *,
    agent: str,
    session_id: str,
    run_id: str,
    phase: str,
    tool_name: str,
    mode: str,
    error: str,
) -> None:
    event = BudgetEvent(
        version=2,
        timestamp=iso_timestamp(),
        agent=agent,
        session_id=session_id,
        run_id=run_id,
        phase=phase,
        tool_name=tool_name,
        category="agent_state",
        candidate_id="error:budget",
        strategy="relevance_gate",
        decision="allow",
        mode=mode,
        estimated_tokens_before=0,
        estimated_tokens_after=0,
        estimated_tokens_saved=0,
        budget_limit=0,
        budget_used_before=0,
        budget_used_after=0,
        relevance_score=0.0,
        reason="budget engine failed open",
        replacement=None,
        error=error,
    )
    append_event(root, event)


def append_compaction_event(
    root: Path,
    *,
    agent: str,
    session_id: str,
    run_id: str,
    mode: str,
    estimated_tokens_before: int,
    estimated_tokens_after: int,
    budget_limit: int,
    reason: str,
) -> None:
    event = BudgetEvent(
        version=2,
        timestamp=iso_timestamp(),
        agent=agent,
        session_id=session_id,
        run_id=run_id,
        phase="compaction",
        tool_name="budget_compaction",
        category="session_summary",
        candidate_id=f"session:{agent}",
        strategy="pressure_compaction",
        decision="summarize",
        mode=mode,
        estimated_tokens_before=estimated_tokens_before,
        estimated_tokens_after=estimated_tokens_after,
        estimated_tokens_saved=max(0, estimated_tokens_before - estimated_tokens_after),
        budget_limit=budget_limit,
        budget_used_before=estimated_tokens_before,
        budget_used_after=estimated_tokens_after,
        relevance_score=1.0,
        reason=reason,
        replacement="compact_summary",
        error=None,
    )
    append_event(root, event)


def load_events(root: Path, *, limit: int | None = None) -> list[dict[str, object]]:
    path = events_path(root)
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    if limit is not None and limit >= 0:
        lines = lines[-limit:]
    events: list[dict[str, object]] = []
    for line in lines:
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            events.append(data)
    return events

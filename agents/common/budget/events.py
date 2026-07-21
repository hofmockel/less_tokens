"""v2 budget telemetry events."""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, replace
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
    invocation_id: str = ""
    input_characters: int = 0
    estimated_input_tokens: int = 0
    event_id: str = ""


def iso_timestamp(now: float | None = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now or time.time()))


def _event_id(*parts: str) -> str:
    event_key = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(event_key.encode("utf-8")).hexdigest()


def event_from_decision(
    decision: BudgetDecision,
    *,
    agent: str,
    session_id: str,
    run_id: str,
    phase: str,
    tool_name: str,
    mode: str,
    invocation_id: str = "",
    input_characters: int = 0,
    estimated_input_tokens: int = 0,
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
        invocation_id=invocation_id,
        input_characters=input_characters,
        estimated_input_tokens=estimated_input_tokens,
        event_id=_event_id(agent, session_id, invocation_id, phase, decision.candidate_id, decision.action),
    )


def events_path(root: Path) -> Path:
    return root / ".less_tokens" / "state" / "events.jsonl"


def append_event(root: Path, event: BudgetEvent) -> bool:
    path = events_path(root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a+", encoding="utf-8") as f:
            locked = False
            try:
                if hasattr(os, "lockf") and hasattr(os, "F_LOCK"):
                    os.lockf(f.fileno(), os.F_LOCK, 0)
                    locked = True
            except OSError:
                locked = False
            try:
                measurement_seen = False
                if event.event_id:
                    f.seek(0)
                    for existing_line in f:
                        try:
                            existing = json.loads(existing_line)
                        except json.JSONDecodeError:
                            continue
                        if existing.get("event_id") == event.event_id:
                            return False
                        if (
                            event.invocation_id
                            and existing.get("agent") == event.agent
                            and existing.get("session_id") == event.session_id
                            and existing.get("invocation_id") == event.invocation_id
                            and existing.get("phase") == event.phase
                            and int(existing.get("input_characters", 0) or 0) > 0
                        ):
                            measurement_seen = True
                if measurement_seen:
                    event = replace(event, input_characters=0, estimated_input_tokens=0)
                line = json.dumps(asdict(event), sort_keys=True) + "\n"
                f.seek(0, os.SEEK_END)
                f.write(line)
                return True
            finally:
                if locked and hasattr(os, "lockf") and hasattr(os, "F_LOCK"):
                    try:
                        os.lockf(f.fileno(), os.F_ULOCK, 0)
                    except OSError:
                        pass
    except OSError:
        return False


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
    invocation_id: str = "",
    input_characters: int = 0,
    estimated_input_tokens: int = 0,
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
        invocation_id=invocation_id,
        input_characters=input_characters,
        estimated_input_tokens=estimated_input_tokens,
        event_id=_event_id(agent, session_id, invocation_id, phase, "error:budget", "allow"),
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
    invocation_id: str = "",
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
        invocation_id=invocation_id,
        event_id=_event_id(agent, session_id, invocation_id, "compaction", f"session:{agent}", "summarize"),
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

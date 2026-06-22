"""Apply budget policy and write telemetry."""
from __future__ import annotations

from pathlib import Path

from .adapters import BudgetInput
from .config import BudgetConfig
from .events import append_event, append_failure_event, event_from_decision
from .gate import score_candidates, select_candidates
from .state import touch_session


def evaluate_budget_input(root: Path, budget_input: BudgetInput, config: BudgetConfig) -> list:
    """Evaluate budget input, append v2 telemetry, and fail open on errors."""
    try:
        touch_session(
            root,
            budget_input.agent,
            session_id=budget_input.session_id,
            run_id=budget_input.run_id,
        )
        scored = score_candidates(budget_input.candidates, query=budget_input.query)
        decisions = select_candidates(scored, config)
        for decision in decisions:
            append_event(root, event_from_decision(
                decision,
                agent=budget_input.agent,
                session_id=budget_input.session_id,
                run_id=budget_input.run_id,
                phase=budget_input.phase,
                tool_name=budget_input.tool_name,
                mode=config.mode,
            ))
        return decisions
    except Exception as exc:
        append_failure_event(
            root,
            agent=budget_input.agent,
            session_id=budget_input.session_id,
            run_id=budget_input.run_id,
            phase=budget_input.phase,
            tool_name=budget_input.tool_name,
            mode=config.mode,
            error=repr(exc),
        )
        return []

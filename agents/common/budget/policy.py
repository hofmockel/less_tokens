"""Apply budget policy and write telemetry."""
from __future__ import annotations

from pathlib import Path

from .adapters import BudgetInput
from .compaction import record_session_activity, refresh_compaction_snapshot, should_compact
from .config import BudgetConfig
from .events import append_compaction_event, append_event, append_failure_event, event_from_decision
from .gate import score_candidates, select_candidates
from .signals import build_budget_signals
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
        signal_text = "\n".join(candidate.text for candidate in budget_input.candidates if candidate.text)
        signals = build_budget_signals(root, query=budget_input.query, text=signal_text)
        scored = score_candidates(budget_input.candidates, query=budget_input.query, signals=signals)
        decisions = select_candidates(scored, config, signals=signals)
        record_session_activity(root, budget_input, decisions)
        if should_compact(decisions):
            summary = refresh_compaction_snapshot(root, budget_input.agent, config)
            append_compaction_event(
                root,
                agent=budget_input.agent,
                session_id=budget_input.session_id,
                run_id=budget_input.run_id,
                mode=config.mode,
                estimated_tokens_before=int(summary.get("estimated_tokens_before", 0) or 0),
                estimated_tokens_after=int(summary.get("estimated_tokens", 0) or 0),
                budget_limit=int(summary.get("budget_limit", config.category_limit("session_summary")) or 0),
                reason="budget pressure triggered compact session summary",
                invocation_id=budget_input.invocation_id,
            )
        for decision in decisions:
            append_event(root, event_from_decision(
                decision,
                agent=budget_input.agent,
                session_id=budget_input.session_id,
                run_id=budget_input.run_id,
                phase=budget_input.phase,
                tool_name=budget_input.tool_name,
                mode=config.mode,
                invocation_id=budget_input.invocation_id,
                input_characters=budget_input.input_characters,
                estimated_input_tokens=budget_input.estimated_input_tokens,
                strategy=_strategy_for_decision(decision),
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
            invocation_id=budget_input.invocation_id,
            input_characters=budget_input.input_characters,
            estimated_input_tokens=budget_input.estimated_input_tokens,
        )
        return []


def _strategy_for_decision(decision) -> str:
    if (
        decision.candidate_id.startswith("tool_output:")
        and decision.action in {"replace", "trim"}
        and decision.replacement
        and "summarized output" in decision.replacement
    ):
        return "dynamic_output_summary"
    return "relevance_gate"

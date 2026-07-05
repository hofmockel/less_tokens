"""Concise native hook advice for budget decisions."""
from __future__ import annotations

import json
from dataclasses import dataclass

from .decisions import BudgetDecision

MAX_ADVICE_CHARS = 600


@dataclass(frozen=True)
class HookBudgetOutcome:
    exit_code: int
    message: str | None = None
    stream: str = "stdout"


def best_advice(decisions: list[BudgetDecision]) -> BudgetDecision | None:
    actionable = [
        decision for decision in decisions
        if decision.action in {"replace", "trim", "defer", "block"} and (decision.replacement or decision.reason)
    ]
    if not actionable:
        return None
    return max(actionable, key=lambda decision: (decision.estimated_tokens_saved, decision.relevance_score))


def format_advice(decision: BudgetDecision, *, max_chars: int = MAX_ADVICE_CHARS) -> str:
    saved = decision.estimated_tokens_saved
    prefix = f"less_tokens budget: {decision.action}"
    if saved:
        prefix += f", saves ~{saved:,} tokens"
    detail = decision.replacement or decision.reason
    msg = f"{prefix}. {detail}"
    if len(msg) <= max_chars:
        return msg
    return msg[: max(0, max_chars - 1)].rstrip() + "…"


def _effective_mode(mode: str, category: str, category_modes: dict[str, str] | None) -> str:
    if category_modes and category in category_modes:
        return category_modes[category]
    return mode


def advice_for_mode(
    decisions: list[BudgetDecision], *, mode: str, category_modes: dict[str, str] | None = None,
) -> str | None:
    advisable = [d for d in decisions if _effective_mode(mode, d.category, category_modes) == "advise"]
    if not advisable:
        return None
    decision = best_advice(advisable)
    return format_advice(decision) if decision else None


def enforcement_decision(
    decisions: list[BudgetDecision], *, mode: str, category_modes: dict[str, str] | None = None,
) -> BudgetDecision | None:
    enforceable = [d for d in decisions if _effective_mode(mode, d.category, category_modes) in {"enforce", "strict"}]
    blocking_actions = {"block", "replace", "trim", "defer"}
    actionable = [
        decision for decision in enforceable
        if decision.action in blocking_actions and (decision.replacement or decision.reason)
    ]
    if not actionable:
        return None
    return max(actionable, key=lambda decision: (decision.estimated_tokens_saved, decision.relevance_score))


def outcome_for_mode(
    decisions: list[BudgetDecision], *, mode: str, category_modes: dict[str, str] | None = None,
) -> HookBudgetOutcome:
    advice = advice_for_mode(decisions, mode=mode, category_modes=category_modes)
    if advice:
        return HookBudgetOutcome(exit_code=0, message=advice, stream="stdout")
    decision = enforcement_decision(decisions, mode=mode, category_modes=category_modes)
    if decision:
        return HookBudgetOutcome(exit_code=2, message=format_advice(decision), stream="stderr")
    return HookBudgetOutcome(exit_code=0)


def claude_hook_output(message: str) -> str:
    return json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": message,
        }
    })

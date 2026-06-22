"""Concise native hook advice for budget decisions."""
from __future__ import annotations

import json

from .decisions import BudgetDecision

MAX_ADVICE_CHARS = 600


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


def advice_for_mode(decisions: list[BudgetDecision], *, mode: str) -> str | None:
    if mode != "advise":
        return None
    decision = best_advice(decisions)
    return format_advice(decision) if decision else None


def claude_hook_output(message: str) -> str:
    return json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": message,
        }
    })

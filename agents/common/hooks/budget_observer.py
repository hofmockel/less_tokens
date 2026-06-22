"""Hook transport for v2 budget telemetry and advise-mode messages."""
from __future__ import annotations

from pathlib import Path


def budget_hook_outcome(raw: dict, *, repo: Path, agent: str):
    """Record budget decisions and return a native hook outcome. Always fail open."""
    try:
        from agents.common.budget import HookBudgetOutcome, evaluate_budget_input, load_budget_config, normalize_budget_input, outcome_for_mode
    except Exception:
        try:
            from budget import HookBudgetOutcome, evaluate_budget_input, load_budget_config, normalize_budget_input, outcome_for_mode  # type: ignore[no-redef]
        except Exception:
            return None
    try:
        if _bypass_requested(raw):
            return HookBudgetOutcome(exit_code=0)
        budget_input = normalize_budget_input(raw, agent=agent)
        config = load_budget_config(repo, agent=agent)
        decisions = evaluate_budget_input(repo, budget_input, config)
        return outcome_for_mode(decisions, mode=config.mode)
    except Exception:
        return None


def observe_budget_payload(raw: dict, *, repo: Path, agent: str) -> str | None:
    outcome = budget_hook_outcome(raw, repo=repo, agent=agent)
    if outcome and outcome.exit_code == 0:
        return outcome.message
    return None


def _bypass_requested(raw: dict) -> bool:
    if raw.get("less_tokens_bypass") is True:
        return True
    tool_input = raw.get("tool_input") or {}
    if isinstance(tool_input, dict):
        if tool_input.get("less_tokens_bypass") is True:
            return True
        text = " ".join(str(value) for value in tool_input.values() if isinstance(value, str))
        if "less_tokens: allow" in text or "less_tokens: bypass" in text:
            return True
    return False

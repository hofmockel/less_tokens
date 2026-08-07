"""Hook transport for v2 budget telemetry and advise-mode messages."""

from __future__ import annotations

from pathlib import Path


def budget_hook_outcome(raw: dict, *, repo: Path, agent: str):
    """Record budget decisions and return a native hook outcome. Always fail open."""
    try:
        from agents.common.budget import (
            HookBudgetOutcome,
            evaluate_budget_input,
            load_budget_config,
            normalize_budget_input,
            outcome_for_mode,
        )
        from agents.common.budget.advice import best_advice
        from agents.common.budget.state import resolve_state_root, should_emit_advice
    except Exception:
        try:
            from budget import (
                HookBudgetOutcome,
                evaluate_budget_input,
                load_budget_config,
                normalize_budget_input,
                outcome_for_mode,
            )  # type: ignore[no-redef]
            from budget.advice import best_advice  # type: ignore[no-redef]
            from budget.state import resolve_state_root, should_emit_advice  # type: ignore[no-redef]
        except Exception:
            return None
    try:
        if _bypass_requested(raw):
            return HookBudgetOutcome(exit_code=0)
        budget_input = normalize_budget_input(raw, agent=agent)
        config = load_budget_config(repo, agent=agent)
        # Telemetry/session state (events, advice rate-limits) is written under
        # resolve_state_root, which honors LESS_TOKENS_STATE_DIR — repo stays the
        # config source of truth and is never redirected by that override.
        state_root = resolve_state_root(repo)
        decisions = evaluate_budget_input(state_root, budget_input, config)
        outcome = outcome_for_mode(
            decisions, mode=config.mode, category_modes=config.category_modes
        )
        # Rate-limit any advisory message (exit_code 0 + message), not just
        # ones from the global mode — a category_modes override can produce
        # advice while the global mode stays "observe".
        if outcome.exit_code == 0 and outcome.message:
            decision = best_advice(decisions)
            key = f"{agent}:{budget_input.phase}:{budget_input.tool_name}:{decision.candidate_id if decision else outcome.message}"
            if not should_emit_advice(state_root, key):
                return HookBudgetOutcome(exit_code=0)
        return outcome
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
        text = " ".join(
            str(value) for value in tool_input.values() if isinstance(value, str)
        )
        if "less_tokens: allow" in text or "less_tokens: bypass" in text:
            return True
    return False

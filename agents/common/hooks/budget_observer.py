"""Hook transport for v2 budget telemetry and advise-mode messages."""
from __future__ import annotations

from pathlib import Path


def observe_budget_payload(raw: dict, *, repo: Path, agent: str) -> str | None:
    """Record budget decisions and return optional advice. Always fail open."""
    try:
        from agents.common.budget import advice_for_mode, evaluate_budget_input, load_budget_config, normalize_budget_input
    except Exception:
        try:
            from budget import advice_for_mode, evaluate_budget_input, load_budget_config, normalize_budget_input  # type: ignore[no-redef]
        except Exception:
            return None
    try:
        budget_input = normalize_budget_input(raw, agent=agent)
        config = load_budget_config(repo, agent=agent)
        decisions = evaluate_budget_input(repo, budget_input, config)
        return advice_for_mode(decisions, mode=config.mode)
    except Exception:
        return None

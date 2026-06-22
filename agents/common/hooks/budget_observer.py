"""Hook transport for v2 budget telemetry in observe mode."""
from __future__ import annotations

from pathlib import Path


def observe_budget_payload(raw: dict, *, repo: Path, agent: str) -> None:
    """Record budget decisions for a native hook payload and always fail open."""
    try:
        from agents.common.budget import evaluate_budget_input, load_budget_config, normalize_budget_input
    except Exception:
        try:
            from budget import evaluate_budget_input, load_budget_config, normalize_budget_input  # type: ignore[no-redef]
        except Exception:
            return
    try:
        budget_input = normalize_budget_input(raw, agent=agent)
        config = load_budget_config(repo, agent=agent)
        evaluate_budget_input(repo, budget_input, config)
    except Exception:
        return

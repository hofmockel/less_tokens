"""Budget-native context control primitives for less_tokens."""
from __future__ import annotations

from .adapters import BudgetInput, normalize_budget_input
from .advice import HookBudgetOutcome, advice_for_mode, format_advice, outcome_for_mode
from .candidates import ContextCandidate
from .config import BudgetConfig, load_budget_config
from .decisions import BudgetDecision
from .events import BudgetEvent, append_event, load_events
from .gate import score_candidates, select_candidates
from .policy import evaluate_budget_input
from .signals import BudgetSignals, build_budget_signals

__all__ = [
    "BudgetConfig",
    "BudgetDecision",
    "BudgetEvent",
    "BudgetInput",
    "HookBudgetOutcome",
    "BudgetSignals",
    "ContextCandidate",
    "append_event",
    "advice_for_mode",
    "build_budget_signals",
    "evaluate_budget_input",
    "format_advice",
    "outcome_for_mode",
    "load_budget_config",
    "load_events",
    "normalize_budget_input",
    "score_candidates",
    "select_candidates",
]

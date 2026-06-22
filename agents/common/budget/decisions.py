"""Budget decisions produced by policy and gate evaluation."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetDecision:
    action: str
    category: str
    candidate_id: str
    estimated_tokens_before: int
    estimated_tokens_after: int
    budget_limit: int
    budget_used_before: int = 0
    budget_used_after: int = 0
    relevance_score: float = 0.0
    reason: str = ""
    replacement: str | None = None
    error: str | None = None

    @property
    def estimated_tokens_saved(self) -> int:
        return max(0, self.estimated_tokens_before - self.estimated_tokens_after)

    def allowed(self) -> bool:
        return self.action in {"allow", "warn"}

"""Budget configuration loading and defaults."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_BUDGET_CONFIG: dict[str, Any] = {
    "version": 2,
    "mode": "observe",
    "token_estimator": "chars_div_4",
    "total_context_tokens": 24000,
    "reserved_response_tokens": 4000,
    "relevance_threshold": 0.35,
    "replacement_required_for_blocks": True,
    "categories": {
        "instructions": 3000,
        "current_request": 2000,
        "session_summary": 3000,
        "retrieved_context": 10000,
        "tool_output": 4000,
        "diffs": 3000,
        "agent_state": 2000,
    },
    "hard_caps": {
        "full_file_read": 3000,
        "single_tool_output": 2500,
        "directory_listing": 1000,
        "unscored_context": 1200,
    },
    "category_modes": {},
    "agent_overrides": {
        "claude": {},
        "codex": {
            "categories": {
                "retrieved_context": 6000,
                "tool_output": 2000,
                "diffs": 1500,
            },
            "hard_caps": {
                "full_file_read": 2000,
                "single_tool_output": 1500,
                "directory_listing": 600,
            },
        },
    },
}


@dataclass(frozen=True)
class BudgetConfig:
    version: int
    mode: str
    token_estimator: str
    total_context_tokens: int
    reserved_response_tokens: int
    relevance_threshold: float
    replacement_required_for_blocks: bool
    categories: dict[str, int]
    hard_caps: dict[str, int]
    category_modes: dict[str, str]
    agent_overrides: dict[str, dict[str, Any]]

    def category_limit(self, category: str) -> int:
        return int(self.categories.get(category, self.hard_caps.get("unscored_context", 1200)))

    def effective_mode(self, category: str) -> str:
        """Per-category mode override, falling back to the global mode. Lets a
        single narrow category (e.g. unscored_context) move to advise/enforce
        without changing behavior anywhere else — see eb_plan_4jul26.md Strategy 2."""
        return self.category_modes.get(category, self.mode)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def default_budget_config_text() -> str:
    return json.dumps(DEFAULT_BUDGET_CONFIG, indent=2) + "\n"


def load_budget_config(root: Path, *, agent: str | None = None) -> BudgetConfig:
    path = root / ".less_tokens" / "config" / "budget.json"
    data = dict(DEFAULT_BUDGET_CONFIG)
    try:
        if path.exists():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = _deep_merge(data, loaded)
    except (OSError, json.JSONDecodeError):
        data = dict(DEFAULT_BUDGET_CONFIG)

    if agent:
        overrides = data.get("agent_overrides", {}).get(agent, {})
        if isinstance(overrides, dict):
            data = _deep_merge(data, overrides)

    return BudgetConfig(
        version=int(data.get("version", 2)),
        mode=str(data.get("mode", "observe")),
        token_estimator=str(data.get("token_estimator", "chars_div_4")),
        total_context_tokens=int(data.get("total_context_tokens", 24000)),
        reserved_response_tokens=int(data.get("reserved_response_tokens", 4000)),
        relevance_threshold=float(data.get("relevance_threshold", 0.35)),
        replacement_required_for_blocks=bool(data.get("replacement_required_for_blocks", True)),
        categories={str(k): int(v) for k, v in dict(data.get("categories", {})).items()},
        hard_caps={str(k): int(v) for k, v in dict(data.get("hard_caps", {})).items()},
        category_modes={str(k): str(v) for k, v in dict(data.get("category_modes", {})).items()},
        agent_overrides=dict(data.get("agent_overrides", {})),
    )

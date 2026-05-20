"""Claude model context-window + recommended search-k lookup table.

Keyed by user-facing model IDs that `search_config.AGENT_MODEL` accepts.
Values come from public Anthropic context-window docs; `recommended_k`
is a conservative heuristic — enough chunks to be useful, few enough to
leave room for the user's task in-context.

Add new model IDs here as Anthropic ships them; the search default
falls back to `DEFAULT_K` when AGENT_MODEL is unset or not in the map.
"""
from __future__ import annotations

# context_window: total tokens the model accepts.
# recommended_k: default `k` for tools/search.py when AGENT_MODEL is set.
MODEL_PROFILES: dict[str, dict[str, int]] = {
    # Haiku — fast, small window: keep search lean.
    "claude-haiku-3-5":   {"context_window": 200_000, "recommended_k": 3},
    "claude-haiku-4-5":   {"context_window": 200_000, "recommended_k": 3},
    # Sonnet — balanced, our common default.
    "claude-sonnet-3-5":  {"context_window": 200_000, "recommended_k": 5},
    "claude-sonnet-3-7":  {"context_window": 200_000, "recommended_k": 5},
    "claude-sonnet-4-0":  {"context_window": 200_000, "recommended_k": 5},
    "claude-sonnet-4-5":  {"context_window": 200_000, "recommended_k": 5},
    "claude-sonnet-4-6":  {"context_window": 1_000_000, "recommended_k": 8},
    # Opus — biggest budget, can afford a wider funnel.
    "claude-opus-3":      {"context_window": 200_000, "recommended_k": 5},
    "claude-opus-4-0":    {"context_window": 200_000, "recommended_k": 8},
    "claude-opus-4-5":    {"context_window": 200_000, "recommended_k": 8},
    "claude-opus-4-7":    {"context_window": 200_000, "recommended_k": 8},
}


def profile(model: str | None) -> dict[str, int] | None:
    """Return the profile dict for `model`, or None if unknown/unset."""
    if not model:
        return None
    return MODEL_PROFILES.get(model)

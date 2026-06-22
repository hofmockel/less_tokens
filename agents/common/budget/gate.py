"""Relevance scoring and budget selection."""
from __future__ import annotations

import re
from pathlib import Path

from .candidates import ContextCandidate
from .config import BudgetConfig
from .decisions import BudgetDecision


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[A-Za-z0-9_./-]+", text) if len(t) > 2}


def score_candidate(candidate: ContextCandidate, *, query: str = "", recent_paths: set[str] | None = None) -> ContextCandidate:
    recent_paths = recent_paths or set()
    haystack = " ".join(
        str(part)
        for part in (candidate.path, candidate.candidate_id, candidate.text[:4000])
        if part
    )
    query_tokens = _tokens(query)
    hay_tokens = _tokens(haystack)
    lexical = 0.0
    if query_tokens:
        lexical = min(1.0, len(query_tokens & hay_tokens) / max(1, len(query_tokens)))

    explicit = 0.0
    if candidate.path and candidate.path in query:
        explicit = 1.0
    elif candidate.path and Path(candidate.path).name in query:
        explicit = 0.75

    recency = 1.0 if candidate.path and candidate.path in recent_paths else 0.0
    structural = 0.0
    if candidate.path:
        name = Path(candidate.path).name
        if name in {"pyproject.toml", "package.json", "README.md", "CLAUDE.md", "AGENTS.md"}:
            structural = 0.8
        elif "/tests/" in candidate.path or name.startswith("test_"):
            structural = 0.65

    failure = 1.0 if re.search(r"(Traceback|AssertionError|failed|error:)", candidate.text, re.I) else 0.0
    semantic = float(candidate.metadata.get("semantic_similarity", 0.0) or 0.0)

    score = (
        explicit * 0.25
        + semantic * 0.25
        + lexical * 0.20
        + recency * 0.15
        + structural * 0.10
        + failure * 0.05
    )
    reasons = []
    if explicit:
        reasons.append("explicit reference")
    if lexical:
        reasons.append("lexical match")
    if recency:
        reasons.append("recent path")
    if structural:
        reasons.append("structural file")
    if failure:
        reasons.append("failure output")
    reason = ", ".join(reasons) if reasons else "low relevance signal"
    return candidate.with_estimate().scored(score, reason)


def score_candidates(
    candidates: list[ContextCandidate],
    *,
    query: str = "",
    recent_paths: set[str] | None = None,
) -> list[ContextCandidate]:
    return [score_candidate(c, query=query, recent_paths=recent_paths) for c in candidates]


def _replacement_for(candidate: ContextCandidate, config: BudgetConfig) -> str | None:
    if candidate.candidate_type == "file" and candidate.path:
        limit = max(40, min(200, int(config.hard_caps.get("full_file_read", 3000) / 12)))
        return f"Read a targeted slice from {candidate.path} with limit {limit}."
    if candidate.candidate_type == "tool_output":
        return "Keep commands, paths, stack traces, assertions, and summarize repetitive output."
    if candidate.candidate_type == "directory_listing":
        return "Use a narrower glob or list one relevant subdirectory."
    return candidate.replacement


def select_candidates(candidates: list[ContextCandidate], config: BudgetConfig) -> list[BudgetDecision]:
    scored = sorted(
        (c.with_estimate() for c in candidates),
        key=lambda c: (c.relevance_score / max(c.estimated_tokens, 1), c.relevance_score),
        reverse=True,
    )
    used_by_category: dict[str, int] = {}
    decisions: list[BudgetDecision] = []
    for candidate in scored:
        category_limit = config.category_limit(candidate.category)
        used_before = used_by_category.get(candidate.category, 0)
        hard_cap = config.hard_caps.get(
            "single_tool_output" if candidate.candidate_type == "tool_output" else "full_file_read",
            category_limit,
        )
        replacement = _replacement_for(candidate, config)

        if candidate.relevance_score < config.relevance_threshold:
            action = "defer" if config.mode in {"observe", "advise"} else "block"
            after = 0
            reason = candidate.reason or "below relevance threshold"
        elif candidate.estimated_tokens > hard_cap:
            action = "replace" if replacement else "trim"
            after = min(candidate.estimated_tokens, hard_cap)
            reason = f"candidate exceeds hard cap {hard_cap}"
        elif used_before + candidate.estimated_tokens > category_limit:
            action = "defer" if config.mode in {"observe", "advise"} else "block"
            after = 0
            reason = f"{candidate.category} budget would exceed {category_limit}"
        else:
            action = "allow"
            after = candidate.estimated_tokens
            reason = candidate.reason or "within budget"

        if action == "allow":
            used_by_category[candidate.category] = used_before + after
        decisions.append(BudgetDecision(
            action=action,
            category=candidate.category,
            candidate_id=candidate.candidate_id,
            estimated_tokens_before=candidate.estimated_tokens,
            estimated_tokens_after=after,
            budget_limit=category_limit,
            budget_used_before=used_before,
            budget_used_after=used_by_category.get(candidate.category, used_before),
            relevance_score=candidate.relevance_score,
            reason=reason,
            replacement=replacement if action in {"replace", "block", "defer", "trim"} else None,
        ))
    return decisions

"""Relevance scoring and budget selection."""
from __future__ import annotations

import re
from pathlib import Path

from .candidates import ContextCandidate
from .config import BudgetConfig
from .decisions import BudgetDecision
from .estimator import estimate_tokens
from .signals import BudgetSignals, first_search_range, path_matches
from .summarizer import summarize_tool_output


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[A-Za-z0-9_./-]+", text) if len(t) > 2}


def score_candidate(
    candidate: ContextCandidate,
    *,
    query: str = "",
    recent_paths: set[str] | None = None,
    signals: BudgetSignals | None = None,
) -> ContextCandidate:
    recent_paths = recent_paths or set()
    if signals:
        recent_paths = recent_paths | signals.recent_paths
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
    if signals and path_matches(candidate.path, signals.explicit_references):
        explicit = max(explicit, 1.0)
    search_span = first_search_range(candidate.path, signals) if signals else None
    if search_span:
        explicit = max(explicit, 0.75)

    recency = 1.0 if candidate.path and path_matches(candidate.path, recent_paths) else 0.0
    structural = 0.0
    if candidate.path:
        name = Path(candidate.path).name
        if name in {"pyproject.toml", "package.json", "README.md", "CLAUDE.md", "AGENTS.md"}:
            structural = 0.8
        elif "/tests/" in candidate.path or name.startswith("test_"):
            structural = 0.65

    failure = 1.0 if re.search(r"(Traceback|AssertionError|failed|error:)", candidate.text, re.I) else 0.0
    if signals and (path_matches(candidate.path, signals.stack_trace_paths) or path_matches(candidate.path, signals.failure_paths)):
        failure = 1.0
    semantic = float(candidate.metadata.get("semantic_similarity", 0.0) or 0.0)
    if search_span:
        semantic = max(semantic, 0.85)

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
    if semantic:
        reasons.append("search hit")
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
    signals: BudgetSignals | None = None,
) -> list[ContextCandidate]:
    return [score_candidate(c, query=query, recent_paths=recent_paths, signals=signals) for c in candidates]


def _replacement_for(candidate: ContextCandidate, config: BudgetConfig, signals: BudgetSignals | None = None) -> str | None:
    span = first_search_range(candidate.path, signals) if signals else None
    if span and candidate.path:
        limit = max(1, span.end - span.start + 1)
        return f"Read only lines {span.start}-{span.end} from {candidate.path} with offset {span.start} and limit {limit}."
    if candidate.candidate_type == "file" and candidate.path:
        limit = max(40, min(200, int(config.hard_caps.get("full_file_read", 3000) / 12)))
        return f"Read a targeted slice from {candidate.path} with limit {limit}."
    if candidate.candidate_type == "tool_output":
        summary = summarize_tool_output(
            candidate.text,
            command=str(candidate.metadata.get("command") or ""),
            max_chars=max(1000, int(config.hard_caps.get("single_tool_output", 2500) * 4)),
        )
        return "Use this summarized output instead:\n" + summary
    if candidate.candidate_type == "directory_listing":
        return "Use a narrower glob, `find <dir> -maxdepth 2`, or list one relevant subdirectory."
    return candidate.replacement


def _forced_decision(candidate: ContextCandidate, config: BudgetConfig, signals: BudgetSignals | None) -> tuple[str, int, str, str | None] | None:
    replacement = _replacement_for(candidate, config, signals)
    if signals and candidate.metadata.get("read_key") in signals.repeated_read_keys:
        return "block", 0, "repeated unchanged read already in context", replacement or "Skip this read; unchanged content is already in context."
    if signals and candidate.metadata.get("search_key") in signals.repeated_search_keys:
        return "block", 0, "repeated search already in context", "Skip this search; recent results are already in context."
    if candidate.candidate_type == "directory_listing":
        return "block", 0, "broad directory listing would produce low-value output", replacement
    if (
        config.mode == "strict"
        and candidate.relevance_score <= 0
        and candidate.estimated_tokens > config.hard_caps.get("unscored_context", 1200)
    ):
        return "block", 0, "unscored context exceeds hard cap", replacement or "Search or narrow the request before adding this context."
    return None


def select_candidates(candidates: list[ContextCandidate], config: BudgetConfig, *, signals: BudgetSignals | None = None) -> list[BudgetDecision]:
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
        replacement = _replacement_for(candidate, config, signals)
        forced = _forced_decision(candidate, config, signals)

        oversized_tool_output = candidate.candidate_type == "tool_output" and candidate.estimated_tokens > hard_cap

        if forced:
            action, after, reason, replacement = forced
        elif oversized_tool_output:
            action = "replace" if replacement else "trim"
            after = min(estimate_tokens(replacement or "", content_type="logs"), hard_cap) if replacement else hard_cap
            reason = f"candidate exceeds hard cap {hard_cap}"
        elif candidate.relevance_score < config.relevance_threshold:
            action = "defer" if config.mode in {"observe", "advise"} else "block"
            after = 0
            reason = candidate.reason or "below relevance threshold"
        elif candidate.estimated_tokens > hard_cap:
            action = "replace" if replacement else "trim"
            if candidate.candidate_type == "tool_output" and replacement:
                after = min(estimate_tokens(replacement, content_type="logs"), hard_cap)
            else:
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

#!/usr/bin/env python3
"""Canonical registry for the bug-hunt protocol's CODE-MODE defaults for this repo.

Single source of truth for less_tokens' own severity tiers, target files,
stop-rule thresholds, and agent prompt template — i.e. what a hunt against
*this* repo looks like once bug-hunt-protocol.md's mode detection (see
protocol_mode.py) lands on code mode. Consumed by:
- hunt_score.py (stop-rule scorer)
- hunt_round.py (round validator/appender)
- bug_hunt_docs.py (renders the code-mode section of agents/common/bug-hunt-protocol.md)

Changing a tier, a target file, or a threshold means editing this file
once — every consumer stays in sync automatically.

Docs mode has no equivalent registry: bug-hunt-protocol.md is delivered to other
repos as a portable skill, and there is no "target Markdown file list to regenerate
from" for a repo this one has never seen. Docs-mode content in the protocol doc is
therefore hand-authored generic prose, not generated from data here. See
bug_hunt_docs.py's module docstring for the render-time split.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeverityTier:
    key: str
    label: str
    definition: str
    example: str


# Ordered worst -> best. hunt_score.py treats an unrecognized median_severity
# as worst-case, so index 0 must stay the worst tier.
SEVERITY_TIERS: tuple[SeverityTier, ...] = (
    SeverityTier(
        key="data_loss",
        label="data-loss",
        definition="Index corrupted or wrong results returned silently; token savings tracked incorrectly.",
        example="UPSERT collision clobbers a different file's embedding; duplicate source_key silently dropped.",
    ),
    SeverityTier(
        key="silent",
        label="silent",
        definition="Behavior is wrong but no immediate data loss; results or counts are misleading.",
        example="search() returns stale-model rows; savings stats under-count due to off-by-one in char math.",
    ),
    SeverityTier(
        key="ux",
        label="ux",
        definition="Hook gives bad signal, false block, or noise that trains the user to ignore it.",
        example="search-first blocks when a search did run; truncate hook logs savings when disabled.",
    ),
    SeverityTier(
        key="cosmetic",
        label="cosmetic",
        definition="Wording / formatting / log-line issue. No functional impact.",
        example="(none documented yet — surface only if encountered.)",
    ),
)

SEVERITY_ORDER: tuple[str, ...] = tuple(t.key for t in SEVERITY_TIERS)

# High-yield target files for coverage tracking (bare filenames — matched
# against bughuntlog.jsonl's "new_files" entries by basename). Verified to
# exist on disk; re-verify before adding an entry.
TARGET_FILES: frozenset[str] = frozenset(
    {
        "embeddings.py",
        "search.py",
        "search_config.py",
        "model_profiles.py",
        "stats.py",
        "savings_log.py",
        "db.py",
        "caveman-reminder.py",
        "search-first.py",
        "truncate-output.py",
        "index-refresh.py",
        "compact-trigger.py",
        "budget-observer.py",
        "install.py",
        "hunt_score.py",
    }
)

OVERLAP_THRESHOLD = 0.60
COVERAGE_THRESHOLD = 0.80

PROMPT_TEMPLATE = """\
Find 10 real, undocumented bugs in $REPO_ROOT (this repo — less_tokens).
- Read BACKLOG.md ## Bugs section first; do NOT pre-exclude (overlap is a signal we want to measure).
- Bug definition: logic / silent failure / state / docstring drift / schema / encoding / hook-ordering.
- NOT bugs: features, refactors, "add tests", performance unless incorrect, anything in non-Bugs backlog sections.
- Method: search-first for indexed files; read whole files for high-yield targets; verify each candidate by tracing or sqlite3 query; rank by severity tier.
- Output: 10 bugs in `**Bug N: title** (file:line)` + What/Why/Repro/Fix format, ≤6 lines each. If <10 solid, surface fewer + say so."""

ROUND_REQUIRED_KEYS: tuple[str, ...] = (
    "round",
    "date",
    "bugs_surfaced",
    "severity",
    "median_severity",
    "overlap",
    "new_files",
)

#!/usr/bin/env python3
"""Canonical registry for README.md's strategy table.

Single source of truth for the strategy rows rendered by strategy_table_docs.py
and validated by label_consistency_gate.py. Adding or changing a strategy means
editing STRATEGIES here once — both consumers stay in sync automatically.

``registry_key`` names the savings_log._KNOWN_STRATEGIES key backing a savings
claim, or None if the strategy is real but categorically unmeasured (no
savings.jsonl category by design — the ``savings`` text must then carry an
honesty marker such as "not telemetry-backed").
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyRow:
    name: str
    how: str
    savings: str
    flag: str
    registry_key: str | None


STRATEGIES: tuple[StrategyRow, ...] = (
    StrategyRow(
        name="Budget control plane",
        how="Scores, replaces, defers, or blocks context before it enters the agent transcript; writes v2 telemetry and reports",
        savings="avoids irrelevant context before it is paid for",
        flag="always on",
        registry_key=None,
    ),
    StrategyRow(
        name="Vector search + symbols",
        how="Pre-embeds source files; exact symbol lookup for Python and JS/TS via `symbols.py` (`/def` only when slash commands are installed)",
        savings="5–10× fewer input tokens",
        flag="always on",
        registry_key="search",
    ),
    StrategyRow(
        name="Read guards",
        how="Search-first, auto-slice, grep-first, noise-file, context-cache, and post-edit reread gates",
        savings="large-file Reads become small slices",
        flag="always on",
        registry_key=None,
    ),
    StrategyRow(
        name="Lean tool output",
        how="Parses pytest/ruff/eslint/git output and blocks recursive listing dumps",
        savings="40–90% fewer tool-output chars (not telemetry-backed — no savings.jsonl category)",
        flag="always on",
        registry_key=None,
    ),
    StrategyRow(
        name="Terse output mode",
        how="Claude Stop hook and Codex terse reminder reduce filler prose",
        savings="not yet measured against a versioned workload (`verbose_final_response` in the [conformance matrix](#conformance-matrix))",
        flag="default; opt out with `--no-caveman`",
        registry_key=None,
    ),
    StrategyRow(
        name="Tool output truncation",
        how="PostToolUse hook caps oversized Bash/Read/WebFetch/filesystem results",
        savings="Claude: 80% of chars elided in one live-captured session ([`noisy_command_output:claude`](#conformance-matrix)); Codex: adapter exists but unwired, not enforced (same workload, `configured: false`)",
        flag="default; opt out with `--no-truncate`",
        registry_key="truncation",
    ),
    StrategyRow(
        name="Compaction trigger",
        how="PostToolUse hook nudges `/compact` (Claude) or a fresh/compacted session (Codex) when session transcript grows large",
        savings="advisory only, not measured savings — Claude hook fires a nudge with no post-compaction size check; a bounded Codex probe measured 19,533→6,588 tokens on a synthetic thread via an experimental app-server method the installed hook can't invoke ([`long_session_compaction`](#conformance-matrix))",
        flag="default; opt out with `--no-compact`",
        registry_key="compaction",
    ),
    StrategyRow(
        name="Instruction pruning",
        how="`CLAUDE.md` and `AGENTS.md` budget audits keep always-loaded files small",
        savings="eliminates per-turn always-loaded tax",
        flag="always on",
        registry_key=None,
    ),
)

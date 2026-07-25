#!/usr/bin/env python3
"""Build the dependency-light less_tokens HTML documentation site."""
from __future__ import annotations

import argparse
import ast
import html
import importlib.util
import json
import os
import re
import shutil
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "docs-site"
SITE = DOCS / "site"
GENERATED = SITE / "generated"
ASSETS = SITE / "assets"
NOUN_ICON_SOURCE = DOCS / "assets" / "noun-icons"

sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / ".claude" / "tools"))

from agents.common.budget.config import DEFAULT_BUDGET_CONFIG  # noqa: E402
from agents.common.hooks.hook_manifest import HOOK_SPECS  # noqa: E402


def load_strategy_registry() -> Any:
    path = REPO / ".claude" / "tools" / "strategy_registry.py"
    spec = importlib.util.spec_from_file_location("strategy_registry", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["strategy_registry"] = module
    spec.loader.exec_module(module)
    return module.STRATEGIES


def load_stats_module() -> Any:
    """Load the shipped telemetry renderer without importing local telemetry."""
    path = REPO / ".claude" / "tools" / "stats.py"
    spec = importlib.util.spec_from_file_location("less_tokens_stats", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["less_tokens_stats"] = module
    spec.loader.exec_module(module)
    return module


def telemetry_example_html() -> str:
    """Render sanitized example data through the real user-facing report UI."""
    stats = load_stats_module()
    session = [
        {"strategy": "truncation", "elided_chars": 6200},
        {"strategy": "truncation", "elided_chars": 5700},
        {"strategy": "truncation", "elided_chars": 6200},
        {"strategy": "context-cache-read", "elided_chars": 9000},
        {"strategy": "compaction", "elided_chars": 42000},
        {"strategy": "search-blocked", "elided_chars": 11300},
        {"strategy": "search-blocked", "elided_chars": 11300},
        {"strategy": "search", "elided_chars": 20300},
    ]
    all_time = session + [
        {"strategy": "truncation", "elided_chars": 28100},
        {"strategy": "context-cache-read", "elided_chars": 17200},
        {"strategy": "search", "elided_chars": 50400},
    ]
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Token Savings Report — Representative Example</title>
<style>{stats._HTML_STYLE}
.demo{{border-left:4px solid #2457e6;padding-left:.75rem}}
</style></head><body>
<h1>Token Savings Report</h1>
<p class="gen">Representative example · <span class="badge">chars÷4 uncalibrated</span></p>
<p class="intro demo"><strong>This is the report users see.</strong> The values are sanitized example data; the structure, labels, separation of measured savings from optimistic upper bounds, and styling come from the shipped <code>stats.py --html</code> renderer.</p>
{stats._html_block("Current session (8 events)", session)}
{stats._html_block("All-time (11 events)", all_time)}
<p class="footer">tokens est. at chars÷4 (uncalibrated)</p>
</body></html>
"""


STRATEGY_DETAILS: dict[str, dict[str, Any]] = {
    "budget-control-plane": {
        "title": "Budget Control Plane",
        "bucket": "input",
        "hooks": ["budget-observer"],
        "source": "agents/common/budget/policy.py",
        "problem": "Raw context can enter the transcript before anyone asks whether it is relevant enough to pay for.",
        "flow": "Normalize candidates, score them, select allow/defer/replace/block decisions, emit telemetry, and refresh compaction snapshots when pressure is high.",
        "failure": "Runs fail-open on internal errors, so broken budget code should be visible in telemetry checks rather than interrupting work.",
        "telemetry": ".less_tokens/state/events.jsonl records v2 budget decisions; local records are never published by default.",
        "tests": ".claude/tests/unit/test_budget_core.py and .claude/tests/unit/test_budget_observer.py",
    },
    "search-first": {
        "title": "Search First",
        "bucket": "input",
        "hooks": ["search-first"],
        "source": "agents/common/hooks/search_first.py",
        "problem": "Whole-file reads are often a costly substitute for asking where the answer lives.",
        "flow": "A broad read is blocked until a recent search or targeted slice exists, nudging the agent toward semantic chunks first.",
        "failure": "Bypass is available when broad context is truly needed; stale or absent search state should produce concise advice.",
        "telemetry": "Search-blocked savings are recorded in the legacy savings log when broad reads are prevented.",
        "tests": ".claude/tests/unit/test_search_first_docstring.py and .claude/tests/unit/test_hooks_protocol.py",
    },
    "vector-search-symbols": {
        "title": "Vector Search And Symbols",
        "bucket": "input",
        "hooks": [],
        "source": ".claude/tools/search.py",
        "problem": "Exploration gets expensive when code discovery depends on repeated grep dumps or full-file reads.",
        "flow": "Structured chunks are embedded locally, ranked by semantic query, and paired with exact symbol lookup for definitions.",
        "failure": "Empty indexes, model download failures, and stale rows are surfaced through refresh and troubleshooting checks.",
        "telemetry": "Search savings compare returned chunk size with matched source-file size using chars divided by four.",
        "tests": ".claude/tests/unit/test_search_dedup.py, .claude/tests/unit/test_symbols.py, and chunker tests",
    },
    "read-guards": {
        "title": "Read Guards",
        "bucket": "input",
        "hooks": ["read-guard", "auto-slice", "grep-first-read", "read-after-edit"],
        "source": "agents/common/hooks/read_guard.py",
        "problem": "Generated files, lockfiles, and broad reads can flood the transcript with low-value text.",
        "flow": "Noise-file checks, grep-before-read guidance, auto-slicing, and post-edit reread gates shape file access before tokens are spent.",
        "failure": "Guards are conservative and should explain the narrower command or bypass path.",
        "telemetry": "Read-shaping events appear through savings logs and budget-plane candidate decisions.",
        "tests": ".claude/tests/unit/test_read_guard.py, test_auto_slice.py, test_grep_first_read.py",
    },
    "context-cache": {
        "title": "Context Cache",
        "bucket": "input",
        "hooks": ["context-cache"],
        "source": "agents/common/hooks/context_cache.py",
        "problem": "Agents often reread or re-search unchanged context already present in the session.",
        "flow": "Recent read, grep, and bash fingerprints are remembered so repeated context can be skipped or summarized.",
        "failure": "Near-miss telemetry identifies useful cache-key widening without silently hiding new information.",
        "telemetry": "context-cache-read, context-cache-grep, and context-cache-bash savings are legacy log keys.",
        "tests": ".claude/tests/unit/test_context_cache.py",
    },
    "lean-output-truncation": {
        "title": "Lean Output And Truncation",
        "bucket": "tool",
        "hooks": ["lean-output", "listing-guard", "truncate-output"],
        "source": "agents/common/hooks/truncate_output.py",
        "problem": "Test runs, recursive listings, and large command outputs can dwarf the useful signal.",
        "flow": "Known command outputs are summarized, recursive listings are blocked, and oversized outputs keep useful head/tail context.",
        "failure": "Errors should remain visible in tails; truncation can be opted out for debugging.",
        "telemetry": "Truncation is measured in savings.jsonl; lean parsers are qualitative unless paired with truncation.",
        "tests": ".claude/tests/unit/test_truncate_output_updated_tool_output.py and listing guard tests",
    },
    "terse-output": {
        "title": "Terse Output",
        "bucket": "output",
        "hooks": ["terse-output"],
        "source": "agents/common/hooks/response_budget.py",
        "problem": "Verbose final answers spend output tokens and train agents toward filler.",
        "flow": "Claude uses Stop hooks; Codex uses a best-effort reminder after tools to keep responses concise.",
        "failure": "Document drafts are explicitly exempted because the user asked for long-form text.",
        "telemetry": "Output savings are not benchmarked because there is no reliable baseline response to diff against.",
        "tests": ".claude/tests/unit/test_caveman_reminder.py",
    },
    "compaction": {
        "title": "Compaction",
        "bucket": "input",
        "hooks": ["compact-trigger"],
        "source": "agents/common/hooks/compact_trigger.py",
        "problem": "Long transcripts become an always-growing input tax.",
        "flow": "Session-size nudges and budget-pressure snapshots prompt compaction before context pressure dominates.",
        "failure": "Compaction savings are estimates unless a before/after transcript shrink is measured.",
        "telemetry": "Legacy compaction savings and v2 pressure_compaction events are reported separately.",
        "tests": ".claude/tests/unit/test_compaction_emitter.py and budget compaction tests",
    },
    "instruction-pruning": {
        "title": "Instruction Pruning",
        "bucket": "fixed",
        "hooks": ["agent-md-budget"],
        "source": ".claude/tools/instruction_prune.py",
        "problem": "Always-loaded instruction files charge every turn, even when most guidance is irrelevant.",
        "flow": "AGENTS.md and CLAUDE.md stay short, with durable detail moved into skills or indexed docs.",
        "failure": "Budget hooks block stale references and oversized edits; audits point to the offending sections.",
        "telemetry": "No per-event savings log exists; the gain is reduced fixed prompt cost.",
        "tests": ".claude/tests/unit/test_agentsmd_budget_hook.py and claudemd audit tests",
    },
}


SLIDES: list[tuple[str, str, str]] = [
    ("title", "less_tokens", "A token-control layer for coding agents: search first, read narrowly, summarize noisy output, and keep fixed instructions small."),
    ("waste-model", "The Waste Model", "Input, output, tool output, and fixed instructions all compound. The site separates which strategy attacks which bucket."),
    ("input-dominates", "Why Input Dominates", "Full-file reads, repeated context, and transcript growth silently become the largest bill in long engineering sessions."),
    ("product-promise", "Product Promise", "Search first, slice narrowly, summarize or block waste, then prove it with local telemetry."),
    ("system-map", "System Map", "Installer, hooks, index, budget plane, telemetry, skills, and generated docs work together rather than as one-off scripts."),
    ("strategy-matrix", "Strategy Matrix", "Every strategy has a bucket, source file, parity status, and telemetry honesty label."),
    ("search-workflow", "Search First Workflow", "Question to semantic chunks to targeted read: the cheap path becomes the default path."),
    ("chunking", "Structural Chunking", "Python AST, Markdown headings, SQL statements, and JS/TS declarations keep retrieved context coherent."),
    ("symbols", "Symbol Lookup", "Exact definitions avoid broad grep dumps when the user or agent knows the name."),
    ("read-stack", "Read Guard Stack", "Search-first, auto-slice, grep-first, noise-file guard, and reread checks cooperate at file boundaries."),
    ("context-cache", "Context Cache", "Unchanged reads and searches should not reenter the transcript."),
    ("tool-output", "Tool Output Controls", "Lean parsers, truncation, and listing guards keep command output useful instead of merely large."),
    ("output-controls", "Output Controls", "Terse reminders and response budgets reduce filler while preserving document-draft escape hatches."),
    ("compaction-controls", "Compaction Controls", "Threshold nudges and pressure snapshots help long sessions shed stale history."),
    ("instruction-pruning", "Instruction Pruning", "Small AGENTS.md and CLAUDE.md files lower the fixed cost on every turn."),
    ("budget-plane", "Budget Control Plane", "Normalize candidates, build signals, score relevance, choose an action, and record the decision."),
    ("relevance-scoring", "Relevance Scoring", "Explicit, semantic, lexical, recency, structural, and failure signals turn context choice into inspectable policy."),
    ("enforcement-modes", "Enforcement Modes", "Observe, advise, enforce, and strict let teams move from measurement to prevention deliberately."),
    ("agent-split", "Agent Split", "Claude has direct hooks; Codex uses best-effort adapters and skills where hooks are not available."),
    ("hook-manifest", "Hook Manifest", "HOOK_SPECS is the shared registry for both agents and generated parity docs."),
    ("telemetry", "Telemetry Model", "Savings logs and budget events stay local; published docs use generated aggregates or checked-in dogfood notes."),
    ("maintenance-skills", "Maintenance Skills", "Bug-hunt, bugfix, and continue are not token-saving strategies, but they help keep this repository healthy."),
    ("data-slide", "Data Caveats", "Chars divided by four are estimates, EB telemetry is external dogfood evidence, and qualitative claims stay labeled."),
    ("drift-prevention", "Drift Prevention", "Generated docs, parity JSON, tests, and source-link checks keep the HTML layer honest."),
    ("operations", "Operational Playbook", "Install, verify, report, troubleshoot, and update without needing a networked docs build."),
    ("contribution-map", "Contribution Map", "Add the strategy, wire the manifest, add tests and telemetry, then let docs generation expose it."),
]


SLIDE_VISUALS: dict[str, tuple[str, tuple[str, ...]]] = {
    "title": ("One control layer sits between agent intent and token spend.", ("Agent", "Control Layer", "Search", "Budget", "Telemetry")),
    "waste-model": ("Four token buckets compound unless each one has a control.", ("Input", "Tool Output", "Final Output", "Fixed Instructions")),
    "input-dominates": ("Broad reads and long history become the largest recurring cost.", ("Full File", "Repeated Context", "Transcript Growth", "Input Tax")),
    "product-promise": ("The default path becomes search, slice, summarize, and measure.", ("Search", "Slice", "Summarize", "Measure")),
    "system-map": ("Installer wiring connects hooks, index, budget policy, and reports.", ("Installer", "Hooks", "Index", "Budget", "Reports")),
    "strategy-matrix": ("Each strategy maps to a bucket, source, parity status, and evidence.", ("Strategy", "Bucket", "Source", "Parity", "Evidence")),
    "search-workflow": ("The question narrows to chunks before any file enters the transcript.", ("Question", "Vector Search", "Ranked Chunks", "Targeted Read")),
    "chunking": ("Structure-aware chunks keep retrieval aligned with how code is written.", ("AST", "Headings", "SQL", "JS/TS", "Chunks")),
    "symbols": ("Known names jump straight to definitions instead of broad output.", ("Symbol Name", "Index", "Definition", "Small Read")),
    "read-stack": ("Layered read guards catch different kinds of broad or stale context.", ("Search First", "Auto Slice", "Grep First", "Noise Guard", "Reread Gate")),
    "context-cache": ("Unchanged context is recognized before it is injected again.", ("Fingerprint", "Recent Context", "Cache Hit", "Skip Tokens")),
    "tool-output": ("Noisy command output is shaped into useful head, tail, and signal.", ("Command", "Parser", "Head/Tail", "Concise Signal")),
    "output-controls": ("Response budget checks push final answers toward useful density.", ("Draft", "Budget Check", "Terse Reminder", "Answer")),
    "compaction-controls": ("Session pressure produces compact summaries before history dominates.", ("Transcript", "Pressure", "Snapshot", "Compacted Context")),
    "instruction-pruning": ("Always-loaded instructions stay small while detail moves to skills.", ("AGENTS.md", "Audit", "Skills", "Indexed Docs")),
    "budget-plane": ("Context candidates are scored before a policy decision is emitted.", ("Normalize", "Signals", "Score", "Decide", "Telemetry")),
    "relevance-scoring": ("Multiple signals combine into one inspectable relevance score.", ("Explicit", "Semantic", "Lexical", "Recency", "Score")),
    "enforcement-modes": ("Teams can move from observation to prevention in controlled steps.", ("Observe", "Advise", "Enforce", "Strict")),
    "agent-split": ("Shared strategy logic fans out to direct Claude hooks and Codex adapters.", ("HOOK_SPECS", "Claude Hooks", "Codex Adapters", "Shared Checks")),
    "hook-manifest": ("One manifest drives wiring, parity data, and generated docs.", ("Manifest", "Settings", "Parity JSON", "Docs")),
    "telemetry": ("Local event streams become aggregate reports without publishing raw state.", ("Savings Log", "Budget Events", "Reports", "Published Aggregates")),
    "maintenance-skills": ("Repo-maintenance skills sit beside the token-control mission.", ("Bug Hunt", "Bugfix", "Continue")),
    "data-slide": ("Evidence labels distinguish estimates, measured logs, and dogfood notes.", ("Chars / 4", "Measured", "External Dogfood", "Qualitative")),
    "drift-prevention": ("Generated docs and tests keep the HTML layer tied to source truth.", ("Registries", "Generated Data", "Link Checks", "CI")),
    "operations": ("The operator loop is install, verify, report, troubleshoot, update.", ("Install", "Verify", "Report", "Troubleshoot", "Update")),
    "contribution-map": ("A new strategy lands through registry, manifest, tests, telemetry, docs.", ("Strategy", "Manifest", "Tests", "Telemetry", "Docs")),
}


REFERENCE_PAGES: dict[str, str] = {
    "reference/install.html": "Install",
    "reference/configuration.html": "Configuration",
    "reference/subagents.html": "Subagent Support",
    "reference/commands.html": "Commands",
    "reference/hook-events.html": "Hook Events",
    "reference/state-files.html": "State Files",
    "reference/telemetry-schema.html": "Telemetry Schema",
    "reference/privacy.html": "Privacy Reference",
    "reference/troubleshooting.html": "Troubleshooting",
    "reference/contributing.html": "Contributing",
    "reference/decisions.html": "Decisions",
    "reference/backlog.html": "Backlog",
}


SCAFFOLDING_PAGES: dict[str, tuple[str, str]] = {
    "scaffolding/installer.html": ("Installer", "Install lifecycle, target detection, venv launchers, update, check, and uninstall are documented from installer metadata."),
    "scaffolding/hook-manifest.html": ("Hook Manifest", "HOOK_SPECS is the source of truth for hook names, optional flags, event matchers, and parity generation."),
    "scaffolding/agent-adapters.html": ("Agent Adapters", "Claude direct hooks and Codex adapter wrappers normalize different event payloads into shared checks."),
    "scaffolding/budget-plane.html": ("Budget Plane", "Candidate normalization, signals, scoring, decisions, advice, and telemetry live in agents/common/budget."),
    "scaffolding/telemetry.html": ("Telemetry", "Savings and budget events are local-only by default; public docs use checked-in aggregates."),
    "scaffolding/generated-docs.html": ("Generated Docs", "Matrices and graphs are generated from registries so the HTML site is additive, not a second truth."),
    "scaffolding/skills.html": ("Skills", "Claude and Codex skills keep deeper workflows available without loading every detail on every turn."),
    "scaffolding/testing-ci.html": ("Testing And CI", "Unit, integration, parity, generated-doc, and protected-telemetry checks prevent drift."),
}


NOUN_PROJECT_ICONS: list[dict[str, str]] = json.loads(
    (NOUN_ICON_SOURCE / "attributions.json").read_text(encoding="utf-8")
)
NOUN_ICON_BY_ANCHOR = {icon["anchor"]: icon for icon in NOUN_PROJECT_ICONS}
MAINTENANCE_SKILL_ROLES = {
    "skill-less-tokens": "less-tokens",
    "skill-bug-hunt": "Bug hunt",
    "skill-bugfix": "Bugfix",
    "skill-continue": "Continue",
}

STRATEGY_ICON_BY_SLUG = {
    "budget-control-plane": "budget-plane",
    "search-first": "search-workflow",
    "vector-search-symbols": "symbols",
    "read-guards": "read-stack",
    "context-cache": "context-cache",
    "lean-output-truncation": "tool-output",
    "terse-output": "output-controls",
    "compaction": "compaction-controls",
    "instruction-pruning": "instruction-pruning",
}


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def e(text: Any) -> str:
    return html.escape(str(text), quote=True)


def rel_from(page: str, target: str) -> str:
    start = (SITE / page).parent
    return Path(target).as_posix() if target.startswith("#") else Path(target).as_posix()


def repo_link(page: str, repo_path: str) -> str:
    repo_url = os.environ.get("LESS_TOKENS_DOCS_REPO_URL", "").rstrip("/")
    commit = os.environ.get("LESS_TOKENS_DOCS_COMMIT", "").strip()
    if repo_url and commit:
        return f"{repo_url}/blob/{commit}/{repo_path}"
    depth = len(Path(page).parent.parts)
    prefix = "../" * (depth + 2)
    return f"{prefix}{repo_path}"


def site_link(page: str, target: str) -> str:
    depth = len(Path(page).parent.parts)
    prefix = "../" * depth
    return f"{prefix}{target}"


def generated_link(page: str, name: str) -> str:
    return site_link(page, f"generated/{name}")


def hook_matrix() -> list[dict[str, Any]]:
    parity_path = REPO / "agents" / "common" / "hooks" / "parity.json"
    parity = json.loads(parity_path.read_text(encoding="utf-8"))
    rows = []
    for spec in HOOK_SPECS:
        rows.append({
            "name": spec.name,
            "optional_flag": spec.optional_flag,
            "claude_script": spec.claude_script,
            "codex_script": spec.codex_script,
            "claude": [asdict(wire) for wire in spec.claude],
            "codex": [asdict(wire) for wire in spec.codex],
            "parity": parity.get(spec.name, {}),
        })
    return rows


def strategy_matrix() -> list[dict[str, Any]]:
    strategies = load_strategy_registry()
    hook_names = {spec.name for spec in HOOK_SPECS}
    rows = []
    for row in strategies:
        slug = slugify(row.name.replace("+", "and"))
        detail_slug = {
            "budget-control-plane": "budget-control-plane",
            "vector-search-and-symbols": "vector-search-symbols",
            "read-guards": "read-guards",
            "lean-tool-output": "lean-output-truncation",
            "terse-output-mode": "terse-output",
            "tool-output-truncation": "lean-output-truncation",
            "compaction-trigger": "compaction",
            "instruction-pruning": "instruction-pruning",
        }.get(slug, slug)
        details = STRATEGY_DETAILS.get(detail_slug, {})
        rows.append({
            "name": row.name,
            "slug": detail_slug,
            "bucket": details.get("bucket", "input"),
            "how": row.how,
            "savings": row.savings,
            "flag": row.flag,
            "registry_key": row.registry_key,
            "hooks": [hook for hook in details.get("hooks", []) if hook in hook_names],
            "canonical_source": details.get("source", ".claude/tools/strategy_registry.py"),
            "telemetry_label": "measured or estimated" if row.registry_key else "qualitative or v2 aggregate",
        })
    for slug, details in STRATEGY_DETAILS.items():
        if not any(row["slug"] == slug for row in rows):
            rows.append({
                "name": details["title"],
                "slug": slug,
                "bucket": details["bucket"],
                "how": details["flow"],
                "savings": details["telemetry"],
                "flag": "generated reference",
                "registry_key": None,
                "hooks": details.get("hooks", []),
                "canonical_source": details["source"],
                "telemetry_label": "qualitative or v2 aggregate",
            })
    return rows


def installer_flags() -> list[dict[str, Any]]:
    tree = ast.parse((REPO / "install.py").read_text(encoding="utf-8"))
    flags = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "add_argument":
            continue
        names = []
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.startswith("-"):
                names.append(arg.value)
        if not names:
            continue
        row: dict[str, Any] = {"flags": names, "help": "", "choices": None, "action": None, "default": None}
        for kw in node.keywords:
            if kw.arg == "help":
                row["help"] = ast.get_source_segment((REPO / "install.py").read_text(encoding="utf-8"), kw.value) or ""
                try:
                    row["help"] = ast.literal_eval(kw.value)
                except Exception:
                    row["help"] = row["help"].strip()
            elif kw.arg == "choices":
                try:
                    row["choices"] = list(ast.literal_eval(kw.value))
                except Exception:
                    row["choices"] = None
            elif kw.arg in {"action", "default"}:
                try:
                    row[kw.arg] = ast.literal_eval(kw.value)
                except Exception:
                    row[kw.arg] = ast.unparse(kw.value) if hasattr(ast, "unparse") else None
        flags.append(row)
    return flags


def deployment_map() -> list[dict[str, str]]:
    return [
        {"source": "agents/common/hooks", "destination": ".claude/hooks/common and .less_tokens/hooks", "purpose": "shared hook implementation"},
        {"source": "agents/common/budget", "destination": ".less_tokens/hooks/budget", "purpose": "budget control plane"},
        {"source": "agents/claude/hooks", "destination": ".claude/hooks", "purpose": "Claude direct hook wrappers"},
        {"source": "agents/codex/hooks", "destination": ".codex/hooks", "purpose": "Codex best-effort adapters"},
        {"source": ".claude/tools", "destination": ".claude/tools and .less_tokens/tools shims", "purpose": "search, symbols, stats, reports"},
        {"source": "agents/codex/skills", "destination": ".less_tokens/skills and AGENTS.md links", "purpose": "Codex fallback guidance"},
        {"source": "agents/claude/skills", "destination": ".claude/skills", "purpose": "Claude workflow guidance"},
        {"source": "agents/common/hooks/hook_manifest.py", "destination": ".claude/settings.json and .codex/hooks.json", "purpose": "generated hook wiring"},
    ]


def budget_schema() -> dict[str, Any]:
    return DEFAULT_BUDGET_CONFIG


def telemetry_summary() -> dict[str, Any]:
    text = (REPO / "eb_telemetry_9jul26.md").read_text(encoding="utf-8")
    legacy: list[dict[str, Any]] = []
    for match in re.finditer(r"\| ([a-z-]+) \| ([0-9,]+) \| ([0-9,]+) \|", text):
        legacy.append({
            "strategy": match.group(1),
            "events": int(match.group(2).replace(",", "")),
            "chars_saved": int(match.group(3).replace(",", "")),
            "estimated_tokens": int(match.group(3).replace(",", "")) // 4,
        })
    session = {}
    for name, value in re.findall(r"\| (n|min|p50|p90|p99|max|count > 500,000.*?|count > 625,000.*?) \| ([^|]+) \|", text):
        session[name.strip()] = value.strip()
    budget_match = re.search(r"all-time, ([0-9,]+)\s+decisions\): \*\*([0-9,]+)\*\* estimated tokens saved, ([0-9,]+) compactions", text)
    return {
        "source": "eb_telemetry_9jul26.md",
        "label": "external dogfood data, not this repo production telemetry",
        "estimator": "chars / 4",
        "session_size": session,
        "legacy_savings": legacy,
        "budget_pipeline": {
            "decisions": int(budget_match.group(1).replace(",", "")) if budget_match else None,
            "estimated_tokens_saved": int(budget_match.group(2).replace(",", "")) if budget_match else None,
            "compactions": int(budget_match.group(3).replace(",", "")) if budget_match else None,
        },
    }


def all_generated() -> dict[str, Any]:
    return {
        "hook-matrix.json": hook_matrix(),
        "strategy-matrix.json": strategy_matrix(),
        "installer-flags.json": installer_flags(),
        "deployment-map.json": deployment_map(),
        "budget-schema.json": budget_schema(),
        "telemetry-summary.json": telemetry_summary(),
    }


def nav(page: str) -> str:
    items = [
        ("index.html", "Overview"),
        ("presentation.html", "Presentation"),
        ("strategy-map.html", "Strategies"),
        ("architecture.html", "Architecture"),
        ("scaffolding/installer.html", "Scaffolding"),
        ("reference/install.html", "Reference"),
        ("privacy.html", "Privacy"),
    ]
    page_group = Path(page).parts[0] if len(Path(page).parts) > 1 else page
    links = []
    for href, label in items:
        href_group = Path(href).parts[0] if len(Path(href).parts) > 1 else href
        current = page == href or (
            page_group == href_group and page_group in {"strategies", "scaffolding", "reference"}
        ) or (page_group == "strategies" and href == "strategy-map.html")
        attr = ' aria-current="page"' if current else ""
        links.append(f'<a href="{e(site_link(page, href))}"{attr}>{e(label)}</a>')
    return "".join(links)


def layout(page: str, title: str, body: str, *, presentation: bool = False) -> str:
    depth = len(Path(page).parent.parts)
    prefix = "../" * depth
    page_kind = ""
    if page == "index.html":
        page_kind = "home-page"
    elif page.startswith("strategies/"):
        page_kind = "strategy-detail-page"
    elif page.startswith("reference/") or page.startswith("scaffolding/"):
        page_kind = "docs-detail-page"
    elif page == "architecture.html":
        page_kind = "architecture-page"
    classes = " ".join(filter(None, ["hybrid-page", "presentation-page" if presentation else "", page_kind]))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(title)} - less_tokens docs</title>
  <link rel="stylesheet" href="{prefix}assets/site.css">
  <script defer src="{prefix}assets/site.js"></script>
</head>
<body class="{classes}">
  <header class="site-header">
    <a class="brand" href="{e(site_link(page, 'index.html'))}"><img src="{prefix}assets/LT_mark.svg" alt=""> less_tokens</a>
    <nav>{nav(page)}</nav>
  </header>
  <main>
{body}
  </main>
</body>
</html>
"""


def card_grid(cards: list[tuple[str, str, str]]) -> str:
    return '<div class="grid">' + "".join(
        f'<article class="card"><h3><a href="{e(href)}">{e(title)}</a></h3><p>{e(text)}</p></article>'
        for title, text, href in cards
    ) + "</div>"


def source_box(page: str, links: list[tuple[str, str]]) -> str:
    items = "".join(f'<li><a href="{e(repo_link(page, path))}">{e(label)}</a></li>' for label, path in links)
    return f'<aside class="trace"><h2>Trace It In Code</h2><ul>{items}</ul></aside>'


def noun_icon_credit(anchor: str) -> str:
    icon = NOUN_ICON_BY_ANCHOR[anchor]
    return (
        f'Icon: <a href="{e(icon["page"])}">{e(icon["title"])}</a> by {e(icon["creator"])}'
        f' · <a href="https://creativecommons.org/licenses/by/3.0/">{e(icon["license"])}</a>'
    )


def noun_project_gallery(page: str, *, compact: bool = False) -> str:
    cards = []
    for anchor, role in MAINTENANCE_SKILL_ROLES.items():
        icon = NOUN_ICON_BY_ANCHOR[anchor]
        cards.append(f"""
        <article class="np-icon">
          <a href="{e(icon["page"])}"><img src="{e(site_link(page, f'assets/slides/{anchor}.svg'))}" alt="{e(icon["title"])} icon by {e(icon["creator"])}"></a>
          <h3>{e(role)}</h3>
          <p><a href="{e(icon["page"])}">{e(icon["title"])}</a> by {e(icon["creator"])}</p>
          <p class="note"><a href="https://creativecommons.org/licenses/by/3.0/">{e(icon["license"])}</a></p>
        </article>
        """.strip())
    class_name = "np-gallery compact" if compact else "np-gallery"
    return f'<div class="{class_name}">{"".join(cards)}</div>'


def svg_bar_chart(name: str, values: list[tuple[str, int]], title: str) -> str:
    width = 900
    height = 280
    left = 190
    max_value = max((value for _, value in values), default=1)
    rows = []
    for index, (label, value) in enumerate(values):
        y = 52 + index * 38
        bar_width = int((width - left - 90) * value / max_value)
        rows.append(f'<text x="18" y="{y + 17}" class="svg-label">{e(label)}</text>')
        rows.append(f'<rect x="{left}" y="{y}" width="{bar_width}" height="24" rx="3" class="svg-bar"/>')
        rows.append(f'<text x="{left + bar_width + 10}" y="{y + 17}" class="svg-value">{value:,}</text>')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="{name}-title">
  <title id="{name}-title">{e(title)}</title>
  <style>.svg-title{{font:700 22px system-ui;fill:#16202a}}.svg-label,.svg-value{{font:13px system-ui;fill:#16202a}}.svg-bar{{fill:#2f7d78}}</style>
  <text x="18" y="30" class="svg-title">{e(title)}</text>
  {''.join(rows)}
</svg>
"""


def _token_dots(points: list[tuple[int, int, int]], css_class: str = "token") -> str:
    return "".join(f'<circle cx="{x}" cy="{y}" r="{r}" class="{css_class}"/>' for x, y, r in points)


def _mini_label(text: str, x: int, y: int) -> str:
    return f'<text x="{x}" y="{y}" class="mini" text-anchor="middle">{e(text)}</text>'


def _scene(anchor: str) -> str:
    dots = [(130, 126, 7), (174, 184, 5), (214, 142, 9), (260, 210, 6), (782, 158, 7), (838, 222, 5)]
    scenes: dict[str, str] = {
        "title": f"""
  <circle cx="490" cy="310" r="94" class="core"/>
  <path d="M168 310 C262 188, 382 174, 448 250" class="stream"/>
  <path d="M532 250 C602 172, 736 186, 818 310" class="stream"/>
  <path d="M532 370 C612 448, 734 438, 818 310" class="stream muted"/>
  <path d="M168 310 C260 430, 382 444, 448 370" class="stream muted"/>
  {_token_dots(dots)}
  <g class="glyph"><path d="M452 314 h76 M490 276 v76"/><circle cx="490" cy="314" r="48"/></g>
""",
        "waste-model": """
  <rect x="150" y="144" width="130" height="300" class="bucket a"/><rect x="330" y="204" width="130" height="240" class="bucket b"/><rect x="510" y="250" width="130" height="194" class="bucket c"/><rect x="690" y="104" width="130" height="340" class="bucket d"/>
  <path d="M120 468 H850" class="base"/>
  <circle cx="215" cy="118" r="18" class="token"/><circle cx="395" cy="178" r="18" class="token alt"/><circle cx="575" cy="224" r="18" class="token warm"/><circle cx="755" cy="78" r="18" class="token green"/>
  <path d="M215 136 v52 M395 196 v52 M575 242 v52 M755 96 v52" class="fall"/>
""",
        "input-dominates": """
  <path d="M158 444 C218 244, 330 150, 492 150 C654 150, 770 244, 824 444 Z" class="mountain"/>
  <path d="M236 444 C274 306, 360 242, 492 242 C624 242, 708 306, 746 444 Z" class="mountain inner"/>
  <path d="M154 444 H834" class="base"/>
  <circle cx="492" cy="138" r="34" class="token"/>
  <path d="M492 172 v202" class="fall heavy"/>
  <path d="M358 314 h268" class="gate"/>
""",
        "product-promise": """
  <path d="M132 122 h716 l-170 150 v154 l-196 74 V272 Z" class="funnel"/>
  <circle cx="220" cy="174" r="18" class="token"/><circle cx="326" cy="174" r="14" class="token alt"/><circle cx="438" cy="174" r="22" class="token warm"/>
  <path d="M482 272 v150" class="stream"/>
  <circle cx="482" cy="458" r="30" class="core"/>
  <path d="M610 380 l74 74 l124 -142" class="check"/>
""",
        "system-map": """
  <circle cx="490" cy="300" r="82" class="core"/>
  <circle cx="244" cy="162" r="48" class="sat a"/><circle cx="736" cy="162" r="48" class="sat b"/><circle cx="244" cy="438" r="48" class="sat c"/><circle cx="736" cy="438" r="48" class="sat d"/>
  <path d="M286 186 L418 260 M694 186 L562 260 M286 414 L418 340 M694 414 L562 340" class="stream"/>
  <path d="M442 300 h96 M490 252 v96" class="glyph"/>
""",
        "strategy-matrix": """
  <g class="matrix">
    <rect x="164" y="136" width="652" height="332" rx="10"/>
    <path d="M164 219 H816 M164 302 H816 M164 385 H816 M294 136 V468 M424 136 V468 M554 136 V468 M684 136 V468"/>
  </g>
  <circle cx="230" cy="178" r="18" class="token"/><circle cx="490" cy="261" r="18" class="token alt"/><circle cx="750" cy="344" r="18" class="token warm"/><circle cx="360" cy="427" r="18" class="token green"/>
""",
        "search-workflow": """
  <circle cx="250" cy="264" r="88" class="lens"/>
  <path d="M314 328 l116 116" class="handle"/>
  <path d="M442 442 C548 374, 630 298, 780 176" class="stream"/>
  <rect x="628" y="142" width="180" height="72" class="slice"/><rect x="558" y="258" width="180" height="72" class="slice muted"/><rect x="470" y="374" width="180" height="72" class="slice"/>
  <circle cx="250" cy="264" r="24" class="token"/>
""",
        "chunking": """
  <path d="M178 146 h250 v310 H178 Z M552 146 h250 v310 H552 Z" class="doc"/>
  <path d="M220 210 h166 M220 262 h110 M220 314 h150 M594 210 h166 M594 262 h110 M594 314 h150" class="docline"/>
  <path d="M428 238 C482 208, 504 208, 552 238 M428 322 C482 352, 504 352, 552 322" class="cut"/>
  <rect x="432" y="248" width="116" height="64" class="chunk"/>
""",
        "symbols": """
  <circle cx="490" cy="292" r="126" class="radar"/>
  <path d="M490 292 L628 166" class="beam"/>
  <circle cx="628" cy="166" r="28" class="token warm"/>
  <path d="M348 430 h284 v56 H348 Z" class="codebox"/>
  <path d="M394 458 h192" class="docline"/>
  <text x="490" y="308" class="symbol" text-anchor="middle">{ }</text>
""",
        "read-stack": """
  <rect x="232" y="390" width="516" height="58" class="layer a"/><rect x="260" y="322" width="460" height="58" class="layer b"/><rect x="288" y="254" width="404" height="58" class="layer c"/><rect x="316" y="186" width="348" height="58" class="layer d"/><rect x="344" y="118" width="292" height="58" class="layer e"/>
  <path d="M492 80 v374" class="fall heavy"/>
  <circle cx="492" cy="82" r="20" class="token"/>
""",
        "context-cache": """
  <path d="M318 220 C410 108, 596 108, 686 220" class="loop"/>
  <path d="M686 220 C770 346, 612 494, 490 420" class="loop"/>
  <path d="M490 420 C346 498, 208 348, 318 220" class="loop"/>
  <rect x="386" y="248" width="208" height="120" class="vault"/>
  <circle cx="490" cy="308" r="24" class="core"/>
  <circle cx="318" cy="220" r="18" class="token"/><circle cx="686" cy="220" r="18" class="token alt"/><circle cx="490" cy="420" r="18" class="token green"/>
""",
        "tool-output": """
  <path d="M130 146 h260 v300 H130 Z" class="terminal"/><path d="M180 206 h162 M180 252 h132 M180 298 h178 M180 344 h108" class="terminal-line"/>
  <path d="M410 296 h176" class="stream heavy"/>
  <path d="M586 160 h250 v104 H586 Z M586 328 h250 v104 H586 Z" class="summary"/>
  <circle cx="712" cy="296" r="26" class="core"/>
""",
        "output-controls": """
  <path d="M170 156 h292 a44 44 0 0 1 44 44 v116 a44 44 0 0 1 -44 44 H318 l-86 74 v-74 h-62 a44 44 0 0 1 -44 -44 V200 a44 44 0 0 1 44 -44 Z" class="bubble"/>
  <path d="M576 158 h232 v276 H576 Z" class="meter"/>
  <path d="M620 382 L764 214" class="check"/>
  <circle cx="692" cy="324" r="88" class="gauge"/>
""",
        "compaction-controls": """
  <path d="M170 132 h260 v340 H170 Z" class="accordion"/>
  <path d="M214 176 h172 M214 222 h172 M214 268 h172 M214 314 h172 M214 360 h172 M214 406 h172" class="docline"/>
  <path d="M454 302 h110" class="stream heavy"/>
  <path d="M608 206 h204 v192 H608 Z" class="compact"/>
  <path d="M650 254 h120 M650 302 h120 M650 350 h120" class="docline"/>
""",
        "instruction-pruning": """
  <path d="M178 130 h260 v336 H178 Z M542 130 h260 v336 H542 Z" class="doc"/>
  <path d="M224 200 h166 M224 250 h166 M224 300 h166 M224 350 h166 M588 228 h168 M588 302 h118" class="docline"/>
  <path d="M420 190 l148 148 M568 190 L420 338" class="scissor"/>
  <circle cx="420" cy="190" r="18" class="handle-dot"/><circle cx="568" cy="190" r="18" class="handle-dot"/>
""",
        "budget-plane": """
  <path d="M128 156 h220 v120 H128 Z M128 340 h220 v120 H128 Z" class="candidate"/>
  <path d="M392 308 h196" class="stream heavy"/>
  <circle cx="490" cy="308" r="76" class="core"/>
  <path d="M628 156 h220 v120 H628 Z M628 340 h220 v120 H628 Z" class="decision"/>
  <path d="M678 216 l42 42 l82 -94 M682 404 h116" class="check"/>
""",
        "relevance-scoring": """
  <circle cx="490" cy="304" r="142" class="radar"/>
  <circle cx="490" cy="304" r="96" class="radar inner"/><circle cx="490" cy="304" r="48" class="radar inner"/>
  <path d="M490 304 L608 206 M490 304 L382 220 M490 304 L570 420 M490 304 L356 360" class="beam muted"/>
  <circle cx="608" cy="206" r="18" class="token"/><circle cx="382" cy="220" r="14" class="token alt"/><circle cx="570" cy="420" r="20" class="token warm"/><circle cx="356" cy="360" r="12" class="token green"/>
""",
        "enforcement-modes": """
  <path d="M158 428 H822" class="base"/>
  <rect x="176" y="344" width="118" height="84" class="step a"/><rect x="334" y="286" width="118" height="142" class="step b"/><rect x="492" y="220" width="118" height="208" class="step c"/><rect x="650" y="152" width="118" height="276" class="step d"/>
  <path d="M216 314 l34 34 l62 -82 M374 256 l34 34 l62 -82 M532 190 l34 34 l62 -82 M690 122 l34 34 l62 -82" class="check small"/>
""",
        "agent-split": """
  <circle cx="490" cy="152" r="58" class="core"/>
  <path d="M490 210 C420 284, 330 322, 228 404 M490 210 C560 284, 650 322, 752 404" class="rail"/>
  <rect x="130" y="386" width="196" height="88" class="agent a"/><rect x="654" y="386" width="196" height="88" class="agent b"/>
  <path d="M178 432 h100 M702 432 h100" class="docline"/>
  <circle cx="228" cy="404" r="22" class="token"/><circle cx="752" cy="404" r="22" class="token alt"/>
""",
        "hook-manifest": """
  <rect x="374" y="124" width="232" height="352" class="manifest"/>
  <path d="M420 190 h140 M420 246 h140 M420 302 h140 M420 358 h140" class="docline"/>
  <path d="M374 220 C280 176, 222 172, 152 206 M606 220 C700 176, 758 172, 828 206 M374 380 C280 424, 222 428, 152 394 M606 380 C700 424, 758 428, 828 394" class="stream"/>
  <circle cx="152" cy="206" r="24" class="token"/><circle cx="828" cy="206" r="24" class="token alt"/><circle cx="152" cy="394" r="24" class="token warm"/><circle cx="828" cy="394" r="24" class="token green"/>
""",
        "telemetry": """
  <path d="M126 176 C250 122, 340 236, 470 180 S706 122, 850 176" class="stream"/>
  <path d="M126 292 C250 238, 340 352, 470 296 S706 238, 850 292" class="stream altstroke"/>
  <path d="M126 408 C250 354, 340 468, 470 412 S706 354, 850 408" class="stream warmstroke"/>
  <rect x="406" y="224" width="168" height="152" class="report"/>
  <path d="M444 270 h92 M444 316 h92" class="docline"/>
""",
        "maintenance-skills": """
  <circle cx="490" cy="304" r="92" class="core"/>
  <path d="M490 212 C410 150, 308 152, 232 232 M490 212 C570 150, 672 152, 748 232 M398 354 C312 430, 242 432, 166 372 M582 354 C668 430, 738 432, 814 372" class="stream"/>
  <rect x="144" y="180" width="176" height="104" class="artifact"/>
  <rect x="660" y="180" width="176" height="104" class="artifact"/>
  <rect x="76" y="330" width="176" height="104" class="artifact"/>
  <rect x="728" y="330" width="176" height="104" class="artifact"/>
  <path d="M184 232 h96 M700 232 h96 M116 382 h96 M768 382 h96" class="docline"/>
  <path d="M454 306 l28 28 l62 -84" class="check small"/>
""",
        "data-slide": """
  <path d="M490 146 v270" class="scale"/>
  <path d="M332 216 h316" class="scale"/>
  <path d="M332 216 l-92 160 h184 Z M648 216 l-92 160 h184 Z" class="pan"/>
  <circle cx="284" cy="330" r="22" class="token"/><circle cx="376" cy="330" r="14" class="token alt"/><circle cx="602" cy="330" r="16" class="token warm"/><circle cx="694" cy="330" r="20" class="token green"/>
  <rect x="430" y="416" width="120" height="42" class="basebox"/>
""",
        "drift-prevention": """
  <path d="M156 150 h248 v124 H156 Z M576 150 h248 v124 H576 Z M366 354 h248 v124 H366 Z" class="artifact"/>
  <path d="M404 212 h172 M490 274 v80 M280 274 L366 354 M700 274 L614 354" class="stream"/>
  <path d="M410 416 l42 42 l94 -114" class="check"/>
  <circle cx="490" cy="274" r="26" class="core"/>
""",
        "operations": """
  <circle cx="490" cy="304" r="158" class="wheel"/>
  <circle cx="490" cy="304" r="62" class="core"/>
  <path d="M490 146 v96 M642 258 l-92 30 M584 432 l-56 -82 M396 432 l56 -82 M338 258 l92 30" class="spoke"/>
  <circle cx="490" cy="146" r="28" class="token"/><circle cx="642" cy="258" r="28" class="token alt"/><circle cx="584" cy="432" r="28" class="token warm"/><circle cx="396" cy="432" r="28" class="token green"/><circle cx="338" cy="258" r="28" class="token"/>
""",
        "contribution-map": """
  <path d="M132 302 H848" class="rail"/>
  <rect x="150" y="242" width="112" height="120" class="station a"/><rect x="330" y="242" width="112" height="120" class="station b"/><rect x="510" y="242" width="112" height="120" class="station c"/><rect x="690" y="242" width="112" height="120" class="station d"/>
  <circle cx="262" cy="302" r="18" class="token"/><circle cx="442" cy="302" r="18" class="token alt"/><circle cx="622" cy="302" r="18" class="token warm"/><circle cx="802" cy="302" r="18" class="token green"/>
  <path d="M764 176 l62 62 l100 -142" class="check"/>
""",
    }
    return scenes[anchor]


def slide_visual_svg(anchor: str, title: str, caption: str, _nodes: tuple[str, ...]) -> str:
    width = 980
    height = 620
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="{anchor}-title {anchor}-desc">
  <title id="{anchor}-title">{e(title)} concept map</title>
  <desc id="{anchor}-desc">{e(caption)}</desc>
  <style>
    .bg{{fill:#f7f8fa}}.grain{{fill:none;stroke:#d8e0e7;stroke-width:1;opacity:.45}}.core{{fill:#16202a}}.token{{fill:#2f7d78}}.token.alt{{fill:#225f88}}.token.warm{{fill:#9a5b20}}.token.green{{fill:#4c6f52}}.stream,.rail,.loop,.spoke{{fill:none;stroke:#2f7d78;stroke-width:8;stroke-linecap:round;stroke-linejoin:round}}.stream.muted,.beam.muted{{stroke:#87929c;stroke-width:5}}.stream.heavy,.fall.heavy{{stroke-width:12}}.altstroke{{stroke:#225f88}}.warmstroke{{stroke:#9a5b20}}.fall,.base,.gate,.scale{{fill:none;stroke:#16202a;stroke-width:5;stroke-linecap:round}}.bucket,.sat,.slice,.doc,.chunk,.terminal,.summary,.bubble,.meter,.accordion,.compact,.candidate,.decision,.step,.agent,.manifest,.report,.pan,.artifact,.station{{fill:#fff;stroke:#16202a;stroke-width:4}}.a{{stroke:#2f7d78}}.b{{stroke:#225f88}}.c{{stroke:#9a5b20}}.d{{stroke:#4c6f52}}.e{{stroke:#725a9b}}.mountain,.funnel,.lens,.radar,.vault,.gauge,.wheel{{fill:#fff;stroke:#2f7d78;stroke-width:5}}.mountain.inner,.radar.inner{{fill:none;stroke:#225f88;stroke-width:4;opacity:.75}}.handle,.beam,.cut,.scissor{{fill:none;stroke:#9a5b20;stroke-width:8;stroke-linecap:round;stroke-linejoin:round}}.check{{fill:none;stroke:#4c6f52;stroke-width:10;stroke-linecap:round;stroke-linejoin:round}}.check.small{{stroke-width:7}}.docline,.terminal-line{{fill:none;stroke:#87929c;stroke-width:5;stroke-linecap:round}}.matrix rect,.matrix path{{fill:none;stroke:#16202a;stroke-width:4}}.glyph,.symbol{{fill:none;stroke:#fff;stroke-width:7;stroke-linecap:round}}.symbol{{font:700 52px ui-monospace,monospace;fill:#16202a;stroke:none}}.mini{{font:700 13px system-ui;fill:#16202a}}.handle-dot{{fill:#fff;stroke:#9a5b20;stroke-width:5}}.basebox{{fill:#16202a}}.layer{{fill:#fff;stroke:#16202a;stroke-width:4}}.terminal{{fill:#16202a}}.terminal-line{{stroke:#f7f8fa}}.summary,.decision{{fill:#edf6f5}}.candidate{{fill:#fff7ed}}.bubble{{fill:#fff}}.meter{{fill:#eef3f5}}.manifest,.report{{fill:#fff}}.pan{{fill:#fff7ed}}.artifact{{fill:#fff}}.station{{fill:#edf6f5}}
  </style>
  <rect class="bg" x="0" y="0" width="{width}" height="{height}"/>
  <path class="grain" d="M80 96 H900 M80 524 H900 M96 80 V540 M884 80 V540"/>
  {_scene(anchor)}
</svg>
"""


def write_slide_visuals(check: bool) -> bool:
    ok = True
    slide_dir = ASSETS / "slides"
    if not check:
        slide_dir.mkdir(parents=True, exist_ok=True)
    for icon in NOUN_PROJECT_ICONS:
        anchor = icon["anchor"]
        source = NOUN_ICON_SOURCE / f"{anchor}.svg"
        text = source.read_text(encoding="utf-8")
        path = slide_dir / f"{anchor}.svg"
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                print(f"stale slide visual: {path.relative_to(REPO)}", file=sys.stderr)
                ok = False
        else:
            path.write_text(text, encoding="utf-8")
    return ok


def write_generated_data(check: bool) -> bool:
    ok = True
    GENERATED.mkdir(parents=True, exist_ok=True)
    data = all_generated()
    for name, value in data.items():
        text = json.dumps(value, indent=2, sort_keys=True) + "\n"
        path = GENERATED / name
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                print(f"stale generated data: {path.relative_to(REPO)}", file=sys.stderr)
                ok = False
        else:
            path.write_text(text, encoding="utf-8")
    telemetry = data["telemetry-summary.json"]
    values = [(row["strategy"], row["estimated_tokens"]) for row in telemetry["legacy_savings"]]
    chart = svg_bar_chart("legacy-savings", values, "External dogfood legacy savings, estimated tokens")
    chart_path = GENERATED / "legacy-savings.svg"
    if check:
        if not chart_path.exists() or chart_path.read_text(encoding="utf-8") != chart:
            print(f"stale generated chart: {chart_path.relative_to(REPO)}", file=sys.stderr)
            ok = False
    else:
        chart_path.write_text(chart, encoding="utf-8")
    return ok


def table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{e(header)}</th>" for header in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def overview_page(page: str) -> str:
    return layout(page, "Overview", f"""
    <section class="home-hero">
      <div class="home-intro">
        <p class="home-kicker"><span>03</span> Context control</p>
        <h1>Make every token <em>earn</em> its place.</h1>
        <p class="home-lede">A visible control plane that helps Claude and Codex search first, trim tool output, compact context, and prove what they save.</p>
        <div class="home-actions">
          <a class="home-button primary" href="{e(site_link(page, 'reference/install.html'))}">Install less_tokens</a>
          <a class="home-button" href="#how-it-works">See how it works</a>
        </div>
        <div class="install-command"><code>python install.py --target both</code><button type="button" data-copy-command="python install.py --target both">Copy</button></div>
        <p class="home-proof"><i></i>Visible. Enforceable. Measured.</p>
      </div>
      <div class="aurora-console" aria-label="Representative token savings report with strategy icons">
        <p class="console-kicker">Local intelligence · representative report</p>
        <div class="aurora-icon-field" aria-hidden="true">
          <img class="aurora-icon icon-search" src="assets/slides/search-workflow.svg" alt="">
          <img class="aurora-icon icon-compact" src="assets/slides/compaction-controls.svg" alt="">
          <img class="aurora-icon icon-output" src="assets/slides/tool-output.svg" alt="">
          <span class="orbit-ring ring-one"></span><span class="orbit-ring ring-two"></span>
        </div>
        <section class="overview-stats" aria-label="Sanitized representative stats">
          <div class="stats-heading"><span>Current session</span><span>8 events</span></div>
          <div class="stats-total"><span>Measured before model</span><strong>27.7k <small>tokens est.</small></strong></div>
          <div class="stats-bars" aria-label="Compaction 16.8 thousand, truncation 7.3 thousand, cached read 3.6 thousand estimated tokens saved">
            <div><span>Compaction</span><i style="--amount:61%"></i><b>16.8k</b></div>
            <div><span>Truncation</span><i style="--amount:26%"></i><b>7.3k</b></div>
            <div><span>Cached read</span><i style="--amount:13%"></i><b>3.6k</b></div>
          </div>
          <div class="stats-upper"><span>Upper bound · separate lane</span><strong>≤17.2k</strong></div>
          <p>Sanitized example data from the shipped report. Measured savings and optimistic avoided cost are never added together.</p>
        </section>
      </div>
    </section>

    <section class="home-section" id="how-it-works">
      <p class="section-number">01 / The operating loop</p>
      <div class="section-heading"><h2>Spend context on evidence, not exploration noise.</h2><p>less_tokens changes the path an agent takes before expensive content reaches the conversation.</p></div>
      <div class="strategy-examples">
        <article class="example-card"><img src="assets/slides/search-workflow.svg" alt="Search-first workflow from a question to a targeted read"><div><span>Input</span><h3>Search before reading</h3><p>Semantic chunks and exact symbol lookup identify the useful slice before a whole file enters context.</p><a href="{e(site_link(page, 'strategies/search-first.html'))}">Explore search-first →</a></div></article>
        <article class="example-card"><img src="assets/slides/tool-output.svg" alt="Tool output being reduced to a concise signal"><div><span>Tools</span><h3>Keep the signal</h3><p>Listing guards, lean parsers, and head-tail truncation prevent noisy commands from dominating the transcript.</p><a href="{e(site_link(page, 'strategies/lean-output-truncation.html'))}">Explore tool controls →</a></div></article>
        <article class="example-card"><img src="assets/slides/compaction-controls.svg" alt="Transcript pressure producing compact context"><div><span>History</span><h3>Compact before pressure wins</h3><p>Threshold nudges and snapshots preserve decisions while releasing stale conversational history.</p><a href="{e(site_link(page, 'strategies/compaction.html'))}">Explore compaction →</a></div></article>
      </div>
    </section>

    <section class="home-section example-walkthrough">
      <p class="section-number">02 / A concrete example</p>
      <div class="section-heading"><h2>One question. Three smaller moves.</h2><p>Instead of opening a large file and hoping the answer appears, the agent narrows the problem deliberately.</p></div>
      <ol class="example-steps">
        <li><span>Ask</span><div><code>Where is budget pressure converted into a compaction decision?</code><p>The task starts as an intent, not a file path.</p></div></li>
        <li><span>Find</span><div><code>symbols.py PressureCompaction</code><p>Exact lookup points to the definition and its line number.</p></div></li>
        <li><span>Read</span><div><code>policy.py: targeted slice</code><p>Only the implementation and nearby evidence enter context.</p></div></li>
      </ol>
    </section>

    <section class="home-section home-evidence">
      <p class="section-number">03 / Go deeper</p>
      <div class="section-heading"><h2>Inspect every layer.</h2><p>The visual explanation is backed by source registries, generated matrices, and local-only telemetry.</p></div>
      <div class="evidence-links">
        <a href="{e(site_link(page, 'presentation.html'))}"><span>Visual walkthrough</span><strong>Open the 25-screen presentation</strong></a>
        <a href="{e(site_link(page, 'strategy-map.html'))}"><span>Strategy matrix</span><strong>Compare every control and evidence label</strong></a>
        <a href="{e(site_link(page, 'architecture.html'))}"><span>Architecture</span><strong>Trace hooks, budget policy, and telemetry</strong></a>
        <a href="{e(site_link(page, 'reference/subagents.html'))}"><span>Subagent support</span><strong>See shipped controls and the evidence-gated roadmap</strong></a>
        <a href="{e(site_link(page, 'reference/install.html'))}"><span>Get started</span><strong>Install for Claude, Codex, or both</strong></a>
      </div>
      <p class="canonical-note">Canonical operational detail remains in <a href="{e(repo_link(page, 'README.md'))}">README.md</a> and <a href="{e(repo_link(page, 'DOCUMENTATION.md'))}">DOCUMENTATION.md</a>; generated matrices remain tied to code registries.</p>
    </section>
    """)


def strategy_map_page(page: str) -> str:
    rows = []
    for row in strategy_matrix():
        hooks = ", ".join(row["hooks"]) or "none"
        rows.append([
            f'<a href="{e(site_link(page, "strategies/" + row["slug"] + ".html"))}">{e(row["name"])}</a>',
            e(row["bucket"]),
            e(row["savings"]),
            e(hooks),
            f'<a href="{e(repo_link(page, row["canonical_source"]))}">source</a>',
        ])
    return layout(page, "Strategy Map", f"""
    <section class="page-title"><h1>Strategy Map</h1><p>Generated from <a href="{e(repo_link(page, '.claude/tools/strategy_registry.py'))}">strategy_registry.py</a> plus <a href="{e(repo_link(page, 'agents/common/hooks/hook_manifest.py'))}">HOOK_SPECS</a>.</p></section>
    {table(["Strategy", "Bucket", "Savings Claim", "Hooks", "Canonical Source"], rows)}
    <p class="note">Data contract: <a href="{e(generated_link(page, 'strategy-matrix.json'))}">strategy-matrix.json</a></p>
    """)


def architecture_page(page: str) -> str:
    return layout(page, "Architecture", f"""
    <section class="page-title"><h1>Architecture</h1><p>The installed project has three visible runtimes: .claude for shared index and Claude hooks, .less_tokens for budget and Codex shims, and .codex for best-effort adapters.</p></section>
    <div class="diagram">
      <div>Source repo<br><small>install.py, agents/, .claude/tools</small></div>
      <span>deploys</span>
      <div>Host project<br><small>.claude, .less_tokens, .codex</small></div>
      <span>emits</span>
      <div>Local telemetry<br><small>savings.jsonl, events.jsonl, reports</small></div>
    </div>
    <section class="two-col">
      <article><h2>Hook Execution</h2><ol><li>Agent emits a native tool event.</li><li>Wrapper normalizes the payload.</li><li>Shared hook or budget code evaluates it.</li><li>The wrapper exits allow, advise, or block.</li></ol></article>
      <article><h2>Budget Sequence</h2><ol><li>Normalize candidates.</li><li>Build signals.</li><li>Score relevance.</li><li>Select decisions.</li><li>Emit telemetry and compaction snapshots.</li></ol></article>
    </section>
    {source_box(page, [("Hook manifest", "agents/common/hooks/hook_manifest.py"), ("Budget policy", "agents/common/budget/policy.py"), ("Payload normalization", "agents/common/hooks/payload.py"), ("Runtime helpers", "agents/common/hooks/runtime.py")])}
    """)


def privacy_page(page: str) -> str:
    return layout(page, "Privacy", f"""
    <section class="page-title"><h1>Privacy And Data Honesty</h1><p>Docs builds do not use network access, and committed HTML never includes raw local telemetry.</p></section>
    <div class="grid">
      <article class="card"><h3>Local telemetry</h3><p>Savings and budget events are written under .claude/state or .less_tokens/state in the installed project.</p></article>
      <article class="card"><h3>Published data</h3><p>Graphs use source registries or checked-in aggregate notes such as EB dogfood telemetry, labeled as external evidence.</p></article>
      <article class="card"><h3>Estimator</h3><p>Token values derived from characters use the documented chars divided by four estimate.</p></article>
    </div>
    {source_box(page, [("Telemetry note", "eb_telemetry_9jul26.md"), ("Stats CLI", ".claude/tools/stats.py"), ("Budget events", "agents/common/budget/events.py")])}
    """)


def presentation_page(page: str) -> str:
    slides = []
    for index, (anchor, title, text) in enumerate(SLIDES, 1):
        link = "scaffolding/skills.html" if anchor == "maintenance-skills" else ("strategy-map.html" if "Strategy" in title or "Matrix" in title else "architecture.html")
        caption, _nodes = SLIDE_VISUALS[anchor]
        if anchor == "telemetry":
            visual = f'<iframe class="telemetry-frame" src="{e(site_link(page, "assets/telemetry-example.html"))}" title="Representative user-facing Token Savings Report"></iframe>'
            credit = "Representative sanitized values rendered through the shipped telemetry report UI."
        elif anchor == "maintenance-skills":
            visual = noun_project_gallery(page, compact=True)
            credit = f"{len(MAINTENANCE_SKILL_ROLES)} attributed Noun Project icons map the maintenance skills."
        else:
            visual = f'<img src="{e(site_link(page, f"assets/slides/{anchor}.svg"))}" alt="{e(caption)}">'
            credit = noun_icon_credit(anchor)
        slides.append(f"""
        <section class="slide" id="{e(anchor)}" tabindex="-1">
          <div class="slide-copy">
            <p class="slide-count">{index:02d} / {len(SLIDES):02d}</p>
            <h1>{e(title)}</h1>
            <p>{e(text)}</p>
            <a href="{e(site_link(page, link))}">Deep link</a>
          </div>
          <figure class="slide-visual">
            {visual}
            <figcaption>{e(caption)}<br>{credit}</figcaption>
          </figure>
        </section>
        """)
    return layout(page, "Presentation", "\n".join(slides), presentation=True)


def strategy_page(page: str, slug: str, details: dict[str, Any]) -> str:
    hook_rows = []
    hooks = {row["name"]: row for row in hook_matrix()}
    for hook in details.get("hooks", []):
        row = hooks.get(hook)
        if not row:
            continue
        hook_rows.append([
            e(hook),
            e(row["claude_script"] or ""),
            e(row["codex_script"] or ""),
            e(row["parity"].get("claude", "unknown")),
            e(row["parity"].get("codex", "unknown")),
        ])
    if not hook_rows:
        hook_rows.append(["none", "command/tool layer", "command/tool layer", "n/a", "n/a"])
    links = [("Canonical source", details["source"]), ("Hook manifest", "agents/common/hooks/hook_manifest.py"), ("Parity JSON", "agents/common/hooks/parity.json")]
    icon_anchor = STRATEGY_ICON_BY_SLUG.get(slug, "strategy-matrix")
    return layout(page, details["title"], f"""
    <section class="page-title strategy-title">
      <div><p class="eyebrow">{e(details["bucket"])} bucket · strategy</p><h1>{e(details["title"])}</h1><p>{e(details["problem"])}</p></div>
      <img class="strategy-title-icon" src="{e(site_link(page, f'assets/slides/{icon_anchor}.svg'))}" alt="">
    </section>
    <section class="two-col strategy-comparison">
      <article><p class="eyebrow">Before</p><h2>Context arrives broad.</h2><p>Broad context enters the transcript before relevance is checked.</p></article>
      <article><p class="eyebrow">After</p><h2>Evidence arrives bounded.</h2><p>{e(details["flow"])}</p></article>
    </section>
    <section class="content-section"><p class="eyebrow">Runtime contract</p><h2>Enforcement And Parity</h2>{table(["Hook", "Claude", "Codex", "Claude parity", "Codex parity"], hook_rows)}</section>
    <section class="grid">
      <article class="card"><h3>Bypass Or Failure Mode</h3><p>{e(details["failure"])}</p></article>
      <article class="card"><h3>Telemetry</h3><p>{e(details["telemetry"])}</p></article>
      <article class="card"><h3>Verification</h3><p>{e(details["tests"])}</p></article>
    </section>
    {source_box(page, links)}
    """)


def scaffolding_page(page: str, title: str, summary: str) -> str:
    extra = ""
    if page.endswith("installer.html"):
        flag_rows = [[e(", ".join(row["flags"])), e(row.get("help") or ""), e(row.get("action") or ""), e(row.get("default") or "")] for row in installer_flags()]
        extra = f'''<h2>Installer Flags</h2>{table(["Flags", "Help", "Action", "Default"], flag_rows)}
        <p class="note"><a href="{e(generated_link(page, "installer-flags.json"))}">installer-flags.json</a></p>
        <h2>Codex Hook Configuration</h2>
        <p>The installer writes Codex CLI's nested matcher-group schema: an outer list of groups, matcher objects inside each group, and typed command hooks inside each matcher. A safe Codex update also migrates the pre-CX21 flat form, which current <code>codex-cli</code> rejects.</p>
        <pre><code>python3 install.py --update --agent codex</code></pre>
        <p class="note">Configuration parsing was fixed by CX21. Live PostToolUse firing and tool-output replacement remain a separate evidence question in DECISIONS.md.</p>'''
    elif page.endswith("hook-manifest.html"):
        hook_rows = [[e(row["name"]), e(row.get("optional_flag") or "always"), e(row["claude_script"]), e(row["codex_script"])] for row in hook_matrix()]
        extra = f'<h2>Hook Matrix</h2>{table(["Hook", "Flag", "Claude", "Codex"], hook_rows)}<p class="note"><a href="{e(generated_link(page, "hook-matrix.json"))}">hook-matrix.json</a></p>'
    elif page.endswith("telemetry.html"):
        extra = f"""
        <h2>What Users See</h2>
        <p>The report below is the actual shipped HTML interface rendered with sanitized example events. It keeps measured removals separate from optimistic upper-bound estimates so users cannot accidentally add unlike claims.</p>
        <iframe class="telemetry-frame telemetry-frame-full" src="{e(site_link(page, "assets/telemetry-example.html"))}" title="Representative user-facing Token Savings Report"></iframe>
        <p class="note">Representative values only. The interface and labels come from the shipped renderer; no private local telemetry is published.</p>
        <h2>Generate Your Local Report</h2>
        <p>The HTML stats view is generated locally from the active savings log. Claude writes <code>.claude/state/savings.html</code>; the Codex shim writes <code>.less_tokens/state/savings.html</code>.</p>
        <pre><code>.claude/bin/python .claude/tools/stats.py --html
.less_tokens/bin/python .less_tokens/tools/stats.py --html</code></pre>
        <p class="note">Renderer source: <a href="{e(repo_link(page, ".claude/tools/stats.py"))}">.claude/tools/stats.py</a>. The Codex command is a shim around the same reporting contract.</p>
        <h2>External Dogfood Snapshot</h2>
        <img class="chart" src="{e(generated_link(page, "legacy-savings.svg"))}" alt="External dogfood legacy savings chart">
        <p class="note">Source: <a href="{e(repo_link(page, "eb_telemetry_9jul26.md"))}">eb_telemetry_9jul26.md</a></p>
        """
    elif page.endswith("budget-plane.html"):
        cats = DEFAULT_BUDGET_CONFIG["categories"]
        extra = table(["Category", "Default tokens"], [[e(k), e(v)] for k, v in cats.items()])
    elif page.endswith("skills.html"):
        skill_rows = [
            ["less-tokens", "Primary token-discipline workflow: search before broad reads, use symbol lookup, keep agent returns compact.", repo_link(page, ".agents/skills/less-tokens/SKILL.md")],
            ["bug-hunt", "Maintenance workflow for structured repo bug rounds, severity scoring, stop rules, and round logs.", repo_link(page, "agents/common/bug-hunt-protocol.md")],
            ["bugfix", "Focused diagnosis, patching, and verification, followed by a repository-wide search for the same root-cause construct. Applicable sibling instances ship together. This is a maintenance safeguard, not a token-saving strategy.", repo_link(page, "agents/common/bugfix-protocol.md")],
            ["continue", "Continue workflow for preserving current state and next actions in continue.md. A native pre-push hook rejects stale continue.md files even when the current session never re-read the file.", repo_link(page, ".claude/skills/continue/SKILL.md")],
        ]
        cards = ""
        for name, text, href in skill_rows:
            source = f'<p><a href="{e(href)}">source</a></p>' if href else '<p class="note">User-level skill; no repo-owned source yet.</p>'
            cards += f'<article class="card"><h3>{e(name)}</h3><p>{e(text)}</p>{source}</article>'
        icon_links = [
            ("Telemetry", "https://thenounproject.com/search/icons/?q=telemetry"),
            ("Measure", "https://thenounproject.com/search/icons/?q=measure"),
            ("Bug Hunt", "https://thenounproject.com/search/icons/?q=bug%20hunt"),
            ("Bug Fix", "https://thenounproject.com/search/icons/?q=bug%20fix"),
            ("Continue", "https://thenounproject.com/search/icons/?q=continue"),
        ]
        icon_items = "".join(f'<li><a href="{e(href)}">{e(label)}</a></li>' for label, href in icon_links)
        extra = f"""
        <h2>Subagent Support</h2>
        <p>The installed Claude and Codex skills share a pointer-first delegation contract while retaining platform-specific mechanics. Claude also has Task-boundary return capping and fan-out telemetry; Codex does not claim those hooks. See <a href="{e(site_link(page, 'reference/subagents.html'))}">Subagent Support</a> for shipped behavior, telemetry, and the evidence-gated roadmap.</p>
        <h2>Repo-Maintenance Skills</h2>
        <p>These are documented beside the scaffolding because they keep the repository maintainable. Only less-tokens is part of the primary token-saving mission; bug-hunt, bugfix, and continue are operational aids.</p>
        <div class="grid">{cards}</div>
        <h2>Noun Project Icons</h2>
        <p>These are the original bold Creative Commons SVG downloads. Attribution is stored centrally and printed below each icon instead of being repeated inside the artwork.</p>
        {noun_project_gallery(page)}
        <h2>Additional Searches</h2>
        <p>Use bold black-and-white noun or verb icons. Prefer Public Domain SVGs where available; otherwise use CC BY 3.0 SVGs with visible creator attribution near the asset or in the slide notes.</p>
        <ul>{icon_items}</ul>
        <p class="note">Final downloaded assets should record icon title, creator, license, source URL, and attribution text.</p>
        """
    return layout(page, title, f"""
    <section class="page-title"><h1>{e(title)}</h1><p>{e(summary)}</p></section>
    <section>{extra}</section>
    {source_box(page, [("Install script", "install.py"), ("Hook manifest", "agents/common/hooks/hook_manifest.py"), ("Budget package", "agents/common/budget/policy.py")])}
    """)


def reference_page(page: str, title: str) -> str:
    body = {
        "Install": """
        <section><h2>Install By Agent</h2><pre><code>python3 less_tokens/install.py                  # Claude (default)
python3 less_tokens/install.py --agent codex    # Codex
python3 less_tokens/install.py --agent both     # both</code></pre>
        <p>The initial index build runs by default. Use <code>--no-build</code> to defer the model download and configure search paths first.</p></section>
        <section><h2>Safe Upgrade</h2><pre><code>cd ~/myproject/less_tokens
git pull
python3 install.py --update --agent codex</code></pre>
        <p>Use the same agent selection as the original install. The Codex update path rewrites the rejected pre-CX21 flat hook list into the nested matcher-group schema accepted by current <code>codex-cli</code>; unrelated valid nested entries are preserved. Hook contracts are fixture-tested through <code>codex-cli 0.145.0</code>.</p>
        <p>In Git repositories, installation also wires a marked native <code>pre-push</code> hook that rejects a stale <code>continue.md</code>. Existing host-owned hooks are left untouched.</p></section>""",
        "Configuration": """
        <section><h2>Canonical Configuration</h2>
        <p>Search/index settings live in <code>.claude/tools/search_config.py</code>. Shared budget policy lives in <code>.less_tokens/config/budget.json</code>. Codex tool files are shims, not another configuration source.</p></section>
        <section><h2>Codex hooks.json Shape</h2>
        <p>The installer owns less_tokens hook entries and emits nested matcher groups. This abridged example shows the required structure:</p>
        <pre><code>{
  "hooks": [[{
    "event": "PostToolUse",
    "matcher": "apply_patch|Edit|Write",
    "hooks": [{"type": "command", "command": "…/index-refresh.py"}]
  }]]
}</code></pre>
        <p>Do not flatten command fields onto matcher objects. Re-run <code>install.py --update --agent codex</code> to migrate a legacy file instead of hand-editing generated entries.</p>
        <p class="note">CX21 fixed the writer. CX22 tracks health-check readers that still interpret the retired flat list.</p></section>""",
        "Subagent Support": """
        <section><h2>Support Boundary</h2>
        <p>Subagents are explicit delegated work, not an automatic routing feature. Spawn only when a child can absorb enough independent exploration or noisy verification to repay its fixed instruction and tool-schema cost.</p>
        <table><thead><tr><th>Capability</th><th>Claude</th><th>Codex</th></tr></thead><tbody>
          <tr><td>SA1 return cap</td><td>PostToolUse:Task replaces returns over 6,000 characters with key fields or bounded head/tail output; measured elision is logged.</td><td>No hookable Task-return boundary; no automatic cap claimed.</td></tr>
          <tr><td>SA2 fan-out telemetry</td><td>Pre/Post Task hooks pair prompt chars, return chars, subagent type, and session metadata. Measurement only; always wired.</td><td>No equivalent Task boundary; no event emitted.</td></tr>
          <tr><td>Delegation guidance</td><td>Prefer narrow explorer/verifier agents, pointer-only context, disjoint ownership, and compact returns.</td><td>Requires user authorization, defaults to fork_context=false, and separates explorer from worker.</td></tr>
        </tbody></table></section>
        <section><h2>Compact Contract</h2><pre><code>Task: answer &lt;specific question&gt;.
Context pointers: &lt;path:line and search command&gt;.
Constraints: do not paste full files, logs, or diffs.
Return only: files changed, findings, verification, blockers.</code></pre></section>
        <section><h2>Telemetry</h2>
        <p>Claude writes SA1 savings and SA2 cost events to <code>.claude/state/savings.jsonl</code>. Reports display spawn count, prompt characters sent, and return characters absorbed by the parent. Fan-out is a cost measurement, not a savings claim, and stays outside savings totals.</p>
        <pre><code>.claude/bin/python .claude/tools/stats.py --all</code></pre></section>
        <section><h2>Evidence-Gated Roadmap</h2>
        <table><thead><tr><th>ID</th><th>State</th><th>Candidate</th><th>Gate</th></tr></thead><tbody>
          <tr><td>SA1</td><td>Shipped</td><td>Generic bounded return digest.</td><td>Measured through subagent-cap records.</td></tr>
          <tr><td>SA2</td><td>Shipped / measuring</td><td>Prompt/return fan-out cost.</td><td>Collect a representative window before downstream changes.</td></tr>
          <tr><td>SA3</td><td>Blocked</td><td>Replace oversized spawn payloads with pointers.</td><td>Prompt-side waste must be material and task success must hold.</td></tr>
          <tr><td>SA4</td><td>Blocked</td><td>Per-child budget state.</td><td>Live payloads must expose distinct child session IDs plus concurrency risk.</td></tr>
          <tr><td>SA5</td><td>Blocked</td><td>Role-specific return digests.</td><td>At least two roles must beat SA1 measurably; rules must be versioned.</td></tr>
          <tr><td>SA6</td><td>Later</td><td>Digest replayed full child transcripts.</td><td>Reopen only if a future harness actually replays them.</td></tr>
        </tbody></table>
        <p class="note">BACKLOG.md is canonical for item state and full acceptance criteria.</p></section>""",
        "Troubleshooting": """
        <section><h2>Common Failures</h2>
        <ul>
          <li><strong>fastembed or model download failure:</strong> rerun after network is available, or install dependencies with --skip-deps only when the venv already has them.</li>
          <li><strong>Wrong venv path:</strong> pass --venv PATH or verify .less_tokens/bin/python and .claude/bin/python launch the intended interpreter.</li>
          <li><strong>Empty index or search results:</strong> inspect search_config.py, run embeddings.py refresh, and check indexed source directories.</li>
          <li><strong>Silent index refresh failure:</strong> inspect index-refresh.log and rerun the refresh command manually.</li>
          <li><strong>Codex hook JSON mistakes:</strong> verify the nested groups → matchers → command-hooks shape and rerun install.py --update --agent codex. Until CX22 lands, the Codex check/audit readers can falsely reject a valid nested file.</li>
          <li><strong>Windows-safe paths:</strong> prefer the generated python launchers and quoted paths from install.py.</li>
        </ul></section>
        """,
        "Commands": """
        <section><h2>Core Commands</h2><pre><code>python3 docs-site/scripts/build_docs.py
python3 docs-site/scripts/check_docs.py
.claude/bin/python .claude/tools/embeddings.py refresh
.less_tokens/bin/python .less_tokens/tools/budget_report.py</code></pre></section>
        """,
        "Decisions": """
        <section><h2>Recent Accepted Decisions</h2>
        <ul>
          <li><strong>DOC7:</strong> keep documentation brand assets under <code>docs-site/assets/</code>, not in the repository root.</li>
          <li><strong>DX1:</strong> every bugfix includes a repository-wide search for applicable same-pattern siblings.</li>
          <li><strong>CN1:</strong> a native <code>pre-push</code> hook enforces <code>continue.md</code> freshness without overwriting host-owned hooks.</li>
          <li><strong>CX32:</strong> the verified Codex hook-contract window extends through <code>codex-cli 0.145.0</code>.</li>
        </ul>
        <p>DECISIONS.md is canonical for evidence, verdict boundaries, and reopen conditions.</p></section>""",
        "Reference": """
        <section><h2>Reference Pages</h2><div class="grid">
          <article class="card"><h3><a href="install.html">Install</a></h3><p>Agent selection, safe updates, and index-build behavior.</p></article>
          <article class="card"><h3><a href="configuration.html">Configuration</a></h3><p>Search, budget, and hook configuration sources.</p></article>
          <article class="card"><h3><a href="subagents.html">Subagent Support</a></h3><p>SA1/SA2 behavior, delegation contracts, telemetry, limitations, and roadmap gates.</p></article>
          <article class="card"><h3><a href="troubleshooting.html">Troubleshooting</a></h3><p>Recovery guidance for common install and runtime failures.</p></article>
          <article class="card"><h3><a href="decisions.html">Decisions</a></h3><p>Current accepted boundaries and evidence-backed verdicts.</p></article>
          <article class="card"><h3><a href="backlog.html">Backlog</a></h3><p>Canonical open work and unblock conditions.</p></article>
        </div></section>""",
    }.get(title, f"""
        <section><p>This reference page is a navigable HTML layer over the canonical Markdown docs. Follow the source links for the full operational detail.</p></section>
    """)
    source_links = [("DOCUMENTATION.md", "DOCUMENTATION.md"), ("README.md", "README.md")]
    if title in {"Install", "Configuration"}:
        source_links.append(("install.py", "install.py"))
    if title == "Subagent Support":
        source_links = [
            ("DOCUMENTATION.md", "DOCUMENTATION.md"),
            ("BACKLOG.md", "BACKLOG.md"),
            ("Hook manifest", "agents/common/hooks/hook_manifest.py"),
            ("SA1 implementation", "agents/common/hooks/truncate_output.py"),
            ("SA2 implementation", "agents/common/hooks/subagent_fanout.py"),
            ("Codex delegation guidance", "agents/common/skills/less-tokens/codex-delegation.md"),
        ]
    if title == "Decisions":
        source_links = [("DECISIONS.md", "DECISIONS.md"), ("BACKLOG.md", "BACKLOG.md"), ("CHANGELOG.md", "CHANGELOG.md")]
    if title == "Backlog":
        source_links = [("BACKLOG.md", "BACKLOG.md")]
    if title == "Contributing":
        source_links = [("CHANGELOG.md", "CHANGELOG.md"), ("BACKLOG.md", "BACKLOG.md")]
    return layout(page, title, f"""
    <section class="page-title"><h1>{e(title)}</h1><p>Canonical operational detail remains in the root Markdown docs.</p></section>
    {body}
    {source_box(page, source_links)}
    """)


def write_assets(check: bool) -> bool:
    ok = True
    css = """\
:root{color-scheme:light;--ink:#17233a;--muted:#677184;--line:#cbd0d5;--bg:#f4f1ea;--panel:#fffdf8;--accent:#2457e6;--accent2:#ff6b55;--code:#e8edf8;--green:#1d8060;--coral-soft:#ffe1da;--cobalt-soft:#dce5ff}
*{box-sizing:border-box}body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--ink);background:var(--bg);line-height:1.55}a{color:#225f88;text-decoration:none}a:hover{text-decoration:underline}.site-header{position:sticky;top:0;z-index:10;display:flex;gap:24px;align-items:center;justify-content:space-between;padding:12px 28px;background:rgba(255,255,255,.94);border-bottom:1px solid var(--line);backdrop-filter:blur(8px)}.brand{display:flex;align-items:center;gap:10px;font-weight:800;color:var(--ink)}.brand img{width:32px;height:32px}nav{display:flex;gap:14px;flex-wrap:wrap;font-size:14px}main{max-width:1180px;margin:0 auto;padding:34px 24px 70px}.hero{min-height:72vh;display:grid;grid-template-columns:minmax(0,1fr) 260px;gap:48px;align-items:center}.hero h1,.page-title h1{font-size:clamp(34px,5vw,68px);line-height:1.02;margin:0 0 18px}.hero p,.page-title p{font-size:18px;color:var(--muted);max-width:780px}.hero img{width:100%;max-width:260px}.eyebrow{font-weight:800;letter-spacing:0;text-transform:uppercase;color:var(--accent);font-size:13px}.button{display:inline-flex;align-items:center;padding:10px 14px;border:1px solid var(--accent);background:var(--accent);color:white;border-radius:6px;font-weight:700;margin-right:8px}.button.secondary{background:transparent;color:var(--accent)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px}.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:18px}.card h3{margin-top:0}.two-col{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px}table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);font-size:14px}th,td{text-align:left;vertical-align:top;border-bottom:1px solid var(--line);padding:10px}th{background:#eaf0f2}.trace{margin-top:28px;padding:18px;border:1px solid var(--line);background:var(--panel);border-radius:8px}.trace h2{margin-top:0}.diagram{display:grid;grid-template-columns:1fr auto 1fr auto 1fr;gap:14px;align-items:center;margin:24px 0}.diagram div{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:18px;text-align:center}.diagram span{font-weight:800;color:var(--accent2)}.note{color:var(--muted);font-size:14px}.chart{width:100%;max-width:900px;background:white;border:1px solid var(--line);border-radius:8px}pre{background:var(--code);padding:16px;border-radius:8px;overflow:auto}.slide{min-height:calc(100vh - 58px);display:flex;flex-direction:column;justify-content:center;border-bottom:1px solid var(--line);padding:8vh 2vw}.slide h1{font-size:clamp(40px,7vw,86px);line-height:1;margin:0 0 22px}.slide p{font-size:clamp(19px,2.4vw,30px);max-width:900px;color:var(--muted)}.slide-count{font-size:13px!important;color:var(--accent)!important;font-weight:800}.presentation-page main{max-width:none;padding-top:0}@media(max-width:760px){.site-header{position:static;align-items:flex-start;flex-direction:column}.hero{grid-template-columns:1fr;min-height:auto}.hero img{max-width:150px}.diagram{grid-template-columns:1fr}.diagram span{text-align:center}main{padding:24px 16px}.slide{min-height:auto;padding:56px 4px}}@media(prefers-reduced-motion:no-preference){html{scroll-behavior:smooth}}@media print{.site-header{display:none}.slide{break-after:page;min-height:95vh}main{max-width:none}.card,.trace,table{break-inside:avoid}}
.presentation-page .slide{display:grid;grid-template-columns:minmax(300px,.86fr) minmax(360px,1fr);gap:42px;align-items:center;padding:7vh 4vw}.slide-copy{min-width:0}.slide-visual{margin:0;align-self:center}.slide-visual img{display:block;width:100%;height:min(68vh,620px);padding:clamp(28px,5vw,72px);object-fit:contain;border:1px solid var(--line);background:#f7f8fa;border-radius:8px}.slide-visual figcaption{margin-top:10px;color:var(--muted);font-size:14px}.slide-copy p:not(.slide-count){max-width:760px}.telemetry-frame{display:block;width:100%;height:min(68vh,650px);border:1px solid var(--line);border-radius:8px;background:var(--panel)}.telemetry-frame-full{height:760px;margin:18px 0 8px}@media(max-width:900px){.presentation-page .slide{grid-template-columns:1fr;gap:24px}.slide-visual img{height:min(58vh,520px);padding:32px}.telemetry-frame{height:620px}}@media print{.slide-visual img{height:52vh;max-height:52vh;padding:28px}.slide-visual figcaption{font-size:12px}.telemetry-frame{height:52vh}}
.np-gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;margin:16px 0 22px}.np-icon{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:14px}.np-icon img{display:block;width:100%;aspect-ratio:1/1;padding:12%;object-fit:contain;background:white;border:1px solid var(--line);border-radius:6px;filter:grayscale(1) contrast(1.2)}.np-icon h3{margin:12px 0 4px;font-size:15px}.np-icon p{margin:4px 0;font-size:13px;color:var(--muted)}.np-gallery.compact{grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin-top:12px;align-items:start}.np-gallery.compact .np-icon{padding:8px}.np-gallery.compact .np-icon h3{font-size:12px;margin-top:7px}.np-gallery.compact .np-icon p{display:none}.np-gallery.compact .np-icon img{height:clamp(96px,9vw,136px);aspect-ratio:auto;padding:clamp(14px,1.4vw,22px);border-radius:5px}@media(max-width:900px){.np-gallery.compact{grid-template-columns:repeat(2,minmax(0,1fr))}}

/* Selected homepage direction: systems-map explainer. */
.home-page{background-color:var(--bg);background-image:radial-gradient(rgba(94,107,130,.22) 1px,transparent 1px);background-size:20px 20px}.home-page .site-header{background:rgba(244,241,234,.94);border-color:var(--ink);padding:14px max(24px,calc((100vw - 1450px)/2))}.home-page .brand{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:18px}.home-page .site-header nav{font-weight:700}.home-page main{max-width:1500px;padding:62px 32px 100px}.home-hero{display:grid;grid-template-columns:minmax(390px,.76fr) minmax(650px,1.24fr);gap:54px;align-items:center;min-height:760px}.home-kicker{display:inline-flex;align-items:center;gap:9px;border:1px solid var(--ink);border-radius:99px;padding:8px 12px;margin:0;background:var(--panel);font:800 11px/1 ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase;letter-spacing:.08em}.home-kicker span{color:var(--accent2)}.home-intro h1{font-size:clamp(58px,5.6vw,88px);line-height:.92;letter-spacing:-.065em;max-width:700px;margin:28px 0 26px}.home-intro h1 em{font-style:normal;color:var(--accent)}.home-lede{font-size:20px;line-height:1.55;color:#505b6e;max-width:630px}.home-actions{display:flex;gap:12px;margin:30px 0}.home-button{display:inline-flex;align-items:center;justify-content:center;min-height:50px;padding:0 22px;border:1.5px solid var(--ink);border-radius:4px;background:var(--panel);color:var(--ink);box-shadow:4px 4px 0 var(--ink);font-weight:850}.home-button:hover{text-decoration:none;transform:translate(2px,2px);box-shadow:2px 2px 0 var(--ink)}.home-button.primary{background:var(--accent);color:white}.install-command{display:flex;align-items:center;justify-content:space-between;gap:16px;max-width:540px;padding:15px 18px;background:var(--ink);border-radius:5px;color:white}.install-command code{background:none;color:inherit}.install-command code:before{content:"$ ";color:var(--accent2)}.install-command button{border:0;background:transparent;color:#b9c2d3;font:800 10px ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase;letter-spacing:.12em;cursor:pointer}.home-proof{display:flex;align-items:center;gap:16px;border-top:1px solid var(--line);margin-top:34px;padding-top:18px;font:850 13px/1 ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase;letter-spacing:.1em}.home-proof i{width:54px;height:4px;background:linear-gradient(90deg,var(--accent) 0 31%,transparent 31% 36%,var(--accent2) 36% 66%,transparent 66% 71%,var(--green) 71%)}
.token-map{background:rgba(255,253,248,.94);border:1.5px solid var(--ink);box-shadow:9px 9px 0 #cbd1d8;padding:24px}.token-map-head{display:flex;justify-content:space-between;gap:16px;padding-bottom:16px;border-bottom:1px solid var(--line)}.token-map-head span{color:var(--muted);font:800 10px ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase;letter-spacing:.1em}.token-flow{display:grid;grid-template-columns:1fr 104px 1fr;gap:14px;min-height:395px;margin-top:18px}.token-lane{position:relative;padding:16px;border:1px solid var(--line)}.token-lane.before{background:#fff7f4}.token-lane.after{background:#f3f6ff}.token-lane-title{display:flex;justify-content:space-between;gap:12px;font-size:13px;font-weight:850}.token-lane-title b{font:900 28px/1 ui-monospace,SFMono-Regular,Menlo,monospace}.before .token-lane-title b{color:var(--accent2)}.after .token-lane-title b{color:var(--accent)}.token-blocks{display:grid;grid-template-columns:repeat(6,1fr);gap:6px;margin-top:24px}.token-blocks i{height:24px;border:1px solid #f8ad9f;background:var(--coral-soft)}.before .token-blocks i:nth-child(4n){background:#dfe2e5;border-color:#c7ccd0}.before .token-blocks i:nth-child(7n){background:white;border-style:dashed}.after .token-blocks{grid-template-columns:repeat(4,1fr);gap:8px}.after .token-blocks i{height:34px;background:var(--cobalt-soft);border-color:#97adf6}.after .token-blocks i:nth-child(4n){background:white;border-style:dashed}.token-lane p{position:absolute;left:16px;right:16px;bottom:4px;padding-top:12px;border-top:1px solid;color:var(--muted);font:700 11px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace}.token-lane p strong{display:block;color:var(--ink);font-size:13px}.token-router{display:flex;flex-direction:column;justify-content:center;gap:14px}.token-router span{padding:14px 7px;border:1.5px solid var(--ink);border-top:5px solid var(--accent);background:var(--panel);box-shadow:3px 3px 0 var(--ink);text-align:center;font:850 9px/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase}.token-router span:nth-child(2){border-top-color:var(--accent2)}.token-router span:nth-child(3){border-top-color:var(--green)}.workload-control{display:flex;justify-content:space-between;margin-top:22px;font:800 11px ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase;color:var(--muted)}.workload-control output{color:var(--ink)}.workload-range{width:100%;accent-color:var(--accent)}.token-meter{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:14px}.token-meter span{display:flex;align-items:end;justify-content:space-between;border-top:1px solid var(--line);padding-top:10px}.token-meter small{font:800 9px ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase;color:var(--muted)}.token-meter strong{font:900 22px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--green)}.token-caveat{margin:12px 0 0;color:var(--muted);font-size:11px}
.home-section{margin-top:120px}.section-number{margin-bottom:24px;color:var(--accent);font:850 11px ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase;letter-spacing:.12em}.section-heading{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(280px,.75fr);gap:60px;align-items:end;padding-bottom:28px;border-bottom:1.5px solid var(--ink)}.section-heading h2{max-width:850px;margin:0;font-size:clamp(38px,4vw,64px);line-height:1;letter-spacing:-.04em}.section-heading p{margin:0;color:var(--muted);font-size:18px}.strategy-examples{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-top:22px}.example-card{background:var(--panel);border:1px solid var(--line)}.example-card>img{display:block;width:100%;aspect-ratio:16/10;padding:clamp(24px,3.2vw,52px);object-fit:contain;border-bottom:1px solid var(--line);background:#f7f8fa}.example-card>div{padding:20px}.example-card span{font:800 10px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--accent);text-transform:uppercase}.example-card h3{margin:8px 0}.example-card p{color:var(--muted)}.example-card a{font-weight:800}.example-steps{list-style:none;padding:0;margin:22px 0 0;border-top:1px solid var(--line)}.example-steps li{display:grid;grid-template-columns:120px 1fr;gap:26px;padding:26px 0;border-bottom:1px solid var(--line)}.example-steps li>span{font:850 12px ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase;color:var(--accent2)}.example-steps code{display:inline-block;padding:7px 10px;background:var(--code);color:var(--ink);font-size:15px}.example-steps p{margin:8px 0 0;color:var(--muted)}.evidence-links{display:grid;grid-template-columns:1fr 1fr;border-left:1px solid var(--line);margin-top:22px}.evidence-links a{display:flex;flex-direction:column;gap:10px;min-height:150px;padding:24px;border-right:1px solid var(--line);border-bottom:1px solid var(--line);background:rgba(255,253,248,.7);color:var(--ink)}.evidence-links a:hover{background:var(--cobalt-soft);text-decoration:none}.evidence-links span{color:var(--accent);font:800 10px ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase}.evidence-links strong{font-size:20px}.canonical-note{max-width:850px;margin:34px 0 0;color:var(--muted)}
@media(max-width:1100px){.home-hero{grid-template-columns:1fr;min-height:auto}.token-map{max-width:850px}.strategy-examples{grid-template-columns:1fr}.example-card{display:grid;grid-template-columns:minmax(260px,.8fr) 1.2fr}.example-card>img{height:100%;aspect-ratio:auto;border-right:1px solid var(--line);border-bottom:0}}@media(max-width:760px){.home-page main{padding:40px 16px 72px}.home-intro h1{font-size:54px}.home-actions{flex-direction:column}.home-button{width:100%}.token-flow{grid-template-columns:1fr;min-height:0}.token-router{flex-direction:row}.token-lane{min-height:350px}.token-meter,.section-heading,.evidence-links{grid-template-columns:1fr}.strategy-examples{grid-template-columns:1fr}.example-card{display:block}.example-card>img{aspect-ratio:16/10;border-right:0;border-bottom:1px solid var(--line)}.section-heading{gap:20px}.home-section{margin-top:80px}.example-steps li{grid-template-columns:70px 1fr}.install-command{align-items:flex-start}.home-page .site-header{padding:14px 16px}}
"""
    css += """

/* Cohesive hybrid: Aurora depth for orientation, editorial light for reading. */
:root{--night:#07111f;--night-2:#0c1b32;--night-3:#142948;--glow:#69a7ff;--violet:#9582ff;--aqua:#66e2d2;--paper:#f5f3ed;--paper-cool:#eef2f8;--glass:rgba(13,28,52,.74);--glass-line:rgba(181,211,255,.22);--soft-shadow:0 22px 64px rgba(26,40,70,.13)}
body.hybrid-page{background:radial-gradient(circle at 82% 0,rgba(105,167,255,.12),transparent 34%),linear-gradient(180deg,var(--paper-cool),var(--paper) 42%,#f7f5ef);color:var(--ink)}
.hybrid-page .site-header{position:sticky;top:0;z-index:20;padding:12px max(24px,calc((100vw - 1440px)/2));background:rgba(246,248,252,.88);border-bottom:1px solid rgba(96,113,142,.2);box-shadow:0 8px 34px rgba(22,38,65,.07);backdrop-filter:blur(18px)}
.hybrid-page .brand{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.02em;color:var(--night)}
.hybrid-page .brand img{filter:drop-shadow(0 5px 10px rgba(20,67,132,.2))}
.hybrid-page nav{gap:5px}
.hybrid-page nav a{padding:7px 10px;border-radius:999px;color:#40516c;font-weight:700;transition:background .2s ease,color .2s ease}
.hybrid-page nav a:hover{background:rgba(105,167,255,.12);color:var(--night);text-decoration:none}
.hybrid-page nav a[aria-current=page]{background:var(--night);color:#edf5ff}
.hybrid-page main{max-width:1280px;padding:46px 28px 92px}
.hybrid-page .page-title{position:relative;isolation:isolate;overflow:hidden;min-height:330px;display:flex;flex-direction:column;justify-content:flex-end;margin:0 0 48px;padding:clamp(34px,5vw,70px);color:#edf5ff;background:radial-gradient(circle at 82% 10%,rgba(105,167,255,.5),transparent 35%),radial-gradient(circle at 12% 115%,rgba(149,130,255,.34),transparent 42%),linear-gradient(135deg,var(--night),var(--night-2) 62%,var(--night-3));border:1px solid rgba(181,211,255,.22);border-radius:28px;box-shadow:0 30px 80px rgba(7,17,31,.28)}
.hybrid-page .page-title:before,.hybrid-page .page-title:after{content:"";position:absolute;z-index:-1;border:1px solid rgba(181,211,255,.18);border-radius:50%}
.hybrid-page .page-title:before{width:360px;height:360px;right:-80px;top:-118px;box-shadow:0 0 90px rgba(105,167,255,.18)}
.hybrid-page .page-title:after{width:230px;height:230px;right:115px;top:-40px}
.hybrid-page .page-title h1{max-width:900px;margin:10px 0 18px;font-size:clamp(48px,6.5vw,86px);letter-spacing:-.055em}
.hybrid-page .page-title p{max-width:760px;margin:0;color:rgba(230,240,255,.76)}
.hybrid-page .page-title a{color:#b7d4ff;text-decoration-color:rgba(183,212,255,.45)}
.hybrid-page .eyebrow,.hybrid-page .section-number{color:#315ecc;font:800 11px/1.2 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.12em;text-transform:uppercase}
.hybrid-page .page-title .eyebrow{color:#90baff}
.hybrid-page .card{border:1px solid rgba(104,119,144,.2);border-radius:18px;background:rgba(255,255,255,.74);box-shadow:var(--soft-shadow);backdrop-filter:blur(12px);transition:transform .2s ease,box-shadow .2s ease}
.hybrid-page .card:hover{transform:translateY(-2px);box-shadow:0 26px 70px rgba(26,40,70,.17)}
.hybrid-page table{overflow:hidden;border:1px solid rgba(104,119,144,.22);border-radius:16px;background:rgba(255,255,255,.78);box-shadow:var(--soft-shadow)}
.hybrid-page th{background:linear-gradient(180deg,#e8eef9,#e3e9f3);color:#273955;font:800 11px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.06em;text-transform:uppercase}
.hybrid-page th,.hybrid-page td{padding:13px 14px;border-color:rgba(104,119,144,.16)}
.hybrid-page tbody tr:hover{background:rgba(105,167,255,.07)}
.hybrid-page pre{border:1px solid rgba(96,113,142,.18);border-radius:14px;background:#e7edf8;box-shadow:inset 0 1px 0 rgba(255,255,255,.7)}
.hybrid-page .trace{position:relative;overflow:hidden;margin-top:42px;padding:26px;color:#eaf3ff;background:radial-gradient(circle at 90% 0,rgba(105,167,255,.26),transparent 36%),linear-gradient(135deg,var(--night),var(--night-2));border:1px solid var(--glass-line);border-radius:20px;box-shadow:0 24px 64px rgba(7,17,31,.2)}
.hybrid-page .trace h2{color:white}.hybrid-page .trace a{color:#a9caff}.hybrid-page .trace li::marker{color:var(--glow)}
.hybrid-page .content-section{margin:58px 0 34px}

/* Overview: one Aurora console set inside the same editorial shell. */
.home-page{background:radial-gradient(circle at 82% 0,rgba(105,167,255,.12),transparent 34%),linear-gradient(180deg,var(--paper-cool),var(--paper) 42%,#f7f5ef);background-size:auto}
.home-page .site-header{padding:12px max(24px,calc((100vw - 1440px)/2));background:rgba(246,248,252,.88);border-color:rgba(96,113,142,.2)}
.home-page main{max-width:1500px;padding:46px 32px 104px}
.home-hero{position:relative;isolation:isolate;overflow:hidden;grid-template-columns:minmax(390px,.78fr) minmax(620px,1.22fr);gap:52px;min-height:740px;padding:clamp(34px,5vw,72px);color:#edf5ff;background:radial-gradient(circle at 82% 8%,rgba(105,167,255,.48),transparent 36%),radial-gradient(circle at 8% 110%,rgba(149,130,255,.34),transparent 42%),linear-gradient(135deg,var(--night),var(--night-2) 62%,var(--night-3));border:1px solid var(--glass-line);border-radius:30px;box-shadow:0 34px 90px rgba(7,17,31,.3)}
.home-hero:before{content:"";position:absolute;inset:0;z-index:-1;background-image:linear-gradient(rgba(181,211,255,.05) 1px,transparent 1px),linear-gradient(90deg,rgba(181,211,255,.05) 1px,transparent 1px);background-size:34px 34px;mask-image:linear-gradient(to bottom,black,transparent 88%)}
.home-kicker{border-color:rgba(181,211,255,.35);background:rgba(7,17,31,.35);color:#dceaff;box-shadow:0 0 28px rgba(105,167,255,.14);backdrop-filter:blur(12px)}
.home-kicker span{color:#93bcff}
.home-intro{position:relative;z-index:3}.home-intro h1{color:#f4f8ff;text-wrap:balance}.home-intro h1 em{color:#9ac1ff;text-shadow:0 0 35px rgba(105,167,255,.38)}
.home-lede{color:rgba(230,240,255,.75)}
.home-button{border-color:rgba(225,238,255,.72);background:rgba(235,243,255,.08);color:#f1f7ff;box-shadow:4px 4px 0 rgba(198,218,247,.35);backdrop-filter:blur(10px)}
.home-button.primary{border-color:#79aaff;background:linear-gradient(135deg,#3167e5,#5b79f0);box-shadow:4px 4px 0 rgba(128,171,255,.34),0 14px 35px rgba(49,103,229,.3)}
.home-button:hover{background:rgba(235,243,255,.14)}
.install-command{max-width:560px;border:1px solid rgba(181,211,255,.16);background:rgba(4,11,23,.62);box-shadow:0 16px 38px rgba(4,11,23,.25);backdrop-filter:blur(12px)}
.install-command code:before{color:#75e4d4}.install-command button{color:#acc5ea}
.home-proof{border-color:rgba(181,211,255,.18);color:rgba(230,240,255,.78)}
.aurora-console{position:relative;min-height:585px;padding:22px;isolation:isolate}
.console-kicker{position:relative;z-index:5;margin:0;color:rgba(230,240,255,.66);font:800 10px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.12em;text-transform:uppercase}
.aurora-icon-field{position:absolute;inset:0;z-index:-1}
.aurora-icon{position:absolute;background:transparent;opacity:.72;filter:invert(80%) sepia(36%) saturate(1442%) hue-rotate(187deg) brightness(108%) contrast(103%) drop-shadow(0 18px 28px rgba(105,167,255,.34))}
.icon-search{width:150px;right:4%;top:1%;transform:rotate(7deg)}
.icon-compact{width:190px;left:2%;top:20%;opacity:.24;transform:rotate(-13deg)}
.icon-output{width:104px;right:14%;top:31%;opacity:.54;transform:rotate(6deg)}
.orbit-ring{position:absolute;border:1px solid rgba(181,211,255,.17);border-radius:50%;box-shadow:0 0 55px rgba(105,167,255,.08)}
.ring-one{width:410px;height:410px;right:-24px;top:-55px}.ring-two{width:265px;height:265px;right:48px;top:18px}
.overview-stats{position:absolute;z-index:4;left:7%;right:3%;bottom:2%;display:grid;gap:14px;padding:24px;color:#eaf3ff;background:var(--glass);border:1px solid var(--glass-line);border-radius:20px;box-shadow:0 28px 72px rgba(3,10,22,.38);backdrop-filter:blur(20px)}
.stats-heading,.stats-total,.stats-bars div,.stats-upper{display:flex;align-items:center;justify-content:space-between;gap:14px}
.stats-heading{color:rgba(225,238,255,.66);font:800 10px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.1em;text-transform:uppercase}
.stats-total{padding:13px 0;border-block:1px solid rgba(181,211,255,.14)}
.stats-total>strong{font:900 clamp(30px,3.2vw,48px) ui-monospace,SFMono-Regular,Menlo,monospace;color:#f4f8ff}.stats-total small{font-size:11px;color:#adc6e9}
.stats-bars{display:grid;gap:10px}.stats-bars div{display:grid;grid-template-columns:minmax(88px,1fr) 2fr auto;font-size:13px}
.stats-bars i{height:8px;border-radius:999px;background:linear-gradient(90deg,#78aaff 0 var(--amount),rgba(188,211,244,.12) var(--amount));box-shadow:0 0 20px rgba(105,167,255,.22)}
.stats-upper{padding-top:12px;border-top:1px solid rgba(181,211,255,.14);color:#cebfff}.overview-stats>p{margin:0;color:rgba(225,238,255,.58);font-size:11px}
.home-section{margin-top:105px}.section-heading{border-color:rgba(31,47,73,.28)}
.section-heading h2{color:var(--night)}
.strategy-examples{gap:22px}.example-card{overflow:hidden;border:1px solid rgba(104,119,144,.19);border-radius:18px;background:linear-gradient(180deg,#e8edf9 0 260px,rgba(255,255,255,.78) 260px);box-shadow:var(--soft-shadow)}
.example-card>img{height:250px;aspect-ratio:auto;padding:44px 60px;border:0;background:transparent;opacity:.76;filter:invert(28%) sepia(36%) saturate(1575%) hue-rotate(188deg) brightness(91%) contrast(96%) drop-shadow(0 18px 22px rgba(52,94,176,.22))}
.example-card>div{padding:24px}.example-card span{color:#315ecc}.example-card p{color:#596579}.example-card a{color:#2457b7}
.example-steps li{border-color:rgba(104,119,144,.2)}.example-steps li>span{color:#6c56c7}.example-steps code{border:1px solid rgba(104,119,144,.16);border-radius:8px;background:#e7edf8}
.evidence-links{border-color:rgba(104,119,144,.2)}.evidence-links a{border-color:rgba(104,119,144,.18);background:rgba(255,255,255,.7);box-shadow:inset 0 0 0 0 rgba(105,167,255,0);transition:background .2s ease,box-shadow .2s ease}.evidence-links a:hover{background:#eef3ff;box-shadow:inset 4px 0 0 #5f8ff0}.evidence-links span{color:#315ecc}

/* Strategy pages use the identical Aurora surface, then return to readable paper. */
.strategy-title{display:grid!important;grid-template-columns:minmax(0,1fr) minmax(220px,.42fr);align-items:center;gap:40px}
.strategy-title>div{position:relative;z-index:2}.strategy-title-icon{position:relative;z-index:1;width:min(100%,280px);justify-self:center;background:transparent;opacity:.66;filter:invert(80%) sepia(36%) saturate(1442%) hue-rotate(187deg) brightness(108%) contrast(103%) drop-shadow(0 24px 34px rgba(105,167,255,.4));transform:rotate(5deg)}
.strategy-comparison{gap:24px;margin-bottom:54px}.strategy-comparison article{position:relative;overflow:hidden;padding:28px;border:1px solid rgba(104,119,144,.2);border-radius:18px;background:rgba(255,255,255,.72);box-shadow:var(--soft-shadow)}
.strategy-comparison article:last-child{background:radial-gradient(circle at 100% 0,rgba(105,167,255,.16),transparent 46%),rgba(255,255,255,.8)}
.strategy-comparison h2{margin:7px 0 12px;color:var(--night)}
.strategy-detail-page .grid{margin-top:34px}

/* Architecture and reference pages inherit the same rhythm and evidence surface. */
.architecture-page .diagram{position:relative;margin:38px 0 50px;padding:30px;border:1px solid rgba(104,119,144,.2);border-radius:20px;background:rgba(255,255,255,.68);box-shadow:var(--soft-shadow)}
.architecture-page .diagram div{border:1px solid rgba(104,119,144,.2);border-radius:14px;background:linear-gradient(160deg,#f9fbff,#e8eef8);box-shadow:0 14px 34px rgba(26,40,70,.09)}
.architecture-page .diagram span{color:#536fd4}
.architecture-page .two-col{gap:34px}.architecture-page .two-col article{padding:6px 8px}
.docs-detail-page section:not(.page-title){margin:34px 0}.docs-detail-page h2{color:var(--night)}
.chart{border-color:rgba(104,119,144,.2);border-radius:16px;box-shadow:var(--soft-shadow)}

/* Presentation stays in the same family instead of becoming a separate theme. */
.presentation-page .slide{border-color:rgba(104,119,144,.2)}
.presentation-page .slide-visual{overflow:hidden;padding:clamp(22px,3vw,44px);border:1px solid rgba(104,119,144,.18);border-radius:20px;background:radial-gradient(circle at 80% 10%,rgba(105,167,255,.2),transparent 42%),linear-gradient(145deg,#eef3fb,#e6ebf4);box-shadow:var(--soft-shadow)}
.presentation-page .slide-visual img{height:min(58vh,540px);padding:0;border:0;background:transparent;opacity:.78;filter:invert(28%) sepia(36%) saturate(1575%) hue-rotate(188deg) brightness(91%) contrast(96%) drop-shadow(0 22px 28px rgba(52,94,176,.24))}
.presentation-page .slide-visual figcaption{color:#596579}.presentation-page .slide h1{color:var(--night)}

@media(max-width:1100px){.home-hero{grid-template-columns:1fr;min-height:auto}.aurora-console{min-height:570px;max-width:850px}.strategy-title{grid-template-columns:1fr minmax(180px,.34fr)}.example-card{background:linear-gradient(90deg,#e8edf9 0 36%,rgba(255,255,255,.78) 36%)}}
@media(max-width:760px){.hybrid-page .site-header{position:static}.hybrid-page main{padding:28px 16px 72px}.hybrid-page .page-title{min-height:300px;padding:30px 24px;border-radius:22px}.hybrid-page .page-title h1{font-size:48px}.home-page main{padding:28px 16px 76px}.home-hero{padding:34px 22px;border-radius:22px}.home-intro h1{font-size:54px}.aurora-console{min-height:600px;padding:0}.overview-stats{left:0;right:0}.icon-search{width:125px}.icon-compact{width:150px}.ring-one{right:-150px}.stats-bars div{grid-template-columns:1fr auto}.stats-bars i{grid-column:1/-1}.strategy-title{grid-template-columns:1fr}.strategy-title-icon{width:170px;position:absolute;right:-24px;top:20px;opacity:.2}.strategy-comparison{grid-template-columns:1fr}.example-card{display:block;background:linear-gradient(180deg,#e8edf9 0 240px,rgba(255,255,255,.78) 240px)}.example-card>img{height:240px}.presentation-page .slide-visual{padding:22px}}
@media(prefers-reduced-motion:reduce){.hybrid-page *{scroll-behavior:auto!important;transition:none!important}}
"""
    js = """\
document.addEventListener("keydown", event => {
  if (!document.body.classList.contains("presentation-page")) return;
  const slides = Array.from(document.querySelectorAll(".slide"));
  const current = Math.max(0, slides.findIndex(slide => {
    const box = slide.getBoundingClientRect();
    return box.top <= window.innerHeight * 0.4 && box.bottom > window.innerHeight * 0.4;
  }));
  let next = current;
  if (event.key === "ArrowRight" || event.key === "PageDown" || event.key === " ") next = Math.min(slides.length - 1, current + 1);
  if (event.key === "ArrowLeft" || event.key === "PageUp") next = Math.max(0, current - 1);
  if (next !== current) {
    event.preventDefault();
    slides[next].scrollIntoView({block: "start"});
    history.replaceState(null, "", "#" + slides[next].id);
  }
});

const workload = document.querySelector("#workload");
if (workload) {
  const before = document.querySelector("[data-before-value]");
  const after = document.querySelector("[data-after-value]");
  const output = document.querySelector("[data-workload-output]");
  const reduction = document.querySelector("[data-reduction-value]");
  const updateWorkload = () => {
    const input = Number(workload.value);
    const relevant = Math.max(4, Math.round(input / 3));
    before.textContent = `${input}k`;
    after.textContent = `${relevant}k`;
    output.textContent = `${input}k`;
    reduction.textContent = `${Math.round((1 - relevant / input) * 100)}%`;
  };
  workload.addEventListener("input", updateWorkload);
  updateWorkload();
}

document.querySelectorAll("[data-copy-command]").forEach(button => {
  button.addEventListener("click", async () => {
    const command = button.dataset.copyCommand;
    try {
      await navigator.clipboard.writeText(command);
      button.textContent = "Copied";
      window.setTimeout(() => { button.textContent = "Copy"; }, 1400);
    } catch (_error) {
      button.textContent = "Select command";
    }
  });
});
"""
    files = {"site.css": css, "site.js": js, "telemetry-example.html": telemetry_example_html()}
    ASSETS.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        path = ASSETS / name
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                print(f"stale asset: {path.relative_to(REPO)}", file=sys.stderr)
                ok = False
        else:
            path.write_text(text, encoding="utf-8")
    mark_src = DOCS / "assets" / "LT_mark.svg"
    mark_dst = ASSETS / "LT_mark.svg"
    if check:
        if not mark_dst.exists() or mark_dst.read_text(encoding="utf-8") != mark_src.read_text(encoding="utf-8"):
            print(f"stale asset: {mark_dst.relative_to(REPO)}", file=sys.stderr)
            ok = False
    else:
        shutil.copyfile(mark_src, mark_dst)
    ok = write_slide_visuals(check) and ok
    nojekyll = SITE / ".nojekyll"
    if check:
        if not nojekyll.exists() or nojekyll.read_text(encoding="utf-8") != "":
            print(f"stale root marker: {nojekyll.relative_to(REPO)}", file=sys.stderr)
            ok = False
    else:
        nojekyll.write_text("", encoding="utf-8")
    return ok


def all_pages() -> dict[str, str]:
    pages = {
        "index.html": overview_page("index.html"),
        "strategy-map.html": strategy_map_page("strategy-map.html"),
        "architecture.html": architecture_page("architecture.html"),
        "privacy.html": privacy_page("privacy.html"),
        "presentation.html": presentation_page("presentation.html"),
    }
    for slug, details in STRATEGY_DETAILS.items():
        page = f"strategies/{slug}.html"
        pages[page] = strategy_page(page, slug, details)
    for page, (title, summary) in SCAFFOLDING_PAGES.items():
        pages[page] = scaffolding_page(page, title, summary)
    for page, title in REFERENCE_PAGES.items():
        pages[page] = reference_page(page, title)
    pages["strategies/index.html"] = strategy_map_page("strategies/index.html")
    pages["reference/index.html"] = reference_page("reference/index.html", "Reference")
    pages["scaffolding/index.html"] = scaffolding_page("scaffolding/index.html", "Scaffolding", "The machinery that makes token reduction enforceable and maintainable.")
    return pages


def write_pages(check: bool) -> bool:
    ok = True
    pages = all_pages()
    for rel, text in pages.items():
        path = SITE / rel
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                print(f"stale page: {path.relative_to(REPO)}", file=sys.stderr)
                ok = False
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    return ok


def build(check: bool = False) -> int:
    if not check:
        SITE.mkdir(parents=True, exist_ok=True)
    ok = True
    ok = write_generated_data(check) and ok
    ok = write_assets(check) and ok
    ok = write_pages(check) and ok
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if generated site files are stale")
    args = parser.parse_args(argv)
    return build(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())

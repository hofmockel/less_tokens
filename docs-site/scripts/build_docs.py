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
    ("data-slide", "Data Caveats", "Chars divided by four are estimates, EB telemetry is external dogfood evidence, and qualitative claims stay labeled."),
    ("drift-prevention", "Drift Prevention", "Generated docs, parity JSON, tests, and source-link checks keep the HTML layer honest."),
    ("operations", "Operational Playbook", "Install, verify, report, troubleshoot, and update without needing a networked docs build."),
    ("contribution-map", "Contribution Map", "Add the strategy, wire the manifest, add tests and telemetry, then let docs generation expose it."),
]


REFERENCE_PAGES: dict[str, str] = {
    "reference/install.html": "Install",
    "reference/configuration.html": "Configuration",
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
    return "".join(f'<a href="{e(site_link(page, href))}">{e(label)}</a>' for href, label in items)


def layout(page: str, title: str, body: str, *, presentation: bool = False) -> str:
    depth = len(Path(page).parent.parts)
    prefix = "../" * depth
    classes = "presentation-page" if presentation else ""
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
    <a class="brand" href="{e(site_link(page, 'index.html'))}"><img src="{prefix}assets/LT_logo_small.png" alt=""> less_tokens</a>
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
    cards = [
        ("Presentation", "A 25-screen walkthrough for peer engineers.", site_link(page, "presentation.html")),
        ("Strategy Map", "Buckets, hooks, parity, and source links generated from code.", site_link(page, "strategy-map.html")),
        ("Scaffolding", "Installer, adapters, telemetry, skills, tests, and generated-doc controls.", site_link(page, "scaffolding/installer.html")),
        ("Troubleshooting", "Fastembed downloads, venv paths, empty indexes, hook JSON, and Windows paths.", site_link(page, "reference/troubleshooting.html")),
    ]
    return layout(page, "Overview", f"""
    <section class="hero">
      <div>
        <p class="eyebrow">Engineer documentation</p>
        <h1>Token control that is visible, enforceable, and measured.</h1>
        <p>less_tokens adds a static HTML layer alongside README.md and DOCUMENTATION.md. It explains the token-reduction strategies and the scaffolding that keeps them portable across Claude and Codex.</p>
        <p class="actions"><a class="button" href="{e(site_link(page, 'presentation.html'))}">Open presentation</a><a class="button secondary" href="{e(site_link(page, 'strategy-map.html'))}">View strategy map</a></p>
      </div>
      <img src="assets/LT_logo.png" alt="less_tokens logo">
    </section>
    <section>
      <h2>Canonical Sources Stay Canonical</h2>
      <p>This site is additive. Operational detail remains in <a href="{e(repo_link(page, 'README.md'))}">README.md</a> and <a href="{e(repo_link(page, 'DOCUMENTATION.md'))}">DOCUMENTATION.md</a>; generated matrices come from code registries.</p>
      {card_grid(cards)}
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
        link = "strategy-map.html" if "Strategy" in title or "Matrix" in title else "architecture.html"
        slides.append(f"""
        <section class="slide" id="{e(anchor)}" tabindex="-1">
          <p class="slide-count">{index:02d} / {len(SLIDES):02d}</p>
          <h1>{e(title)}</h1>
          <p>{e(text)}</p>
          <a href="{e(site_link(page, link))}">Deep link</a>
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
    return layout(page, details["title"], f"""
    <section class="page-title"><p class="eyebrow">{e(details["bucket"])} bucket</p><h1>{e(details["title"])}</h1><p>{e(details["problem"])}</p></section>
    <section class="two-col">
      <article><h2>Before</h2><p>Broad context enters the transcript before relevance is checked.</p></article>
      <article><h2>After</h2><p>{e(details["flow"])}</p></article>
    </section>
    <section><h2>Enforcement And Parity</h2>{table(["Hook", "Claude", "Codex", "Claude parity", "Codex parity"], hook_rows)}</section>
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
        extra = f'<h2>Installer Flags</h2>{table(["Flags", "Help", "Action", "Default"], flag_rows)}<p class="note"><a href="{e(generated_link(page, "installer-flags.json"))}">installer-flags.json</a></p>'
    elif page.endswith("hook-manifest.html"):
        hook_rows = [[e(row["name"]), e(row.get("optional_flag") or "always"), e(row["claude_script"]), e(row["codex_script"])] for row in hook_matrix()]
        extra = f'<h2>Hook Matrix</h2>{table(["Hook", "Flag", "Claude", "Codex"], hook_rows)}<p class="note"><a href="{e(generated_link(page, "hook-matrix.json"))}">hook-matrix.json</a></p>'
    elif page.endswith("telemetry.html"):
        extra = f'<h2>External Dogfood Snapshot</h2><img class="chart" src="{e(generated_link(page, "legacy-savings.svg"))}" alt="External dogfood legacy savings chart"><p class="note">Source: <a href="{e(repo_link(page, "eb_telemetry_9jul26.md"))}">eb_telemetry_9jul26.md</a></p>'
    elif page.endswith("budget-plane.html"):
        cats = DEFAULT_BUDGET_CONFIG["categories"]
        extra = table(["Category", "Default tokens"], [[e(k), e(v)] for k, v in cats.items()])
    return layout(page, title, f"""
    <section class="page-title"><h1>{e(title)}</h1><p>{e(summary)}</p></section>
    <section>{extra}</section>
    {source_box(page, [("Install script", "install.py"), ("Hook manifest", "agents/common/hooks/hook_manifest.py"), ("Budget package", "agents/common/budget/policy.py"), ("Documentation plan", "HTML_DOCUMENTATION_PLAN.md")])}
    """)


def reference_page(page: str, title: str) -> str:
    body = {
        "Troubleshooting": """
        <section><h2>Common Failures</h2>
        <ul>
          <li><strong>fastembed or model download failure:</strong> rerun after network is available, or install dependencies with --skip-deps only when the venv already has them.</li>
          <li><strong>Wrong venv path:</strong> pass --venv PATH or verify .less_tokens/bin/python and .claude/bin/python launch the intended interpreter.</li>
          <li><strong>Empty index or search results:</strong> inspect search_config.py, run embeddings.py refresh, and check indexed source directories.</li>
          <li><strong>Silent index refresh failure:</strong> inspect index-refresh.log and rerun the refresh command manually.</li>
          <li><strong>Hook JSON mistakes:</strong> compare settings against generated hook-matrix.json and run install.py --check.</li>
          <li><strong>Windows-safe paths:</strong> prefer the generated python launchers and quoted paths from install.py.</li>
        </ul></section>
        """,
        "Commands": """
        <section><h2>Core Commands</h2><pre><code>python3 docs-site/scripts/build_docs.py
python3 docs-site/scripts/check_docs.py
.claude/bin/python .claude/tools/embeddings.py refresh
.less_tokens/bin/python .less_tokens/tools/budget_report.py</code></pre></section>
        """,
    }.get(title, f"""
        <section><p>This reference page is a navigable HTML layer over the canonical Markdown docs. Follow the source links for the full operational detail.</p></section>
    """)
    source_links = [("DOCUMENTATION.md", "DOCUMENTATION.md"), ("README.md", "README.md")]
    if title == "Decisions":
        source_links = [("DECISIONS.md", "DECISIONS.md")]
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
:root{color-scheme:light;--ink:#16202a;--muted:#5d6975;--line:#d8e0e7;--bg:#f7f8fa;--panel:#ffffff;--accent:#2f7d78;--accent2:#9a5b20;--code:#eef3f5}
*{box-sizing:border-box}body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--ink);background:var(--bg);line-height:1.55}a{color:#225f88;text-decoration:none}a:hover{text-decoration:underline}.site-header{position:sticky;top:0;z-index:10;display:flex;gap:24px;align-items:center;justify-content:space-between;padding:12px 28px;background:rgba(255,255,255,.94);border-bottom:1px solid var(--line);backdrop-filter:blur(8px)}.brand{display:flex;align-items:center;gap:10px;font-weight:800;color:var(--ink)}.brand img{width:30px;height:30px}nav{display:flex;gap:14px;flex-wrap:wrap;font-size:14px}main{max-width:1180px;margin:0 auto;padding:34px 24px 70px}.hero{min-height:72vh;display:grid;grid-template-columns:minmax(0,1fr) 260px;gap:48px;align-items:center}.hero h1,.page-title h1{font-size:clamp(34px,5vw,68px);line-height:1.02;margin:0 0 18px}.hero p,.page-title p{font-size:18px;color:var(--muted);max-width:780px}.hero img{width:100%;max-width:260px}.eyebrow{font-weight:800;letter-spacing:0;text-transform:uppercase;color:var(--accent);font-size:13px}.button{display:inline-flex;align-items:center;padding:10px 14px;border:1px solid var(--accent);background:var(--accent);color:white;border-radius:6px;font-weight:700;margin-right:8px}.button.secondary{background:transparent;color:var(--accent)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px}.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:18px}.card h3{margin-top:0}.two-col{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px}table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);font-size:14px}th,td{text-align:left;vertical-align:top;border-bottom:1px solid var(--line);padding:10px}th{background:#eaf0f2}.trace{margin-top:28px;padding:18px;border:1px solid var(--line);background:var(--panel);border-radius:8px}.trace h2{margin-top:0}.diagram{display:grid;grid-template-columns:1fr auto 1fr auto 1fr;gap:14px;align-items:center;margin:24px 0}.diagram div{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:18px;text-align:center}.diagram span{font-weight:800;color:var(--accent2)}.note{color:var(--muted);font-size:14px}.chart{width:100%;max-width:900px;background:white;border:1px solid var(--line);border-radius:8px}pre{background:var(--code);padding:16px;border-radius:8px;overflow:auto}.slide{min-height:calc(100vh - 58px);display:flex;flex-direction:column;justify-content:center;border-bottom:1px solid var(--line);padding:8vh 2vw}.slide h1{font-size:clamp(40px,7vw,86px);line-height:1;margin:0 0 22px}.slide p{font-size:clamp(19px,2.4vw,30px);max-width:900px;color:var(--muted)}.slide-count{font-size:13px!important;color:var(--accent)!important;font-weight:800}.presentation-page main{max-width:none;padding-top:0}@media(max-width:760px){.site-header{position:static;align-items:flex-start;flex-direction:column}.hero{grid-template-columns:1fr;min-height:auto}.hero img{max-width:150px}.diagram{grid-template-columns:1fr}.diagram span{text-align:center}main{padding:24px 16px}.slide{min-height:auto;padding:56px 4px}}@media(prefers-reduced-motion:no-preference){html{scroll-behavior:smooth}}@media print{.site-header{display:none}.slide{break-after:page;min-height:95vh}main{max-width:none}.card,.trace,table{break-inside:avoid}}
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
"""
    files = {"site.css": css, "site.js": js}
    ASSETS.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        path = ASSETS / name
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                print(f"stale asset: {path.relative_to(REPO)}", file=sys.stderr)
                ok = False
        else:
            path.write_text(text, encoding="utf-8")
    for logo in ("LT_logo.png", "LT_logo_small.png"):
        src = REPO / logo
        dst = ASSETS / logo
        if check:
            if not dst.exists():
                print(f"missing asset: {dst.relative_to(REPO)}", file=sys.stderr)
                ok = False
        else:
            shutil.copyfile(src, dst)
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

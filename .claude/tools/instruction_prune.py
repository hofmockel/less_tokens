#!/usr/bin/env python3
"""Automate the mechanical half of the claudemd/agentsmd pruning workflow.

CLAUDE.md and AGENTS.md are audited by claudemd_audit.py, which flags each
section KEEP / TRIM / CUT->doc / REVIEW. Moving a CUT->doc/REVIEW section to
the overflow doc, leaving a pointer, and re-checking the budget/refs is
mechanical -- this tool does that part. TRIM (rewrite to caveman prose) and
FIX-REF (repair a stale path:line) stay manual: both need judgment this tool
doesn't attempt.

Usage:
  python .claude/tools/instruction_prune.py --agent claude|codex
  python .claude/tools/instruction_prune.py --agent claude --apply --verify-recall
  python .claude/tools/instruction_prune.py --agent codex --apply --no-pointer
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import claudemd_audit as cma

try:
    from search_config import (  # noqa: E402
        AGENTS_MD_OVERFLOW_DOC,
        AGENTS_MD_TOKEN_BUDGET,
        CLAUDE_MD_OVERFLOW_DOC,
        CLAUDE_MD_TOKEN_BUDGET,
    )
except Exception:
    CLAUDE_MD_TOKEN_BUDGET = 1200
    CLAUDE_MD_OVERFLOW_DOC = "DOCUMENTATION.md"
    AGENTS_MD_TOKEN_BUDGET = 1200
    AGENTS_MD_OVERFLOW_DOC = "DOCUMENTATION.md"

BASE = cma.BASE

AGENT_PROFILES = {
    "claude": {
        "doc_name": "CLAUDE.md",
        "budget": CLAUDE_MD_TOKEN_BUDGET,
        "overflow_doc": CLAUDE_MD_OVERFLOW_DOC,
    },
    "codex": {
        "doc_name": "AGENTS.md",
        "budget": AGENTS_MD_TOKEN_BUDGET,
        "overflow_doc": AGENTS_MD_OVERFLOW_DOC,
    },
}

MOVABLE_PREFIXES = ("CUT→doc", "REVIEW")


def _sections_with_verdicts(path: Path) -> list[dict]:
    """Same per-section computation as claudemd_audit.audit(), keeping int lines."""
    text = path.read_text(encoding="utf-8")
    sections = cma.parse_sections(text)
    dup = cma.duplication(sections)
    out = []
    for s in sections:
        s["_tokens"] = cma.est_tokens(s["body"])
        verb = cma.scan_verbosity(s["body"])
        out.append(
            {
                "title": s["title"],
                "level": s["level"],
                "start": s["start"],
                "end": s["end"],
                "body": s["body"],
                "tokens": s["_tokens"],
                "verdict": cma.verdict(s, dup, verb),
            }
        )
    return out


def plan_moves(path: Path) -> list[dict]:
    """Sections eligible to move: level >= 1 (never the preamble) and a
    CUT->doc/REVIEW verdict."""
    return [
        s
        for s in _sections_with_verdicts(path)
        if s["level"] >= 1 and s["verdict"].startswith(MOVABLE_PREFIXES)
    ]


def _pointer_line(title: str, overflow_doc: str) -> str:
    return f"_Moved to {overflow_doc} → {title}._"


def apply_moves(
    path: Path, overflow_path: Path, moves: list[dict], leave_pointer: bool
) -> None:
    """Mutate path and overflow_path in place. moves must be the exact list
    from plan_moves(path) -- caller recomputes it fresh so the plan shown is
    always the plan applied.

    parse_sections() produces a flat partition of the document (every heading,
    regardless of level, ends the previous section), so move spans never
    overlap -- safe to extract in document order, then delete bottom-to-top so
    earlier spans' line numbers stay valid while later ones are edited.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    ordered = sorted(moves, key=lambda s: s["start"])
    bodies_in_order = ["\n".join(lines[s["start"] - 1 : s["end"]]) for s in ordered]

    for s in sorted(moves, key=lambda s: s["start"], reverse=True):
        replacement = (
            [_pointer_line(s["title"], overflow_path.name)] if leave_pointer else []
        )
        lines[s["start"] - 1 : s["end"]] = replacement
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    marker = f"## Moved from {path.name}"
    overflow_text = (
        overflow_path.read_text(encoding="utf-8") if overflow_path.exists() else ""
    )
    new_overflow = overflow_text.rstrip("\n")
    if marker not in overflow_text:
        new_overflow += ("\n\n" if new_overflow else "") + marker
    for body in bodies_in_order:
        new_overflow += "\n\n" + body
    overflow_path.write_text(new_overflow.strip("\n") + "\n", encoding="utf-8")


search_mod = None
embeddings_mod = None


def _load_search_deps() -> None:
    """Lazy + patchable: keeps numpy/fastembed off the import path for plain
    dry-run/--apply use, and lets tests substitute fakes via
    patch.object(instruction_prune, "search_mod"/"embeddings_mod", ...)."""
    global search_mod, embeddings_mod
    if search_mod is None:
        import search as search_mod  # noqa: PLC0415
    if embeddings_mod is None:
        import embeddings as embeddings_mod  # noqa: PLC0415


def verify_recall(titles: list[str], overflow_doc_name: str) -> list[dict]:
    _load_search_deps()

    if search_mod._index_is_stale():
        embeddings_mod.refresh()

    results = []
    for title in titles:
        hits = search_mod.search(title, k=5)
        found = any(overflow_doc_name in h["source_path"] for h in hits)
        results.append({"title": title, "passed": found})
    return results


def _print_plan(
    agent: str, path: Path, overflow_doc: str, moves: list[dict], audit_result: dict
) -> None:
    print(f"[{agent}] {path.name} -> {overflow_doc}")
    if not moves:
        print("  no CUT→doc / REVIEW sections to move")
    for s in moves:
        print(
            f"  MOVE  L{s['start']}-{s['end']}  {s['tokens']}tok  "
            f'"{s["title"]}"  [{s["verdict"]}]'
        )
    trims = [s for s in audit_result["sections"] if s["verdict"] == "TRIM"]
    for s in trims:
        print(f'  TRIM (manual)  L{s["lines"]}  "{s["title"]}"')
    for r in audit_result["dead_refs"]:
        print(f"  FIX-REF (manual)  L{r['line']}  {r['ref']}  -- {r['reason']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--agent", required=True, choices=sorted(AGENT_PROFILES))
    ap.add_argument(
        "--apply", action="store_true", help="perform the moves shown by the dry run"
    )
    ap.add_argument(
        "--verify-recall",
        action="store_true",
        help="after --apply, confirm moved topics are searchable",
    )
    ap.add_argument(
        "--no-pointer",
        action="store_true",
        help="don't leave a one-line pointer at the moved section's old spot",
    )
    ap.add_argument("--budget", type=int, default=None)
    ap.add_argument("--overflow-doc", default=None)
    ap.add_argument(
        "--path",
        default=None,
        help="override the default CLAUDE.md/AGENTS.md location (advanced/testing)",
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    profile = AGENT_PROFILES[args.agent]
    path = Path(args.path) if args.path else BASE / profile["doc_name"]
    budget = args.budget if args.budget is not None else profile["budget"]
    overflow_doc = args.overflow_doc or profile["overflow_doc"]
    overflow_path = path.parent / overflow_doc if args.path else BASE / overflow_doc
    display_path = (
        str(path.relative_to(BASE)) if path.is_relative_to(BASE) else str(path)
    )

    if not path.exists():
        print(f"not found: {path}", file=sys.stderr)
        return 2

    moves = plan_moves(path)
    audit_before = cma.audit(path, budget)

    if not args.apply:
        if args.json:
            print(
                json.dumps(
                    {
                        "agent": args.agent,
                        "path": display_path,
                        "overflow_doc": overflow_doc,
                        "moves": [
                            {
                                "title": s["title"],
                                "lines": f"{s['start']}-{s['end']}",
                                "tokens": s["tokens"],
                                "verdict": s["verdict"],
                            }
                            for s in moves
                        ],
                        "over_budget": audit_before["over_budget"],
                        "dead_refs": audit_before["dead_refs"],
                    },
                    indent=2,
                )
            )
        else:
            _print_plan(args.agent, path, overflow_doc, moves, audit_before)
        return 0

    apply_moves(path, overflow_path, moves, leave_pointer=not args.no_pointer)
    audit_after = cma.audit(path, budget)
    print(f"applied {len(moves)} move(s) -> {overflow_doc}")
    print(
        f"re-audit: over_budget={audit_after['over_budget']} "
        f"dead_refs={len(audit_after['dead_refs'])}"
    )

    exit_code = 0
    if args.verify_recall:
        try:
            results = verify_recall([s["title"] for s in moves], overflow_doc)
        except ModuleNotFoundError as e:
            venv_python = BASE / ".claude" / ".venv-tokens" / "bin" / "python"
            print(
                f"--verify-recall needs '{e.name}', not importable under this interpreter.\n"
                f"Run this tool with {venv_python} instead of a plain python3.",
                file=sys.stderr,
            )
            return 2
        for r in results:
            status = "PASS" if r["passed"] else "FAIL"
            print(f'  verify-recall {status}  "{r["title"]}"')
            if not r["passed"]:
                exit_code = 1
        if exit_code:
            print(
                "verify-recall FAILed for at least one topic -- "
                "restore that section manually, this tool will not auto-restore it.",
                file=sys.stderr,
            )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

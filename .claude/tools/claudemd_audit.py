#!/usr/bin/env python3
"""Audit CLAUDE.md and keep it to only what must be always-loaded.

CLAUDE.md is injected every turn and never searched, so every token is a
per-turn tax. This tool measures that tax deterministically and flags what to
cut, trim, or fix — no model judgment required.

Checks:
  1. Token estimate per section + total vs CLAUDE_MD_TOKEN_BUDGET.
  2. Stale references — `path:line` and backticked paths that no longer resolve.
  3. Verbosity — filler phrases and over-long sentences.
  4. Duplication (optional) — sections already discoverable in the search index;
     skipped gracefully when fastembed / index.db are unavailable.

Usage:
  python .claude/tools/claudemd_audit.py [path] [--budget N] [--json] [--strict]
  python .claude/tools/claudemd_audit.py --rules [--rules-dir .claude/rules]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def find_base() -> Path:
    cwd = Path.cwd().resolve()
    if (cwd / ".claude" / "tools" / "search_config.py").exists():
        return cwd
    return Path(__file__).resolve().parent.parent.parent


BASE = find_base()
sys.path.insert(0, str(BASE / ".claude" / "tools"))

try:
    from search_config import (  # noqa: E402
        CHARS_PER_TOKEN,
        CLAUDE_MD_OVERFLOW_DOC,
        CLAUDE_MD_TOKEN_BUDGET,
        RULES_OVERFLOW_DOC,
        RULES_TOKEN_BUDGET,
    )
except Exception:
    CHARS_PER_TOKEN = 4
    CLAUDE_MD_TOKEN_BUDGET = 1200
    CLAUDE_MD_OVERFLOW_DOC = "documentation.md"
    RULES_TOKEN_BUDGET = 600
    RULES_OVERFLOW_DOC = "documentation.md"

DUP_SIM = 0.80          # cosine above which a section is "already discoverable"
DUP_MIN_TOKENS = 120    # don't bother flagging tiny sections as dup
BIG_SECTION_TOKENS = 250  # size that warrants review when no dup data
LONG_SENTENCE_WORDS = 40

FILLER = re.compile(
    r"\b(I apologize|I'm sorry|certainly|absolutely|I'd be (?:happy|glad) to|"
    r"great question|of course|I hope this helps|please let me know|feel free to|"
    r"in order to|it is important to note|as you can see)\b",
    re.IGNORECASE,
)

# file.ext:line  or  file.ext:line-line
LINE_REF = re.compile(r"([A-Za-z0-9_./\-]+\.[A-Za-z]{1,6}):(\d+)(?:-(\d+))?")
# backticked tokens that look like real paths (not globs)
BACKTICK = re.compile(r"`([^`]+)`")
PATHISH = re.compile(
    r"^[A-Za-z0-9_./\-]+\.(py|md|sql|json|toml|txt|yml|yaml|cfg|ini|sh)$"
)


def est_tokens(s: str) -> int:
    return len(s) // max(1, CHARS_PER_TOKEN)


def parse_sections(text: str) -> list[dict]:
    lines = text.splitlines()
    heads = []
    for i, ln in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.*)", ln)
        if m:
            heads.append((i, len(m.group(1)), m.group(2).strip()))
    sections = []
    if heads and heads[0][0] > 0:
        body = "\n".join(lines[: heads[0][0]])
        sections.append({"level": 0, "title": "(preamble)", "start": 1,
                         "end": heads[0][0], "body": body})
    for idx, (i, lvl, title) in enumerate(heads):
        end = heads[idx + 1][0] if idx + 1 < len(heads) else len(lines)
        body = "\n".join(lines[i:end])
        sections.append({"level": lvl, "title": title, "start": i + 1,
                         "end": end, "body": body})
    return sections


def _strip_code(body: str) -> str:
    return re.sub(r"```.*?(?:```|\Z)", "", body, flags=re.DOTALL)



_IGNORE_DIRS = {".git", ".venv", ".venv-tokens", "__pycache__", "node_modules"}


def _resolve(path: str):
    """Return an existing Path for a ref, or None. Bare filenames (no '/')
    are matched anywhere in the tree so `search_config.py` resolves to
    `.claude/tools/search_config.py` instead of false-flagging."""
    direct = BASE / path
    if direct.exists():
        return direct
    for hit in BASE.rglob(path):
        if not any(part in _IGNORE_DIRS for part in hit.parts):
            return hit
    return None


def scan_refs(text: str) -> list[dict]:
    out = []
    seen = set()
    lines = text.splitlines()
    for lineno, ln in enumerate(lines, 1):
        for m in LINE_REF.finditer(ln):
            path, a, b = m.group(1), int(m.group(2)), m.group(3)
            key = (path, a, b, lineno)
            if key in seen:
                continue
            seen.add(key)
            rec = {"ref": m.group(0), "line": lineno, "kind": "line-ref"}
            fp = _resolve(path)
            if fp is None:
                rec.update(ok=False, reason="path not found")
            else:
                try:
                    n = len(fp.read_text(errors="ignore").splitlines())
                except OSError:
                    n = 0
                hi = int(b) if b else a
                if hi > n:
                    rec.update(ok=False, reason=f"line {hi} > file length {n}")
                else:
                    rec.update(ok=True, reason="")
            out.append(rec)
        for m in BACKTICK.finditer(ln):
            tok = m.group(1).strip()
            if any(c in tok for c in "*? ") or not PATHISH.match(tok):
                continue
            if LINE_REF.search(tok):
                continue
            key = ("bt", tok, lineno)
            if key in seen:
                continue
            seen.add(key)
            fp = _resolve(tok)
            out.append({"ref": tok, "line": lineno, "kind": "path",
                        "ok": fp is not None,
                        "reason": "" if fp is not None else "path not found"})
    return out


def scan_verbosity(body: str) -> dict:
    prose = _strip_code(body)
    filler = sorted({m.group(0).lower() for m in FILLER.finditer(prose)})
    longs = 0
    for sent in re.split(r"(?<=[.!?])\s+", prose):
        words = [w for w in re.findall(r"\b\w+\b", sent)]
        if len(words) > LONG_SENTENCE_WORDS:
            longs += 1
    return {"filler": filler, "long_sentences": longs}


def duplication(sections: list[dict]):
    """Return {title: (sim, source_path)} or None if index unavailable."""
    try:
        from db import connect_index  # noqa: PLC0415
        from embeddings import DIM, embed, unpack_vectors  # noqa: PLC0415
        import numpy as np  # noqa: PLC0415
        import search_config  # noqa: PLC0415
    except Exception:
        return None
    try:
        with connect_index() as c:
            rows = c.execute(
                "SELECT source_path, source_key, embedding FROM documents "
                "WHERE source_path NOT LIKE '%CLAUDE.md' "
                "AND embedding_model = ?",
                (search_config.EMBEDDING_MODEL,),
            ).fetchall()
    except Exception:
        return None
    if not rows:
        return None
    mats, meta = [], []
    for r in rows:
        v = unpack_vectors(r["embedding"], DIM)
        mats.append(v.reshape(-1))
        meta.append(r["source_path"])
    M = np.vstack(mats).astype("float32")
    M /= (np.linalg.norm(M, axis=1, keepdims=True) + 1e-9)
    targets = [s for s in sections if s["level"]]
    if not targets:
        return {}
    try:
        Q = embed([s["body"] for s in targets], input_type="query")
    except Exception:
        return None
    Q = np.asarray(Q, dtype="float32")
    Q /= (np.linalg.norm(Q, axis=1, keepdims=True) + 1e-9)
    sims = Q @ M.T
    out = {}
    for i, s in enumerate(targets):
        j = int(sims[i].argmax())
        out[s["title"]] = (float(sims[i][j]), meta[j])
    return out


def verdict(sec: dict, dup, verb: dict) -> str:
    tok = sec["_tokens"]
    if dup is not None:
        sim, src = dup.get(sec["title"], (0.0, ""))
        if sim >= DUP_SIM and tok >= DUP_MIN_TOKENS:
            return f"CUT→doc (dup {sim*100:.0f}% {src})"
    if dup is None and tok >= BIG_SECTION_TOKENS and sec["level"] in (1, 2):
        return "REVIEW (likely CUT→doc; run with index for dup check)"
    if verb["filler"] or verb["long_sentences"]:
        return "TRIM"
    return "KEEP"


def audit(path: Path, budget: int) -> dict:
    text = path.read_text(encoding="utf-8")
    sections = parse_sections(text)
    total_tokens = est_tokens(text)
    refs = scan_refs(text)
    dup = duplication(sections)
    rows = []
    for s in sections:
        s["_tokens"] = est_tokens(s["body"])
        verb = scan_verbosity(s["body"])
        rows.append({
            "title": s["title"], "level": s["level"],
            "lines": f"{s['start']}-{s['end']}", "tokens": s["_tokens"],
            "filler": verb["filler"], "long_sentences": verb["long_sentences"],
            "verdict": verdict(s, dup, verb),
        })
    dead = [r for r in refs if not r["ok"]]
    return {
        "path": str(path.relative_to(BASE)) if path.is_relative_to(BASE) else str(path),
        "total_tokens": total_tokens, "budget": budget,
        "over_budget": budget and total_tokens > budget,
        "dup_check": dup is not None,
        "sections": rows, "refs": refs, "dead_refs": dead,
        "overflow_doc": CLAUDE_MD_OVERFLOW_DOC,
    }


def audit_rules(rules_dir: Path, budget: int) -> dict:
    files = sorted(
        p for p in rules_dir.glob("*.md")
        if p.is_file() and not p.name.startswith(".")
    )
    audits = []
    for file in files:
        result = audit(file, budget)
        result["overflow_doc"] = RULES_OVERFLOW_DOC
        audits.append(result)
    return {
        "path": str(rules_dir.relative_to(BASE)) if rules_dir.is_relative_to(BASE) else str(rules_dir),
        "budget": budget,
        "files": audits,
        "total_tokens": sum(int(a["total_tokens"]) for a in audits),
        "over_budget": any(a["over_budget"] for a in audits),
        "dead_refs": [ref for a in audits for ref in a["dead_refs"]],
        "overflow_doc": RULES_OVERFLOW_DOC,
    }


def render(a: dict) -> str:
    L = []
    status = "OVER" if a["over_budget"] else "ok"
    over = f" — OVER by {a['total_tokens'] - a['budget']:,}" if a["over_budget"] else ""
    L.append(f"{a['path']}: ~{a['total_tokens']:,} tokens "
             f"(budget {a['budget']:,}) [{status}]{over}")
    if not a["dup_check"]:
        L.append("dup check: SKIPPED (no index/fastembed) — token + ref + verbosity checks ran")
    L.append("")
    L.append(f"{'verdict':<42} {'tok':>5}  section")
    L.append("-" * 78)
    for r in a["sections"]:
        flags = []
        if r["filler"]:
            flags.append(f"filler:{len(r['filler'])}")
        if r["long_sentences"]:
            flags.append(f"long:{r['long_sentences']}")
        fl = ("  [" + ",".join(flags) + "]") if flags else ""
        L.append(f"{r['verdict']:<42} {r['tokens']:>5}  {r['title']}{fl}")
    if a["dead_refs"]:
        L.append("")
        L.append("FIX-REF — stale references:")
        for r in a["dead_refs"]:
            L.append(f"  L{r['line']}: {r['ref']}  ({r['reason']})")
    else:
        L.append("")
        L.append("refs: all resolve ok")
    L.append("")
    cut = [r for r in a["sections"] if r["verdict"].startswith(("CUT", "REVIEW"))]
    if cut:
        save = sum(r["tokens"] for r in cut)
        L.append(f"move {len(cut)} section(s) → {a['overflow_doc']} (indexed): "
                 f"~{save:,} tokens off every turn")
    return "\n".join(L)


def render_rules(a: dict) -> str:
    L = []
    status = "OVER" if a["over_budget"] else "ok"
    L.append(f"{a['path']}: {len(a['files'])} rule file(s), ~{a['total_tokens']:,} total tokens "
             f"(budget {a['budget']:,} each) [{status}]")
    if not a["files"]:
        L.append("no markdown rule files found")
        return "\n".join(L)
    L.append("")
    for idx, item in enumerate(a["files"]):
        if idx:
            L.append("")
        L.append(render(item))
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit CLAUDE.md token tax")
    ap.add_argument("path", nargs="?", default=str(BASE / "CLAUDE.md"))
    ap.add_argument("--rules", action="store_true",
                    help="audit every markdown rule under .claude/rules/")
    ap.add_argument("--rules-dir", default=str(BASE / ".claude" / "rules"))
    ap.add_argument("--budget", type=int, default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 if over budget or dead refs found")
    args = ap.parse_args()

    if args.rules:
        rules_dir = Path(args.rules_dir)
        if not rules_dir.exists():
            print(f"not found: {rules_dir}", file=sys.stderr)
            return 2
        budget = args.budget if args.budget is not None else RULES_TOKEN_BUDGET
        a = audit_rules(rules_dir, budget)
        print(json.dumps(a, indent=2) if args.json else render_rules(a))
        if args.strict and (a["over_budget"] or a["dead_refs"]):
            return 1
        return 0

    p = Path(args.path)
    if not p.exists():
        print(f"not found: {p}", file=sys.stderr)
        return 2
    budget = args.budget if args.budget is not None else CLAUDE_MD_TOKEN_BUDGET
    a = audit(p, budget)
    print(json.dumps(a, indent=2) if args.json else render(a))
    if args.strict and (a["over_budget"] or a["dead_refs"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Audit the complete launch-time instruction chain, not just one root file.

claudemd_audit.py measures CLAUDE.md/AGENTS.md/rules in isolation. This tool
reports what an agent actually loads at startup for a given launch CWD:
every CLAUDE.md/AGENTS.md in the resolution chain, every rule (recursively,
scoped vs unscoped), and the bounded auto-memory entrypoint — split into
"fixed" (always loaded, every-turn tax) and "on-demand" (lazy-loaded only
when a matching file is read) tokens.

Sourced from Anthropic's memory docs (code.claude.com/docs/en/memory) and
OpenAI's AGENTS.md guide (developers.openai.com/codex/guides/agents-md), both
fetched 2026-07-22. Modeling assumptions that could not be verified against a
live session/CLI are marked ASSUMPTION below and belong in a follow-up
research item, not silently treated as fact.

Usage:
  python .claude/tools/instruction_chain_audit.py --agent claude [--cwd PATH] [--json]
  python .claude/tools/instruction_chain_audit.py --agent codex [--cwd PATH] [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:  # pragma: no cover - py<3.11
    tomllib = None

CHARS_PER_TOKEN = 4
MEMORY_MAX_LINES = 200
MEMORY_MAX_BYTES = 25 * 1024
CODEX_DEFAULT_MAX_BYTES = 32 * 1024

# Documented format, disputed by an unconfirmed community report
# (github.com/anthropics/claude-code/issues/17204: quoted/list `paths:` silently
# no-ops in some versions; unquoted `paths:` and `globs:` work). Not verified
# live here — flagged per-rule below rather than assumed broken.
PATHS_RELIABILITY_NOTE = (
    "paths: frontmatter (quoted or YAML-list form) has an unconfirmed "
    "community report of silently not scoping the rule; globs: is reported "
    "to work reliably. Verify live before relying on paths: — see "
    "github.com/anthropics/claude-code/issues/17204."
)

FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n?", re.S)
PATHISH_HINT = re.compile(
    r"\.(ts|tsx|js|jsx|py|go|rs|java|rb|php|css|scss|sql|md)\b|/\w+/"
)


def est_tokens(s: str) -> int:
    return len(s) // max(1, CHARS_PER_TOKEN)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _find_base(start: Path | None = None) -> Path:
    cwd = (start or Path.cwd()).resolve()
    for cand in (cwd, *cwd.parents):
        if (cand / ".git").exists():
            return cand
    return cwd


def _rule_frontmatter(text: str) -> dict:
    m = FRONTMATTER.match(text)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        fm[key.strip()] = val.strip()
    return fm


def _rule_scope(path: Path) -> dict:
    """Return {'scoped': bool, 'pattern': str, 'reliability_flag': bool}."""
    text = _read(path)
    fm_block = FRONTMATTER.match(text)
    fm_text = fm_block.group(1) if fm_block else ""
    has_globs = bool(re.search(r"^globs:", fm_text, re.M))
    has_paths = bool(re.search(r"^paths:", fm_text, re.M))
    if not has_globs and not has_paths:
        return {"scoped": False, "pattern": "", "reliability_flag": False}
    pattern_line = ""
    for line in fm_text.splitlines():
        if line.strip().startswith(("globs:", "paths:")):
            pattern_line = line.strip()
            break
    return {
        "scoped": True,
        "pattern": pattern_line,
        # only paths:-without-globs is the disputed form
        "reliability_flag": has_paths and not has_globs,
    }


def _looks_non_global(body: str) -> bool:
    """Heuristic: unscoped rule whose prose reads like it targets specific
    file types/dirs rather than project-wide conventions. Not a proof —
    a hint worth a human look, same spirit as claudemd_audit's verdict()."""
    hits = len(set(PATHISH_HINT.findall(body)))
    return hits >= 2


def _collect_rules(rules_dir: Path, base: Path, nested: bool = False) -> list[dict]:
    """Recursively discover *.md rules. `nested=True` marks rules found in a
    .claude/rules/ dir other than the top-level project one — those load
    on-demand per docs, same as path-scoped rules."""
    out = []
    if not rules_dir.exists():
        return out
    for path in sorted(rules_dir.rglob("*.md")):
        if not path.is_file():
            continue
        text = _read(path)
        scope = _rule_scope(path)
        rel = (
            path.relative_to(base).as_posix()
            if path.is_relative_to(base)
            else str(path)
        )
        tokens = est_tokens(text)
        fixed = (not scope["scoped"]) and not nested
        flag_candidate = fixed and _looks_non_global(text)
        out.append(
            {
                "path": rel,
                "tokens": tokens,
                "fixed": fixed,
                "scoped": scope["scoped"],
                "pattern": scope["pattern"],
                "reliability_flag": scope["reliability_flag"],
                "path_scope_candidate": flag_candidate,
            }
        )
    return out


def _memory_dir_for(base: Path) -> Path:
    """~/.claude/projects/<slug>/memory — slug mirrors the session-dir naming
    already visible on disk (path with '/' -> '-', leading '-' kept).
    ASSUMPTION: exact slug algorithm is not published; this matches observed
    directory names, not verified against Claude Code source."""
    posix = base.as_posix()
    if len(posix) >= 2 and posix[1] == ":":
        # strip a Windows drive prefix (e.g. "C:") so the slug is always a
        # plain relative-looking segment — a leading "C:" makes pathlib treat
        # it as a new anchor and discard the joined-in Path.home() prefix
        posix = posix[2:]
    slug = posix.replace("/", "-")
    return Path.home() / ".claude" / "projects" / slug / "memory"


def _memory_summary(base: Path) -> dict:
    mem_dir = _memory_dir_for(base)
    index = mem_dir / "MEMORY.md"
    if not index.exists():
        return {"path": None, "found": False, "loaded_tokens": 0, "topic_files": 0}
    raw = _read(index)
    # frontmatter/comments are stripped before the limit is measured (docs);
    # approximate by dropping a leading --- block and HTML comments.
    stripped = FRONTMATTER.sub("", raw, count=1)
    stripped = re.sub(r"<!--.*?-->", "", stripped, flags=re.S)
    lines = stripped.splitlines()
    loaded = "\n".join(lines[:MEMORY_MAX_LINES])
    if len(loaded.encode("utf-8")) > MEMORY_MAX_BYTES:
        loaded = loaded.encode("utf-8")[:MEMORY_MAX_BYTES].decode("utf-8", "ignore")
    topic_files = [p for p in mem_dir.glob("*.md") if p.name != "MEMORY.md"]
    return {
        "path": index.relative_to(Path.home()).as_posix(),
        "found": True,
        "loaded_tokens": est_tokens(loaded),
        "over_limit": len(lines) > MEMORY_MAX_LINES
        or len(stripped.encode("utf-8")) > MEMORY_MAX_BYTES,
        "topic_files": len(topic_files),
    }


_CLAUDE_MANAGED_POLICY = {
    "darwin": Path("/Library/Application Support/ClaudeCode/CLAUDE.md"),
    "linux": Path("/etc/claude-code/CLAUDE.md"),
}


def claude_chain(cwd: Path, base: Path) -> dict:
    fixed, on_demand, flags = [], [], []

    policy = _CLAUDE_MANAGED_POLICY.get(sys.platform.rstrip("0123456789"))
    if policy and policy.exists():
        text = _read(policy)
        fixed.append(
            {"path": str(policy), "kind": "managed-policy", "tokens": est_tokens(text)}
        )

    user_claude = Path.home() / ".claude" / "CLAUDE.md"
    if user_claude.exists():
        text = _read(user_claude)
        fixed.append(
            {"path": "~/.claude/CLAUDE.md", "kind": "user", "tokens": est_tokens(text)}
        )

    user_rules_dir = Path.home() / ".claude" / "rules"
    for r in _collect_rules(user_rules_dir, user_rules_dir):
        r["path"] = f"~/.claude/rules/{r['path']}"
        r["kind"] = "user-rule"
        (fixed if r["fixed"] else on_demand).append(r)
        if r["reliability_flag"]:
            flags.append(f"{r['path']}: {PATHS_RELIABILITY_NOTE}")
        if r["path_scope_candidate"]:
            flags.append(
                f"{r['path']}: unscoped but reads path-specific — "
                "consider scoping with globs:"
            )

    ancestors = [cwd, *[p for p in cwd.parents if base in (p, *p.parents) or p == base]]
    # de-dup while keeping cwd-nearest last (root-first load order)
    seen, chain_dirs = set(), []
    for d in reversed(ancestors):
        if d not in seen:
            seen.add(d)
            chain_dirs.append(d)
    if base not in chain_dirs:
        chain_dirs.insert(0, base)

    for d in chain_dirs:
        for name, kind in (
            ("CLAUDE.md", "project"),
            (".claude/CLAUDE.md", "project"),
            ("CLAUDE.local.md", "local"),
        ):
            p = d / name
            if p.exists():
                text = _read(p)
                rel = (
                    p.relative_to(base).as_posix() if p.is_relative_to(base) else str(p)
                )
                fixed.append({"path": rel, "kind": kind, "tokens": est_tokens(text)})

        rules_dir = d / ".claude" / "rules"
        is_top_level = d == base
        for r in _collect_rules(rules_dir, base, nested=not is_top_level):
            r["kind"] = "rule" if is_top_level else "nested-rule"
            (fixed if r["fixed"] else on_demand).append(r)
            if r["reliability_flag"]:
                flags.append(f"{r['path']}: {PATHS_RELIABILITY_NOTE}")
            if r["path_scope_candidate"]:
                flags.append(
                    f"{r['path']}: unscoped but reads path-specific — "
                    "consider scoping with globs:"
                )

    mem = _memory_summary(base)
    if mem["found"]:
        fixed.append(
            {"path": mem["path"], "kind": "auto-memory", "tokens": mem["loaded_tokens"]}
        )
        if mem["over_limit"]:
            flags.append(
                f"{mem['path']}: over the 200-line/25KB read limit — "
                "content past the limit is silently dropped on load"
            )
        if mem["topic_files"]:
            on_demand.append(
                {
                    "path": f"{mem['path']} (+{mem['topic_files']} topic files)",
                    "kind": "auto-memory-topics",
                    "tokens": 0,
                    "fixed": False,
                }
            )

    return {
        "agent": "claude",
        "cwd": str(cwd),
        "base": str(base),
        "fixed": fixed,
        "on_demand": on_demand,
        "fixed_tokens": sum(f["tokens"] for f in fixed),
        "on_demand_tokens": sum(f["tokens"] for f in on_demand),
        "flags": flags,
    }


def _codex_config(base: Path) -> dict:
    cfg_path = Path.home() / ".codex" / "config.toml"
    if not cfg_path.exists() or tomllib is None:
        return {
            "project_doc_max_bytes": CODEX_DEFAULT_MAX_BYTES,
            "project_doc_fallback_filenames": [],
        }
    try:
        data = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "project_doc_max_bytes": CODEX_DEFAULT_MAX_BYTES,
            "project_doc_fallback_filenames": [],
        }
    return {
        "project_doc_max_bytes": data.get(
            "project_doc_max_bytes", CODEX_DEFAULT_MAX_BYTES
        ),
        "project_doc_fallback_filenames": data.get(
            "project_doc_fallback_filenames", []
        ),
    }


def codex_chain(cwd: Path, base: Path) -> dict:
    cfg = _codex_config(base)
    max_bytes = cfg["project_doc_max_bytes"]
    fallback_names = cfg["project_doc_fallback_filenames"]
    candidates = ["AGENTS.override.md", "AGENTS.md", *fallback_names]

    entries = []

    global_dir = Path.home() / ".codex"
    for name in ("AGENTS.override.md", "AGENTS.md"):
        p = global_dir / name
        if p.exists() and _read(p).strip():
            entries.append((f"~/.codex/{name}", p))
            break  # only the first non-empty global file loads

    chain_dirs = []
    d = cwd
    while True:
        chain_dirs.append(d)
        if d == base or d.parent == d:
            break
        d = d.parent
    chain_dirs.reverse()  # root-down concatenation order

    for d in chain_dirs:
        for name in candidates:
            p = d / name
            if p.exists() and _read(p).strip():
                rel = (
                    p.relative_to(base).as_posix() if p.is_relative_to(base) else str(p)
                )
                entries.append((rel, p))
                break  # at most one file per directory

    included, skipped, cumulative = [], [], 0
    for rel, p in entries:
        size = len(_read(p).encode("utf-8"))
        if cumulative + size > max_bytes:
            # ASSUMPTION: docs say Codex "stops adding files once the combined
            # size reaches the limit" but don't confirm whether the file that
            # crosses the threshold is partially included. Modeled here as
            # excluded-in-full; verify live before treating as fact.
            skipped.append({"path": rel, "bytes": size})
            continue
        cumulative += size
        included.append({"path": rel, "bytes": size, "tokens": est_tokens(_read(p))})

    return {
        "agent": "codex",
        "cwd": str(cwd),
        "base": str(base),
        "project_doc_max_bytes": max_bytes,
        "included": included,
        "skipped_over_limit": skipped,
        "included_tokens": sum(e["tokens"] for e in included),
        "included_bytes": cumulative,
        "flags": (
            [
                "over project_doc_max_bytes: "
                f"{len(skipped)} file(s) never loaded — "
                "raise project_doc_max_bytes or trim the chain"
            ]
            if skipped
            else []
        ),
    }


def render_claude(a: dict) -> str:
    lines = [f"Claude instruction chain — cwd={a['cwd']}", ""]
    lines.append("FIXED (loaded every session):")
    for f in a["fixed"]:
        lines.append(f"  {f['tokens']:>5} tok  [{f['kind']}]  {f['path']}")
    lines.append(f"  = {a['fixed_tokens']} tokens fixed")
    lines.append("")
    lines.append("ON-DEMAND (lazy-loaded when a matching file is read):")
    for f in a["on_demand"]:
        extra = f" ({f.get('pattern', '')})" if f.get("pattern") else ""
        lines.append(f"  {f['tokens']:>5} tok  [{f['kind']}]  {f['path']}{extra}")
    lines.append(f"  = {a['on_demand_tokens']} tokens on-demand")
    if a["flags"]:
        lines.append("")
        lines.append("FLAGS:")
        for fl in a["flags"]:
            lines.append(f"  - {fl}")
    return "\n".join(lines)


def render_codex(a: dict) -> str:
    lines = [
        f"Codex instruction chain — cwd={a['cwd']} "
        f"(project_doc_max_bytes={a['project_doc_max_bytes']})",
        "",
    ]
    lines.append("INCLUDED (root-to-cwd concatenation order):")
    for f in a["included"]:
        lines.append(f"  {f['tokens']:>5} tok  {f['bytes']:>6}B  {f['path']}")
    lines.append(f"  = {a['included_tokens']} tokens, {a['included_bytes']} bytes")
    if a["skipped_over_limit"]:
        lines.append("")
        lines.append("SKIPPED (never reached — over project_doc_max_bytes):")
        for f in a["skipped_over_limit"]:
            lines.append(f"  {f['bytes']:>6}B  {f['path']}")
    if a["flags"]:
        lines.append("")
        lines.append("FLAGS:")
        for fl in a["flags"]:
            lines.append(f"  - {fl}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Audit the full launch-time instruction chain"
    )
    ap.add_argument("--agent", choices=["claude", "codex"], required=True)
    ap.add_argument("--cwd", default=".", help="launch working directory to model")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    cwd = Path(args.cwd).resolve()
    base = _find_base(cwd)
    if args.agent == "claude":
        a = claude_chain(cwd, base)
        print(json.dumps(a, indent=2) if args.json else render_claude(a))
    else:
        a = codex_chain(cwd, base)
        print(json.dumps(a, indent=2) if args.json else render_codex(a))
    return 0


if __name__ == "__main__":
    sys.exit(main())

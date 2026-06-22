"""Shared hook adapter helpers for Claude and Codex wrappers."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def resolve_repo(*, markers: tuple[str, ...] = (".git", "CLAUDE.md", "AGENTS.md"), max_up: int = 8) -> Path:
    if os.environ.get("LESS_TOKENS_REPO"):
        return Path(os.environ["LESS_TOKENS_REPO"]).resolve()

    starts = [Path(__file__).resolve().parent, Path.cwd().resolve()]
    for start in starts:
        curr = start
        for _ in range(max_up):
            if any((curr / marker).exists() for marker in markers):
                return curr
            if curr == curr.parent:
                break
            curr = curr.parent
    return Path(__file__).resolve().parent.parent.parent


def add_hook_paths(repo: Path, *, agent: str) -> None:
    paths = [
        repo / "agents" / "common" / "hooks",
        repo / ".claude" / "hooks" / "common",
        repo / ".less_tokens" / "hooks",
    ]
    if agent == "codex":
        paths += [repo / ".less_tokens" / "tools", repo / ".claude" / "tools"]
    else:
        paths += [repo / ".claude" / "tools", repo / ".less_tokens" / "tools"]
    for path in reversed(paths):
        sys.path.insert(0, str(path))


def load_json_stdin() -> dict:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


def print_result(code: int, stdout: str, stderr: str) -> int:
    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)
    return code


def map_codex_read(raw: dict) -> dict:
    if raw.get("tool_name") == "mcp__filesystem__read_file":
        inp = raw.setdefault("tool_input", {})
        raw["tool_name"] = "Read"
        inp["file_path"] = inp.get("path", "")
    return raw


def map_codex_search(raw: dict) -> dict:
    tool = raw.get("tool_name", "")
    if tool.startswith("mcp__filesystem__") and "search" in tool:
        raw["tool_name"] = "Grep"
    return raw

"""Shared adapter helpers for Codex hook wrappers."""
from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from pathlib import Path


def resolve_repo() -> Path:
    if os.environ.get("LESS_TOKENS_REPO"):
        return Path(os.environ["LESS_TOKENS_REPO"]).resolve()
    for start in (Path(__file__).resolve().parent, Path.cwd().resolve()):
        curr = start
        for _ in range(8):
            if (curr / ".git").exists() or (curr / "AGENTS.md").exists():
                return curr
            curr = curr.parent
    return Path(__file__).resolve().parent.parent.parent.parent


def bootstrap() -> Path:
    repo = resolve_repo()
    os.environ.setdefault("LESS_TOKENS_AGENT", "codex")
    sys.path[:0] = [
        str(repo),
        str(repo / "agents" / "common" / "hooks"),
        str(repo / ".less_tokens" / "hooks"),
        str(repo / ".less_tokens" / "tools"),
        str(repo / ".claude" / "tools"),
    ]
    return repo


def load_json_stdin(*mappers: Callable[[dict], dict]) -> dict:
    try:
        raw = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    for mapper in mappers:
        raw = mapper(raw)
    return raw


def print_result(code: int, stdout: str, stderr: str) -> int:
    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)
    return code


# @modelcontextprotocol/server-filesystem renamed its read tool from
# read_file to read_text_file (confirmed live against v2026.7.10); accept
# both so an older pinned server version doesn't silently no-op these hooks.
FILESYSTEM_READ_TOOLS = ("mcp__filesystem__read_file", "mcp__filesystem__read_text_file")


def map_read(raw: dict) -> dict:
    if raw.get("tool_name") in FILESYSTEM_READ_TOOLS:
        inp = raw.setdefault("tool_input", {})
        raw["tool_name"] = "Read"
        inp["file_path"] = inp.get("path", "")
    return raw


def map_read_or_search(raw: dict) -> dict:
    tool = raw.get("tool_name", "")
    if tool in FILESYSTEM_READ_TOOLS:
        return map_read(raw)
    if tool.startswith("mcp__filesystem__") and "search" in tool:
        raw["tool_name"] = "Grep"
    return raw

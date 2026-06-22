"""Normalize native hook payloads into budget inputs."""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .candidates import ContextCandidate
from .estimator import estimate_size_tokens, estimate_tokens
from .signals import extract_failure_paths, extract_path_references, grep_cache_key, read_cache_key


@dataclass(frozen=True)
class BudgetInput:
    agent: str
    phase: str
    tool_name: str
    session_id: str
    run_id: str
    query: str = ""
    candidates: list[ContextCandidate] = field(default_factory=list)


def _payload_tool_input(payload: dict) -> dict:
    value = payload.get("tool_input") or payload.get("arguments") or {}
    return value if isinstance(value, dict) else {}


def _payload_output(payload: dict) -> str:
    raw = payload.get("tool_result") or payload.get("tool_response") or payload.get("output") or ""
    if isinstance(raw, str):
        return raw
    try:
        return json.dumps(raw)
    except TypeError:
        return str(raw)


def _phase(payload: dict) -> str:
    event = str(payload.get("hook_event_name") or payload.get("event") or "").lower()
    tool = str(payload.get("tool_name") or "")
    if event.startswith("pre"):
        if tool in {"Read", "mcp__filesystem__read_file"}:
            return "pre_read"
        if tool in {"Grep", "Glob"} or "search" in tool.lower():
            return "pre_search"
        return "pre_tool"
    if event.startswith("post"):
        if tool in {"Edit", "Write", "apply_patch"}:
            return "post_edit"
        return "post_output"
    return "observe"


def _session_id(payload: dict) -> str:
    return str(
        payload.get("session_id")
        or os.environ.get("LESS_TOKENS_SESSION_ID")
        or "local-session"
    )


def _run_id(payload: dict) -> str:
    return str(payload.get("run_id") or os.environ.get("LESS_TOKENS_RUN_ID") or uuid.uuid4().hex[:12])


def _path_candidate(path: str, *, candidate_type: str = "file_ref", text: str = "") -> ContextCandidate:
    return ContextCandidate(
        candidate_id=f"{candidate_type}:{path}",
        category="retrieved_context",
        candidate_type=candidate_type,
        path=path,
        text=text,
    )


def _candidates_from_payload(payload: dict, *, phase: str, tool_name: str) -> list[ContextCandidate]:
    inp = _payload_tool_input(payload)
    output = _payload_output(payload)
    if phase == "pre_tool" and tool_name == "Bash":
        command = str(inp.get("command") or "")
        if _is_broad_listing(command):
            return [ContextCandidate(
                candidate_id=f"directory_listing:{command[:80]}",
                category="tool_output",
                candidate_type="directory_listing",
                text=command,
                metadata={"command": command},
            )]
    if phase == "pre_read":
        file_path = str(inp.get("file_path") or inp.get("path") or "")
        if not file_path:
            return []
        p = Path(file_path)
        size = 0
        try:
            size = p.stat().st_size
        except OSError:
            pass
        return [ContextCandidate(
            candidate_id=f"file:{file_path}",
            category="retrieved_context",
            candidate_type="file",
            path=file_path,
            estimated_tokens=estimate_size_tokens(size),
            metadata={
                "size_chars": size,
                "offset": inp.get("offset"),
                "limit": inp.get("limit"),
                "read_key": read_cache_key(file_path, inp.get("offset"), inp.get("limit")),
            },
        )]
    if phase == "pre_search":
        pattern = str(inp.get("pattern") or inp.get("query") or inp.get("path") or "")
        return [ContextCandidate(
            candidate_id=f"search:{tool_name}:{pattern}",
            category="retrieved_context",
            candidate_type="search",
            text=pattern,
            estimated_tokens=estimate_tokens(pattern),
            metadata={"search_key": grep_cache_key(
                pattern=str(inp.get("pattern") or ""),
                path=str(inp.get("path") or ""),
                glob=str(inp.get("glob") or ""),
                type_=str(inp.get("type") or ""),
                query=str(inp.get("query") or ""),
            )},
        )]
    if phase == "post_edit":
        path = str(inp.get("file_path") or inp.get("path") or "")
        return [ContextCandidate(
            candidate_id=f"diff:{path or tool_name}",
            category="diffs",
            candidate_type="diff",
            text=output,
            path=path or None,
        )]
    if output:
        candidates = [ContextCandidate(
            candidate_id=f"tool_output:{tool_name}",
            category="tool_output",
            candidate_type="tool_output",
            text=output,
            content_type="logs",
        )]
        for path in sorted(extract_failure_paths(output) or extract_path_references(output)):
            candidates.append(_path_candidate(path, text=output[:1200]))
        return candidates
    return []


def _is_broad_listing(command: str) -> bool:
    stripped = command.strip()
    if not stripped:
        return False
    return (
        stripped in {"find .", "tree"}
        or stripped.startswith("find . ")
        or stripped.startswith("tree ")
        or "ls -R" in stripped
        or "ls -laR" in stripped
        or "ls -alR" in stripped
    )


def normalize_budget_input(payload: dict, *, agent: str | None = None) -> BudgetInput:
    tool_name = str(payload.get("tool_name") or "")
    resolved_agent = agent or str(payload.get("agent") or os.environ.get("LESS_TOKENS_AGENT") or "claude")
    phase = _phase(payload)
    inp = _payload_tool_input(payload)
    query = " ".join(str(v) for v in inp.values() if isinstance(v, (str, int, float)))
    candidates = _candidates_from_payload(payload, phase=phase, tool_name=tool_name)
    return BudgetInput(
        agent=resolved_agent,
        phase=phase,
        tool_name=tool_name,
        session_id=_session_id(payload),
        run_id=_run_id(payload),
        query=query,
        candidates=candidates,
    )

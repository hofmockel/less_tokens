"""Normalized hook payload dataclass for Claude and Codex agents."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class HookPayload:
    agent: str
    tool_name: str
    tool_input: dict
    tool_output: str
    transcript_path: Path | None
    touched_files: tuple[Path, ...]


def _path_or_none(v: object) -> Path | None:
    return Path(str(v)) if v else None


def normalize_claude(payload: dict) -> HookPayload:
    tool_input = payload.get("tool_input") or {}
    raw_output = payload.get("tool_result") or payload.get("tool_response") or ""
    if not isinstance(raw_output, str):
        import json
        raw_output = json.dumps(raw_output)

    fp = tool_input.get("file_path")
    touched = (Path(fp),) if fp else ()

    return HookPayload(
        agent="claude",
        tool_name=payload.get("tool_name", ""),
        tool_input=tool_input,
        tool_output=raw_output,
        transcript_path=_path_or_none(payload.get("transcript_path")),
        touched_files=touched,
    )


def extract_apply_patch_paths(patch_text: str) -> tuple[Path, ...]:
    """Extract touched paths from Codex apply_patch text."""
    paths: list[Path] = []
    seen: set[str] = set()
    patterns = (
        re.compile(r"^\*\*\* (?:Add|Delete|Update) File: (.+)$"),
        re.compile(r"^\*\*\* Move to: (.+)$"),
    )
    for line in patch_text.splitlines():
        for pattern in patterns:
            match = pattern.match(line)
            if not match:
                continue
            value = match.group(1).strip()
            if value and value not in seen:
                paths.append(Path(value))
                seen.add(value)
            break
    return tuple(paths)


def _apply_patch_text(payload: dict, tool_input: dict) -> str:
    for key in ("patch", "input", "payload", "command"):
        value = tool_input.get(key)
        if isinstance(value, str):
            return value
    value = payload.get("patch")
    return value if isinstance(value, str) else ""


def normalize_codex(payload: dict) -> HookPayload:
    tool_input = payload.get("tool_input") or {}
    raw_output = payload.get("tool_response") or payload.get("tool_result") or ""
    if not isinstance(raw_output, str):
        import json
        raw_output = json.dumps(raw_output)

    tool_name = payload.get("tool_name", "")
    if tool_name == "apply_patch":
        touched = extract_apply_patch_paths(_apply_patch_text(payload, tool_input))
    else:
        fp = tool_input.get("file_path")
        touched = (Path(fp),) if fp else ()

    return HookPayload(
        agent="codex",
        tool_name=tool_name,
        tool_input=tool_input,
        tool_output=raw_output,
        transcript_path=_path_or_none(payload.get("transcript_path")),
        touched_files=touched,
    )

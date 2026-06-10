"""Normalized hook payload dataclass for Claude and Codex agents."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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


def normalize_codex(payload: dict) -> HookPayload:
    tool_input = payload.get("tool_input") or {}
    raw_output = payload.get("tool_response") or payload.get("tool_result") or ""
    if not isinstance(raw_output, str):
        import json
        raw_output = json.dumps(raw_output)

    # apply_patch doesn't give a single file_path — stay conservative
    tool_name = payload.get("tool_name", "")
    fp = tool_input.get("file_path") if tool_name != "apply_patch" else None
    touched = (Path(fp),) if fp else ()

    return HookPayload(
        agent="codex",
        tool_name=tool_name,
        tool_input=tool_input,
        tool_output=raw_output,
        transcript_path=_path_or_none(payload.get("transcript_path")),
        touched_files=touched,
    )

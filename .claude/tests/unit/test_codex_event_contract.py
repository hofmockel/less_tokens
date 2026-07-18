"""Codex hook event-contract tests for installed hooks.json matchers."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))

from install import build_codex_hook_entries  # noqa: E402

CODEX_HOOKS = REPO / "agents" / "codex" / "hooks"


def _env(state_dir: Path) -> dict[str, str]:
    return {
        **os.environ,
        "PYTHONPATH": os.pathsep.join((
            str(REPO / ".claude" / "tests"),
            str(REPO / ".claude" / "tools"),
            str(REPO / "agents" / "common" / "hooks"),
            os.environ.get("PYTHONPATH", ""),
        )),
        "LESS_TOKENS_REPO": str(REPO),
        "LESS_TOKENS_AGENT": "codex",
        "LESS_TOKENS_STATE_DIR": str(state_dir),
    }


def _args() -> Namespace:
    return Namespace(truncate=False, compact=False, caveman=False)


def _entries() -> list[tuple[str, str, str]]:
    return build_codex_hook_entries(REPO / ".venv" / "bin" / "python", REPO, _args())


def _script(command: str) -> str:
    return Path(command.split()[-1]).name


def _payloads_for_token(token: str, tmp_path: Path) -> list[dict]:
    target = tmp_path / "contract.txt"
    target.write_text("old\n", encoding="utf-8")
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# Agent Notes\n\nUse targeted context.\n", encoding="utf-8")
    patch = "*** Begin Patch\n*** Update File: contract.txt\n@@\n-old\n+new\n*** End Patch\n"

    if token == "mcp__filesystem__.*":
        return [
            {
                "tool_name": "mcp__filesystem__read_file",
                "tool_input": {"path": str(target), "offset": 0, "limit": 20},
                "tool_response": "old\n",
            },
            {
                # CX24: @modelcontextprotocol/server-filesystem's live tool
                # name (confirmed against v2026.7.10) — read_file above is
                # the legacy alias some pinned server versions still use.
                "tool_name": "mcp__filesystem__read_text_file",
                "tool_input": {"path": str(target), "offset": 0, "limit": 20},
                "tool_response": "old\n",
            },
            {
                "tool_name": "mcp__filesystem__search_files",
                "tool_input": {"path": str(tmp_path), "pattern": "contract"},
                "tool_response": str(target),
            },
        ]
    if token == "Bash":
        return [{
            "tool_name": "Bash",
            "tool_input": {"command": "pwd"},
            "tool_response": str(tmp_path),
        }]
    if token == "apply_patch":
        return [{
            "tool_name": "apply_patch",
            "tool_input": {"patch": patch},
            "tool_response": "Done!",
        }]
    if token == "Edit":
        return [{
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "old\n",
                "new_string": "new\n",
            },
            "tool_response": "",
        }]
    if token == "Write":
        return [{
            "tool_name": "Write",
            "tool_input": {"file_path": str(agents), "content": agents.read_text(encoding="utf-8")},
            "tool_response": "",
        }]
    if token == ".*":
        return [{
            "tool_name": "Bash",
            "tool_input": {"command": "pytest"},
            "tool_response": "1 passed\n",
        }]
    raise AssertionError(f"no Codex fixture for matcher token {token!r}")


def _payloads_for_matcher(matcher: str, tmp_path: Path) -> list[dict]:
    return [
        payload
        for token in matcher.split("|")
        for payload in _payloads_for_token(token, tmp_path)
    ]


def _contract_cases() -> list[tuple[str, str, str, str]]:
    cases = []
    for event, matcher, command in _entries():
        for token in matcher.split("|"):
            cases.append((event, matcher, _script(command), token))
    return cases


def _case_id(case: tuple[str, str, str, str]) -> str:
    event, matcher, script, token = case
    return f"{event}:{matcher}:{script}:{token}"


CONTRACT_CASES = _contract_cases()


def test_every_codex_matcher_has_representative_payload(tmp_path):
    seen_tools = set()
    for _, matcher, _ in _entries():
        payloads = _payloads_for_matcher(matcher, tmp_path)
        assert payloads, matcher
        for payload in payloads:
            tool_name = payload["tool_name"]
            assert re.fullmatch(matcher, tool_name), f"{tool_name!r} does not match {matcher!r}"
            seen_tools.add(tool_name)

    assert {
        "mcp__filesystem__read_file",
        "mcp__filesystem__read_text_file",
        "mcp__filesystem__search_files",
        "Bash",
        "apply_patch",
        "Edit",
        "Write",
    } <= seen_tools


@pytest.mark.parametrize(
    "event,matcher,script,token",
    CONTRACT_CASES,
    ids=[_case_id(case) for case in CONTRACT_CASES],
)
def test_codex_hook_entry_accepts_representative_payload(event, matcher, script, token, tmp_path):
    for payload in _payloads_for_token(token, tmp_path):
        result = subprocess.run(
            [sys.executable, str(CODEX_HOOKS / script)],
            input=json.dumps({**payload, "hook_event_name": event, "session_id": "contract-session"}),
            capture_output=True,
            text=True,
            env=_env(tmp_path / "state"),
            timeout=15,
        )

        combined = result.stdout + result.stderr
        assert result.returncode in {0, 2}, combined
        assert "Traceback" not in combined
        assert "JSONDecodeError" not in combined

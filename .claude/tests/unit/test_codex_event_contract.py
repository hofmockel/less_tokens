"""Codex hook event-contract tests for installed hooks.json matchers."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
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


MCP_TOKEN = "mcp__filesystem__.*"
GATE_HOOKS = {
    "search-first.py": "Search-first rule",
    "read-guard.py": "Read-guard:",
    "auto-slice.py": "Auto-slice:",
    "grep-first-read.py": "Grep-first gate",
    "read-after-edit.py": "read-after-edit:",
    "continue-freshness.py": "continue.md is",
}

BASE_SCENARIOS = {
    MCP_TOKEN: ("filesystem-read-legacy", "filesystem-read-current", "filesystem-search"),
    "Bash": ("bash",),
    "apply_patch": ("apply-patch",),
    "Edit": ("edit",),
    "Write": ("write",),
    ".*": ("any-tool",),
}


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _handoff_repo(tmp_path: Path, *, stale: bool) -> Path:
    repo = tmp_path / "handoff-repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "less_tokens tests")
    _git(repo, "commit", "--allow-empty", "-m", "initial")
    recorded = _git(repo, "rev-parse", "HEAD")
    if stale:
        _git(repo, "commit", "--allow-empty", "-m", "newer work")
    (repo / "continue.md").write_text(
        f"# Continue\n\n_Last updated at HEAD `{recorded}`._\n",
        encoding="utf-8",
    )
    return repo


def _read_payload(token: str, path: Path, *, offset: int | None = None) -> dict:
    if token == MCP_TOKEN:
        tool_input: dict[str, object] = {"path": str(path)}
        if offset is not None:
            tool_input["offset"] = offset
        return {
            "tool_name": "mcp__filesystem__read_file",
            "tool_input": tool_input,
            "tool_response": path.read_text(encoding="utf-8", errors="replace"),
        }
    if token == "Bash":
        command = f"cat {path}" if offset is None else f"sed -n '{offset},20p' {path}"
        return {
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "tool_response": path.read_text(encoding="utf-8", errors="replace"),
        }
    raise AssertionError(f"{token!r} is not a read matcher token")


def _base_payload(token: str, scenario: str, tmp_path: Path) -> dict:
    target = tmp_path / "contract.txt"
    target.write_text("old\n", encoding="utf-8")
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# Agent Notes\n\nUse targeted context.\n", encoding="utf-8")
    patch = "*** Begin Patch\n*** Update File: contract.txt\n@@\n-old\n+new\n*** End Patch\n"

    if token == MCP_TOKEN:
        if scenario == "filesystem-read-legacy":
            return {
                "tool_name": "mcp__filesystem__read_file",
                "tool_input": {"path": str(target), "offset": 0, "limit": 20},
                "tool_response": "old\n",
            }
        if scenario == "filesystem-read-current":
            return {
                # CX24: current server name, retained beside the legacy alias.
                "tool_name": "mcp__filesystem__read_text_file",
                "tool_input": {"path": str(target), "offset": 0, "limit": 20},
                "tool_response": "old\n",
            }
        if scenario == "filesystem-search":
            return {
                "tool_name": "mcp__filesystem__search_files",
                "tool_input": {"path": str(tmp_path), "pattern": "contract"},
                "tool_response": str(target),
            }
    if token == "Bash" and scenario == "bash":
        return {
            "tool_name": "Bash",
            "tool_input": {"command": "pwd"},
            "tool_response": str(tmp_path),
        }
    if token == "apply_patch" and scenario == "apply-patch":
        return {
            "tool_name": "apply_patch",
            "tool_input": {"patch": patch},
            "tool_response": "Done!",
        }
    if token == "Edit" and scenario == "edit":
        return {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "old\n",
                "new_string": "new\n",
            },
            "tool_response": "",
        }
    if token == "Write" and scenario == "write":
        return {
            "tool_name": "Write",
            "tool_input": {"file_path": str(agents), "content": agents.read_text(encoding="utf-8")},
            "tool_response": "",
        }
    if token == ".*" and scenario == "any-tool":
        return {
            "tool_name": "Bash",
            "tool_input": {"command": "pytest"},
            "tool_response": "1 passed\n",
        }
    raise AssertionError(f"no Codex fixture for {token!r} scenario {scenario!r}")


def _gate_payload(
    script: str,
    token: str,
    scenario: str,
    tmp_path: Path,
    state_dir: Path,
) -> tuple[dict, dict[str, str]]:
    state_dir.mkdir(parents=True, exist_ok=True)
    phase = scenario.rsplit("-", 1)[-1]
    extra_env: dict[str, str] = {}

    if script == "search-first.py":
        target = REPO / "README.md"
        if phase == "allow":
            (state_dir / "last-search").touch()
        payload = _read_payload(token, target)
    elif script == "read-guard.py":
        target = tmp_path / "package-lock.json"
        target.write_text("{}\n", encoding="utf-8")
        payload = _read_payload(token, target, offset=1 if phase == "allow" else None)
    elif script == "auto-slice.py":
        target = tmp_path / "auto-slice.py"
        target.write_text("one\ntwo\nthree\n", encoding="utf-8")
        if phase != "allow":
            (state_dir / "last-search.json").write_text(
                json.dumps({str(target): [[2, 3]]}), encoding="utf-8"
            )
        payload = _read_payload(token, target)
    elif script == "grep-first-read.py":
        target = tmp_path / "large.txt"
        target.write_text("\n".join(str(i) for i in range(250)), encoding="utf-8")
        if phase == "allow":
            (state_dir / "last-search.json").write_text(
                json.dumps({str(target): [[20, 25]]}), encoding="utf-8"
            )
        payload = _read_payload(token, target)
    elif script == "read-after-edit.py":
        target = tmp_path / "recently-edited.py"
        target.write_text("print('new')\n", encoding="utf-8")
        if phase != "allow":
            (state_dir / "last-edit.json").write_text(
                json.dumps({str(target.resolve()): time.time()}), encoding="utf-8"
            )
        payload = _read_payload(token, target)
    elif script == "continue-freshness.py":
        repo = _handoff_repo(tmp_path, stale=phase != "allow")
        extra_env["LESS_TOKENS_REPO"] = str(repo)
        payload = _read_payload(token, repo / "continue.md")
    else:
        raise AssertionError(f"no gate fixture for {script}")

    if phase == "error":
        payload["tool_response"] = {"error": "boom", "exit_code": 1}
    return payload, extra_env


def _payloads_for_matcher(matcher: str, tmp_path: Path) -> list[dict]:
    return [
        _base_payload(token, scenario, tmp_path)
        for token in matcher.split("|")
        for scenario in BASE_SCENARIOS[token]
    ]


def _scenarios_for(script: str, token: str) -> tuple[str, ...]:
    scenarios = BASE_SCENARIOS[token]
    if script in GATE_HOOKS and token in {MCP_TOKEN, "Bash"}:
        stem = script.removesuffix(".py")
        return (*scenarios, f"{stem}-block", f"{stem}-allow", f"{stem}-error")
    return scenarios


def _contract_cases() -> list[tuple[str, str, str, str, str]]:
    cases = []
    for event, matcher, command in _entries():
        script = _script(command)
        for token in matcher.split("|"):
            for scenario in _scenarios_for(script, token):
                cases.append((event, matcher, script, token, scenario))
    return cases


def _case_id(case: tuple[str, str, str, str, str]) -> str:
    event, matcher, script, token, scenario = case
    return f"{event}:{matcher}:{script}:{token}:{scenario}"


CONTRACT_CASES = _contract_cases()

OUTCOMES = {
    (script, token, scenario): (0, None)
    for _, _, script, token, scenario in CONTRACT_CASES
}
for _script_name, _message in GATE_HOOKS.items():
    _stem = _script_name.removesuffix(".py")
    for _token in (MCP_TOKEN, "Bash"):
        OUTCOMES[(_script_name, _token, f"{_stem}-block")] = (2, _message)
        OUTCOMES[(_script_name, _token, f"{_stem}-error")] = (2, _message)


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
    "event,matcher,script,token,scenario",
    CONTRACT_CASES,
    ids=[_case_id(case) for case in CONTRACT_CASES],
)
def test_codex_hook_entry_has_semantic_outcome(event, matcher, script, token, scenario, tmp_path):
    state_dir = tmp_path / "state"
    if scenario in BASE_SCENARIOS[token]:
        payload = _base_payload(token, scenario, tmp_path)
        extra_env = {}
    else:
        payload, extra_env = _gate_payload(script, token, scenario, tmp_path, state_dir)
    result = subprocess.run(
        [sys.executable, str(CODEX_HOOKS / script)],
        input=json.dumps({**payload, "hook_event_name": event, "session_id": "contract-session"}),
        capture_output=True,
        text=True,
        env={**_env(state_dir), **extra_env},
        timeout=15,
    )

    combined = result.stdout + result.stderr
    expected_code, expected_message = OUTCOMES[(script, token, scenario)]
    assert result.returncode == expected_code, combined
    if expected_message is not None:
        assert expected_message in combined
    assert "Traceback" not in combined
    assert "JSONDecodeError" not in combined


def test_codex_unknown_mcp_tool_fails_open(tmp_path):
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "mcp__other_server__do_thing",
        "tool_input": {"path": "/not/used"},
        "tool_response": {"error": "unknown tool"},
        "session_id": "contract-session",
    }
    for script in GATE_HOOKS:
        result = subprocess.run(
            [sys.executable, str(CODEX_HOOKS / script)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=_env(tmp_path / script),
            timeout=15,
        )
        assert (result.returncode, result.stdout, result.stderr) == (0, "", ""), script


def test_codex_has_no_stop_wiring_yet():
    # CX23 found no real Codex Stop/SubagentStop event surface. Force fixture
    # coverage to be added if the platform contract changes.
    assert not [entry for entry in _entries() if entry[0] in {"Stop", "SubagentStop"}]

"""Codex hook event-contract tests for installed hooks.json matchers."""
from __future__ import annotations

import json
import io
import os
import re
import shlex
import subprocess
import sys
import time
from argparse import Namespace
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))

from install import build_codex_hook_entries  # noqa: E402
from agents.codex.hooks import _codex_runtime  # noqa: E402

CODEX_HOOKS = REPO / "agents" / "codex" / "hooks"
LIVE_FIXTURES = REPO / ".claude" / "tests" / "fixtures" / "codex-hooks"


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
    script = shlex.split(command)[-1].replace("\\", "/")
    return Path(script).name


def test_script_extracts_shell_quoted_windows_path():
    command = r"LESS_TOKENS_AGENT=codex python 'C:\workspace\hooks\search-first.py'"
    assert _script(command) == "search-first.py"


MCP_TOKEN = "mcp__filesystem__.*"
GATE_HOOKS = {
    "search-first.py": "Search-first rule",
    "read-guard.py": "Read-guard:",
    "auto-slice.py": "Auto-slice:",
    "grep-first-read.py": "Grep-first gate",
    "read-after-edit.py": "read-after-edit:",
    "continue-freshness.py": "continue.md is",
}
NATIVE_DECISION_HOOKS = set(GATE_HOOKS) - {"read-after-edit.py"}

BASE_SCENARIOS = {
    MCP_TOKEN: ("filesystem-read-legacy", "filesystem-read-current", "filesystem-search"),
    "Bash": ("bash",),
    "apply_patch": ("apply-patch",),
    "Edit": ("edit",),
    "Write": ("write",),
    ".*": ("any-tool", "other-local-tool", "agent-local-tool"),
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
        quoted_path = shlex.quote(str(path))
        command = (
            f"cat {quoted_path}"
            if offset is None
            else f"sed -n '{offset},20p' {quoted_path}"
        )
        return {
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "tool_response": path.read_text(encoding="utf-8", errors="replace"),
        }
    raise AssertionError(f"{token!r} is not a read matcher token")


def test_bash_read_payload_shell_quotes_target(tmp_path):
    target = tmp_path / "path with spaces.txt"
    target.write_text("content\n", encoding="utf-8")
    payload = _read_payload("Bash", target)
    assert shlex.split(payload["tool_input"]["command"])[-1] == str(target)


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
            # Edit/Write are matcher aliases; the published hook input keeps
            # apply_patch as the canonical tool name.
            "tool_name": "apply_patch",
            "tool_input": {"command": patch},
            "tool_response": "",
        }
    if token == "Write" and scenario == "write":
        return {
            "tool_name": "apply_patch",
            "tool_input": {"command": patch},
            "tool_response": "",
        }
    if token == ".*" and scenario == "any-tool":
        return {
            "tool_name": "Bash",
            "tool_input": {"command": "pytest"},
            "tool_response": "1 passed\n",
        }
    if token == ".*" and scenario == "other-local-tool":
        return {
            "tool_name": "update_plan",
            "tool_input": {"plan": [{"step": "verify", "status": "in_progress"}]},
            "tool_response": {"ok": True},
        }
    if token == ".*" and scenario == "agent-local-tool":
        return {
            "tool_name": "Agent",
            "tool_input": {"description": "inspect contract coverage"},
            "tool_response": {"agent_id": "agent-contract"},
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


def _scenarios_for(event: str, script: str, token: str) -> tuple[str, ...]:
    scenarios = BASE_SCENARIOS[token]
    if script in GATE_HOOKS and token in {MCP_TOKEN, "Bash"}:
        stem = script.removesuffix(".py")
        return (*scenarios, f"{stem}-block", f"{stem}-allow", f"{stem}-error")
    if event == "PostToolUse":
        return (*scenarios, *(f"{scenario}-error" for scenario in scenarios))
    return scenarios


def _contract_cases() -> list[tuple[str, str, str, str, str]]:
    cases = []
    for event, matcher, command in _entries():
        script = _script(command)
        for token in matcher.split("|"):
            for scenario in _scenarios_for(event, script, token):
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
        _code = 0 if _script_name in NATIVE_DECISION_HOOKS else 2
        OUTCOMES[(_script_name, _token, f"{_stem}-block")] = (_code, _message)
        OUTCOMES[(_script_name, _token, f"{_stem}-error")] = (_code, _message)


def test_every_codex_matcher_has_representative_payload(tmp_path):
    seen_tools = set()
    for _, matcher, _ in _entries():
        payloads = _payloads_for_matcher(matcher, tmp_path)
        assert payloads, matcher
        for token in matcher.split("|"):
            for scenario in BASE_SCENARIOS[token]:
                payload = _base_payload(token, scenario, tmp_path)
                tool_name = payload["tool_name"]
                if token in {"Edit", "Write"}:
                    assert tool_name == "apply_patch"
                else:
                    assert re.fullmatch(token, tool_name), f"{tool_name!r} does not match {token!r}"
                seen_tools.add(tool_name)

    assert {
        "mcp__filesystem__read_file",
        "mcp__filesystem__read_text_file",
        "mcp__filesystem__search_files",
        "Bash",
        "apply_patch",
        "update_plan",
        "Agent",
    } <= seen_tools


@pytest.mark.parametrize("release", ["0.142.3", "0.144.5", "0.144.6"])
@pytest.mark.parametrize(
    "fixture_name,tool_name",
    [("pre-tool-use-bash.json", "Bash"), ("pre-tool-use-apply-patch.json", "apply_patch")],
)
def test_release_labeled_live_pre_tool_use_fixture(release, fixture_name, tool_name):
    payload = json.loads(
        (LIVE_FIXTURES / release / fixture_name).read_text(encoding="utf-8")
    )
    assert payload["hook_event_name"] == "PreToolUse"
    assert payload["tool_name"] == tool_name
    if tool_name == "Bash":
        assert payload["tool_input"] == {"command": "pwd"}
    else:
        assert payload["tool_input"]["command"].startswith("*** Begin Patch")
    assert payload["session_id"] == f"session-{release}"
    assert payload["turn_id"] == f"turn-{release}"
    assert payload["cwd"] == "/workspace"
    expected_prefix = "call_" if release == "0.142.3" else "exec-"
    assert payload["tool_use_id"].startswith(expected_prefix)


@pytest.mark.parametrize(
    "fixture_name,event,tool_name",
    [
        ("session-start-startup.json", "SessionStart", None),
        ("user-prompt-submit.json", "UserPromptSubmit", None),
        ("pre-tool-use-bash.json", "PreToolUse", "Bash"),
        ("permission-request-bash.json", "PermissionRequest", "Bash"),
        ("post-tool-use-bash.json", "PostToolUse", "Bash"),
        ("post-tool-use-bash-error.json", "PostToolUse", "Bash"),
        ("pre-tool-use-apply-patch.json", "PreToolUse", "apply_patch"),
        ("post-tool-use-apply-patch.json", "PostToolUse", "apply_patch"),
        ("pre-tool-use-update-plan.json", "PreToolUse", "update_plan"),
        ("post-tool-use-update-plan.json", "PostToolUse", "update_plan"),
        ("pre-compact-manual.json", "PreCompact", None),
        ("post-compact-manual.json", "PostCompact", None),
        ("subagent-start-default.json", "SubagentStart", None),
        ("subagent-stop-default.json", "SubagentStop", None),
        ("stop.json", "Stop", None),
    ],
)
def test_current_cli_live_fixture_matrix(fixture_name, event, tool_name):
    payload = json.loads(
        (LIVE_FIXTURES / "0.144.6" / fixture_name).read_text(encoding="utf-8")
    )
    assert payload["hook_event_name"] == event
    assert payload["session_id"] == "session-0.144.6"
    assert payload["cwd"] == "/workspace"
    assert payload["model"] == "gpt-5.6-sol"
    if event != "SessionStart":
        assert payload["turn_id"] == "turn-0.144.6"
    if tool_name:
        assert payload["tool_name"] == tool_name
        assert isinstance(payload["tool_input"], dict)
        if event == "PermissionRequest":
            assert payload["permission_mode"] == "default"
            assert payload["tool_input"] == {
                "command": "pwd",
                "description": "PermissionRequest fixture probe",
            }
            assert "tool_use_id" not in payload
        else:
            assert payload["tool_use_id"] == "exec-SANITIZED"
    if event == "PostToolUse":
        assert isinstance(payload["tool_response"], str)


def test_current_cli_manual_compaction_fixture_pair_is_ordered_and_correlated():
    paths = ["pre-compact-manual.json", "post-compact-manual.json"]
    payloads = [
        json.loads((LIVE_FIXTURES / "0.144.6" / path).read_text(encoding="utf-8"))
        for path in paths
    ]
    assert [payload["hook_event_name"] for payload in payloads] == [
        "PreCompact",
        "PostCompact",
    ]
    assert {payload["session_id"] for payload in payloads} == {"session-0.144.6"}
    assert {payload["turn_id"] for payload in payloads} == {"turn-0.144.6"}
    assert {payload["trigger"] for payload in payloads} == {"manual"}


def test_current_cli_subagent_fixture_pair_is_correlated():
    paths = ["subagent-start-default.json", "subagent-stop-default.json"]
    started, stopped = [
        json.loads((LIVE_FIXTURES / "0.144.6" / path).read_text(encoding="utf-8"))
        for path in paths
    ]
    assert [started["hook_event_name"], stopped["hook_event_name"]] == [
        "SubagentStart",
        "SubagentStop",
    ]
    assert started["session_id"] == stopped["session_id"] == "session-0.144.6"
    assert started["turn_id"] == stopped["turn_id"] == "turn-0.144.6"
    assert started["agent_id"] == stopped["agent_id"] == "agent-0.144.6"
    assert started["agent_type"] == stopped["agent_type"] == "default"
    assert started["transcript_path"] == stopped["agent_transcript_path"]
    assert stopped["last_assistant_message"] == "/workspace"
    assert stopped["stop_hook_active"] is False


def test_current_cli_failed_bash_fixture_preserves_observed_empty_response():
    payload = json.loads(
        (LIVE_FIXTURES / "0.144.6" / "post-tool-use-bash-error.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["tool_input"] == {"command": "false"}
    assert payload["tool_response"] == ""
    assert "error" not in payload


def test_current_cli_live_fixtures_are_sanitized():
    fixture_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((LIVE_FIXTURES / "0.144.6").glob("*.json"))
    )
    assert "/tmp/" not in fixture_text
    assert "/private/" not in fixture_text
    assert not re.search(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
        fixture_text,
        re.IGNORECASE,
    )


def test_schema_drift_telemetry_preserves_payload_and_omits_values(tmp_path, monkeypatch):
    payload = {
        "hook_event_name": "FutureToolEvent",
        "tool_name": "future_tool",
        "tool_input": {"secret": "DO-NOT-RECORD"},
    }
    monkeypatch.setenv("LESS_TOKENS_STATE_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))

    mapped = _codex_runtime.load_json_stdin(lambda raw: {**raw, "mapped": True})

    assert mapped == {**payload, "mapped": True}
    telemetry = (tmp_path / "codex-hook-schema-drift.jsonl").read_text(
        encoding="utf-8"
    )
    assert "unknown-hook-event" in telemetry
    assert "FutureToolEvent" in telemetry
    assert "future_tool" in telemetry
    assert "DO-NOT-RECORD" not in telemetry


@pytest.mark.parametrize(
    "event,matcher,script,token,scenario",
    CONTRACT_CASES,
    ids=[_case_id(case) for case in CONTRACT_CASES],
)
def test_codex_hook_entry_has_semantic_outcome(event, matcher, script, token, scenario, tmp_path):
    state_dir = tmp_path / "state"
    base_scenario = scenario.removesuffix("-error")
    if base_scenario in BASE_SCENARIOS[token]:
        payload = _base_payload(token, base_scenario, tmp_path)
        if scenario.endswith("-error"):
            payload["tool_response"] = {"error": "boom", "exit_code": 1}
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
    if script in NATIVE_DECISION_HOOKS and scenario.endswith(("-block", "-error")):
        assert result.stderr == ""
        output = json.loads(result.stdout)
        specific = output["hookSpecificOutput"]
        assert specific["hookEventName"] == "PreToolUse"
        if script == "auto-slice.py" and token == "Bash":
            assert specific["permissionDecision"] == "allow"
            assert specific["updatedInput"]["command"].startswith("sed -n 2,3p ")
        else:
            assert specific["permissionDecision"] == "deny"
            assert expected_message in specific["permissionDecisionReason"]
    elif expected_message is not None:
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

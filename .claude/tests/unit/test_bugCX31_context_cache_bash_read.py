"""Regression test for CX31 (BACKLOG.md): context-cache.py did not call
`map_bash_read`, so a repeated `cat <file>` issued over `Bash` (the dominant
read path on a default Codex install, which has no `mcp__filesystem__`
server) was never recognized as a repeat of an already-served Read and was
never cache-blocked. The identical repeat via `mcp__filesystem__read_text_file`
was already blocked (see `test_context_cache_blocks_repeat_read` in
`test_codex_hooks.py`) — only the Bash-path wiring was missing.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent.parent
CODEX_HOOKS = REPO / "agents" / "codex" / "hooks"

_ENV = {
    **os.environ,
    "PYTHONPATH": os.pathsep.join((
        str(REPO / ".claude" / "tests"),
        str(REPO / ".claude" / "tools"),
        str(REPO / "agents" / "common" / "hooks"),
        os.environ.get("PYTHONPATH", ""),
    )),
    "LESS_TOKENS_REPO": str(REPO),
}


def _run_hook(hook_name: str, payload: dict, extra_env: dict | None = None) -> tuple[int, str, str]:
    env = {**_ENV, **(extra_env or {})}
    result = subprocess.run(
        [sys.executable, str(CODEX_HOOKS / hook_name)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


def _deny_reason(code: int, stdout: str, stderr: str) -> str:
    assert code == 0, stderr
    assert stderr == ""
    output = json.loads(stdout)
    specific = output["hookSpecificOutput"]
    assert specific["hookEventName"] == "PreToolUse"
    assert specific["permissionDecision"] == "deny"
    return specific["permissionDecisionReason"]


def test_context_cache_blocks_repeat_bash_cat_read(tmp_path):
    state_dir = tmp_path / "state"
    target = tmp_path / "app.py"
    target.write_text("print(1)\n")
    pre = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": f"cat {target}"},
        "transcript_path": str(tmp_path / "transcript.jsonl"),
    }
    post = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": f"cat {target}"},
        "tool_response": "print(1)\n",
        "transcript_path": str(tmp_path / "transcript.jsonl"),
    }
    code1, _, _ = _run_hook("context-cache.py", pre, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})
    code_post, _, _ = _run_hook("context-cache.py", post, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})
    code2, stdout2, stderr2 = _run_hook("context-cache.py", pre, extra_env={"LESS_TOKENS_STATE_DIR": str(state_dir)})
    assert code1 == 0
    assert code_post == 0
    assert "context-cache" in _deny_reason(code2, stdout2, stderr2)

from __future__ import annotations

import importlib.util
import io
import json
import os
import shlex
import shutil
import sys
from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent.parent
TOOL = REPO / ".claude" / "tools" / "codex_parity_audit.py"
spec = importlib.util.spec_from_file_location("codex_parity_audit", TOOL)
audit_mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
sys.modules[spec.name] = audit_mod  # type: ignore[union-attr]
spec.loader.exec_module(audit_mod)  # type: ignore[union-attr]

from agents.common.hooks.hook_manifest import HOOK_SPECS  # noqa: E402
from install import (  # noqa: E402
    build_codex_hook_entries,
    codex_hooks_json_value,
    launcher_rel,
    write_python_launcher,
)


def _command_script_name(command: str) -> str:
    return shlex.split(command)[-1].replace("\\", "/").rsplit("/", 1)[-1]


def _write_codex_install(
    root: Path,
    *,
    drop_strategy: str | None = None,
    stale_commands: bool = False,
    real_hooks: bool = False,
) -> None:
    hooks_dir = root / ".codex" / "hooks"
    hooks_dir.mkdir(parents=True)
    (root / "AGENTS.md").write_text("# Test install\n", encoding="utf-8")
    common_hooks = root / ".less_tokens" / "hooks"
    if real_hooks:
        shutil.copytree(REPO / "agents" / "common" / "hooks", common_hooks, dirs_exist_ok=True)
        shutil.copytree(REPO / "agents" / "codex" / "hooks", hooks_dir, dirs_exist_ok=True)
    else:
        common_hooks.mkdir(parents=True)
        shutil.copy2(REPO / "agents" / "common" / "hooks" / "hook_manifest.py", common_hooks)
    with redirect_stdout(io.StringIO()):
        write_python_launcher(root, launcher_rel("codex"), Path(sys.executable))
    if not real_hooks:
        for hook_spec in HOOK_SPECS:
            if hook_spec.codex_script:
                (hooks_dir / hook_spec.codex_script).write_text("# hook\n", encoding="utf-8")
    entries = build_codex_hook_entries(
        Path(sys.executable),
        root,
        Namespace(no_truncate=False, no_compact=False, no_caveman=False),
    )
    drop_script = next(
        (spec.codex_script for spec in HOOK_SPECS if spec.name == drop_strategy),
        None,
    )
    hooks = []
    for event, matcher, command in entries:
        script = _command_script_name(command)
        if drop_script == script:
            continue
        if stale_commands:
            command = f"LESS_TOKENS_AGENT=codex .less_tokens/bin/python .codex/hooks/{script}"
        hooks.append({"event": event, "matcher": matcher, "command": command})
    (root / ".codex" / "hooks.json").write_text(
        json.dumps({"hooks": codex_hooks_json_value(hooks)}), encoding="utf-8"
    )


def test_command_script_name_handles_quoted_windows_paths():
    command = (
        "LESS_TOKENS_AGENT=codex "
        "'C:\\repo\\.less_tokens\\bin\\python.cmd' "
        "'C:\\repo\\.codex\\hooks\\search-first.py'"
    )

    assert _command_script_name(command) == "search-first.py"


def test_codex_parity_audit_reports_best_effort_when_fully_wired(tmp_path):
    _write_codex_install(tmp_path)
    rows, problems = audit_mod.audit(tmp_path)

    assert problems == []
    by_name = {row.strategy: row for row in rows}
    assert by_name["search-first"].feature == "feature-parity"
    assert by_name["search-first"].enforcement == "best-effort-only"
    assert "fail open" in by_name["search-first"].notes


@pytest.mark.skipif(os.name == "nt", reason="Codex hook env prefix is POSIX shell syntax")
def test_codex_parity_audit_passes_current_generated_install(tmp_path):
    _write_codex_install(tmp_path, real_hooks=True)

    rows, problems = audit_mod.audit(tmp_path)

    assert problems == []
    assert rows
    # SA1's subagent-cap is Claude-only by design (no Codex Task-boundary hook
    # exists), so it reports enforcement="missing" — only feature-parity rows
    # are held to "best-effort-only".
    parity_rows = [row for row in rows if row.feature == "feature-parity"]
    assert parity_rows
    assert all(row.enforcement == "best-effort-only" for row in parity_rows)
    assert any(row.strategy == "subagent-cap" and row.enforcement == "missing" for row in rows)


def test_codex_parity_audit_fails_on_legacy_flat_hooks_json(tmp_path):
    """CX22: a pre-CX21 flat hooks.json must fail loud, not silently read as zero hooks."""
    _write_codex_install(tmp_path)
    entries = build_codex_hook_entries(
        Path(sys.executable),
        tmp_path,
        Namespace(no_truncate=False, no_compact=False, no_caveman=False),
    )
    flat = [{"event": ev, "matcher": matcher, "command": cmd} for ev, matcher, cmd in entries]
    (tmp_path / ".codex" / "hooks.json").write_text(json.dumps({"hooks": flat}), encoding="utf-8")

    _, problems = audit_mod.audit(tmp_path)

    assert any("malformed or unsupported" in p for p in problems)


def test_codex_parity_audit_fails_when_matcher_missing(tmp_path):
    _write_codex_install(tmp_path, drop_strategy="search-first")
    rows, problems = audit_mod.audit(tmp_path)

    by_name = {row.strategy: row for row in rows}
    assert by_name["search-first"].enforcement == "unwired"
    assert any("search-first" in problem for problem in problems)
    assert "missing exact command" in by_name["search-first"].notes


def test_codex_parity_audit_rejects_stale_relative_commands(tmp_path):
    _write_codex_install(tmp_path, stale_commands=True)
    rows, problems = audit_mod.audit(tmp_path)

    assert problems
    # subagent-cap has no Codex adapter (feature="missing-feature-parity") so
    # it is never rewritten with a stale command and stays enforcement="missing".
    parity_rows = [row for row in rows if row.feature == "feature-parity"]
    assert parity_rows
    assert all(row.enforcement == "unwired" for row in parity_rows)
    assert any("stale command" in row.notes for row in parity_rows)


@pytest.mark.skipif(os.name == "nt", reason="Codex hook env prefix is POSIX shell syntax")
def test_codex_parity_audit_runs_representative_command_from_nested_cwd(tmp_path):
    _write_codex_install(tmp_path)
    marker = tmp_path / "nested-cwd.txt"
    script = tmp_path / ".codex" / "hooks" / "search-first.py"
    script.write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text(str(Path.cwd()), encoding='utf-8')\n",
        encoding="utf-8",
    )

    _, problems = audit_mod.audit(tmp_path)

    assert problems == []
    assert marker.read_text(encoding="utf-8") == str(tmp_path / ".codex" / "hooks")


@pytest.mark.skipif(os.name == "nt", reason="Codex hook env prefix is POSIX shell syntax")
def test_codex_parity_audit_fails_when_nested_cwd_command_cannot_run(tmp_path):
    _write_codex_install(tmp_path)
    script = tmp_path / ".codex" / "hooks" / "search-first.py"
    script.write_text("raise SystemExit(7)\n", encoding="utf-8")

    _, problems = audit_mod.audit(tmp_path)

    assert any("failed from nested cwd (exit 7)" in problem for problem in problems)


def test_codex_parity_audit_json_output(tmp_path, capsys):
    _write_codex_install(tmp_path)
    rc = audit_mod.main(["--root", str(tmp_path), "--json"])
    out = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert out["problems"] == []
    assert any(row["strategy"] == "listing-guard" for row in out["rows"])

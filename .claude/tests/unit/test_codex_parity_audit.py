from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent.parent
TOOL = REPO / ".claude" / "tools" / "codex_parity_audit.py"
spec = importlib.util.spec_from_file_location("codex_parity_audit", TOOL)
audit_mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
sys.modules[spec.name] = audit_mod  # type: ignore[union-attr]
spec.loader.exec_module(audit_mod)  # type: ignore[union-attr]

from agents.common.hooks.hook_manifest import HOOK_SPECS  # noqa: E402


def _write_codex_install(root: Path, *, drop_strategy: str | None = None) -> None:
    hooks_dir = root / ".codex" / "hooks"
    hooks_dir.mkdir(parents=True)
    hooks = []
    for hook_spec in HOOK_SPECS:
        if not hook_spec.codex_script:
            continue
        (hooks_dir / hook_spec.codex_script).write_text("# hook\n", encoding="utf-8")
        for wire in hook_spec.codex:
            if hook_spec.name == drop_strategy:
                continue
            hooks.append({
                "event": wire.event,
                "matcher": wire.matcher,
                "command": f".less_tokens/bin/python .codex/hooks/{hook_spec.codex_script}",
            })
    (root / ".codex" / "hooks.json").write_text(json.dumps({"hooks": hooks}), encoding="utf-8")


def test_codex_parity_audit_reports_best_effort_when_fully_wired(tmp_path):
    _write_codex_install(tmp_path)
    rows, problems = audit_mod.audit(tmp_path)

    assert problems == []
    by_name = {row.strategy: row for row in rows}
    assert by_name["search-first"].feature == "feature-parity"
    assert by_name["search-first"].enforcement == "best-effort-only"
    assert "fail open" in by_name["search-first"].notes


def test_codex_parity_audit_fails_when_matcher_missing(tmp_path):
    _write_codex_install(tmp_path, drop_strategy="search-first")
    rows, problems = audit_mod.audit(tmp_path)

    by_name = {row.strategy: row for row in rows}
    assert by_name["search-first"].enforcement == "unwired"
    assert any("search-first" in problem for problem in problems)
    assert "missing matcher" in by_name["search-first"].notes


def test_codex_parity_audit_json_output(tmp_path, capsys):
    _write_codex_install(tmp_path)
    rc = audit_mod.main(["--root", str(tmp_path), "--json"])
    out = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert out["problems"] == []
    assert any(row["strategy"] == "listing-guard" for row in out["rows"])

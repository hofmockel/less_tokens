"""Tests for agents/codex/hooks/agentsmd-budget.py and its install wiring."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO = Path(__file__).resolve().parent.parent.parent.parent
HOOK = REPO / "agents" / "codex" / "hooks" / "agentsmd-budget.py"

sys.path.insert(0, str(REPO))
from install import build_codex_hook_entries  # noqa: E402


# ---------------------------------------------------------------------------
# install wiring
# ---------------------------------------------------------------------------

def _codex_args(**kw) -> argparse.Namespace:
    defaults = {"truncate": False, "compact": False, "caveman": False}
    defaults.update(kw)
    return argparse.Namespace(**defaults)


class TestAgentsMdBudgetWiring:
    def test_agentsmd_budget_in_codex_entries(self, tmp_path):
        venv_py = tmp_path / ".venv" / "bin" / "python"
        entries = build_codex_hook_entries(venv_py, tmp_path, _codex_args())
        hooks = [(ev, m) for ev, m, cmd in entries if "agentsmd-budget.py" in cmd]
        assert hooks, "agentsmd-budget.py not in codex hook entries"
        assert hooks[0] == ("PostToolUse", "Edit|Write")

    def test_agentsmd_budget_always_present(self, tmp_path):
        venv_py = tmp_path / ".venv" / "bin" / "python"
        for caveman in (True, False):
            entries = build_codex_hook_entries(venv_py, tmp_path, _codex_args(caveman=caveman))
            assert any("agentsmd-budget.py" in cmd for _, _, cmd in entries)


# ---------------------------------------------------------------------------
# hook logic
# ---------------------------------------------------------------------------

def _load_hook():
    spec = importlib.util.spec_from_file_location("agentsmd_budget", HOOK)
    mod = importlib.util.module_from_spec(spec)
    return mod, spec


def _run_main(mod, spec, stdin_data: dict, agents_md: Path | None = None,
              budget: int = 1200, cma=None) -> int:
    spec.loader.exec_module(mod)
    mod.AGENTS_MD_TOKEN_BUDGET = budget
    mod.AGENTS_MD_OVERFLOW_DOC = "DOCUMENTATION.md"
    mod.cma = cma
    with patch.object(mod.sys, "stdin",
                      MagicMock(read=lambda: json.dumps(stdin_data))):
        import io
        mod.sys.stdin = io.StringIO(json.dumps(stdin_data))
        return mod.main()


class TestAgentsMdBudgetHook:
    def _payload(self, tool="Edit", file_path="AGENTS.md"):
        return {"tool_name": tool, "tool_input": {"file_path": file_path}}

    def test_noop_when_budget_zero(self, tmp_path):
        spec = importlib.util.spec_from_file_location("agentsmd_budget", HOOK)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.AGENTS_MD_TOKEN_BUDGET = 0
        assert mod.main.__code__ is not None  # module loads
        # With budget=0, main() returns 0 immediately
        import io
        mod.sys.stdin = io.StringIO(json.dumps(self._payload()))
        result = mod.main()
        assert result == 0

    def test_noop_when_cma_none(self, tmp_path):
        spec = importlib.util.spec_from_file_location("agentsmd_budget2", HOOK)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.cma = None
        import io
        mod.sys.stdin = io.StringIO(json.dumps(self._payload()))
        assert mod.main() == 0

    def test_noop_for_non_agentsmd_file(self, tmp_path):
        spec = importlib.util.spec_from_file_location("agentsmd_budget3", HOOK)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.AGENTS_MD_TOKEN_BUDGET = 1200
        fake_cma = MagicMock()
        mod.cma = fake_cma
        import io
        mod.sys.stdin = io.StringIO(json.dumps(self._payload(file_path="CLAUDE.md")))
        assert mod.main() == 0
        fake_cma.audit.assert_not_called()

    def test_noop_for_wrong_tool(self, tmp_path):
        spec = importlib.util.spec_from_file_location("agentsmd_budget4", HOOK)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.AGENTS_MD_TOKEN_BUDGET = 1200
        fake_cma = MagicMock()
        mod.cma = fake_cma
        import io
        mod.sys.stdin = io.StringIO(json.dumps(self._payload(tool="Bash")))
        assert mod.main() == 0
        fake_cma.audit.assert_not_called()

    def test_returns_2_when_over_budget(self, tmp_path):
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("# AGENTS.md\n" * 100)
        spec = importlib.util.spec_from_file_location("agentsmd_budget5", HOOK)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.AGENTS_MD_TOKEN_BUDGET = 1200
        mod.AGENTS_MD_OVERFLOW_DOC = "DOCUMENTATION.md"
        fake_cma = MagicMock()
        fake_cma.audit.return_value = {
            "over_budget": True, "total_tokens": 1500, "budget": 1200, "dead_refs": []
        }
        mod.cma = fake_cma
        import io
        mod.sys.stdin = io.StringIO(
            json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(agents_md)}})
        )
        assert mod.main() == 2

    def test_returns_0_when_under_budget(self, tmp_path):
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("# AGENTS.md\nshort\n")
        spec = importlib.util.spec_from_file_location("agentsmd_budget6", HOOK)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.AGENTS_MD_TOKEN_BUDGET = 1200
        mod.AGENTS_MD_OVERFLOW_DOC = "DOCUMENTATION.md"
        fake_cma = MagicMock()
        fake_cma.audit.return_value = {
            "over_budget": False, "total_tokens": 50, "budget": 1200, "dead_refs": []
        }
        mod.cma = fake_cma
        import io
        mod.sys.stdin = io.StringIO(
            json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(agents_md)}})
        )
        assert mod.main() == 0

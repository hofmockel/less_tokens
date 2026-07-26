"""WIN1: mechanical guard against the recurring "hardcoded POSIX assumption"
bug class — bare launcher paths and POSIX-only subprocess kwargs used with no
sys.platform/os.name check in scope.

Fixtures reconstruct two real historical bugs from CHANGELOG.md: PT9's
WinError 193 (lean-output.py's pre-fix `_python()`, which `.exists()`-checked
a bare `.less_tokens/bin/python`) and the pre-`_detach_kwargs` index-refresh.py
bug (`start_new_session=True` with no platform branch). Both must have failed
before their respective fixes and must not recur — this audit is what would
have caught them pre-merge.
"""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent.parent
TOOL = REPO / ".claude" / "tools" / "win_platform_audit.py"
spec = importlib.util.spec_from_file_location("win_platform_audit", TOOL)
audit_mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
sys.modules[spec.name] = audit_mod  # type: ignore[union-attr]
spec.loader.exec_module(audit_mod)  # type: ignore[union-attr]


def _violations(source: str, filename: str = "fixture.py") -> list[str]:
    tree = ast.parse(source, filename=filename)
    return audit_mod.check_bare_launcher_exists(tree, filename) + audit_mod.check_posix_only_subprocess_kwargs(
        tree, filename
    )


def test_flags_pt9_bare_launcher_winerror_193_shape():
    """Pins PT9 (CHANGELOG.md): pre-fix lean-output.py/listing-guard.py `_python()`."""
    source = """
import sys
from pathlib import Path

REPO = Path("/repo")

def _python() -> Path:
    p = REPO / ".less_tokens" / "bin" / "python"
    return p if p.exists() else Path(sys.executable)
"""
    violations = _violations(source)
    assert len(violations) == 1
    assert "_python" in violations[0]
    assert "fixture.py:9" in violations[0]


def test_flags_inline_bare_launcher_exists_without_intermediate_variable():
    source = """
from pathlib import Path

def _python(repo: Path) -> Path:
    return (repo / ".less_tokens" / "bin" / "python").exists()
"""
    assert len(_violations(source)) == 1


def test_does_not_flag_venv_python_style_fix_with_platform_branch():
    """The actual PT9 fix: a win32 comparison in scope clears the bare join."""
    source = """
import sys
from pathlib import Path

def venv_python(repo: Path) -> Path:
    launcher = repo / ".less_tokens" / "bin" / "python"
    if sys.platform == "win32":
        launcher = launcher.with_suffix(".cmd")
    return launcher if launcher.exists() else Path(sys.executable)
"""
    assert _violations(source) == []


def test_does_not_flag_launcher_rel_that_never_checks_existence():
    """install.py's launcher_rel() returns a bare relative name for a caller
    to suffix later — it never calls .exists(), so it's not the PT9 bug shape."""
    source = """
from pathlib import Path

def launcher_rel(agent: str) -> Path:
    if agent == "codex":
        return Path(".less_tokens") / "bin" / "python"
    return Path(".claude") / "bin" / "python"
"""
    assert _violations(source) == []


def test_flags_pre_detach_kwargs_start_new_session_shape():
    """Pins the pre-_detach_kwargs index-refresh.py bug (CHANGELOG.md):
    start_new_session=True is POSIX-only and silently ignored on Windows."""
    source = """
import subprocess

def refresh(venv_py, embeddings_py, repo, fh):
    subprocess.Popen(
        [str(venv_py), str(embeddings_py), "refresh"],
        cwd=repo,
        stdout=fh,
        start_new_session=True,
    )
"""
    violations = _violations(source)
    assert len(violations) == 1
    assert "start_new_session" in violations[0]
    assert "refresh" in violations[0]


def test_does_not_flag_detach_kwargs_style_fix_with_platform_branch():
    source = """
import subprocess

def _detach_kwargs(platform: str) -> dict:
    if platform == "win32":
        return {"creationflags": 8}
    return {"start_new_session": True}
"""
    assert _violations(source) == []


def test_current_repo_is_clean():
    """No unguarded instance of either pattern currently exists in the repo —
    both known cases (PT9, pre-_detach_kwargs) are already fixed."""
    assert audit_mod.audit(REPO) == []

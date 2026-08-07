"""Pre-commit config wires ruff so contributors get lint feedback before pushing.

Plain-text parse — avoids a PyYAML dependency for this single check.
"""

from __future__ import annotations

from tests.conftest import REPO_ROOT


def test_pre_commit_config_exists_and_uses_ruff():
    cfg = REPO_ROOT / ".pre-commit-config.yaml"
    assert cfg.exists(), "Add .pre-commit-config.yaml so contributors can install hooks"
    text = cfg.read_text()
    assert "ruff-pre-commit" in text
    assert "id: ruff" in text

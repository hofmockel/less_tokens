"""Shared fixtures for all test layers."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
FIXTURES = Path(__file__).parent / "fixtures" / "sample_project"

if "coverage" in sys.modules:
    os.environ.setdefault("COVERAGE_PROCESS_START", str(REPO_ROOT / ".coveragerc"))


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def sample_py() -> Path:
    return FIXTURES / "tools" / "sample.py"


@pytest.fixture(scope="session")
def sample_sql() -> Path:
    return FIXTURES / "schema" / "tables.sql"


@pytest.fixture(scope="session")
def sample_md() -> Path:
    return FIXTURES / "docs" / "guide.md"


@pytest.fixture(scope="session")
def sample_changelog() -> Path:
    return FIXTURES / "CHANGELOG.md"


def load_hook(hook_path: Path):
    """Load a hook module from its file path, ensuring tools/ is on sys.path first."""
    if str(REPO_ROOT / ".claude" / "tools") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / ".claude" / "tools"))
    module_name = hook_path.stem.replace("-", "_")
    spec = importlib.util.spec_from_file_location(module_name, hook_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

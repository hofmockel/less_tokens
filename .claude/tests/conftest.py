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


# The v2 budget-plane event log, plus near_misses.jsonl (session_size samples
# feeding the compaction-threshold decision — BACKLOG.md). Both are meant to be
# redirected via LESS_TOKENS_STATE_DIR by every hook test (a broken override
# once left events.jsonl 100% pytest artifacts, fixed in resolve_state_root() —
# see CHANGELOG.md; near_misses.jsonl had the same class of bug via two
# compact-trigger tests that isolated STATE_FILE but not active_state_dir(),
# fixed alongside this gate addition).
# savings.jsonl is deliberately excluded here: test_hooks_protocol.py
# intentionally runs real hooks (truncate-output.py etc.) against the real repo
# without isolation, same accepted pattern as its compact-trigger-last handling,
# and "always on" savings tracking means that's real, correctly
# recorded behavior, not a leak — flagging it here would be a false positive.
_WATCHED_TELEMETRY_LOGS = [
    REPO_ROOT / ".less_tokens" / "state" / "events.jsonl",
    REPO_ROOT / ".claude" / "state" / "near_misses.jsonl",
]


@pytest.fixture(scope="session", autouse=True)
def _no_production_telemetry_writes():
    """Regression net for the events.jsonl contamination bug: fail the run if
    any test writes a real line into production telemetry instead of isolating
    state via LESS_TOKENS_STATE_DIR. Deterministic byte-count diff, no fixtures,
    can't be fabricated or flaky."""
    def _sizes() -> dict[str, int]:
        return {
            str(p.relative_to(REPO_ROOT)): p.stat().st_size
            for p in _WATCHED_TELEMETRY_LOGS
            if p.exists()
        }

    before = _sizes()
    yield
    after = _sizes()

    grown = {path: (before.get(path, 0), size) for path, size in after.items() if size != before.get(path, 0)}
    if grown:
        details = "; ".join(f"{path} ({b} -> {a} bytes)" for path, (b, a) in grown.items())
        pytest.fail(
            "Production telemetry changed during the test run — a hook wrote "
            f"real events instead of honoring LESS_TOKENS_STATE_DIR: {details}"
        )

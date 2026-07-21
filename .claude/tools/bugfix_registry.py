#!/usr/bin/env python3
"""Canonical registry for the bugfix protocol's CODE-MODE defaults for this repo.

Single source of truth for less_tokens' own regression-test convention,
verification commands, and commit-message template — i.e. what fixing a bug in
*this* repo looks like once bugfix-protocol.md's mode detection (see
protocol_mode.py) lands on code mode. Consumed by:
- bugfix_docs.py (renders the code-mode section of agents/common/bugfix-protocol.md)

Severity vocabulary is intentionally NOT redefined here — bugfix consumes the same
tiers a bug was already assigned during bug-hunt, so `SEVERITY_TIERS` is imported
from `bug_hunt_registry` rather than duplicated (duplicating it would itself be the
exact "vocabulary drift" bug docs-mode exists to catch).

Docs mode has no equivalent registry, for the same reason `bug_hunt_registry.py`
doesn't have one: bugfix-protocol.md is delivered to other repos as a portable
skill, and there is no "this repo's lint/type/test command list" for a repo this
one has never seen. Docs-mode content in the protocol doc is hand-authored generic
prose instead. See bugfix_docs.py's module docstring for the render-time split.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

# Self-sufficient regardless of how this module is loaded (direct script run,
# `import bugfix_registry` after bug_hunt_docs.py already extended sys.path, or a
# test loading this file standalone via importlib) — always ensure this file's own
# directory is importable before pulling in its sibling registry.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bug_hunt_registry import SEVERITY_TIERS  # noqa: E402,F401  (re-exported for consumers)


@dataclass(frozen=True)
class VerificationCommand:
    label: str
    command: str


# Run in this order after the minimal fix and before changelog/backlog/commit.
# Keep in sync with CLAUDE.md's "Test commands" section and .pre-commit-config.yaml.
VERIFICATION_COMMANDS: tuple[VerificationCommand, ...] = (
    VerificationCommand(
        label="lint",
        command="ruff check .",
    ),
    VerificationCommand(
        label="format check",
        command="ruff format --check .",
    ),
    VerificationCommand(
        label="regression test",
        command=".claude/.venv-tokens/bin/python .claude/tools/dev.py single <nodeid>",
    ),
    VerificationCommand(
        label="full unit suite",
        command=".claude/.venv-tokens/bin/python .claude/tools/dev.py unit",
    ),
)

REGRESSION_TEST_DIR = ".claude/tests/unit/"
REGRESSION_TEST_NAMING = "test_bug<id>_<short_description>.py"

COMMIT_MESSAGE_TEMPLATE = """\
fix: <one-line summary>

<what was wrong, what changed, file:line>. Regression test: <test file>.

Co-Authored-By: <agent name> <noreply@anthropic.com>"""

ROUND_REQUIRED_KEYS_NOTE = (
    "Docs-mode targets without hunt_round.py can hand-check a fix record against "
    "the same required-key shape hunt_round.ROUND_REQUIRED_KEYS expects for a hunt "
    "round, adapted for a fix: bug id, date, file(s) touched, severity tier, "
    "verification commands run and their results."
)

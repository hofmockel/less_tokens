"""Contract checks for the bounded live Codex app-server compaction probe."""

from __future__ import annotations

import json
from pathlib import Path


REPO = Path(__file__).parent.parent.parent.parent
FIXTURE = (
    REPO
    / ".claude"
    / "tests"
    / "fixtures"
    / "codex-app-server"
    / "0.144.6"
    / "thread-compact-start.json"
)


def test_live_compaction_fixture_proves_control_and_measured_reduction():
    capture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert capture["method"] == "thread/compact/start"
    assert capture["response"] == {}
    assert capture["completion_item_type"] == "contextCompaction"
    assert capture["method_maturity"] == "experimental"
    assert capture["content_retained"] is False
    assert capture["working_directory_kind"] == "empty-temporary-directory"
    assert capture["measured_tokens_elided"] == (
        capture["context_tokens_before"] - capture["context_tokens_after"]
    )
    assert capture["measured_tokens_elided"] > 0


def test_rollout_bytes_are_not_a_compaction_savings_signal():
    capture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert capture["transcript_bytes_after"] > capture["transcript_bytes_before"]

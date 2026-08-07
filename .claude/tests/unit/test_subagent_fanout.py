"""SA2: PreToolUse+PostToolUse:Task hook pairs a spawned subagent's prompt
size with its return size into one subagent_fanout event per spawn."""

from __future__ import annotations

import io
import json
import sys

from tests.conftest import REPO_ROOT, load_hook

HOOK = REPO_ROOT / ".claude" / "hooks" / "subagent-fanout.py"


class TestSpawnKey:
    def test_stable_for_identical_input(self):
        mod = load_hook(HOOK)
        inp = {
            "subagent_type": "qa",
            "prompt": "check the diff",
            "description": "review",
        }
        assert mod.spawn_key(inp) == mod.spawn_key(dict(inp))

    def test_differs_for_different_input(self):
        mod = load_hook(HOOK)
        a = mod.spawn_key({"prompt": "one"})
        b = mod.spawn_key({"prompt": "two"})
        assert a != b


class TestPendingQueue:
    def test_pop_returns_none_when_empty(self):
        mod = load_hook(HOOK)
        state = {"pending": []}
        assert mod.pop_spawn(state, "missing-key") is None

    def test_record_then_pop_round_trips(self):
        mod = load_hook(HOOK)
        state = {"pending": []}
        mod.record_spawn(state, key="k1", subagent_type="qa", prompt_chars=42, ts=1.0)
        entry = mod.pop_spawn(state, "k1")
        assert entry == {
            "key": "k1",
            "subagent_type": "qa",
            "prompt_chars": 42,
            "ts": 1.0,
        }
        assert state["pending"] == []

    def test_pop_is_fifo_for_duplicate_keys(self):
        mod = load_hook(HOOK)
        state = {"pending": []}
        mod.record_spawn(state, key="k1", subagent_type="qa", prompt_chars=10, ts=1.0)
        mod.record_spawn(state, key="k1", subagent_type="qa", prompt_chars=20, ts=2.0)
        first = mod.pop_spawn(state, "k1")
        second = mod.pop_spawn(state, "k1")
        assert first["prompt_chars"] == 10
        assert second["prompt_chars"] == 20


class TestSubagentTypeOf:
    def test_extracts_declared_type(self):
        mod = load_hook(HOOK)
        assert mod.subagent_type_of({"subagent_type": "qa"}) == "qa"

    def test_falls_back_to_unknown(self):
        mod = load_hook(HOOK)
        assert mod.subagent_type_of({}) == "unknown"
        assert mod.subagent_type_of({"subagent_type": "  "}) == "unknown"


class TestHandlePrePost:
    def test_post_without_matching_pre_still_emits_a_record(self, tmp_path):
        mod = load_hook(HOOK)
        record = mod.handle_post_return(
            tmp_path,
            {"subagent_type": "tect"},
            500,
            session_id="s1",
            session_source="payload",
        )
        assert record == {
            "event": "subagent_fanout",
            "subagent_type": "tect",
            "prompt_chars": 0,
            "return_chars": 500,
            "session_id": "s1",
            "session_source": "payload",
        }

    def test_pre_then_post_pairs_prompt_and_return_size(self, tmp_path):
        mod = load_hook(HOOK)
        tool_input = {"subagent_type": "qa", "prompt": "check it"}
        mod.handle_pre_spawn(tmp_path, tool_input, now=1.0)
        record = mod.handle_post_return(
            tmp_path,
            tool_input,
            900,
            session_id="s1",
            session_source="payload",
        )
        assert record["prompt_chars"] == len(json.dumps(tool_input, default=str))
        assert record["return_chars"] == 900
        assert record["subagent_type"] == "qa"

    def test_two_concurrent_spawns_pair_in_fifo_order(self, tmp_path):
        mod = load_hook(HOOK)
        tool_input = {"subagent_type": "qa", "prompt": "same prompt"}
        mod.handle_pre_spawn(tmp_path, tool_input, now=1.0)
        mod.handle_pre_spawn(tmp_path, tool_input, now=2.0)
        first = mod.handle_post_return(
            tmp_path, tool_input, 100, session_id="s", session_source="payload"
        )
        second = mod.handle_post_return(
            tmp_path, tool_input, 200, session_id="s", session_source="payload"
        )
        assert first["return_chars"] == 100
        assert second["return_chars"] == 200


class TestSubagentFanoutHook:
    def test_pre_stashes_and_post_emits_one_event(self, tmp_path, monkeypatch):
        mod = load_hook(HOOK)
        monkeypatch.setattr(mod, "_active_state_dir", lambda: tmp_path)
        logged: list[dict] = []
        monkeypatch.setattr(mod, "_log_savings", logged.append)

        pre_payload = json.dumps(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Task",
                "tool_input": {"subagent_type": "qa", "prompt": "hello"},
            }
        )
        monkeypatch.setattr(sys, "stdin", io.StringIO(pre_payload))
        assert mod.main() == 0
        assert logged == []

        post_payload = json.dumps(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Task",
                "tool_input": {"subagent_type": "qa", "prompt": "hello"},
                "tool_result": "the subagent's final answer",
            }
        )
        monkeypatch.setattr(sys, "stdin", io.StringIO(post_payload))
        assert mod.main() == 0

        assert len(logged) == 1
        record = logged[0]
        assert record["event"] == "subagent_fanout"
        assert record["subagent_type"] == "qa"
        assert record["return_chars"] == len("the subagent's final answer")
        assert record["prompt_chars"] > 0

    def test_non_task_tool_ignored(self, tmp_path, monkeypatch):
        mod = load_hook(HOOK)
        monkeypatch.setattr(mod, "_active_state_dir", lambda: tmp_path)
        logged: list[dict] = []
        monkeypatch.setattr(mod, "_log_savings", logged.append)

        payload = json.dumps(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {},
                "tool_result": "x" * 500,
            }
        )
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        assert mod.main() == 0
        assert logged == []

    def test_never_prints_or_blocks(self, tmp_path, monkeypatch):
        mod = load_hook(HOOK)
        monkeypatch.setattr(mod, "_active_state_dir", lambda: tmp_path)
        monkeypatch.setattr(mod, "_log_savings", lambda _r: None)

        payload = json.dumps(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Task",
                "tool_input": {"subagent_type": "qa"},
                "tool_result": "short",
            }
        )
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        captured = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured)

        rc = mod.main()

        assert rc == 0
        assert captured.getvalue() == ""


class TestSubagentFanoutWiring:
    def test_hook_wired_as_pre_and_post_tooluse_task_in_settings_json(self):
        """PT6: without this, subagent-fanout.py can silently fall out of
        .claude/settings.json (as it did for PT1) with every unit test above
        still green, since they load the hook module directly rather than
        going through the live wiring."""
        settings = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text())

        def _wired(event: str) -> bool:
            return any(
                "subagent-fanout.py" in h.get("command", "")
                for block in settings["hooks"].get(event, [])
                if block.get("matcher") == "Task"
                for h in block.get("hooks", [])
            )

        assert _wired("PreToolUse"), (
            "subagent-fanout.py must be wired as a PreToolUse:Task hook in .claude/settings.json"
        )
        assert _wired("PostToolUse"), (
            "subagent-fanout.py must be wired as a PostToolUse:Task hook in .claude/settings.json"
        )

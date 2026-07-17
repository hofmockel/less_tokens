"""Unit tests for tools/toolcost.py and tools/mcp-prune.py."""
from __future__ import annotations

import json
import sys
from pathlib import Path


BASE = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(BASE / ".claude" / "tools"))

import toolcost
import importlib
mcp_prune = importlib.import_module("mcp-prune")


# ---------------------------------------------------------------------------
# toolcost: token estimation
# ---------------------------------------------------------------------------

class TestEstTokens:
    def test_empty_dict(self):
        assert toolcost.est_tokens({}) == 0  # len("{}") // 4 == 0

    def test_string(self):
        s = "x" * 40
        assert toolcost.est_tokens(s) == int(len(json.dumps(s)) / toolcost.CHARS_PER_TOKEN)

    def test_tool_schema(self):
        tool = {
            "name": "get_user",
            "description": "Retrieve a user record by ID",
            "inputSchema": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
            },
        }
        tok = toolcost.est_tokens(tool)
        assert tok > 0
        assert tok < 200  # sanity

    def test_server_tokens_empty(self):
        assert toolcost.server_tokens([]) == 0

    def test_server_tokens_additive(self):
        tools = [{"name": "a"}, {"name": "b"}, {"name": "c"}]
        total = toolcost.server_tokens(tools)
        assert total == sum(toolcost.est_tokens(t) for t in tools)


# ---------------------------------------------------------------------------
# toolcost: load_mcp_servers
# ---------------------------------------------------------------------------

class TestLoadMcpServers:
    def test_missing_file(self, tmp_path):
        result = toolcost.load_mcp_servers([tmp_path / "nope.json"])
        assert result == {}

    def test_single_file(self, tmp_path):
        cfg = tmp_path / "s.json"
        cfg.write_text(json.dumps({"mcpServers": {"foo": {"command": "npx"}}}))
        assert toolcost.load_mcp_servers([cfg]) == {"foo": {"command": "npx"}}

    def test_merge_later_wins(self, tmp_path):
        a = tmp_path / "a.json"
        b = tmp_path / "b.json"
        a.write_text(json.dumps({"mcpServers": {"foo": {"command": "old"}, "bar": {}}}))
        b.write_text(json.dumps({"mcpServers": {"foo": {"command": "new"}}}))
        result = toolcost.load_mcp_servers([a, b])
        assert result["foo"] == {"command": "new"}
        assert "bar" in result

    def test_no_mcp_servers_key(self, tmp_path):
        cfg = tmp_path / "s.json"
        cfg.write_text(json.dumps({"hooks": {}}))
        assert toolcost.load_mcp_servers([cfg]) == {}

    def test_malformed_json_skipped(self, tmp_path):
        cfg = tmp_path / "bad.json"
        cfg.write_text("{not valid json")
        assert toolcost.load_mcp_servers([cfg]) == {}


# ---------------------------------------------------------------------------
# toolcost: load_toolignore
# ---------------------------------------------------------------------------

class TestLoadToolignore:
    def test_no_file(self, tmp_path):
        assert toolcost.load_toolignore(tmp_path) == set()

    def test_claude_toolignore(self, tmp_path):
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / ".toolignore").write_text("slack\ngithub\n")
        assert toolcost.load_toolignore(tmp_path) == {"slack", "github"}

    def test_root_toolignore(self, tmp_path):
        (tmp_path / ".toolignore").write_text("notion\n")
        assert toolcost.load_toolignore(tmp_path) == {"notion"}

    def test_comments_ignored(self, tmp_path):
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / ".toolignore").write_text(
            "# this is a comment\nslack\n  # indented comment\nlinear\n"
        )
        result = toolcost.load_toolignore(tmp_path)
        assert result == {"slack", "linear"}

    def test_blank_lines_ignored(self, tmp_path):
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / ".toolignore").write_text("\n\nfoo\n\n")
        assert toolcost.load_toolignore(tmp_path) == {"foo"}

    def test_both_files_merged(self, tmp_path):
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / ".toolignore").write_text("a\n")
        (tmp_path / ".toolignore").write_text("b\n")
        result = toolcost.load_toolignore(tmp_path)
        assert result == {"a", "b"}


# ---------------------------------------------------------------------------
# toolcost: render_table
# ---------------------------------------------------------------------------

class TestRenderTable:
    def _rows(self):
        return [
            {"name": "slack", "tokens": 3000, "tool_count": 20, "probed": True},
            {"name": "github", "tokens": 1500, "tool_count": 10, "probed": True},
            {"name": "small", "tokens": 200, "tool_count": 3, "probed": True},
        ]

    def test_contains_server_names(self):
        rows = self._rows()
        out = toolcost.render_table(rows, set(), 4700, True)
        assert "slack" in out
        assert "github" in out
        assert "small" in out

    def test_heavy_star(self):
        rows = self._rows()
        out = toolcost.render_table(rows, set(), 4700, True)
        assert "★" in out

    def test_ignored_tag(self):
        rows = self._rows()
        out = toolcost.render_table(rows, {"slack"}, 4700, True)
        assert "[ignored]" in out

    def test_no_probe_note(self):
        rows = self._rows()
        out = toolcost.render_table(rows, set(), 4700, False)
        assert "no-probe" in out or "estimate" in out.lower()

    def test_total_line(self):
        rows = self._rows()
        out = toolcost.render_table(rows, set(), 4700, True)
        assert "TOTAL" in out


# ---------------------------------------------------------------------------
# mcp-prune: load_toolignore (same logic, test via module)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# toolcost: _recv skips server notifications
# ---------------------------------------------------------------------------

class TestRecv:
    def _make_proc(self, lines: list[bytes]):
        """Return a mock Popen whose stdout yields the given lines."""
        import io
        from unittest.mock import MagicMock
        proc = MagicMock()
        proc.stdout = io.BytesIO(b"".join(line + b"\n" for line in lines))
        return proc

    def test_skips_notification_before_response(self):
        """_recv must skip JSON-RPC notifications and return the real response."""
        notification = json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/message",
            "params": {"level": "info", "data": "server ready"},
        }).encode()
        response = json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "result": {"tools": [{"name": "my_tool"}]},
        }).encode()

        proc = self._make_proc([notification, response])
        result = toolcost._recv(proc, timeout=5.0)
        assert result is not None
        assert result.get("id") == 2
        assert "result" in result

    def test_single_response_no_notification(self):
        """_recv returns normal response when no notification precedes it."""
        response = json.dumps({
            "jsonrpc": "2.0", "id": 1,
            "result": {"protocolVersion": "2024-11-05", "capabilities": {}},
        }).encode()
        proc = self._make_proc([response])
        result = toolcost._recv(proc, timeout=5.0)
        assert result is not None
        assert result.get("id") == 1


class TestPruneLoadIgnore:
    def test_basic(self, tmp_path):
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / ".toolignore").write_text("svc\n")
        assert mcp_prune.load_toolignore(tmp_path) == {"svc"}


# ---------------------------------------------------------------------------
# mcp-prune: prune()
# ---------------------------------------------------------------------------

class TestPrune:
    def _settings(self, tmp_path, servers: dict) -> Path:
        p = tmp_path / "settings.json"
        p.write_text(json.dumps({"mcpServers": servers}))
        return p

    def test_removes_ignored(self, tmp_path):
        p = self._settings(tmp_path, {"slack": {"command": "npx"}, "keep": {}})
        pruned, removed = mcp_prune.prune(p, {"slack"})
        assert "slack" not in pruned["mcpServers"]
        assert "keep" in pruned["mcpServers"]
        assert removed == ["slack"]

    def test_no_overlap(self, tmp_path):
        p = self._settings(tmp_path, {"foo": {}, "bar": {}})
        _, removed = mcp_prune.prune(p, {"baz"})
        assert removed == []

    def test_empty_ignored(self, tmp_path):
        p = self._settings(tmp_path, {"foo": {}})
        _, removed = mcp_prune.prune(p, set())
        assert removed == []

    def test_all_removed(self, tmp_path):
        p = self._settings(tmp_path, {"a": {}, "b": {}})
        pruned, removed = mcp_prune.prune(p, {"a", "b"})
        assert pruned["mcpServers"] == {}
        assert set(removed) == {"a", "b"}

    def test_non_mcp_keys_preserved(self, tmp_path):
        p = tmp_path / "s.json"
        p.write_text(json.dumps({"hooks": {"PreToolUse": []}, "mcpServers": {"x": {}}}))
        pruned, _ = mcp_prune.prune(p, {"x"})
        assert "hooks" in pruned
        assert pruned["hooks"] == {"PreToolUse": []}

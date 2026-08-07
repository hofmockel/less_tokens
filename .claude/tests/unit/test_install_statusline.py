"""Tests for Phase 5 statusline wiring in install.py (merge-safe)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from install import statusline_command, unwire_settings, wire_statusline


def _read(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def test_statusline_command_runs_oneliner(tmp_path):
    cmd = statusline_command(tmp_path)
    assert "stats.py --oneliner" in cmd


def test_wire_statusline_sets_when_absent(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"hooks": {}}), encoding="utf-8")
    changed = wire_statusline(settings, "PY stats.py --oneliner")
    assert changed == 1
    sl = _read(settings)["statusLine"]
    assert sl["type"] == "command"
    assert sl["command"] == "PY stats.py --oneliner"


def test_wire_statusline_idempotent(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({}), encoding="utf-8")
    wire_statusline(settings, "PY stats.py --oneliner")
    changed = wire_statusline(settings, "PY stats.py --oneliner")
    assert changed == 0


def test_wire_statusline_never_clobbers_host(tmp_path):
    settings = tmp_path / "settings.json"
    host = {"statusLine": {"type": "command", "command": "my-own-statusline"}}
    settings.write_text(json.dumps(host), encoding="utf-8")
    changed = wire_statusline(settings, "PY stats.py --oneliner")
    assert changed == 0
    assert _read(settings)["statusLine"]["command"] == "my-own-statusline"


def test_unwire_removes_our_statusline_only(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps(
            {
                "statusLine": {
                    "type": "command",
                    "command": "x .claude/tools/stats.py --oneliner",
                }
            }
        ),
        encoding="utf-8",
    )
    unwire_settings(settings, Path(__file__).parent.parent.parent.parent, dry_run=False)
    assert "statusLine" not in _read(settings)


def test_unwire_keeps_host_statusline(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps({"statusLine": {"type": "command", "command": "host-line"}}),
        encoding="utf-8",
    )
    unwire_settings(settings, Path(__file__).parent.parent.parent.parent, dry_run=False)
    assert _read(settings)["statusLine"]["command"] == "host-line"

#!/usr/bin/env python3
"""Estimate the per-session token tax of configured MCP servers.

Every MCP server's tool schemas are injected into context on every turn —
a fixed cost paid regardless of task. This audit makes that invisible tax
visible and surfaces .toolignore candidates.

Usage:
  python .claude/tools/toolcost.py             # probe all configured servers
  python .claude/tools/toolcost.py --no-probe  # list servers without probing
  python .claude/tools/toolcost.py --json      # machine-readable output
  python .claude/tools/toolcost.py --timeout 5 # shorter probe timeout

Settings searched (merged in order, later wins):
  ~/.claude.json                global Claude Code settings
  .claude/settings.json         project-level settings
  .claude/settings.local.json   local overrides

Ignore file: .claude/.toolignore (one server name per line, # = comment)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CHARS_PER_TOKEN: int = 4  # rough estimate; overridden by search_config.py
_PROBE_TIMEOUT: float = 8.0  # seconds per server probe
HEAVY_THRESHOLD: int = 1000  # tokens — flag as heavy above this

_BASE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_BASE / ".claude" / "tools"))

try:
    from search_config import CHARS_PER_TOKEN  # type: ignore[assignment]  # noqa: F811
except Exception:
    pass

_DEFAULT_SETTINGS_PATHS: list[Path] = [
    Path.home() / ".claude.json",
    _BASE / ".claude" / "settings.json",
    _BASE / ".claude" / "settings.local.json",
]

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def load_mcp_servers(paths: list[Path]) -> dict[str, Any]:
    """Merge mcpServers from all settings files (later files win)."""
    merged: dict[str, Any] = {}
    for p in paths:
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        servers = data.get("mcpServers", {})
        if isinstance(servers, dict):
            merged.update(servers)
    return merged


def load_toolignore(base: Path) -> set[str]:
    """Return server names listed in .claude/.toolignore or .toolignore."""
    candidates = [base / ".claude" / ".toolignore", base / ".toolignore"]
    ignored: set[str] = set()
    for p in candidates:
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                ignored.add(line)
    return ignored


# ---------------------------------------------------------------------------
# MCP probe (JSON-RPC over stdio)
# ---------------------------------------------------------------------------


def _send(proc: subprocess.Popen, msg: dict) -> None:  # type: ignore[type-arg]
    assert proc.stdin is not None
    proc.stdin.write((json.dumps(msg) + "\n").encode())
    proc.stdin.flush()


def _recv(proc: subprocess.Popen, timeout: float) -> dict | None:  # type: ignore[type-arg]
    result: list[dict] = []  # type: ignore[type-arg]
    exc: list[Exception] = []

    def _read() -> None:
        try:
            assert proc.stdout is not None
            while True:
                line = proc.stdout.readline()
                if not line:
                    return
                msg = json.loads(line.decode(errors="replace"))
                if "id" in msg:  # skip notifications (no id field)
                    result.append(msg)
                    return
        except Exception as e:
            exc.append(e)

    t = threading.Thread(target=_read, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive() or exc:
        return None
    return result[0] if result else None


def probe_server(name: str, config: dict, timeout: float) -> list[dict] | None:  # type: ignore[type-arg]
    """Start MCP server, list tools, return tool defs or None on failure."""
    cmd = config.get("command")
    if not cmd:
        return None  # SSE/HTTP server — skip

    args_list: list[str] = [str(cmd)] + [str(a) for a in config.get("args", [])]
    env = {**os.environ, **{k: str(v) for k, v in config.get("env", {}).items()}}

    try:
        proc = subprocess.Popen(
            args_list,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
        )
    except Exception:
        return None

    try:
        _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "toolcost", "version": "1.0"},
                },
            },
        )
        init_resp = _recv(proc, timeout)
        if init_resp is None or "error" in (init_resp or {}):
            return None

        _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        _send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tools_resp = _recv(proc, timeout)
        if tools_resp is None:
            return None
        return tools_resp.get("result", {}).get("tools", [])
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------


def est_tokens(obj: Any) -> int:
    return int(len(json.dumps(obj)) / max(1, CHARS_PER_TOKEN))


def server_tokens(tools: list[dict]) -> int:  # type: ignore[type-arg]
    return sum(est_tokens(t) for t in tools)


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def _bar(frac: float, width: int = 20) -> str:
    filled = round(frac * width)
    return "█" * filled + "░" * (width - filled)


def render_table(
    rows: list[dict], ignored: set[str], total: int, any_probed: bool
) -> str:  # type: ignore[type-arg]
    lines: list[str] = []
    lines.append(f"\n{'server':<32} {'tools':>6}  {'tokens':>10}  {'share':>6}  bar")
    lines.append("-" * 76)

    for r in sorted(rows, key=lambda x: (-x["tokens"], x["name"])):
        tag = (
            " [ignored]"
            if r["name"] in ignored
            else (" ★" if r["tokens"] >= HEAVY_THRESHOLD else "")
        )
        frac = r["tokens"] / max(1, total)
        bar = _bar(frac)
        tc = str(r["tool_count"]) if r["tool_count"] >= 0 else "?"
        share = f"{frac * 100:.1f}%"
        lines.append(
            f"{r['name']:<32} {tc:>6}  {r['tokens']:>10,}  {share:>6}  {bar}{tag}"
        )

    lines.append("-" * 76)
    active_tok = sum(r["tokens"] for r in rows if r["name"] not in ignored)
    ignored_tok = sum(r["tokens"] for r in rows if r["name"] in ignored)
    lines.append(f"{'TOTAL (active)':<32} {'':>6}  {active_tok:>10,}")
    if ignored:
        lines.append(
            f"{'  .toolignore savings':<32} {'':>6}  {ignored_tok:>10,}  ← excluded"
        )

    lines.append(f"\n  Fixed cost per turn: ~{active_tok:,} tokens")
    if not any_probed:
        lines.append("  (estimates only — run without --no-probe for exact counts)")

    heavy = [
        r for r in rows if r["tokens"] >= HEAVY_THRESHOLD and r["name"] not in ignored
    ]
    if heavy:
        lines.append(
            f"\n  ★ Heavy (≥{HEAVY_THRESHOLD:,} tok) — candidates for .claude/.toolignore:"
        )
        for r in sorted(heavy, key=lambda x: -x["tokens"]):
            lines.append(f"    {r['name']}")
    elif not any_probed:
        lines.append("\n  Run without --no-probe to identify heavy servers.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit MCP server token cost")
    ap.add_argument(
        "--no-probe",
        action="store_true",
        help="Don't start servers; estimate from config size only",
    )
    ap.add_argument("--json", action="store_true", help="JSON output")
    ap.add_argument(
        "--settings",
        metavar="PATH",
        action="append",
        default=[],
        help="Settings file(s) to read (overrides defaults)",
    )
    ap.add_argument(
        "--timeout",
        type=float,
        default=_PROBE_TIMEOUT,
        help=f"Probe timeout per server in seconds (default {_PROBE_TIMEOUT})",
    )
    args = ap.parse_args()

    timeout = args.timeout
    settings_paths = (
        [Path(p) for p in args.settings] if args.settings else _DEFAULT_SETTINGS_PATHS
    )
    servers = load_mcp_servers(settings_paths)
    ignored = load_toolignore(_BASE)

    if not servers:
        print(
            "No mcpServers found in:",
            ", ".join(str(p) for p in settings_paths),
            file=sys.stderr,
        )
        return 1

    rows: list[dict] = []  # type: ignore[type-arg]
    any_probed = False

    for name, config in servers.items():
        tokens = 0
        tool_count = -1
        probed = False
        error: str | None = None

        if not args.no_probe:
            tools = probe_server(name, config, timeout)
            if tools is not None:
                tokens = server_tokens(tools)
                tool_count = len(tools)
                probed = True
                any_probed = True
            else:
                tokens = est_tokens(config) * 3
                error = "probe failed"
        else:
            tokens = est_tokens(config) * 3

        rows.append(
            {
                "name": name,
                "tokens": tokens,
                "tool_count": tool_count,
                "probed": probed,
                "ignored": name in ignored,
                "config_type": "command" if "command" in config else "url",
                "error": error,
            }
        )

    total = sum(r["tokens"] for r in rows)

    if args.json:
        print(
            json.dumps(
                {
                    "servers": rows,
                    "total_tokens": total,
                    "active_tokens": sum(r["tokens"] for r in rows if not r["ignored"]),
                    "ignored": sorted(ignored),
                },
                indent=2,
            )
        )
        return 0

    print(render_table(rows, ignored, total, any_probed))
    return 0


if __name__ == "__main__":
    sys.exit(main())

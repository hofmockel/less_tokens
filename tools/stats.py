#!/usr/bin/env python3
"""Token savings tracker — enable, report, and disable.

Usage:
  python tools/stats.py              # show session stats; prompt to enable if off
  python tools/stats.py --report     # write savings-report.md and print path
  python tools/stats.py --all        # show all-time totals
  python tools/stats.py --disable    # turn tracking off
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "tools"))

CONFIG_FILE = BASE / "tools" / "search_config.py"

try:
    from search_config import STATE_DIR, TRACK_SAVINGS
except Exception:
    TRACK_SAVINGS = False
    STATE_DIR = BASE / ".claude" / "state"

LOG_FILE = STATE_DIR / "savings.jsonl"
REPORT_FILE = STATE_DIR / "savings-report.md"
CHARS_PER_TOKEN = 4
SESSION_HOURS = 8

_STRATEGY_LABELS = {
    "truncation":     "Truncation",
    "search-blocked": "Search-first block",
    "search":         "Search (vs full file)",
    "compaction":     "Compaction nudges",
}


def _set_tracking(enabled: bool) -> None:
    src = CONFIG_FILE.read_text(encoding="utf-8")
    old = f"TRACK_SAVINGS = {not enabled}"
    new = f"TRACK_SAVINGS = {enabled}"
    if old not in src:
        print(f"Could not find '{old}' in {CONFIG_FILE}", file=sys.stderr)
        return
    CONFIG_FILE.write_text(src.replace(old, new, 1), encoding="utf-8")


def _load_records(all_time: bool = False) -> list[dict]:
    if not LOG_FILE.exists():
        return []
    cutoff = 0.0 if all_time else time.time() - SESSION_HOURS * 3600
    out = []
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("ts", 0) >= cutoff:
            out.append(r)
    return out


def _summarize(records: list[dict]) -> dict:
    data = {k: {"events": 0, "saved_chars": 0} for k in _STRATEGY_LABELS}
    for r in records:
        s = r.get("strategy", "")
        if s in data:
            data[s]["events"] += 1
            data[s]["saved_chars"] += r.get("saved_chars", 0)
    return data


def _build_table_lines(heading: str, records: list[dict]) -> list[str]:
    data = _summarize(records)
    total_chars = total_tokens = 0
    body_rows = []
    for key, lbl in _STRATEGY_LABELS.items():
        d = data[key]
        sc = d["saved_chars"]
        tok = sc // CHARS_PER_TOKEN if sc else 0
        total_chars += sc
        total_tokens += tok
        sc_str = f"{sc:,}" if sc else "—"
        tok_str = f"{tok:,}" if tok else "—"
        body_rows.append(
            f"| {lbl:<22} | {d['events']:>6} | {sc_str:>12} | {tok_str:>14} |"
        )
    sep = f"|{'-'*24}|{'-'*8}|{'-'*14}|{'-'*16}|"
    return [
        f"## {heading}",
        "",
        f"| {'Strategy':<22} | {'Events':>6} | {'Chars saved':>12} | {'~Tokens saved':>14} |",
        sep,
        *body_rows,
        sep,
        f"| {'**Total**':<22} | {'':>6} | **{total_chars:,}** | **{total_tokens:,}** |",
    ]


def _write_report(session_records: list[dict], all_records: list[dict]) -> Path:
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    session_label = f"Session (last {SESSION_HOURS}h · {len(session_records)} events)"
    all_label = f"All-time ({len(all_records)} events)"
    lines = [
        "# Token Savings Report",
        f"Generated: {now}",
        "",
        *_build_table_lines(session_label, session_records),
        "",
        *_build_table_lines(all_label, all_records),
        "",
        f"_~{CHARS_PER_TOKEN} chars per token (estimate)_",
        "",
    ]
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")
    return REPORT_FILE


def main() -> int:
    ap = argparse.ArgumentParser(description="Token savings tracker")
    ap.add_argument("--enable", action="store_true", help="Turn tracking on (non-interactive)")
    ap.add_argument("--report", action="store_true", help="Write savings-report.md")
    ap.add_argument("--disable", action="store_true", help="Turn tracking off")
    ap.add_argument("--all", dest="all_time", action="store_true",
                    help="Show all-time totals instead of session")
    args = ap.parse_args()

    if args.enable:
        _set_tracking(True)
        print(f"Token tracking enabled. Savings logged to {LOG_FILE}")
        return 0

    if args.disable:
        _set_tracking(False)
        print("Token tracking disabled.")
        return 0

    if not TRACK_SAVINGS:
        print("Token tracking is disabled.")
        try:
            answer = input("Enable? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if answer == "y":
            _set_tracking(True)
            print(f"Token tracking enabled. Savings logged to {LOG_FILE}")
        return 0

    session_records = _load_records(all_time=False)
    all_records = _load_records(all_time=True)

    if args.report:
        path = _write_report(session_records, all_records)
        print(f"Report written to {path}\n")

    label = (
        f"All-time ({len(all_records)} events)"
        if args.all_time
        else f"Session (last {SESSION_HOURS}h · {len(session_records)} events)"
    )
    display = all_records if args.all_time else session_records
    print("\n".join(_build_table_lines(label, display)))
    print(f"\n_~{CHARS_PER_TOKEN} chars per token (estimate)_")
    return 0


if __name__ == "__main__":
    sys.exit(main())

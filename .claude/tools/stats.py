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
import re
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent
CLAUDE_DIR = BASE / ".claude"
sys.path.insert(0, str(Path(__file__).resolve().parent))

CONFIG_FILE = CLAUDE_DIR / "tools" / "search_config.py"

try:
    from search_config import STATE_DIR, TRACK_SAVINGS
except Exception:
    TRACK_SAVINGS = False
    STATE_DIR = CLAUDE_DIR / "state"

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
    # Matches TRACK_SAVINGS = True, TRACK_SAVINGS: bool = False,
    # TRACK_SAVINGS: bool | None = False, etc.
    pattern = r"^(TRACK_SAVINGS(?:\s*:[^=]+)?\s*=\s*)(?:True|False)"
    replacement = rf"\g<1>{enabled}"
    new_src = re.sub(pattern, replacement, src, count=1, flags=re.MULTILINE)
    if new_src == src:
        print(f"Could not find 'TRACK_SAVINGS' in {CONFIG_FILE}", file=sys.stderr)
        return
    CONFIG_FILE.write_text(new_src, encoding="utf-8")


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
        except Exception as e:
            print(f"  WARN: skipping malformed record in {LOG_FILE}: {e}", file=sys.stderr)
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
    total_chars = 0
    body_rows = []
    for key, lbl in _STRATEGY_LABELS.items():
        d = data[key]
        sc = d["saved_chars"]
        total_chars += sc
        sc_str = f"{sc:,}" if sc else "—"
        tok = sc // CHARS_PER_TOKEN if sc else 0
        tok_str = f"{tok:,}" if tok else "—"
        body_rows.append(
            f"| {lbl:<22} | {d['events']:>6} | {sc_str:>12} | {tok_str:>14} |"
        )
    total_tokens = total_chars // CHARS_PER_TOKEN
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


def _methodology_lines() -> list[str]:
    """Prose explaining how each number is derived and how trustworthy it is."""
    return [
        "## How these numbers are measured",
        "",
        "Each strategy estimates `saved_chars` differently, so they are not equally "
        "real. From most grounded to most speculative:",
        "",
        "- **Truncation** — `truncate-output.py` caps oversized tool output to a "
        "head+tail slice. Saved = `original_chars − kept_chars`. This is **actual**: "
        "those bytes were removed before the output ever reached the model.",
        "- **Search-first block** — `search-first.py` blocks a Read of a large file and "
        "redirects you to search. Saved = the file's full byte size. This is a "
        "**counterfactual upper bound**: it assumes you would otherwise have read the "
        "*entire* file, and it does not subtract the cost of the search you run instead.",
        "- **Search (vs full file)** — `search.py` returns ranked chunks. Saved = "
        "`sum(full size of every matched file) − returned chunk chars`. Also a "
        "**counterfactual upper bound**: it credits the full size of all matched files "
        "as if you would have read every one of them whole.",
        "- **Compaction nudges** — placeholder. Nothing emits this event yet, so the "
        "row is always `—`.",
        "",
        "Caveats: tokens are estimated as chars ÷ "
        f"{CHARS_PER_TOKEN} (rough). \"Session\" means events in the last "
        f"{SESSION_HOURS}h of wall-clock time, not a true session boundary. File sizes "
        "use byte counts, which equal char counts only for ASCII. Net of these, "
        "**Truncation is a real saving; the search rows are optimistic estimates** — "
        "useful as a directional signal, not an exact ledger.",
        "",
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
        "Counts tokens *not* sent to the model because a hook or tool intervened. "
        "Tracking is opt-in (`TRACK_SAVINGS`); each event appends one line to "
        "`state/savings.jsonl`, and this report sums them. Read the numbers with the "
        "methodology below — the four strategies are *not* equally grounded.",
        "",
        *_build_table_lines(session_label, session_records),
        "",
        *_build_table_lines(all_label, all_records),
        "",
        f"_~{CHARS_PER_TOKEN} chars per token (estimate)_",
        "",
        *_methodology_lines(),
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

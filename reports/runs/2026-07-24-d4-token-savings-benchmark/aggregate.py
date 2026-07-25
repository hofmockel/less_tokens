#!/usr/bin/env python3
"""D4 benchmark aggregator — reproducible summary over a frozen savings.jsonl snapshot.

Usage:
  python3 aggregate.py savings_less_tokens.jsonl --chars-per-token 2.4927
  python3 aggregate.py savings_ever_better.jsonl --chars-per-token 4

Reads a frozen savings.jsonl fixture (never the live, still-growing state file)
and computes, per strategy: event count, kept/elided chars (exact, as logged),
an estimated tokens-saved figure (elided_chars / chars_per_token — an estimate,
labeled as such), and cross-session variance (mean/stdev of per-session saved
chars, for strategies observed in >=2 sessions). Deterministic: same input file
always produces byte-identical output, which is what makes this reproducible —
unlike querying the live (still-growing) state file directly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

# Canonical strategy labels/basis, kept in sync with savings_log.py's registry
# by hand (this script intentionally has zero runtime dependency on the
# installed tool so it keeps working even against a future schema change to
# the live tool, as a fixed record of what D4 measured).
KNOWN_STRATEGIES = {
    "truncation": ("Truncation", "measured"),
    "compaction": ("Compaction", "measured"),
    "context-cache-read": ("Cached read (repeat)", "measured"),
    "context-cache-grep": ("Cached grep (repeat)", "measured"),
    "context-cache-bash": ("Cached bash (repeat)", "measured"),
    "search-blocked": ("Search-first block", "upper_bound"),
    "search": ("Search (vs full file)", "upper_bound"),
    "subagent-cap": ("Subagent return cap", "measured"),
}

# Strategies seen in real logs that are not savings events at all (hook
# connectivity smoke-test pings) — excluded, not silently folded into totals.
NON_SAVINGS_STRATEGIES = {"test"}


def load_events(path: Path) -> list[dict]:
    events = []
    for i, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as e:
            print(f"{path}:{i}: skipping malformed line ({e})", file=sys.stderr)
    return events


def aggregate(events: list[dict], chars_per_token: float) -> dict:
    by_strategy: dict[str, list[dict]] = {}
    unknown: dict[str, int] = {}
    skipped_non_savings = 0
    for e in events:
        strat = e.get("strategy")
        if strat in NON_SAVINGS_STRATEGIES:
            skipped_non_savings += 1
            continue
        if strat not in KNOWN_STRATEGIES:
            unknown[strat] = unknown.get(strat, 0) + 1
            continue
        by_strategy.setdefault(strat, []).append(e)

    sessions_overall = {e.get("session_id") for e in events if e.get("strategy") not in NON_SAVINGS_STRATEGIES}

    strategies_out = {}
    total_kept = 0
    total_elided = 0
    for strat, evs in sorted(by_strategy.items()):
        label, basis = KNOWN_STRATEGIES[strat]
        kept = sum(int(e.get("kept_chars") or 0) for e in evs)
        elided = sum(int(e.get("elided_chars") or 0) for e in evs)
        total_kept += kept
        total_elided += elided

        per_session: dict[str, int] = {}
        for e in evs:
            sid = e.get("session_id", "unknown")
            per_session[sid] = per_session.get(sid, 0) + int(e.get("elided_chars") or 0)
        session_totals = list(per_session.values())
        variance = None
        if len(session_totals) >= 2:
            variance = {
                "n_sessions": len(session_totals),
                "mean_elided_chars_per_session": round(statistics.mean(session_totals), 1),
                "stdev_elided_chars_per_session": round(statistics.stdev(session_totals), 1),
                "min_elided_chars_per_session": min(session_totals),
                "max_elided_chars_per_session": max(session_totals),
            }

        strategies_out[strat] = {
            "label": label,
            "basis": basis,
            "events": len(evs),
            "kept_chars": kept,
            "elided_chars": elided,
            "tokens_saved_estimate": round(elided / chars_per_token) if chars_per_token else None,
            "cross_session_variance": variance,
        }

    timestamps = [e.get("ts") for e in events if e.get("ts") is not None]
    return {
        "chars_per_token_used": chars_per_token,
        "total_events_in_file": len(events),
        "events_skipped_non_savings": skipped_non_savings,
        "events_unknown_strategy": unknown,
        "distinct_sessions": len(sessions_overall),
        "ts_min": min(timestamps) if timestamps else None,
        "ts_max": max(timestamps) if timestamps else None,
        "strategies": strategies_out,
        "totals": {
            "kept_chars": total_kept,
            "elided_chars": total_elided,
            "tokens_saved_estimate": round(total_elided / chars_per_token) if chars_per_token else None,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl_path", type=Path)
    ap.add_argument("--chars-per-token", type=float, default=4.0,
                     help="chars-per-token divisor for the token estimate (default 4; pass a calibrated value if available)")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    events = load_events(args.jsonl_path)
    result = aggregate(events, args.chars_per_token)
    result["source_file"] = args.jsonl_path.name
    result["source_sha256"] = hashlib.sha256(args.jsonl_path.read_bytes()).hexdigest()

    out_text = json.dumps(result, indent=2, sort_keys=False)
    if args.out:
        args.out.write_text(out_text + "\n")
    print(out_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

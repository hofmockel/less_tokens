#!/usr/bin/env python3
"""Token savings tracker — always-on, local-only report.

Usage:
  python tools/stats.py              # show current-session stats
  python tools/stats.py --report     # write savings-report.md and print path
  python tools/stats.py --html       # write savings.html (self-contained page)
  python tools/stats.py --all        # show all-time totals
"""
from __future__ import annotations

import argparse
import html as _html
import json
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent
CLAUDE_DIR = BASE / ".claude"
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from search_config import STATE_DIR
except Exception:
    STATE_DIR = CLAUDE_DIR / "state"

LOG_FILE = STATE_DIR / "savings.jsonl"
REPORT_FILE = STATE_DIR / "savings-report.md"
HTML_FILE = STATE_DIR / "savings.html"
CHARS_PER_TOKEN = 4
SESSION_HOURS = 8

# Honest token footer. Tokens are never stored; they are a report-time estimate.
# Stays "uncalibrated" until Phase 6 `--calibrate` grounds the divisor in Claude's
# real tokenizer.
TOKEN_FOOTER = f"_tokens est. at chars÷{CHARS_PER_TOKEN} (uncalibrated)_"

_STRATEGY_LABELS = {
    "truncation":     "Truncation",
    "search-blocked": "Search-first block",
    "search":         "Search (vs full file)",
    "compaction":     "Compaction",
}

# Measured vs upper-bound is the report's central honesty axis. Measured rows were
# actually removed before reaching the model; upper-bound rows are counterfactual
# avoided cost. The two are rendered in separate panels and never cross-summed.
_MEASURED_STRATEGIES = ("truncation", "compaction")
_UPPER_BOUND_STRATEGIES = ("search-blocked", "search")


def _normalize_record(r: dict) -> dict:
    """Map any record — new-schema or legacy — to the canonical shape.

    New records carry ``basis``/``kept_chars``/``elided_chars``. Legacy records
    (pre-Phase-1) only have ``saved_chars``: treat the saved amount as elided,
    infer ``basis`` from the strategy (truncation is measured, everything else is
    an upper bound), tag ``content_kind="legacy"``, and fold the old ``glob-cap``
    strategy into ``truncation``. The file is never rewritten — the reader is
    tolerant. ``saved_chars`` is kept as an alias of ``elided_chars`` so existing
    summing keeps working until the Phase 3 report split.
    """
    r = dict(r)
    if r.get("strategy") == "glob-cap":
        r["strategy"] = "truncation"
    if "basis" not in r:
        elided = r.get("elided_chars", r.get("saved_chars", 0))
        r["elided_chars"] = elided
        r.setdefault("kept_chars", 0)
        r["basis"] = "measured" if r.get("strategy") == "truncation" else "upper_bound"
        r["content_kind"] = "legacy"
    r["saved_chars"] = r.get("elided_chars", r.get("saved_chars", 0))
    return r


def _load_all() -> list[dict]:
    """Every normalized record in the log, oldest first. Malformed lines skipped."""
    if not LOG_FILE.exists():
        return []
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
        out.append(_normalize_record(r))
    return out


def _current_session_id(records: list[dict]) -> str | None:
    """The session_id of the most recent *real* session, or None if there is none.

    A real session is one resolved from a payload/transcript/env source — not the
    ``local`` last-resort bucket and not a legacy record (which carries no
    ``session_id`` at all). When none exists we fall back to the wall-clock window.
    """
    real = [
        r for r in records
        if r.get("session_id") and r.get("session_source") not in (None, "local")
    ]
    if not real:
        return None
    return max(real, key=lambda r: r.get("ts", 0)).get("session_id")


def _session_subset(records: list[dict], session_id: str | None) -> list[dict]:
    """Records for the current (or given) session_id.

    With a real session_id, group by it. Without one (only legacy/local records),
    fall back to the old ``SESSION_HOURS`` wall-clock window — kept strictly as a
    legacy view, never the primary grouping.
    """
    if session_id is None:
        session_id = _current_session_id(records)
    if session_id is not None:
        return [r for r in records if r.get("session_id") == session_id]
    cutoff = time.time() - SESSION_HOURS * 3600
    return [r for r in records if r.get("ts", 0) >= cutoff]


def _load_records(all_time: bool = False, session_id: str | None = None) -> list[dict]:
    records = _load_all()
    if all_time:
        return records
    return _session_subset(records, session_id)


def _summarize(records: list[dict]) -> dict:
    data = {k: {"events": 0, "saved_chars": 0} for k in _STRATEGY_LABELS}
    for r in records:
        s = r.get("strategy", "")
        if s in data:
            data[s]["events"] += 1
            data[s]["saved_chars"] += r.get("elided_chars", r.get("saved_chars", 0))
    return data


def _panel_lines(title: str, records: list[dict], strategies: tuple[str, ...],
                 *, prefix: str = "") -> list[str]:
    """One basis-homogeneous table: only ``strategies``, with its own total.

    ``prefix`` (e.g. "≤") marks upper-bound magnitudes as optimistic. The total
    sums only this panel's strategies — measured and upper-bound are never mixed.
    """
    data = _summarize(records)
    total_chars = 0
    body_rows = []
    for key in strategies:
        lbl = _STRATEGY_LABELS[key]
        d = data[key]
        sc = d["saved_chars"]
        total_chars += sc
        sc_str = f"{prefix}{sc:,}" if sc else "—"
        tok = sc // CHARS_PER_TOKEN if sc else 0
        tok_str = f"{prefix}{tok:,}" if tok else "—"
        body_rows.append(
            f"| {lbl:<22} | {d['events']:>6} | {sc_str:>12} | {tok_str:>14} |"
        )
    total_tokens = total_chars // CHARS_PER_TOKEN
    sep = f"|{'-'*24}|{'-'*8}|{'-'*14}|{'-'*16}|"
    return [
        f"### {title}",
        "",
        f"| {'Strategy':<22} | {'Events':>6} | {'Chars saved':>12} | {'~Tokens saved':>14} |",
        sep,
        *body_rows,
        sep,
        f"| {'**Total**':<22} | {'':>6} | **{prefix}{total_chars:,}** | **{prefix}{total_tokens:,}** |",
    ]


def _build_table_lines(heading: str, records: list[dict]) -> list[str]:
    """Render a session/all-time block as two separate panels.

    Measured (truncation, compaction) and upper-bound (search) live in their own
    tables with their own totals so the report never cross-sums real removals with
    counterfactual avoided cost.
    """
    return [
        f"## {heading}",
        "",
        *_panel_lines(
            "Measured — removed before reaching the model",
            records, _MEASURED_STRATEGIES,
        ),
        "",
        *_panel_lines(
            "Upper bound — avoided cost, optimistic (≤)",
            records, _UPPER_BOUND_STRATEGIES, prefix="≤",
        ),
        "",
        "_Upper-bound rows assume you would otherwise have read the whole file and "
        "do not subtract the search you ran instead. Do not add them to the measured "
        "total._",
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
        "- **Compaction** — `compact-trigger.py` watches the transcript and, when "
        "Claude Code compacts it, logs `kept_chars` = the post-compaction transcript "
        "(the produced summary) and `elided_chars` = peak − kept. **Actual** on both "
        "sides — two real transcript char counts. Only fires on a genuine shrink, so "
        "the row stays `—` until a compaction actually happens.",
        "- **Search-first block** — `search-first.py` blocks a Read of a large file and "
        "redirects you to search. Saved = the file's full byte size. This is a "
        "**counterfactual upper bound**: it assumes you would otherwise have read the "
        "*entire* file, and it does not subtract the cost of the search you run instead.",
        "- **Search (vs full file)** — `search.py` returns ranked chunks. Saved = "
        "`sum(full size of every matched file) − returned chunk chars`. Also a "
        "**counterfactual upper bound**: it credits the full size of all matched files "
        "as if you would have read every one of them whole.",
        "",
        "Caveats: tokens are an estimate, not a count — chars ÷ "
        f"{CHARS_PER_TOKEN}, uncalibrated against Claude's tokenizer (run "
        "`stats.py --calibrate` to ground the divisor). \"Session\" groups by the "
        "resolved `session_id`; only when no real session is known does it fall back "
        f"to the last {SESSION_HOURS}h of wall-clock time (a legacy view). File sizes "
        "use byte counts, which equal char counts only for ASCII. Net of these, "
        "**truncation and compaction are real savings; the search rows are optimistic "
        "estimates** — useful as a directional signal, not an exact ledger.",
        "",
    ]


def _session_label(records: list[dict]) -> str:
    sid = _current_session_id(records)
    if sid:
        return f"Current session ({sid} · {len(records)} events)"
    return f"Session (last {SESSION_HOURS}h, legacy view · {len(records)} events)"


def _write_report(session_records: list[dict], all_records: list[dict]) -> Path:
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    session_label = _session_label(session_records)
    all_label = f"All-time ({len(all_records)} events)"
    lines = [
        "# Token Savings Report",
        f"Generated: {now}",
        "",
        "Counts tokens *not* sent to the model because a hook or tool intervened. "
        "Tracking is always on and **local-only**: each event appends one line to "
        "`state/savings.jsonl` (never transmitted), and this report sums them. "
        "Disable with `LESS_TOKENS_NO_STATS=1`. Measured and upper-bound savings are "
        "shown in **separate panels** and never added together — read the methodology "
        "below; the four strategies are *not* equally grounded.",
        "",
        *_build_table_lines(session_label, session_records),
        "",
        *_build_table_lines(all_label, all_records),
        "",
        TOKEN_FOOTER,
        "",
        *_methodology_lines(),
    ]
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")
    return REPORT_FILE


# ---------------------------------------------------------------------------
# HTML renderer — self-contained page (Phase 4)
#
# The HTML mirrors the Markdown report's honesty axis: measured and upper-bound
# panels stay separate, each with its own total, never cross-summed. The page is
# fully self-contained — inline CSS only, no external links, scripts, fonts, or
# images — so it opens straight from `file://` and the Stop hook can regenerate
# it after every turn without a network round-trip.
# ---------------------------------------------------------------------------

_HTML_STYLE = """
:root { color-scheme: light dark; }
body { font-family: -apple-system, system-ui, sans-serif; margin: 2rem auto;
  max-width: 52rem; padding: 0 1rem; line-height: 1.5; }
h1 { margin-bottom: .25rem; }
.gen { color: #888; font-size: .85rem; margin-top: 0; }
.intro { background: rgba(127,127,127,.08); border-radius: 8px; padding: .75rem 1rem; }
h2 { margin-top: 2rem; border-bottom: 1px solid rgba(127,127,127,.3); padding-bottom: .25rem; }
table { border-collapse: collapse; width: 100%; margin: .5rem 0 1rem; }
th, td { padding: .35rem .6rem; text-align: right; border-bottom: 1px solid rgba(127,127,127,.2); }
th:first-child, td:first-child { text-align: left; }
tbody tr:last-child { font-weight: 600; border-top: 2px solid rgba(127,127,127,.4); }
.measured h3 { color: #1a7f37; }
.upper h3 { color: #9a6700; }
.note, .footer { color: #888; font-size: .85rem; }
caption { display: none; }
""".strip()


def _html_panel(title: str, records: list[dict], strategies: tuple[str, ...],
                *, prefix: str = "") -> str:
    """One basis-homogeneous HTML table. Mirrors :func:`_panel_lines`."""
    data = _summarize(records)
    total_chars = 0
    rows = []
    for key in strategies:
        d = data[key]
        sc = d["saved_chars"]
        total_chars += sc
        sc_str = f"{prefix}{sc:,}" if sc else "—"
        tok = sc // CHARS_PER_TOKEN if sc else 0
        tok_str = f"{prefix}{tok:,}" if tok else "—"
        rows.append(
            f"<tr><td>{_html.escape(_STRATEGY_LABELS[key])}</td>"
            f"<td>{d['events']:,}</td><td>{sc_str}</td><td>{tok_str}</td></tr>"
        )
    total_tokens = total_chars // CHARS_PER_TOKEN
    rows.append(
        f"<tr><td>Total</td><td></td>"
        f"<td>{prefix}{total_chars:,}</td><td>{prefix}{total_tokens:,}</td></tr>"
    )
    return (
        f"<h3>{_html.escape(title)}</h3>\n"
        "<table><thead><tr><th>Strategy</th><th>Events</th>"
        "<th>Chars saved</th><th>~Tokens saved</th></tr></thead>\n"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _html_block(heading: str, records: list[dict]) -> str:
    """A session/all-time section: measured panel + upper-bound panel."""
    return (
        f"<h2>{_html.escape(heading)}</h2>\n"
        '<div class="measured">'
        + _html_panel("Measured — removed before reaching the model",
                      records, _MEASURED_STRATEGIES)
        + "</div>\n"
        '<div class="upper">'
        + _html_panel("Upper bound — avoided cost, optimistic (≤)",
                      records, _UPPER_BOUND_STRATEGIES, prefix="≤")
        + "</div>\n"
        '<p class="note">Upper-bound rows assume you would otherwise have read the '
        "whole file and do not subtract the search you ran instead. They are not "
        "added to the measured total.</p>"
    )


def _render_html(session_records: list[dict], all_records: list[dict]) -> str:
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    session_label = _session_label(session_records)
    all_label = f"All-time ({len(all_records)} events)"
    return (
        "<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>Token Savings Report</title>\n"
        f"<style>{_HTML_STYLE}</style>\n</head>\n<body>\n"
        "<h1>Token Savings Report</h1>\n"
        f"<p class=\"gen\">Generated: {_html.escape(now)}</p>\n"
        "<p class=\"intro\">Counts tokens <em>not</em> sent to the model because a hook "
        "or tool intervened. Tracking is always on and <strong>local-only</strong>: each "
        "event appends one line to <code>state/savings.jsonl</code> (never transmitted). "
        "Disable with <code>LESS_TOKENS_NO_STATS=1</code>. Measured and upper-bound "
        "savings are shown in separate panels and never added together.</p>\n"
        f"{_html_block(session_label, session_records)}\n"
        f"{_html_block(all_label, all_records)}\n"
        f"<p class=\"footer\">{_html.escape(TOKEN_FOOTER.strip('_'))}</p>\n"
        "</body></html>\n"
    )


def _write_html_report(session_records: list[dict], all_records: list[dict]) -> Path:
    HTML_FILE.parent.mkdir(parents=True, exist_ok=True)
    HTML_FILE.write_text(_render_html(session_records, all_records), encoding="utf-8")
    return HTML_FILE


# --- Phase 5 surfacing: glanceable one-liner + clickable link ---------------
#
# Both surfaces (Claude Stop-hook transcript line, Claude Code statusline) read
# the same log and report measured strategies only — upper-bound counterfactuals
# are never folded into the headline number, to stay honest.

def _fmt_tokens(tok: int) -> str:
    if tok >= 10_000:
        return f"{tok / 1000:.0f}k"
    if tok >= 1_000:
        return f"{tok / 1000:.1f}k"
    return str(tok)


def _measured_saved_chars(records: list[dict]) -> int:
    data = _summarize(records)
    return sum(data[k]["saved_chars"] for k in _MEASURED_STRATEGIES)


def _measured_oneliner(records: list[dict], *, scope: str = "session") -> str:
    """Measured-only savings headline, e.g. ``↓ ~122k tok saved (measured) · session``."""
    tok = _measured_saved_chars(records) // CHARS_PER_TOKEN
    return f"↓ ~{_fmt_tokens(tok)} tok saved (measured) · {scope}"


def _savings_link() -> str:
    """``file://`` URL to the generated HTML page, for click-through."""
    return HTML_FILE.resolve().as_uri()


def main() -> int:
    ap = argparse.ArgumentParser(description="Token savings tracker (always on, local-only)")
    ap.add_argument("--report", action="store_true", help="Write savings-report.md")
    ap.add_argument("--html", action="store_true", help="Write savings.html")
    ap.add_argument("--oneliner", action="store_true",
                    help="Print one measured savings line (for statusline) and exit")
    ap.add_argument("--all", dest="all_time", action="store_true",
                    help="Show all-time totals instead of session")
    args = ap.parse_args()

    if args.oneliner:
        print(_measured_oneliner(_load_records(all_time=False)))
        return 0

    session_records = _load_records(all_time=False)
    all_records = _load_records(all_time=True)

    if args.report:
        path = _write_report(session_records, all_records)
        print(f"Report written to {path}\n")

    if args.html:
        path = _write_html_report(session_records, all_records)
        print(f"HTML written to {path}\n")

    label = (
        f"All-time ({len(all_records)} events)"
        if args.all_time
        else _session_label(session_records)
    )
    display = all_records if args.all_time else session_records
    print("\n".join(_build_table_lines(label, display)))
    print(f"\n{TOKEN_FOOTER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

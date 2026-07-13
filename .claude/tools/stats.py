#!/usr/bin/env python3
"""Token savings tracker — always-on, local-only report.

Usage:
  python tools/stats.py              # show current-session stats
  python tools/stats.py --report     # write savings-report.md and print path
  python tools/stats.py --html       # write savings.html (self-contained page)
  python tools/stats.py --all        # show all-time totals
  python tools/stats.py --calibrate  # ground the token divisor in Claude's tokenizer
"""
from __future__ import annotations

import argparse
import html as _html
import json
import os
import re
import subprocess
import sys
import time
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent
CLAUDE_DIR = BASE / ".claude"
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from search_config import CHARS_PER_TOKEN, active_state_dir
    STATE_DIR = active_state_dir()
except Exception:
    STATE_DIR = CLAUDE_DIR / "state"
    CHARS_PER_TOKEN = 4

LOG_FILE = STATE_DIR / "savings.jsonl"
REPORT_FILE = STATE_DIR / "savings-report.md"
HTML_FILE = STATE_DIR / "savings.html"
CALIBRATION_FILE = STATE_DIR / "calibration.json"
SESSION_HOURS = 8

# Claude model `--calibrate` counts tokens against. Opus is the project default;
# override with `--model`.
CALIBRATION_MODEL = "claude-opus-4-8"


def _cpt_str() -> str:
    """Render the divisor compactly — '4', not '4.0'; '3.72' once calibrated."""
    return f"{CHARS_PER_TOKEN:g}"


def _to_tokens(chars: int) -> int:
    """Chars → estimated tokens. Float-safe so a calibrated divisor works."""
    if not chars:
        return 0
    return int(chars / CHARS_PER_TOKEN)


def _load_calibration() -> dict | None:
    """Calibration metadata (date, basis, sample counts), or None if uncalibrated.

    Written by ``--calibrate``. Tolerant: a missing or malformed file reads as
    uncalibrated, never an error.
    """
    try:
        return json.loads(CALIBRATION_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _calibration_label(cal: dict) -> str:
    """Human badge tail: ``calibrated <date>``, or ``repo-sample calibrated <date>``
    when the sample didn't include real tool output."""
    date = cal.get("calibrated_at", "?")
    basis = cal.get("basis", "full")
    return f"calibrated {date}" if basis == "full" else f"{basis} calibrated {date}"


def _token_footer() -> str:
    """Honest token footer reflecting calibration state.

    Tokens are never stored; they are a report-time estimate at chars÷divisor.
    Until ``--calibrate`` grounds the divisor in Claude's real tokenizer the
    footer reads ``(uncalibrated)``; afterwards it names the date and sample basis.
    """
    cal = _load_calibration()
    state = _calibration_label(cal) if cal else "uncalibrated"
    return f"_tokens est. at chars÷{_cpt_str()} ({state})_"


def _calibration_badge() -> str:
    """Glanceable HTML-header badge: ``chars÷4 uncalibrated`` vs
    ``chars÷3.72 calibrated <date>``."""
    cal = _load_calibration()
    state = _calibration_label(cal) if cal else "uncalibrated"
    return f"chars÷{_cpt_str()} {state}"


# Module-level snapshot for callers/tests that read the constant directly.
TOKEN_FOOTER = _token_footer()

# Label map and measured/upper-bound partition are *derived* from savings_log's
# _KNOWN_STRATEGIES — the single canonical registry every emitter writes against
# (see savings_log.py). Do not hand-add a key here; add it to _KNOWN_STRATEGIES
# and it flows through automatically. This is what keeps emit and consume from
# drifting apart again (see CHANGELOG: context-cache-read/-grep were once silently
# dropped here after being added to the emitter but not to this map).
try:
    from savings_log import _KNOWN_STRATEGIES
except Exception:
    # Legacy fallback so stats.py still works if savings_log can't be imported
    # (e.g. isolated test import order). Mirrors the registry as of this write.
    _KNOWN_STRATEGIES = {
        "truncation":          ("Truncation", "measured"),
        "compaction":          ("Compaction", "measured"),
        "context-cache-read":  ("Cached read (repeat)", "measured"),
        "context-cache-grep":  ("Cached grep (repeat)", "measured"),
        "context-cache-bash":  ("Cached bash (repeat)", "measured"),
        "search-blocked":      ("Search-first block", "upper_bound"),
        "search":              ("Search (vs full file)", "upper_bound"),
    }

_STRATEGY_LABELS = {k: v[0] for k, v in _KNOWN_STRATEGIES.items()}

# Measured vs upper-bound is the report's central honesty axis. Measured rows were
# actually removed before reaching the model; upper-bound rows are counterfactual
# avoided cost. The two are rendered in separate panels and never cross-summed.
_MEASURED_STRATEGIES = tuple(k for k, v in _KNOWN_STRATEGIES.items() if v[1] == "measured")
_UPPER_BOUND_STRATEGIES = tuple(k for k, v in _KNOWN_STRATEGIES.items() if v[1] == "upper_bound")

# Expected firing frequency per strategy — a human judgment recorded once per
# strategy, not inferred at runtime. This is what lets --audit-liveness tell a
# structurally-dead strategy (frequent, but never fires — e.g. cached-bash's
# exact-string cache key) from one that's rare by design (compaction fires once
# in months, and that's fine).
#   "frequent"      — should show real events regularly; zero over the window is
#                      worth investigating (the gate/cache key may be too narrow).
#   "rare-but-real" — expected to go long stretches with no events; flag only
#                      as informational, never as a problem.
#   "experimental"  — newly added, no expectation recorded yet.
_FREQUENCY_CLASS: dict[str, str] = {
    "truncation":          "frequent",
    "compaction":          "rare-but-real",
    "context-cache-read":  "frequent",
    "context-cache-grep":  "frequent",
    "context-cache-bash":  "frequent",
    "search-blocked":      "frequent",
    "search":              "frequent",
}

DEFAULT_LIVENESS_WINDOW_DAYS = 90


def audit_liveness(records: list[dict], *, now: float | None = None, window_days: int = DEFAULT_LIVENESS_WINDOW_DAYS) -> list[dict]:
    """Per-strategy liveness classification against real telemetry.

    Returns one row per _KNOWN_STRATEGIES entry: whether it has fired within
    `window_days`, how long since its last event (or never), and a verdict.
    Pure function over `records` — callers pass real `_load_all()` output for
    a real audit, or a hand-built fixture in tests (see stats_plan.md: tests
    cover classification logic, never assert a real savings magnitude).
    """
    now = time.time() if now is None else now
    last_ts: dict[str, float] = {}
    for r in records:
        strategy = r.get("strategy", "")
        if strategy not in _KNOWN_STRATEGIES:
            continue
        ts = r.get("ts", 0) or 0
        if ts > last_ts.get(strategy, float("-inf")):
            last_ts[strategy] = ts

    rows = []
    for strategy, (label, _basis) in _KNOWN_STRATEGIES.items():
        freq_class = _FREQUENCY_CLASS.get(strategy, "experimental")
        ts = last_ts.get(strategy)
        days_since = None if ts is None else (now - ts) / 86400
        if ts is None:
            verdict = "dead lever, investigate the gate" if freq_class == "frequent" else "no events yet, informational"
        elif freq_class == "frequent" and days_since > window_days:
            verdict = "dead lever, investigate the gate"
        else:
            verdict = "rare by design, informational" if freq_class != "frequent" else "live"
        rows.append({
            "strategy": strategy,
            "label": label,
            "frequency_class": freq_class,
            "days_since_last_event": days_since,
            "verdict": verdict,
        })
    return rows


def _run_audit_liveness(window_days: int = DEFAULT_LIVENESS_WINDOW_DAYS) -> int:
    rows = audit_liveness(_load_all(), window_days=window_days)
    print(f"## Strategy liveness audit (window: {window_days}d)\n")
    print(f"{'Strategy':<24} {'Class':<14} {'Last event':<16} Verdict")
    for row in rows:
        days = row["days_since_last_event"]
        last = "never" if days is None else f"{days:.1f}d ago"
        print(f"{row['label']:<24} {row['frequency_class']:<14} {last:<16} {row['verdict']}")
    return 0


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
        r["basis"] = "measured" if r.get("strategy") in _MEASURED_STRATEGIES else "upper_bound"
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
        tok = _to_tokens(sc)
        tok_str = f"{prefix}{tok:,}" if tok else "—"
        body_rows.append(
            f"| {lbl:<22} | {d['events']:>6} | {sc_str:>12} | {tok_str:>14} |"
        )
    total_tokens = _to_tokens(total_chars)
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
    cal = _load_calibration()
    cal_phrase = (
        f"{_calibration_label(cal)} against Claude's tokenizer"
        if cal
        else "uncalibrated against Claude's tokenizer (run `stats.py --calibrate` "
        "to ground the divisor)"
    )
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
        (
            "- **Cached read (repeat block)** — `context-cache.py` blocks a Read of a file "
            "already in context. Saved = the chars that would have re-entered (full file "
            "size for a whole-file read, or just the line slice for a partial read); "
            "`kept_chars` = 0 because nothing new entered. **Actual**: the agent issued the "
            "duplicate Read with known args and those bytes were prevented from re-entering "
            "context."
        ),
        (
            "- **Cached grep (repeat block)** — `context-cache.py` blocks a repeat Grep "
            "within the TTL window. Logged with `saved_chars = 0` (the grep never ran, so "
            "its output size is unknown); the row counts events only, never magnitude."
        ),
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
        f"{_cpt_str()}, {cal_phrase}. \"Session\" groups by the "
        "resolved `session_id`; only when no real session is known does it fall back "
        f"to the last {SESSION_HOURS}h of wall-clock time (a legacy view). File sizes "
        "use byte counts, which equal char counts only for ASCII. Net of these, "
        "**truncation, compaction, and cached repeat-reads are real savings; the search "
        "rows are optimistic estimates** — useful as a directional signal, not an exact ledger.",
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
        _token_footer(),
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
.badge { font-size: .8rem; border: 1px solid rgba(127,127,127,.4); border-radius: 6px;
  padding: .05rem .4rem; color: #888; }
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
        tok = _to_tokens(sc)
        tok_str = f"{prefix}{tok:,}" if tok else "—"
        rows.append(
            f"<tr><td>{_html.escape(_STRATEGY_LABELS[key])}</td>"
            f"<td>{d['events']:,}</td><td>{sc_str}</td><td>{tok_str}</td></tr>"
        )
    total_tokens = _to_tokens(total_chars)
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
        f"<p class=\"gen\">Generated: {_html.escape(now)} · "
        f"<span class=\"badge\">{_html.escape(_calibration_badge())}</span></p>\n"
        "<p class=\"intro\">Counts tokens <em>not</em> sent to the model because a hook "
        "or tool intervened. Tracking is always on and <strong>local-only</strong>: each "
        "event appends one line to <code>state/savings.jsonl</code> (never transmitted). "
        "Disable with <code>LESS_TOKENS_NO_STATS=1</code>. Measured and upper-bound "
        "savings are shown in separate panels and never added together.</p>\n"
        f"{_html_block(session_label, session_records)}\n"
        f"{_html_block(all_label, all_records)}\n"
        f"<p class=\"footer\">{_html.escape(_token_footer().strip('_'))}</p>\n"
        "</body></html>\n"
    )


def _write_html_report(session_records: list[dict], all_records: list[dict]) -> Path:
    HTML_FILE.parent.mkdir(parents=True, exist_ok=True)
    HTML_FILE.write_text(_render_html(session_records, all_records), encoding="utf-8")
    return HTML_FILE


def _active_agent_name() -> str:
    agent = os.environ.get("LESS_TOKENS_AGENT", "").strip().lower()
    return agent if agent in {"claude", "codex"} else "claude"


def _fmt_mtime(path: Path) -> str:
    if not path.exists():
        return "missing"
    return time.strftime("%Y-%m-%d %H:%M:%S %z", time.localtime(path.stat().st_mtime))


def _scan_log_file() -> dict:
    """Cheap raw-log scan for doctor output, separate from report normalization."""
    info = {"exists": LOG_FILE.exists(), "events": 0, "malformed": 0, "newest_ts": None}
    if not LOG_FILE.exists():
        return info
    for line in LOG_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except Exception:
            info["malformed"] += 1
            continue
        info["events"] += 1
        ts = record.get("ts")
        if isinstance(ts, (int, float)):
            newest = info["newest_ts"]
            info["newest_ts"] = ts if newest is None else max(newest, ts)
    return info


def _fmt_log_ts(ts: object) -> str:
    if not isinstance(ts, (int, float)):
        return "none"
    return time.strftime("%Y-%m-%d %H:%M:%S %z", time.localtime(ts))


def _basis_totals(records: list[dict]) -> tuple[int, int]:
    data = _summarize(records)
    measured = sum(data[k]["saved_chars"] for k in _MEASURED_STRATEGIES)
    upper = sum(data[k]["saved_chars"] for k in _UPPER_BOUND_STRATEGIES)
    return measured, upper


def _html_hook_path(agent: str) -> Path:
    if agent == "codex":
        return BASE / "agents" / "codex" / "hooks" / "savings-html.py"
    return BASE / ".claude" / "hooks" / "savings-html.py"


def _run_html_hook_check(cwd: Path, agent: str) -> dict:
    hook = _html_hook_path(agent)
    env = dict(os.environ)
    env.setdefault("LESS_TOKENS_REPO", str(BASE))
    env["LESS_TOKENS_AGENT"] = agent
    before_mtime = HTML_FILE.stat().st_mtime_ns if HTML_FILE.exists() else None
    try:
        proc = subprocess.run(
            [sys.executable, str(hook)],
            input="{}\n",
            text=True,
            capture_output=True,
            cwd=str(cwd),
            env=env,
            timeout=10,
            check=False,
        )
    except Exception as e:
        return {"ok": False, "returncode": "error", "stdout": "", "stderr": str(e)}
    after_mtime = HTML_FILE.stat().st_mtime_ns if HTML_FILE.exists() else None
    refreshed = after_mtime is not None and after_mtime != before_mtime
    return {
        "ok": proc.returncode == 0 and refreshed,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def _hook_result_line(label: str, result: dict) -> str:
    status = "ok" if result["ok"] else f"failed rc={result['returncode']}"
    detail = ""
    if result.get("stderr"):
        detail = f" stderr={result['stderr'][:160]!r}"
    elif result.get("stdout"):
        detail = f" stdout={result['stdout'][:160]!r}"
    return f"hook regeneration ({label}): {status}{detail}"


def _doctor_html_lines() -> list[str]:
    agent = _active_agent_name()
    log_info = _scan_log_file()
    session_records = _load_records(all_time=False)
    all_records = _load_records(all_time=True)
    session_measured, session_upper = _basis_totals(session_records)
    all_measured, all_upper = _basis_totals(all_records)

    lines = [
        "Savings HTML doctor",
        f"agent: {agent}",
        f"state dir: {STATE_DIR}",
        f"log path: {LOG_FILE}",
        f"log exists: {log_info['exists']}",
        f"log events: {log_info['events']}",
        f"log malformed lines: {log_info['malformed']}",
        f"newest log ts: {_fmt_log_ts(log_info['newest_ts'])}",
        f"html path: {HTML_FILE}",
        f"html mtime: {_fmt_mtime(HTML_FILE)}",
        f"session records: {len(session_records)}",
        f"all-time records: {len(all_records)}",
        f"session measured chars: {session_measured:,}",
        f"session upper-bound chars: {session_upper:,}",
        f"all-time measured chars: {all_measured:,}",
        f"all-time upper-bound chars: {all_upper:,}",
    ]

    root_result = _run_html_hook_check(BASE, agent)
    lines.append(_hook_result_line("repo root", root_result))
    with tempfile.TemporaryDirectory(prefix=".doctor-html-", dir=BASE) as tmp:
        nested = Path(tmp) / "nested"
        nested.mkdir()
        nested_result = _run_html_hook_check(nested, agent)
    lines.append(_hook_result_line("nested cwd", nested_result))
    lines.append(f"html mtime after hook: {_fmt_mtime(HTML_FILE)}")
    return lines


def _run_doctor_html() -> int:
    print("\n".join(_doctor_html_lines()))
    return 0


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
    tok = _to_tokens(_measured_saved_chars(records))
    return f"↓ ~{_fmt_tokens(tok)} tok saved (measured) · {scope}"


def _savings_link() -> str:
    """``file://`` URL to the generated HTML page, for click-through."""
    return HTML_FILE.resolve().as_uri()


# --- Phase 6: opt-in calibration against Claude's real tokenizer ------------
#
# `--calibrate` samples representative repo content (code + prose, plus any
# captured tool outputs when a store exists), counts its tokens against the real
# model via Anthropic's count_tokens endpoint, and computes the true
# chars-per-token for OUR content against Claude. It writes the divisor to
# search_config.CHARS_PER_TOKEN (with a dated comment) and a calibration.json
# sidecar the report/HTML badge read. Network + API-key gated; never automatic.
# Stored chars are unchanged — only the report-time estimate is re-grounded.

_CALIBRATION_MAX_FILES = 24
_CALIBRATION_MAX_FILE_CHARS = 20_000


def _chars_per_token(total_chars: int, total_tokens: int) -> float:
    """The calibration identity: chars ÷ tokens. Guards divide-by-zero."""
    if total_tokens <= 0:
        raise ValueError("token count must be positive")
    return total_chars / total_tokens


def _gather_calibration_samples() -> tuple[list[str], dict]:
    """Representative real content for calibration, bounded for cost.

    Repo prose (root ``*.md``) and code (``.claude/tools/*.py``) always; recent
    captured tool outputs when a capture store exists (none today). Returns
    ``(texts, counts)`` — counts records how many of each kind contributed, so
    the report can label the basis ``repo-sample`` when no real tool output was
    available.
    """
    texts: list[str] = []
    counts = {"prose": 0, "code": 0, "tool_outputs": 0}
    candidates = sorted(BASE.glob("*.md")) + sorted((CLAUDE_DIR / "tools").glob("*.py"))
    for p in candidates:
        if len(texts) >= _CALIBRATION_MAX_FILES:
            break
        try:
            t = p.read_text(encoding="utf-8")[:_CALIBRATION_MAX_FILE_CHARS]
        except Exception:
            continue
        if not t.strip():
            continue
        texts.append(t)
        counts["code" if p.suffix == ".py" else "prose"] += 1
    return texts, counts


def _count_tokens_via_api(texts: list[str], model: str) -> int:
    """Total Claude tokens for ``texts`` via Anthropic's count_tokens endpoint.

    Local import so the SDK is never on the hot path. Raises ImportError when the
    SDK is absent and the SDK's own errors on auth/network failure — the caller
    turns these into a clear, actionable message.
    """
    import anthropic  # opt-in, network path only

    client = anthropic.Anthropic()
    total = 0
    for t in texts:
        resp = client.messages.count_tokens(
            model=model, messages=[{"role": "user", "content": t}]
        )
        total += resp.input_tokens
    return total


def _write_config_divisor(cpt: float, *, model: str, basis: str, date: str,
                          cfg_path: Path | None = None) -> None:
    """Rewrite the ``CHARS_PER_TOKEN`` line in search_config.py with a dated note.

    Tolerant single-line regex replace; the rest of the file is untouched.
    """
    cfg = cfg_path or (Path(__file__).resolve().parent / "search_config.py")
    text = cfg.read_text(encoding="utf-8")
    line = (
        f"CHARS_PER_TOKEN: float = {cpt:.4f}  "
        f"# calibrated {date} vs {model} ({basis}); was 4 (prose ~4, code ~3)"
    )
    new, n = re.subn(r"^CHARS_PER_TOKEN\s*:.*$", line, text, count=1, flags=re.M)
    if n != 1:
        raise RuntimeError("could not locate CHARS_PER_TOKEN in search_config.py")
    cfg.write_text(new, encoding="utf-8")


def _run_calibrate(model: str) -> int:
    from datetime import datetime

    texts, counts = _gather_calibration_samples()
    if not texts:
        print("Calibration: no sample content found.", file=sys.stderr)
        return 1
    try:
        total_tokens = _count_tokens_via_api(texts, model)
    except ImportError:
        print("Calibration needs the Anthropic SDK: pip install anthropic "
              "(and set ANTHROPIC_API_KEY).", file=sys.stderr)
        return 1
    except Exception as e:  # auth / network / API — opt-in, so surface and stop
        print(f"Calibration failed: {e}", file=sys.stderr)
        return 1

    total_chars = sum(len(t) for t in texts)
    try:
        cpt = _chars_per_token(total_chars, total_tokens)
    except ValueError as e:
        print(f"Calibration failed: {e}", file=sys.stderr)
        return 1

    basis = "full" if counts["tool_outputs"] else "repo-sample"
    date = datetime.now().strftime("%Y-%m-%d")
    payload = {
        "chars_per_token": round(cpt, 4),
        "calibrated_at": date,
        "model": model,
        "basis": basis,
        "samples": counts,
        "total_chars": total_chars,
        "total_tokens": total_tokens,
    }
    CALIBRATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    CALIBRATION_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    try:
        _write_config_divisor(cpt, model=model, basis=basis, date=date)
    except Exception as e:
        print(f"Calibrated, but could not update search_config.py: {e}", file=sys.stderr)
        return 1
    print(
        f"Calibrated chars÷{cpt:.4f} vs {model} ({basis}: {sum(counts.values())} "
        f"samples, {total_chars:,} chars / {total_tokens:,} tokens). "
        f"Written to search_config.py and {CALIBRATION_FILE}."
    )
    return 0


def main() -> int:
    # The report uses non-ASCII glyphs (≤, em dashes); a non-UTF-8 console
    # (e.g. Windows cp1252) would raise UnicodeEncodeError on print. Force UTF-8.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(description="Token savings tracker (always on, local-only)")
    ap.add_argument("--report", action="store_true", help="Write savings-report.md")
    ap.add_argument("--html", action="store_true", help="Write savings.html")
    ap.add_argument("--doctor-html", action="store_true",
                    help="Diagnose savings.html state, log counts, paths, and hook refresh")
    ap.add_argument("--oneliner", action="store_true",
                    help="Print one measured savings line (for statusline) and exit")
    ap.add_argument("--calibrate", action="store_true",
                    help="Calibrate the token divisor against Claude's tokenizer "
                         "(opt-in; needs anthropic + ANTHROPIC_API_KEY)")
    ap.add_argument("--model", default=CALIBRATION_MODEL,
                    help="Model for --calibrate count_tokens (default: %(default)s)")
    ap.add_argument("--all", dest="all_time", action="store_true",
                    help="Show all-time totals instead of session")
    ap.add_argument("--audit-liveness", action="store_true",
                    help="Periodic health check: flag strategies that are wired but haven't "
                         "fired in real telemetry recently (manual/periodic, not a CI gate — "
                         "liveness is a property of production telemetry, not a fresh checkout)")
    ap.add_argument("--liveness-window-days", type=int, default=DEFAULT_LIVENESS_WINDOW_DAYS,
                    help="Window for --audit-liveness (default: %(default)s days)")
    args = ap.parse_args()

    if args.calibrate:
        return _run_calibrate(args.model)

    if args.audit_liveness:
        return _run_audit_liveness(args.liveness_window_days)

    if args.doctor_html:
        return _run_doctor_html()

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
    print(f"\n{_token_footer()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

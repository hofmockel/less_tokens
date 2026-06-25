"""End-to-end savings-report CLI test.

Replaces the old `Generate savings report` CI job (`.github/workflows/stats.yml`),
which seeded synthetic events and ran `stats.py` flags but asserted nothing beyond
non-crash. This exercises the same path — append events through `savings_log`, then
drive `stats.py` as a subprocess — and asserts on the produced report so a broken
CLI entrypoint, arg parser, or report aggregation fails the normal test matrix.

State is redirected to a tmp dir via `LESS_TOKENS_STATE_DIR` so the test never
touches the repo's real `state/`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent.parent
TOOLS = REPO / ".claude" / "tools"
STATS = TOOLS / "stats.py"

# Mirrors the synthetic session the old CI job logged (legacy `saved_chars` shape,
# which also exercises the legacy-tolerant loader).
SYNTHETIC_EVENTS = [
    {"strategy": "truncation", "tool": "Bash", "original_chars": 14200, "saved_chars": 10200},
    {"strategy": "truncation", "tool": "Read", "original_chars": 9800, "saved_chars": 5800},
    {"strategy": "truncation", "tool": "Bash", "original_chars": 6100, "saved_chars": 2100},
    {"strategy": "search-blocked", "file": "a.py", "saved_chars": 18400},
    {"strategy": "search-blocked", "file": "b.py", "saved_chars": 4200},
    {"strategy": "search", "query": "q1", "chunk_chars": 1400, "full_file_chars": 18400, "saved_chars": 17000},
    {"strategy": "search", "query": "q2", "chunk_chars": 900, "full_file_chars": 4200, "saved_chars": 3300},
    {"strategy": "compaction", "transcript_chars": 620000, "saved_chars": 0},
]


def _env(state_dir: Path) -> dict:
    import os
    env = dict(os.environ)
    env["LESS_TOKENS_STATE_DIR"] = str(state_dir)
    env.pop("LESS_TOKENS_NO_STATS", None)  # ensure tracking is not disabled
    return env


def _seed(state_dir: Path) -> None:
    """Append the synthetic events through savings_log in a fresh interpreter,
    so it picks up LESS_TOKENS_STATE_DIR at import time."""
    import json
    code = (
        "import sys, json\n"
        f"sys.path.insert(0, {str(TOOLS)!r})\n"
        "from savings_log import append\n"
        "for rec in json.loads(sys.stdin.read()):\n"
        "    append(rec)\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        input=json.dumps(SYNTHETIC_EVENTS),
        env=_env(state_dir),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert (state_dir / "savings.jsonl").exists()


def _run_stats(state_dir: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(STATS), *args],
        env=_env(state_dir),
        capture_output=True,
        text=True,
    )


def test_report_renders_measured_and_upper_bound(tmp_path):
    _seed(tmp_path)
    proc = _run_stats(tmp_path, "--report")
    assert proc.returncode == 0, proc.stderr

    report = tmp_path / "savings-report.md"
    assert report.exists()
    text = report.read_text(encoding="utf-8")

    # Structure: title, both honesty panels, methodology section.
    assert "# Token Savings Report" in text
    assert "Measured — removed before reaching the model" in text
    assert "Upper bound — avoided cost" in text
    assert "## How these numbers are measured" in text

    # Aggregation across the 3 truncation events (10200+5800+2100) lands in the
    # measured panel — proves rows are summed, not just passed through.
    assert "18,100" in text

    # Upper-bound magnitudes carry the optimistic ≤ prefix and are kept separate;
    # the two search-first events (18400+4200) sum to 22,600.
    assert "≤22,600" in text

    # Measured and upper-bound totals are different numbers — never cross-summed.
    assert "Search-first block" in text


def test_bare_invocation_does_not_crash(tmp_path):
    """The old job ran a bare `stats.py` ("Show session stats"); keep that path covered."""
    _seed(tmp_path)
    proc = _run_stats(tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "Token Savings" in proc.stdout or "saved" in proc.stdout.lower()


def test_report_on_empty_log(tmp_path):
    """No events: report still generates without crashing (no synthetic seed)."""
    proc = _run_stats(tmp_path, "--report")
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "savings-report.md").exists()

"""Shared compact-trigger logic — agent-neutral."""
from __future__ import annotations

import json
import os
from pathlib import Path

try:
    from .payload import HookPayload
except ImportError:
    from payload import HookPayload  # type: ignore[no-redef]

# Best-effort import of the canonical strategy key. This module is agent-neutral
# (shared by Claude and Codex hooks) and must not hard-depend on the Claude-only
# .claude/tools/savings_log path, so fall back to the literal if it isn't on
# sys.path — the literal must stay in sync with savings_log.STRATEGY_COMPACTION.
try:
    from savings_log import STRATEGY_COMPACTION  # noqa: PLC0415
except Exception:
    STRATEGY_COMPACTION = "compaction"

# Post-compaction transcript must be below this fraction of its peak for the
# shrink to count as a compaction (rather than within-session noise).
_COMPACTION_RATIO = 0.5


def check_compact_trigger(
    payload: HookPayload,
    *,
    state_dir: Path,
    max_session_chars: int,
    message: str,
    state_file: Path | None = None,
) -> tuple[int, str, str]:
    """Return (exit_code, stdout, stderr)."""
    if max_session_chars == 0:
        return 0, "", ""

    transcript_path = payload.transcript_path
    if not transcript_path:
        return 0, "", ""

    try:
        size = os.path.getsize(transcript_path)
    except OSError:
        return 0, "", ""

    if size <= max_session_chars:
        return 0, "", ""

    state_file = state_file or state_dir / "compact-trigger-last"
    try:
        last = int(state_file.read_text().strip())
    except Exception:
        last = 0

    hysteresis = max_session_chars // 4
    if last and last <= size < last + hysteresis:
        return 0, "", ""

    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file.write_text(str(size))
    except Exception:
        pass

    return 2, "", message.format(size=size, threshold=max_session_chars)


def measure_compaction(
    payload: HookPayload,
    *,
    state_dir: Path,
    max_session_chars: int,
    log,
    session: tuple[str, str] = ("local-session", "local"),
    peak_file: Path | None = None,
) -> None:
    """Emit a *measured* compaction savings event when the transcript shrinks.

    We do not produce the summary — Claude Code does, when the user runs
    ``/compact``. We detect it after the fact: the per-transcript peak size is
    tracked across calls, and when the current transcript drops below half its
    peak (and that peak exceeded the compaction threshold) the post-compaction
    transcript *is* the produced summary. We log ``basis="measured"`` with
    ``kept_chars`` = current size and ``elided_chars`` = peak − current, then
    reset the peak.

    Fires only when both sides are real char counts and the drop is real. A
    new/unknown transcript path just (re)starts tracking and logs nothing, so a
    fresh session is never mistaken for a compaction. Stays cheap (one
    ``getsize`` plus one small JSON read/write) and failure-safe.
    """
    transcript_path = payload.transcript_path
    if not transcript_path:
        return
    try:
        cur = os.path.getsize(transcript_path)
    except OSError:
        return

    tid = str(transcript_path)
    peak_file = peak_file or state_dir / "compact-peak"
    try:
        prev = json.loads(peak_file.read_text())
    except Exception:
        prev = {}
    same_transcript = prev.get("transcript") == tid
    peak = int(prev.get("peak", 0)) if same_transcript else 0

    threshold = max_session_chars if max_session_chars > 0 else 500_000
    compacted = same_transcript and peak >= threshold and cur < peak * _COMPACTION_RATIO

    if compacted and log is not None:
        sid, ssrc = session
        try:
            log({
                "strategy": STRATEGY_COMPACTION,
                "basis": "measured",
                "kept_chars": cur,
                "elided_chars": max(0, peak - cur),
                "content_kind": "transcript",
                "where": "compact",
                "session_id": sid,
                "session_source": ssrc,
            })
        except Exception:
            pass
        new_peak = cur
    else:
        new_peak = max(peak, cur)

    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        peak_file.write_text(json.dumps({"transcript": tid, "peak": new_peak}))
    except Exception:
        pass

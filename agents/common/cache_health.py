"""Prompt-cache health from native transcript usage records (PC1).

Agent-neutral. Reads the *host's* own usage counters straight from the native
transcript — never inferred from size — and reports cache-read share plus
abrupt-miss windows separately from `savings.jsonl`'s strategy totals, which
this module does not touch.

Verified fields and version windows are recorded in `DECISIONS.md`'s PC1 entry:

- Claude Code: every assistant `message.usage` object in
  `~/.claude/projects/<slug>/<session_id>.jsonl` carries `input_tokens`
  (fresh-only), `cache_creation_input_tokens`, `cache_read_input_tokens`.
  Verified stable across CLI 2.1.181-2.1.215.
- Codex CLI: `token_count` event lines carry
  `payload.info.total_token_usage.{input_tokens,cached_input_tokens}` in
  `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`. `cached_input_tokens` is
  present 0.142.3-0.145.0-alpha.18; `cache_write_input_tokens` only from
  0.145.0-alpha.18 onward (report `unavailable`, never zero, below that).

Cache-read share is platform-specific because the two hosts define
`input_tokens` differently (Claude excludes cache entirely; Codex's is a
total that includes it) — a shared formula would silently double-count:

- Claude: ``cache_read_input_tokens / (input_tokens + cache_creation_input_tokens + cache_read_input_tokens)``
- Codex:  ``cached_input_tokens / input_tokens``

Transcript discovery for "the current session":

- Claude: deterministic. The hook payload's native `session_id` *is* the
  transcript filename stem (verified: a transcript line's own `sessionId`
  field matches it), and the project directory is `cwd` with every non
  `[A-Za-z0-9]` character mapped to `-`. No filesystem search needed.
- Codex: not cwd-organized and the payload's `session_id`/`id` split (parent
  thread vs. this thread, including nested subagent rollouts) is not yet
  verified against the hook contract, so this module falls back to scanning
  recent `rollout-*.jsonl` files for a top-level `session_meta` line whose
  `cwd` matches, newest first.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Verified version windows (DECISIONS.md PC1)
# ---------------------------------------------------------------------------

CLAUDE_VERIFIED_MIN = (2, 1, 181)
CLAUDE_VERIFIED_MAX = (2, 1, 215)
CODEX_VERIFIED_MIN = (0, 142, 3)
CODEX_CACHE_WRITE_MIN = (0, 145, 0)  # -alpha.18; release-triple floor only

_VERSION_RE = re.compile(r"(?<!\d)(\d+)\.(\d+)\.(\d+)(?!\d)")


def parse_version(text: str) -> tuple[int, int, int] | None:
    """First release triple in *text*, or None."""
    match = _VERSION_RE.search(text or "")
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def claude_version_supported(version: tuple[int, int, int] | None) -> bool:
    if version is None:
        return False
    return CLAUDE_VERIFIED_MIN <= version <= CLAUDE_VERIFIED_MAX


def codex_version_supports_reads(version: tuple[int, int, int] | None) -> bool:
    if version is None:
        return False
    return version >= CODEX_VERIFIED_MIN


def codex_version_supports_writes(version: tuple[int, int, int] | None) -> bool:
    if version is None:
        return False
    return version >= CODEX_CACHE_WRITE_MIN


# ---------------------------------------------------------------------------
# Transcript discovery
# ---------------------------------------------------------------------------

def slugify_cwd(cwd: Path) -> str:
    """Claude Code's project-directory slug for *cwd*."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(cwd))


def claude_transcript_path(cwd: Path, session_id: str, *, claude_home: Path | None = None) -> Path:
    """Deterministic transcript path for a native (payload-sourced) session_id."""
    home = claude_home or (Path.home() / ".claude")
    return home / "projects" / slugify_cwd(cwd) / f"{session_id}.jsonl"


def find_claude_transcript_fallback(cwd: Path, *, claude_home: Path | None = None) -> Path | None:
    """Newest-mtime transcript in cwd's slug directory. Used only when no
    payload-sourced session_id is on hand (session_source != "payload")."""
    home = claude_home or (Path.home() / ".claude")
    project_dir = home / "projects" / slugify_cwd(cwd)
    if not project_dir.is_dir():
        return None
    candidates = sorted(project_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def find_codex_transcript(cwd: Path, *, codex_home: Path | None = None, max_days: int = 14) -> Path | None:
    """Newest rollout file whose top-level `session_meta.cwd` matches *cwd*.

    Skips nested subagent rollouts (`thread_source == "subagent"`) — those
    share the parent's cwd but are not "the session" a user would mean by
    "this session". Scans at most `max_days` of date directories, newest
    first, and stops at the first match (directories are date-ordered so the
    first hit is already the newest).
    """
    home = codex_home or (Path.home() / ".codex")
    sessions_dir = home / "sessions"
    if not sessions_dir.is_dir():
        return None
    day_dirs = sorted(sessions_dir.glob("*/*/*"), reverse=True)[:max_days]
    target = str(cwd)
    for day_dir in day_dirs:
        files = sorted(day_dir.glob("rollout-*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        for f in files:
            meta = _codex_session_meta(f)
            if meta is None:
                continue
            if meta.get("cwd") == target and meta.get("thread_source") != "subagent":
                return f
    return None


def _codex_session_meta(path: Path) -> dict | None:
    try:
        with path.open("r", encoding="utf-8") as fh:
            first = fh.readline()
    except OSError:
        return None
    try:
        rec = json.loads(first)
    except (json.JSONDecodeError, ValueError):
        return None
    if rec.get("type") != "session_meta":
        return None
    payload = rec.get("payload")
    return payload if isinstance(payload, dict) else None


# ---------------------------------------------------------------------------
# Native usage parsing
# ---------------------------------------------------------------------------

def parse_claude_cache_usage(transcript_path: Path) -> list[dict]:
    """One entry per assistant turn with a `usage` block, oldest first."""
    turns: list[dict] = []
    try:
        lines = transcript_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return turns
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        usage = (rec.get("message") or {}).get("usage") if isinstance(rec.get("message"), dict) else None
        if not isinstance(usage, dict):
            continue
        input_tokens = usage.get("input_tokens")
        cache_read = usage.get("cache_read_input_tokens")
        cache_creation = usage.get("cache_creation_input_tokens")
        if input_tokens is None or cache_read is None or cache_creation is None:
            continue
        turns.append({
            "ts": rec.get("timestamp"),
            "input_tokens": input_tokens,
            "cache_read_input_tokens": cache_read,
            "cache_creation_input_tokens": cache_creation,
        })
    return turns


def parse_codex_cache_usage(transcript_path: Path) -> list[dict]:
    """One entry per `token_count` event, oldest first."""
    turns: list[dict] = []
    try:
        lines = transcript_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return turns
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        payload = rec.get("payload")
        if not isinstance(payload, dict) or payload.get("type") != "token_count":
            continue
        usage = (payload.get("info") or {}).get("total_token_usage")
        if not isinstance(usage, dict):
            continue
        input_tokens = usage.get("input_tokens")
        cached = usage.get("cached_input_tokens")
        if input_tokens is None or cached is None:
            continue
        turns.append({
            "ts": rec.get("timestamp"),
            "input_tokens": input_tokens,
            "cached_input_tokens": cached,
            "cache_write_input_tokens": usage.get("cache_write_input_tokens"),
        })
    return turns


# ---------------------------------------------------------------------------
# Cache-read share and abrupt-miss detection
# ---------------------------------------------------------------------------

def claude_cache_read_share(turn: dict) -> float | None:
    denom = turn["input_tokens"] + turn["cache_creation_input_tokens"] + turn["cache_read_input_tokens"]
    if denom <= 0:
        return None
    return turn["cache_read_input_tokens"] / denom


def codex_cache_read_share(turn: dict) -> float | None:
    if turn["input_tokens"] <= 0:
        return None
    return turn["cached_input_tokens"] / turn["input_tokens"]

# An "abrupt miss" is a cache-read share that falls sharply off a *stable,
# already-warm* baseline — not the normal ramp-up of the first few turns of a
# session, where share is expected to be low or absent. Both constants are
# initial estimates (no calibration corpus exists yet, tracked as D4); they
# are named and centralized here specifically so a future calibration pass
# has one place to change them.
ABRUPT_MISS_WINDOW = 5
ABRUPT_MISS_BASELINE_MIN = 0.70  # trailing window must average at least this high
ABRUPT_MISS_DROP = 0.30          # ...and drop by at least this many points


def detect_abrupt_miss_windows(shares: list[float | None], *,
                                window: int = ABRUPT_MISS_WINDOW,
                                baseline_min: float = ABRUPT_MISS_BASELINE_MIN,
                                drop: float = ABRUPT_MISS_DROP) -> list[dict]:
    """Indices where a warm trailing baseline drops sharply.

    ``shares`` is the per-turn cache-read share, oldest first (None for turns
    that couldn't be computed — e.g. denom 0 — and skipped as baseline noise).
    Returns one dict per flagged turn: index, the trailing baseline mean, and
    the turn's own share.
    """
    flagged = []
    for i, share in enumerate(shares):
        if share is None or i < window:
            continue
        trailing = [s for s in shares[i - window:i] if s is not None]
        if len(trailing) < window:
            continue
        baseline = sum(trailing) / len(trailing)
        if baseline >= baseline_min and (baseline - share) >= drop:
            flagged.append({"index": i, "baseline": baseline, "share": share})
    return flagged


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def compute_cache_health(*, agent: str, cwd: Path, session_id: str | None,
                          session_source: str | None, cli_version: str | None) -> dict:
    """Top-level entry point. Always returns a dict with an ``available`` key;
    never raises, never estimates a value it cannot back with native counters.
    """
    version = parse_version(cli_version or "")

    if agent == "claude":
        if not claude_version_supported(version):
            return _unavailable("claude", f"cli_version {cli_version!r} outside verified window "
                                            f"{'.'.join(map(str, CLAUDE_VERIFIED_MIN))}-"
                                            f"{'.'.join(map(str, CLAUDE_VERIFIED_MAX))}")
        transcript = None
        if session_id and session_source == "payload":
            candidate = claude_transcript_path(cwd, session_id)
            if candidate.exists():
                transcript = candidate
        if transcript is None:
            transcript = find_claude_transcript_fallback(cwd)
        if transcript is None:
            return _unavailable("claude", "no transcript found for this cwd")
        turns = parse_claude_cache_usage(transcript)
        if not turns:
            return _unavailable("claude", "transcript has no usage records yet")
        shares = [claude_cache_read_share(t) for t in turns]
        return _health_result("claude", transcript, shares, source="payload" if session_id else "cwd-fallback")

    if agent == "codex":
        if not codex_version_supports_reads(version):
            return _unavailable("codex", f"cli_version {cli_version!r} below verified floor "
                                            f"{'.'.join(map(str, CODEX_VERIFIED_MIN))}")
        transcript = find_codex_transcript(cwd)
        if transcript is None:
            return _unavailable("codex", "no rollout file found for this cwd")
        turns = parse_codex_cache_usage(transcript)
        if not turns:
            return _unavailable("codex", "transcript has no token_count records yet")
        shares = [codex_cache_read_share(t) for t in turns]
        result = _health_result("codex", transcript, shares, source="cwd-grep")
        result["cache_write_available"] = codex_version_supports_writes(version)
        return result

    return _unavailable(agent, f"unsupported agent {agent!r}")


def _unavailable(agent: str, reason: str) -> dict:
    return {"available": False, "agent": agent, "reason": reason}


def _health_result(agent: str, transcript: Path, shares: list[float | None], *, source: str) -> dict:
    valid = [s for s in shares if s is not None]
    avg = sum(valid) / len(valid) if valid else None
    return {
        "available": True,
        "agent": agent,
        "transcript_path": str(transcript),
        "source": source,
        "turns": len(shares),
        "cache_read_share_avg": avg,
        "abrupt_miss_windows": detect_abrupt_miss_windows(shares),
    }

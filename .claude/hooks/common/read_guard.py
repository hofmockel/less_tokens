"""Shared read guard logic for high-noise files."""

from __future__ import annotations

import fnmatch
from pathlib import Path


def _matches_glob(name: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in patterns)


def _is_binary(p: Path) -> bool:
    try:
        with p.open("rb") as f:
            return b"\x00" in f.read(8192)
    except OSError:
        return False


def _count_lines(p: Path) -> int:
    n = 0
    try:
        with p.open("rb") as f:
            for _ in f:
                n += 1
    except OSError:
        return 0
    return n


def check_read_guard(
    file_path: str,
    *,
    offset: object = None,
    deny_globs: tuple[str, ...] = (),
    data_max_lines: int = 1000,
    data_exts: tuple[str, ...] = (
        ".csv",
        ".tsv",
        ".json",
        ".jsonl",
        ".ndjson",
        ".parquet",
    ),
) -> str | None:
    """Return a block reason for a wasteful whole-file read, or None."""
    if offset is not None:
        return None
    if not file_path:
        return None

    p = Path(file_path)
    name = p.name
    if _matches_glob(name, deny_globs):
        return (
            f"{name} is a lockfile/generated/binary file (matches READ_DENY_GLOBS) — "
            "reading it whole is near-pure token waste. If you truly need part of it, "
            "read a specific slice or grep/head the specific lines."
        )
    if not p.exists():
        return None
    if _is_binary(p):
        return (
            f"{name} is binary — a whole-file read would dump garbage tokens. "
            "Use a dedicated tool, `file`, or `xxd | head` instead."
        )
    if data_max_lines and p.suffix.lower() in data_exts:
        n = _count_lines(p)
        if n > data_max_lines:
            return (
                f"{name} is a {n:,}-line data file (> {data_max_lines:,}). "
                "Do not load it whole — use `head`/`wc -l`, a column summary, "
                "or a targeted slice."
            )
    return None

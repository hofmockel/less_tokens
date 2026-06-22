#!/usr/bin/env python3
"""CLI noise-file guard for checking before a whole-file read."""
from __future__ import annotations

import argparse
import fnmatch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from search_config import (  # noqa: E402
        READ_DENY_DATA_EXTS,
        READ_DENY_DATA_MAX_LINES,
        READ_DENY_GLOBS,
    )
except Exception:
    READ_DENY_GLOBS = ()
    READ_DENY_DATA_MAX_LINES = 1000
    READ_DENY_DATA_EXTS = (".csv", ".tsv", ".json", ".jsonl", ".ndjson", ".parquet")


def _matches_glob(name: str) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in READ_DENY_GLOBS)


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


def check(path: Path) -> str | None:
    name = path.name
    if _matches_glob(name):
        return (
            f"{name} matches READ_DENY_GLOBS. Avoid reading it whole; use "
            "a targeted grep/head or an explicit Read offset+limit."
        )
    if not path.exists():
        return None
    if _is_binary(path):
        return f"{name} appears binary. Use file-specific tooling instead of Read."
    if READ_DENY_DATA_MAX_LINES and path.suffix.lower() in READ_DENY_DATA_EXTS:
        n = _count_lines(path)
        if n > READ_DENY_DATA_MAX_LINES:
            return (
                f"{name} is a {n:,}-line data file. Summarize or slice it; "
                "do not read it whole."
            )
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Check whether a file is noisy to read whole")
    ap.add_argument("path", type=Path)
    args = ap.parse_args()

    reason = check(args.path)
    if reason:
        print("BLOCK: " + reason)
        return 2
    print("OK: no read-guard warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())

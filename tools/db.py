"""SQLite connection + schema init for index.db.

Usage:
  python3 tools/db.py init     # create index.db from schema/index.sql
  python3 tools/db.py migrate  # apply any pending schema migrations
  python3 tools/db.py verify   # print row counts
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent
INDEX_DB = BASE / "index.db"
SCHEMA_FILE = BASE / "schema" / "index.sql"

SCHEMA_VERSION = 1


class _ClosingConn:
    """sqlite3.Connection wrapper that commits/rolls-back AND closes on exit."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c = conn

    def __enter__(self) -> sqlite3.Connection:
        return self._c

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is None:
                self._c.commit()
            else:
                self._c.rollback()
        finally:
            self._c.close()


def connect_index() -> sqlite3.Connection:
    c = sqlite3.connect(INDEX_DB)
    c.execute("PRAGMA journal_mode = WAL")
    c.row_factory = sqlite3.Row
    return _ClosingConn(c)  # type: ignore[return-value]


def _current_version(c: sqlite3.Connection) -> int:
    try:
        row = c.execute("SELECT MAX(version) FROM schema_version").fetchone()
        return row[0] or 0
    except sqlite3.OperationalError:
        return 0


def init() -> int:
    if not SCHEMA_FILE.exists():
        print(f"ERROR: {SCHEMA_FILE} missing", file=sys.stderr)
        return 1
    with connect_index() as c:
        c.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
        # Record schema version if not already present
        c.execute(
            "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()),
        )
    print(f"Initialized {INDEX_DB.name} (schema v{SCHEMA_VERSION})")
    return 0


def migrate() -> int:
    """Apply any pending schema migrations above the current recorded version."""
    if not INDEX_DB.exists():
        print(f"{INDEX_DB.name}: MISSING — run `db.py init` first", file=sys.stderr)
        return 1
    with connect_index() as c:
        v = _current_version(c)
        if v >= SCHEMA_VERSION:
            print(f"Schema up to date (v{v})")
            return 0
        # Future migrations: add ALTER TABLE / CREATE INDEX blocks here,
        # gated on `if v < N`, then bump version at the end.
        # Example:
        #   if v < 2:
        #       c.execute("ALTER TABLE documents ADD COLUMN new_col TEXT")
        c.execute(
            "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()),
        )
        print(f"Schema migrated from v{v} to v{SCHEMA_VERSION}")
    return 0


def verify() -> int:
    if not INDEX_DB.exists():
        print(f"{INDEX_DB.name}: MISSING — run `db.py init`")
        return 1
    with connect_index() as c:
        rows = c.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        for r in rows:
            table = r[0]
            # Whitelist known tables to avoid SQL injection via sqlite_master content
            if not table.replace("_", "").isalnum():
                continue
            n = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
            print(f"  {table:<24} {n}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["init", "migrate", "verify"])
    args = ap.parse_args()
    return {"init": init, "migrate": migrate, "verify": verify}[args.cmd]()


if __name__ == "__main__":
    sys.exit(main())

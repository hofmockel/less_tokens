"""SQLite connection + schema init for index.db.

Usage:
  python3 tools/db.py init    # create index.db from schema/index.sql
  python3 tools/db.py verify  # print row counts
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
INDEX_DB = BASE / "index.db"
SCHEMA_FILE = BASE / "schema" / "index.sql"


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


def init() -> int:
    if not SCHEMA_FILE.exists():
        print(f"ERROR: {SCHEMA_FILE} missing", file=sys.stderr)
        return 1
    with connect_index() as c:
        c.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
    print(f"Initialized {INDEX_DB.name}")
    return 0


def verify() -> int:
    if not INDEX_DB.exists():
        print(f"{INDEX_DB.name}: MISSING — run `db.py init`")
        return 1
    with connect_index() as c:
        rows = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        for r in rows:
            n = c.execute(f"SELECT COUNT(*) FROM {r[0]}").fetchone()[0]
            print(f"  {r[0]:<24} {n}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["init", "verify"])
    args = ap.parse_args()
    return {"init": init, "verify": verify}[args.cmd]()


if __name__ == "__main__":
    sys.exit(main())

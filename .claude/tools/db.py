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

def _find_base() -> Path:
    """Project root: cwd when it contains .claude/tools/search_config.py, else __file__ ancestor."""
    cwd = Path.cwd().resolve()
    if (cwd / ".claude" / "tools" / "search_config.py").exists():
        return cwd
    return Path(__file__).resolve().parent.parent.parent


BASE = _find_base()
CLAUDE_DIR = BASE / ".claude"
INDEX_DB = CLAUDE_DIR / "index.db"

# Schema: prefer project-local copy; fall back to the one alongside this script
_schema_local = CLAUDE_DIR / "schema" / "index.sql"
_schema_global = Path(__file__).resolve().parent.parent / "schema" / "index.sql"
SCHEMA_FILE = _schema_local if _schema_local.exists() else _schema_global

SCHEMA_VERSION = 2


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


def connect_index() -> _ClosingConn:
    c = sqlite3.connect(INDEX_DB)
    # DELETE journal mode: no -wal or -shm files. WAL created those files, and
    # on FUSE mounts (e.g. Cowork sandbox) SQLite's -shm cleanup while another
    # process held the file open caused FUSE to rename them to .fuse_hidden*,
    # which accumulated indefinitely. index.db is small and single-writer, so
    # WAL's concurrency advantage does not apply here.
    c.execute("PRAGMA journal_mode = DELETE")
    c.row_factory = sqlite3.Row
    return _ClosingConn(c)


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
        if v < 2:
            # v1 stored embeddings in host-native byte order; v2 pins
            # little-endian on disk (search.py always decodes <f4). Drop the
            # rows so the next `embeddings.py refresh` repopulates them in the
            # new format — a v1 index built on a big-endian host would
            # otherwise score silently wrong for every unchanged row.
            try:
                c.execute("DELETE FROM documents")
            except sqlite3.OperationalError:
                pass  # no documents table yet — nothing to invalidate
        # Future migrations: add more `if v < N:` blocks here, then bump
        # SCHEMA_VERSION and let the version row below record it.
        c.execute(
            "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()),
        )
        print(f"Schema migrated from v{v} to v{SCHEMA_VERSION}")
    return 0


def ensure_current_schema() -> int:
    """Create the schema on a fresh db, or apply pending migrations on an
    existing one. Safe to call on every refresh: a no-op once current. This
    is the hook that makes the v1->v2 endianness invalidation fire on the
    normal upgrade path without a manual `db.py migrate`.
    """
    if not INDEX_DB.exists():
        return init()
    with connect_index() as c:
        if _current_version(c) == 0:
            return init()
    return migrate()


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

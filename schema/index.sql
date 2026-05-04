-- index.db schema (v1)
-- Search index over docs, code, journal, changelog, notes. Regenerable from filesystem.

CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_type TEXT NOT NULL,         -- 'doc', 'code', 'journal', 'changelog', 'note'
  source_path TEXT NOT NULL,         -- 'MANUAL.md', 'tools/wash.py', etc.
  source_key TEXT NOT NULL,          -- section heading, function name, journal date, ledger row id
  text TEXT NOT NULL,
  content_hash TEXT NOT NULL,        -- sha256(text); skip unchanged on refresh
  embedding BLOB NOT NULL,           -- float32[DIM] little-endian, raw bytes (default model: BAAI/bge-small-en-v1.5, DIM=384)
  embedding_model TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (source_path, source_key)
);
CREATE INDEX IF NOT EXISTS idx_documents_source_type ON documents(source_type);
CREATE INDEX IF NOT EXISTS idx_documents_source_path ON documents(source_path);

-- index.db schema (v2)
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

CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
  text,
  content='documents',
  content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS documents_fts_insert AFTER INSERT ON documents BEGIN
  INSERT INTO documents_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS documents_fts_delete AFTER DELETE ON documents BEGIN
  INSERT INTO documents_fts(documents_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;
CREATE TRIGGER IF NOT EXISTS documents_fts_update AFTER UPDATE OF text ON documents BEGIN
  INSERT INTO documents_fts(documents_fts, rowid, text) VALUES ('delete', old.id, old.text);
  INSERT INTO documents_fts(rowid, text) VALUES (new.id, new.text);
END;

-- Symbol index (S8): exact file:line for top-level defs/classes/constants.
-- AST-only, populated by tools/symbols.py; independent of the embedding rows.
CREATE TABLE IF NOT EXISTS symbols (
  name        TEXT NOT NULL,
  kind        TEXT NOT NULL,          -- 'func', 'class', 'const'
  source_path TEXT NOT NULL,
  start_line  INTEGER NOT NULL,
  end_line    INTEGER NOT NULL,
  PRIMARY KEY (name, source_path, start_line)
);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);

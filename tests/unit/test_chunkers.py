"""Unit tests for all chunker functions in tools/embeddings.py."""
from __future__ import annotations

from pathlib import Path

import pytest

from tools.embeddings import chunk_changelog, chunk_markdown, chunk_python, chunk_sql


# ---------------------------------------------------------------------------
# chunk_python
# ---------------------------------------------------------------------------

class TestChunkPython:
    def test_top_level_functions(self, sample_py):
        chunks = chunk_python(sample_py)
        keys = [k for k, _ in chunks]
        assert "simple_function" in keys
        assert "another_function" in keys
        assert "third_function" in keys

    def test_classes(self, sample_py):
        keys = [k for k, _ in chunk_python(sample_py)]
        assert "MyClass" in keys
        assert "AnotherClass" in keys

    def test_uppercase_constants(self, sample_py):
        keys = [k for k, _ in chunk_python(sample_py)]
        assert "MY_CONSTANT" in keys
        assert "ANOTHER_CONSTANT" in keys
        assert "THRESHOLD" in keys

    def test_async_function(self, sample_py):
        keys = [k for k, _ in chunk_python(sample_py)]
        assert "async_function" in keys

    def test_chunk_body_contains_source(self, sample_py):
        chunks = dict(chunk_python(sample_py))
        assert "return x * 2" in chunks["simple_function"]
        assert "class MyClass" in chunks["MyClass"]

    def test_module_docstring(self, sample_py):
        keys = [k for k, _ in chunk_python(sample_py)]
        assert "__module__" in keys

    def test_syntax_error_falls_back_to_whole_file(self, tmp_path):
        bad = tmp_path / "bad.py"
        bad.write_text("def foo(:\n    pass\n")
        chunks = chunk_python(bad)
        assert len(chunks) == 1
        assert chunks[0][0] == "__file__"
        assert "def foo" in chunks[0][1]

    def test_empty_file(self, tmp_path):
        empty = tmp_path / "empty.py"
        empty.write_text("")
        chunks = chunk_python(empty)
        assert chunks == []

    def test_lowercase_assignment_not_included(self, tmp_path):
        f = tmp_path / "config.py"
        f.write_text("lower_var = 1\nUPPER_VAR = 2\n")
        keys = [k for k, _ in chunk_python(f)]
        assert "UPPER_VAR" in keys
        assert "lower_var" not in keys


# ---------------------------------------------------------------------------
# chunk_markdown
# ---------------------------------------------------------------------------

class TestChunkMarkdown:
    def test_h1_h2_h3_headings(self, sample_md):
        chunks = chunk_markdown(sample_md)
        keys = [k for k, _ in chunks]
        assert "User Guide" in keys
        assert "Installation" in keys
        assert "Configuration" in keys
        assert "Advanced Options" in keys

    def test_heading_dedup(self, sample_md):
        keys = [k for k, _ in chunk_markdown(sample_md)]
        # "Advanced Options" appears twice; second becomes "Advanced Options_2"
        assert "Advanced Options_2" in keys
        # "Installation" appears twice
        assert "Installation_2" in keys

    def test_chunk_body_contains_text(self, sample_md):
        chunks = dict(chunk_markdown(sample_md))
        assert "Python 3.9" in chunks["Prerequisites"]

    def test_heading_only_section_is_included(self, tmp_path):
        """A section with no content below its heading still appears — the heading
        line itself becomes the body. Only a fully-blank preamble is skipped."""
        f = tmp_path / "test.md"
        f.write_text("# Title\n\n## Empty\n\n## HasContent\n\nSome text here.\n")
        keys = [k for k, _ in chunk_markdown(f)]
        assert "HasContent" in keys
        assert "Empty" in keys  # heading line is always the body

    def test_blank_preamble_skipped(self, tmp_path):
        """If there is no text before the first heading, preamble is not emitted."""
        f = tmp_path / "test.md"
        f.write_text("# Title\n\nBody text.\n")
        keys = [k for k, _ in chunk_markdown(f)]
        assert "preamble" not in keys

    def test_preamble_before_first_heading(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("Preamble text.\n\n# Title\n\nBody.\n")
        keys = [k for k, _ in chunk_markdown(f)]
        assert "preamble" in keys

    def test_no_headings_returns_preamble(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("Just plain text with no headings.\n")
        chunks = chunk_markdown(f)
        assert len(chunks) == 1
        assert chunks[0][0] == "preamble"


# ---------------------------------------------------------------------------
# chunk_sql
# ---------------------------------------------------------------------------

class TestChunkSql:
    def test_create_table_names(self, sample_sql):
        chunks = chunk_sql(sample_sql)
        keys = [k for k, _ in chunks]
        assert "users" in keys
        assert "sessions" in keys
        assert "audit_log" in keys

    def test_chunk_body_contains_columns(self, sample_sql):
        chunks = dict(chunk_sql(sample_sql))
        assert "email" in chunks["users"]

    def test_semicolon_in_line_comment_does_not_split(self, tmp_path):
        """Semicolons inside -- comments must not be treated as statement boundaries."""
        sql = tmp_path / "bug.sql"
        sql.write_text(
            "-- note: expires after 24h; refresh token on activity\n"
            "CREATE TABLE sessions (id TEXT PRIMARY KEY);\n"
        )
        chunks = chunk_sql(sql)
        keys = [k for k, _ in chunks]
        assert keys == ["sessions"], f"expected ['sessions'], got {keys}"

    def test_empty_statements_skipped(self, tmp_path):
        sql = tmp_path / "test.sql"
        sql.write_text("CREATE TABLE foo (id INTEGER);\n\n\nCREATE TABLE bar (id INTEGER);\n")
        chunks = chunk_sql(sql)
        keys = [k for k, _ in chunks]
        assert "foo" in keys
        assert "bar" in keys

    def test_unknown_statement_gets_hash_key(self, tmp_path):
        sql = tmp_path / "test.sql"
        sql.write_text("INSERT INTO foo VALUES (1);\n")
        chunks = chunk_sql(sql)
        assert len(chunks) == 1
        assert chunks[0][0].startswith("stmt:")


# ---------------------------------------------------------------------------
# chunk_changelog
# ---------------------------------------------------------------------------

class TestChunkChangelog:
    def test_keep_a_changelog_format_splits_on_version_headers(self, sample_changelog):
        """Keep-a-Changelog headers (## [version] - date) must produce per-version chunks."""
        chunks = chunk_changelog(sample_changelog)
        keys = [k for k, _ in chunks]
        version_keys = [k for k in keys if "1.0.0" in k or "0.9.0" in k]
        assert version_keys, f"no version keys found; got: {keys}"

    def test_date_only_format_splits_correctly(self, tmp_path):
        """The chunker works correctly when headers use the date-only format."""
        f = tmp_path / "CHANGELOG.md"
        f.write_text(
            "# Changelog\n\n"
            "## 2026-05-01 Release\n\n"
            "Added feature X.\n\n"
            "## 2026-04-01 Beta\n\n"
            "Initial beta.\n"
        )
        chunks = chunk_changelog(f)
        keys = [k for k, _ in chunks]
        assert any("2026-05-01" in k for k in keys)
        assert any("2026-04-01" in k for k in keys)
        assert len(chunks) == 2

    def test_no_date_headers_falls_back_to_markdown(self, tmp_path):
        f = tmp_path / "CHANGELOG.md"
        f.write_text("# Changelog\n\n## Added\n\nSome items.\n")
        chunks = chunk_changelog(f)
        # No date headers → fallback to chunk_markdown
        keys = [k for k, _ in chunks]
        assert "Added" in keys

"""Token performance benchmarks — measure reduction delivered by each strategy.

Requires fastembed. Run with: pytest .claude/tests/perf/ -v -m perf

The benchmark builds a search index from .claude/tests/fixtures/sample_project/,
runs 10 representative queries, and compares chars-in-results vs chars-in-source.
Truncation and compaction trigger are tested against synthetic payloads.

Results are written to .claude/tests/perf/latest.json for CI trend tracking.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent.parent
FIXTURES = REPO / ".claude" / "tests" / "fixtures" / "sample_project"
PERF_DIR = Path(__file__).parent
sys.path.insert(0, str(REPO / ".claude" / "tools"))
sys.path.insert(0, str(REPO))

fastembed = pytest.importorskip("fastembed", reason="fastembed not installed")
numpy = pytest.importorskip("numpy", reason="numpy not installed")

pytestmark = pytest.mark.perf

BENCHMARK_QUERIES = [
    "simple function that doubles a value",
    "database sessions table schema",
    "installation steps prerequisites",
    "user guide configuration options",
    "async function definition",
    "class with two methods",
    "audit log append only",
    "uppercase constants threshold",
    "advanced configuration options",
    "summary of the guide",
]

MIN_SEARCH_REDUCTION = 0.50   # search must return ≤50% of chars vs reading whole files
MIN_TRUNCATION_REDUCTION = 0.40  # truncation must remove ≥40% of chars


# ---------------------------------------------------------------------------
# Session-scoped index fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def indexed_project(tmp_path_factory):
    """Copy sample_project to tmp, build search index, return (project_dir, venv_py)."""
    project = tmp_path_factory.mktemp("perf_project")

    # Copy fixture source files
    shutil.copytree(FIXTURES, project, dirs_exist_ok=True)

    # Build index using the installed tools from the repo
    import tools.db as db_mod
    import importlib

    # Point db at a fresh index in the temp project
    index_path = project / "index.db"
    schema_path = REPO / ".claude" / "schema" / "index.sql"

    # Init DB
    conn_mod = importlib.import_module("tools.db")
    import sqlite3
    conn = sqlite3.connect(str(index_path))
    conn.executescript(schema_path.read_text())
    conn.commit()
    conn.close()

    # Embed all fixture files directly
    from tools.embeddings import chunk_python, chunk_markdown, chunk_sql, chunk_changelog
    from fastembed import TextEmbedding
    import numpy as np

    model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    chunks_to_embed: list[tuple[str, str, str, str]] = []

    for py_file in (project / "tools").glob("*.py"):
        for key, text in chunk_python(py_file):
            chunks_to_embed.append(("code", py_file.name, key, text))

    for sql_file in (project / "schema").glob("*.sql"):
        for key, text in chunk_sql(sql_file):
            chunks_to_embed.append(("code", sql_file.name, key, text))

    for md_file in (project / "docs").glob("*.md"):
        for key, text in chunk_markdown(md_file):
            chunks_to_embed.append(("doc", md_file.name, key, text))

    changelog = project / "CHANGELOG.md"
    if changelog.exists():
        for key, text in chunk_changelog(changelog):
            chunks_to_embed.append(("changelog", "CHANGELOG.md", key, text))

    texts = [t for _, _, _, t in chunks_to_embed]
    vecs = np.array(list(model.embed(texts)), dtype=np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9
    vecs = vecs / norms

    conn = sqlite3.connect(str(index_path))
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    import hashlib
    for (st, sp, sk, text), vec in zip(chunks_to_embed, vecs):
        h = hashlib.sha256(text.encode()).hexdigest()
        conn.execute(
            """INSERT OR REPLACE INTO documents
               (source_type, source_path, source_key, text, content_hash,
                embedding, embedding_model, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (st, sp, sk, text, h, vec.tobytes(), "BAAI/bge-small-en-v1.5", now),
        )
    conn.commit()
    conn.close()

    return project, index_path, chunks_to_embed


# ---------------------------------------------------------------------------
# Vector search reduction
# ---------------------------------------------------------------------------

def cosine_search(query: str, index_path: Path, k: int = 5) -> list[tuple[str, str, float]]:
    """Return top-k (source_path, text, score) for query."""
    from fastembed import TextEmbedding
    import numpy as np
    import sqlite3

    model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    q_vec = np.array(list(model.query_embed([query])), dtype=np.float32)[0]
    q_norm = np.linalg.norm(q_vec) + 1e-9
    q_vec = q_vec / q_norm

    conn = sqlite3.connect(str(index_path))
    rows = conn.execute(
        "SELECT source_path, text, embedding FROM documents"
    ).fetchall()
    conn.close()

    results = []
    for sp, text, emb_bytes in rows:
        vec = numpy.frombuffer(emb_bytes, dtype=numpy.float32)
        score = float(numpy.dot(q_vec, vec))
        results.append((sp, text, score))

    results.sort(key=lambda x: x[2], reverse=True)
    return results[:k]


class TestVectorSearchReduction:
    def test_search_returns_fewer_chars_than_full_read(self, indexed_project):
        _, index_path, all_chunks = indexed_project

        total_source_chars = sum(len(text) for _, _, _, text in all_chunks)

        search_chars_total = 0
        for query in BENCHMARK_QUERIES:
            results = cosine_search(query, index_path, k=5)
            search_chars_total += sum(len(text) for _, text, _ in results)

        avg_source_chars_per_query = total_source_chars  # reading all files each time
        reduction = 1.0 - (search_chars_total / (avg_source_chars_per_query * len(BENCHMARK_QUERIES)))

        result = {
            "strategy": "vector_search",
            "queries": len(BENCHMARK_QUERIES),
            "total_source_chars": total_source_chars * len(BENCHMARK_QUERIES),
            "total_search_chars": search_chars_total,
            "reduction_pct": round(reduction * 100, 1),
            "threshold_pct": MIN_SEARCH_REDUCTION * 100,
            "passed": reduction >= MIN_SEARCH_REDUCTION,
        }
        _save_result("vector_search", result)

        assert reduction >= MIN_SEARCH_REDUCTION, (
            f"Search returned {search_chars_total:,} chars vs "
            f"{avg_source_chars_per_query * len(BENCHMARK_QUERIES):,} source chars — "
            f"{reduction:.1%} reduction, need ≥{MIN_SEARCH_REDUCTION:.0%}"
        )

    def test_search_returns_relevant_chunk(self, indexed_project):
        _, index_path, _ = indexed_project
        results = cosine_search("simple function doubles a value", index_path, k=3)
        texts = " ".join(t for _, t, _ in results)
        assert "simple_function" in texts or "return x * 2" in texts

    def test_search_returns_k_results(self, indexed_project):
        _, index_path, _ = indexed_project
        results = cosine_search("installation steps", index_path, k=5)
        assert len(results) == 5


# ---------------------------------------------------------------------------
# Truncation reduction
# ---------------------------------------------------------------------------

class TestTruncationReduction:
    def test_bash_truncation_meets_threshold(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "truncate_output", REPO / ".claude" / "hooks" / "truncate-output.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        large_output = "\n".join(f"line {i}: " + "x" * 80 for i in range(300))
        before = len(large_output)
        truncated = mod.truncate_bash(large_output, head=50, tail=20, ceiling=4000)
        after = len(truncated)
        reduction = 1.0 - (after / before)

        result = {
            "strategy": "truncation_bash",
            "before_chars": before,
            "after_chars": after,
            "reduction_pct": round(reduction * 100, 1),
            "threshold_pct": MIN_TRUNCATION_REDUCTION * 100,
            "passed": reduction >= MIN_TRUNCATION_REDUCTION,
        }
        _save_result("truncation_bash", result)

        assert reduction >= MIN_TRUNCATION_REDUCTION, (
            f"Bash truncation: {before} → {after} chars, "
            f"{reduction:.1%} reduction, need ≥{MIN_TRUNCATION_REDUCTION:.0%}"
        )

    def test_char_split_truncation_meets_threshold(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "truncate_output", REPO / ".claude" / "hooks" / "truncate-output.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        large_output = "A" * 20_000
        before = len(large_output)
        truncated = mod.truncate_chars(large_output, ceiling=4000)
        after = len(truncated)
        reduction = 1.0 - (after / before)

        assert reduction >= MIN_TRUNCATION_REDUCTION


# ---------------------------------------------------------------------------
# Compaction trigger
# ---------------------------------------------------------------------------

class TestCompactionTrigger:
    def test_trigger_fires_at_threshold(self, tmp_path):
        transcript = tmp_path / "session.jsonl"
        transcript.write_text("x" * 600_000)
        env = {
            **os.environ,
            "PYTHONPATH": str(REPO / ".claude" / "tools"),
            "LESS_TOKENS_STATE_DIR": str(tmp_path / "state"),
        }
        result = subprocess.run(
            [sys.executable, str(REPO / ".claude" / "hooks" / "compact-trigger.py")],
            input=json.dumps({"tool_name": "Bash", "transcript_path": str(transcript)}),
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 2
        assert "compact" in result.stderr.lower()

        _save_result("compaction_trigger", {
            "strategy": "compaction_trigger",
            "transcript_chars": 600_000,
            "threshold_chars": 500_000,
            "fired": True,
            "passed": True,
        })

    def test_trigger_silent_below_threshold(self, tmp_path):
        transcript = tmp_path / "session.jsonl"
        transcript.write_text("x" * 100_000)
        env = {
            **os.environ,
            "PYTHONPATH": str(REPO / ".claude" / "tools"),
            "LESS_TOKENS_STATE_DIR": str(tmp_path / "state"),
        }
        result = subprocess.run(
            [sys.executable, str(REPO / ".claude" / "hooks" / "compact-trigger.py")],
            input=json.dumps({"tool_name": "Bash", "transcript_path": str(transcript)}),
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Results persistence
# ---------------------------------------------------------------------------

_results: dict = {}


def _save_result(key: str, data: dict) -> None:
    _results[key] = data


@pytest.fixture(scope="session", autouse=True)
def _write_perf_results():
    yield
    if _results:
        out = PERF_DIR / "latest.json"
        out.write_text(json.dumps(_results, indent=2))

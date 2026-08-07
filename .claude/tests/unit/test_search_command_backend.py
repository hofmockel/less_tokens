"""External vector backend is the sole semantic owner when configured."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(REPO))
from tools import search  # noqa: E402


@pytest.fixture()
def command_backend(monkeypatch):
    monkeypatch.setattr(search.search_config, "SEARCH_BACKEND", "command")
    monkeypatch.setattr(
        search.search_config,
        "SEARCH_BACKEND_COMMAND",
        ("vector-search", "--json"),
    )
    monkeypatch.setattr(search.search_config, "SEARCH_BACKEND_TIMEOUT_SECONDS", 7)
    monkeypatch.setattr(search.search_config, "SEARCH_BACKEND_CANDIDATE_MULTIPLIER", 3)
    monkeypatch.delenv("LESS_TOKENS_SEARCH_BACKEND", raising=False)
    monkeypatch.delenv("LESS_TOKENS_SEARCH_COMMAND", raising=False)


def _result(**overrides):
    value = {
        "score": 0.9,
        "source_type": "code",
        "source_path": "src/app.py",
        "source_key": "run",
        "text": "def run(): pass",
        "start_line": 10,
        "end_line": 12,
    }
    value.update(overrides)
    return value


def test_command_backend_never_queries_local_index(command_backend, monkeypatch):
    captured = {}

    def fake_run(argv, **kwargs):
        captured.update({"argv": argv, **kwargs})
        return subprocess.CompletedProcess(argv, 0, json.dumps([_result()]), "")

    def forbidden(*args, **kwargs):
        raise AssertionError("external backend touched local vector search")

    monkeypatch.setattr(search.subprocess, "run", fake_run)
    monkeypatch.setattr(search, "connect_index", forbidden)
    monkeypatch.setattr(search, "embed", forbidden)

    hits = search.search("request validation", k=2, source_type="code")

    assert hits == [_result()]
    request = json.loads(captured["input"])
    assert request == {
        "query": "request validation",
        "k": 6,
        "requested_k": 2,
        "source_type": "code",
        "min_score": None,
        "project_root": str(search.BASE),
    }
    assert captured["argv"] == ["vector-search", "--json"]
    assert captured["cwd"] == search.BASE
    assert captured["timeout"] == 7.0


def test_command_backend_limits_and_deduplicates_private_candidates(
    command_backend, monkeypatch
):
    candidates = [
        _result(score=0.99, source_path="src/a.py", text="same"),
        _result(score=0.98, source_path="src/a.py", text="other"),
        _result(score=0.97, source_path="src/b.py", text="same"),
        _result(score=0.96, source_path="src/c.py", text="third"),
        _result(score=0.20, source_path="src/d.py", text="low"),
    ]
    monkeypatch.setattr(
        search.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(
            a[0], 0, json.dumps(candidates), ""
        ),
    )

    hits = search.search("q", k=2, source_type="code", min_score=0.5)

    assert [hit["source_path"] for hit in hits] == ["src/a.py", "src/c.py"]


def test_backend_failure_does_not_fall_back_to_sqlite(
    command_backend, monkeypatch, capsys
):
    monkeypatch.setattr(
        search.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 2, "", "database offline"),
    )
    monkeypatch.setattr(
        search,
        "_search_sqlite",
        lambda *a, **k: pytest.fail("must not fall back to the local index"),
    )

    with pytest.raises(search.SearchBackendError, match="database offline"):
        search.search("q")
    assert capsys.readouterr().err == ""


def test_backend_failure_keeps_search_first_gate_closed(
    command_backend, monkeypatch, tmp_path, capsys
):
    monkeypatch.setattr(
        search.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 2, "", "database offline"),
    )
    monkeypatch.setattr(search, "active_state_dir", lambda: tmp_path / "state")
    monkeypatch.setattr(sys, "argv", ["search.py", "q"])

    assert search.main() == 1
    assert "database offline" in capsys.readouterr().err
    assert not (tmp_path / "state" / "last-search").exists()


def test_external_ranges_skip_file_relocation(command_backend, monkeypatch, tmp_path):
    monkeypatch.setattr(search, "BASE", tmp_path)
    monkeypatch.setattr(search, "active_state_dir", lambda: tmp_path / "state")

    search._write_last_search_ranges([_result()])

    ranges = json.loads((tmp_path / "state" / "last-search.json").read_text())
    assert ranges == {"src/app.py": [[10, 12]]}


def test_external_source_types_do_not_open_local_index(command_backend, monkeypatch):
    monkeypatch.setattr(
        search,
        "connect_index",
        lambda: pytest.fail("external source types belong to the external corpus"),
    )
    assert search._source_type_choices() is None


def test_invalid_external_response_fails_closed(command_backend, monkeypatch, capsys):
    monkeypatch.setattr(
        search.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(
            a[0], 0, '{"results": [{"score": 1}]}', ""
        ),
    )

    with pytest.raises(
        search.SearchBackendError, match="invalid external search response"
    ):
        search.search("q")
    assert capsys.readouterr().err == ""


def test_non_finite_score_fails_closed(command_backend, monkeypatch, capsys):
    monkeypatch.setattr(
        search.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(
            a[0], 0, json.dumps([_result(score="NaN")]), ""
        ),
    )

    with pytest.raises(search.SearchBackendError, match="non-finite score"):
        search.search("q")
    assert capsys.readouterr().err == ""

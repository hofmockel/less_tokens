"""chunk_python optionally prepends the module docstring to code chunks.

A bare function chunk gives Claude no signal about the file it lives in,
often forcing a follow-up Read. With CHUNK_INCLUDE_MODULE_CONTEXT on,
each top-level def/class chunk is prefixed with the module docstring (as
a comment). Default off — zero change to existing indexes until opted in.
"""
from __future__ import annotations

import sys
from pathlib import Path

from tests.conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / ".claude" / "tools"))
import embeddings  # noqa: E402
import search_config  # noqa: E402

SAMPLE = '''"""Purpose line one.
Detail line two.
"""

CONST = 1


def alpha():
    return 1


class Beta:
    pass
'''


def _write(tmp_path: Path) -> Path:
    p = tmp_path / "m.py"
    p.write_text(SAMPLE)
    return p


def test_default_off_leaves_chunks_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(search_config, "CHUNK_INCLUDE_MODULE_CONTEXT", False)
    chunks = dict(embeddings.chunk_python(_write(tmp_path)))
    assert chunks["alpha"] == "def alpha():\n    return 1"
    assert chunks["Beta"] == "class Beta:\n    pass"
    assert "__module__" in chunks


def test_opt_in_prefixes_module_docstring(tmp_path, monkeypatch):
    monkeypatch.setattr(search_config, "CHUNK_INCLUDE_MODULE_CONTEXT", True)
    chunks = dict(embeddings.chunk_python(_write(tmp_path)))

    header = "# Purpose line one.\n# Detail line two."
    assert chunks["alpha"] == f"{header}\n\ndef alpha():\n    return 1"
    assert chunks["Beta"] == f"{header}\n\nclass Beta:\n    pass"
    # Constants and the __module__ chunk are not wrapped.
    assert chunks["CONST"] == "CONST = 1"
    assert chunks["__module__"] == "Purpose line one.\nDetail line two."


def test_opt_in_no_docstring_is_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(search_config, "CHUNK_INCLUDE_MODULE_CONTEXT", True)
    p = tmp_path / "n.py"
    p.write_text("def solo():\n    return 2\n")
    chunks = dict(embeddings.chunk_python(p))
    assert chunks["solo"] == "def solo():\n    return 2"

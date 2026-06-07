"""Bug 10: chunk_python emits '# ' (trailing space) for empty lines in mod_doc.

When CHUNK_INCLUDE_MODULE_CONTEXT=True and the module docstring contains blank
lines, _ctx() produces comment lines like '# ' instead of plain '#', adding
trailing whitespace to the embedded header.
"""
from __future__ import annotations

import sys

from tests.conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / ".claude" / "tools"))

import embeddings  # noqa: E402
import search_config  # noqa: E402


_SRC_WITH_BLANK_DOCLINE = '''\
"""Line one.

Line three.
"""


def foo():
    pass
'''


def test_empty_docstring_lines_produce_bare_hash(tmp_path, monkeypatch):
    """Empty lines in mod_doc must produce '#' not '# ' (trailing space)."""
    monkeypatch.setattr(search_config, "CHUNK_INCLUDE_MODULE_CONTEXT", True)
    p = tmp_path / "m.py"
    p.write_text(_SRC_WITH_BLANK_DOCLINE)
    chunks = dict(embeddings.chunk_python(p))
    assert "# \n" not in chunks["foo"], (
        "empty docstring line produced '# ' with trailing space in chunk header"
    )
    assert "# Line one.\n#\n# Line three." in chunks["foo"]

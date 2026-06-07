"""Bug 19: chunk_python returned duplicate source_key values for same-named functions.

When a Python file defines two functions or classes with the same name (valid
Python, even if unusual), chunk_python emitted both with identical source_key
values.  The UPSERT in embeddings.refresh then silently dropped the first
chunk because ON CONFLICT DO UPDATE overwrote it.

The fix deduplicates source_key values in chunk_python using the same suffix
strategy that chunk_markdown already uses.
"""
from __future__ import annotations

import sys

from tests.conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / ".claude" / "tools"))
import embeddings  # noqa: E402


_TWO_SAME_NAME_FUNCS = """\
def foo():
    return 1


def foo():
    return 2
"""

_TWO_SAME_NAME_CLASSES = """\
class Bar:
    x = 1


class Bar:
    x = 2
"""


def test_duplicate_function_names_get_unique_keys(tmp_path):
    """chunk_python must not emit duplicate source_key values."""
    p = tmp_path / "dupe.py"
    p.write_text(_TWO_SAME_NAME_FUNCS)
    chunks = embeddings.chunk_python(p)
    keys = [k for k, _ in chunks]
    assert len(keys) == len(set(keys)), (
        f"duplicate source_key values in chunk_python output: {keys}"
    )
    assert "foo" in keys
    assert "foo_2" in keys


def test_duplicate_class_names_get_unique_keys(tmp_path):
    p = tmp_path / "dupe_cls.py"
    p.write_text(_TWO_SAME_NAME_CLASSES)
    chunks = embeddings.chunk_python(p)
    keys = [k for k, _ in chunks]
    assert len(keys) == len(set(keys))
    assert "Bar" in keys
    assert "Bar_2" in keys

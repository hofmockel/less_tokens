"""EMBEDDING_MODEL / EMBEDDING_DIM live in search_config.py, not hardcoded.

The embedding model name and vector dimension were hardcoded in
embeddings.py, so switching models meant editing tool source. They now come
from search_config.py; embeddings.py re-exports them as MODEL/DIM (search.py
imports DIM from embeddings, which is now config-sourced). This guards the
constants' presence and the wiring.
"""
from __future__ import annotations

import sys

from tests.conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / ".claude" / "tools"))
import search_config  # noqa: E402
import embeddings  # noqa: E402


def test_config_exposes_embedding_constants():
    assert search_config.EMBEDDING_MODEL == "BAAI/bge-small-en-v1.5"
    assert search_config.EMBEDDING_DIM == 384


def test_embeddings_sources_model_and_dim_from_config():
    assert embeddings.MODEL is search_config.EMBEDDING_MODEL
    assert embeddings.DIM == search_config.EMBEDDING_DIM


def test_embeddings_has_no_hardcoded_literals():
    src = (REPO_ROOT / ".claude" / "tools" / "embeddings.py").read_text()
    assert 'MODEL = "BAAI/bge-small-en-v1.5"' not in src
    assert "DIM = 384" not in src

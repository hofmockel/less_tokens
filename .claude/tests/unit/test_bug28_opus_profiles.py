"""Bug 28: model_profiles.py had inconsistent recommended_k for Opus models.

claude-opus-3 was assigned recommended_k=5 (Sonnet level) while all other
Opus models have recommended_k=8.  The comment "biggest budget, can afford
a wider funnel" implies Opus should consistently use the larger k.

Additionally, claude-opus-4-8 (the current flagship Opus) was missing entirely.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / ".claude" / "tools"))

from model_profiles import MODEL_PROFILES, profile  # noqa: E402


def test_all_opus_models_have_consistent_k():
    """All Opus models must share the same recommended_k."""
    opus_profiles = {k: v for k, v in MODEL_PROFILES.items() if "opus" in k}
    assert opus_profiles, "no Opus models in MODEL_PROFILES"
    k_values = {v["recommended_k"] for v in opus_profiles.values()}
    assert len(k_values) == 1, (
        f"Opus models have inconsistent recommended_k: "
        f"{[(k, v['recommended_k']) for k, v in opus_profiles.items()]}"
    )


def test_opus_k_exceeds_sonnet_k():
    """Opus recommended_k must be >= Sonnet's, reflecting its larger context budget."""
    opus_k = MODEL_PROFILES["claude-opus-4-7"]["recommended_k"]
    sonnet_k = MODEL_PROFILES["claude-sonnet-4-5"]["recommended_k"]
    assert opus_k >= sonnet_k, (
        f"Opus k={opus_k} should be >= Sonnet k={sonnet_k}"
    )


def test_opus_4_8_in_profiles():
    """claude-opus-4-8 (current flagship) must be in MODEL_PROFILES."""
    assert "claude-opus-4-8" in MODEL_PROFILES, (
        "claude-opus-4-8 missing from MODEL_PROFILES (Bug 28)"
    )
    p = profile("claude-opus-4-8")
    assert p is not None
    assert p["recommended_k"] > 0
    assert p["context_window"] > 0

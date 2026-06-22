"""Cheap deterministic token estimates."""
from __future__ import annotations

import math

CONTENT_MULTIPLIERS: dict[str, float] = {
    "plain_text": 1.0,
    "code": 0.9,
    "json": 1.15,
    "logs": 1.2,
    "markdown": 1.0,
    "diff": 1.1,
}


def estimate_tokens(text: str, *, content_type: str = "plain_text") -> int:
    """Estimate tokens with chars/4 plus a content-type multiplier."""
    if not text:
        return 0
    multiplier = CONTENT_MULTIPLIERS.get(content_type, 1.0)
    return max(1, int(math.ceil((len(text) / 4) * multiplier)))


def estimate_size_tokens(size_chars: int, *, content_type: str = "plain_text") -> int:
    """Estimate tokens from a character count without materializing text."""
    if size_chars <= 0:
        return 0
    multiplier = CONTENT_MULTIPLIERS.get(content_type, 1.0)
    return max(1, int(math.ceil((size_chars / 4) * multiplier)))

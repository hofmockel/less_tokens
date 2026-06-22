"""Context candidate schema used by the budget gate."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from .estimator import estimate_size_tokens, estimate_tokens


def _content_type_for_path(path: str | None) -> str:
    if not path:
        return "plain_text"
    suffix = Path(path).suffix.lower()
    if suffix in {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".c", ".cpp", ".h", ".sh"}:
        return "code"
    if suffix in {".json", ".jsonl", ".ndjson"}:
        return "json"
    if suffix in {".md", ".mdx", ".rst"}:
        return "markdown"
    if suffix in {".diff", ".patch"}:
        return "diff"
    if suffix in {".log", ".out", ".err"}:
        return "logs"
    return "plain_text"


@dataclass(frozen=True)
class ContextCandidate:
    """A possible piece of context with cost and relevance metadata."""

    candidate_id: str
    category: str
    candidate_type: str
    text: str = ""
    path: str | None = None
    content_type: str | None = None
    estimated_tokens: int = 0
    relevance_score: float = 0.0
    reason: str = ""
    replacement: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def with_estimate(self) -> "ContextCandidate":
        content_type = self.content_type or _content_type_for_path(self.path)
        if self.estimated_tokens:
            return replace(self, content_type=content_type)
        if self.text:
            tokens = estimate_tokens(self.text, content_type=content_type)
        else:
            size = int(self.metadata.get("size_chars", 0) or 0)
            tokens = estimate_size_tokens(size, content_type=content_type)
        return replace(self, content_type=content_type, estimated_tokens=tokens)

    def scored(self, score: float, reason: str) -> "ContextCandidate":
        return replace(self, relevance_score=max(0.0, min(1.0, score)), reason=reason)

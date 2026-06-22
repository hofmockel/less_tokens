"""Relevance signals mined from payloads and less_tokens state."""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

PATH_RE = re.compile(
    r"(?P<path>(?:[A-Za-z]:)?(?:\.{1,2}/|/)?[A-Za-z0-9_.@+~/-]+"
    r"\.(?:py|js|ts|tsx|jsx|go|rs|java|c|cpp|h|md|toml|json|yaml|yml|sql|txt))"
)
PYTEST_RE = re.compile(r"\b(?:FAILED|ERROR)\s+(?P<path>[A-Za-z0-9_.@+~/-]+\.py)(?:::|\s)")
TRACEBACK_RE = re.compile(r'File "(?P<path>[^"]+)", line (?P<line>\d+)')


@dataclass(frozen=True)
class SearchRange:
    start: int
    end: int


@dataclass(frozen=True)
class BudgetSignals:
    explicit_references: set[str] = field(default_factory=set)
    stack_trace_paths: set[str] = field(default_factory=set)
    search_ranges: dict[str, list[SearchRange]] = field(default_factory=dict)
    recent_paths: set[str] = field(default_factory=set)
    failure_paths: set[str] = field(default_factory=set)


def normalize_path(value: str) -> str:
    return str(Path(value).as_posix()).lstrip("./")


def path_matches(candidate_path: str | None, references: set[str]) -> bool:
    if not candidate_path:
        return False
    path = normalize_path(candidate_path)
    name = Path(path).name
    for ref in references:
        norm = normalize_path(ref)
        if path == norm or path.endswith(norm) or norm.endswith(path) or name == Path(norm).name:
            return True
    return False


def extract_path_references(text: str) -> set[str]:
    return {normalize_path(match.group("path")) for match in PATH_RE.finditer(text or "")}


def extract_failure_paths(text: str) -> set[str]:
    found = {normalize_path(match.group("path")) for match in PYTEST_RE.finditer(text or "")}
    found.update(normalize_path(match.group("path")) for match in TRACEBACK_RE.finditer(text or ""))
    return found


def _state_dirs(root: Path) -> list[Path]:
    return [root / ".less_tokens" / "state", root / ".claude" / "state"]


def _load_recent_paths(root: Path, *, max_age_seconds: int = 3600) -> set[str]:
    now = time.time()
    recent: set[str] = set()
    for state_dir in _state_dirs(root):
        path = state_dir / "last-edit.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        for item, ts in data.items():
            try:
                if now - float(ts) <= max_age_seconds:
                    recent.add(normalize_path(item))
            except (TypeError, ValueError):
                continue
    return recent


def _load_search_ranges(root: Path, *, max_age_seconds: int = 600) -> dict[str, list[SearchRange]]:
    now = time.time()
    ranges: dict[str, list[SearchRange]] = {}
    for state_dir in _state_dirs(root):
        path = state_dir / "last-search.json"
        try:
            if now - path.stat().st_mtime > max_age_seconds:
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        for item, spans in data.items():
            parsed: list[SearchRange] = []
            if isinstance(spans, list):
                for span in spans:
                    if not (isinstance(span, list) and len(span) >= 2):
                        continue
                    try:
                        parsed.append(SearchRange(start=int(span[0]), end=int(span[1])))
                    except (TypeError, ValueError):
                        continue
            if parsed:
                ranges[normalize_path(item)] = parsed
    return ranges


def build_budget_signals(root: Path, *, query: str = "", text: str = "") -> BudgetSignals:
    explicit = extract_path_references(query)
    output_paths = extract_path_references(text)
    failure_paths = extract_failure_paths(text)
    return BudgetSignals(
        explicit_references=explicit | output_paths,
        stack_trace_paths=failure_paths,
        search_ranges=_load_search_ranges(root),
        recent_paths=_load_recent_paths(root),
        failure_paths=failure_paths,
    )


def first_search_range(candidate_path: str | None, signals: BudgetSignals) -> SearchRange | None:
    if not candidate_path:
        return None
    path = normalize_path(candidate_path)
    for key, ranges in signals.search_ranges.items():
        if path == key or path.endswith(key) or key.endswith(path):
            return ranges[0] if ranges else None
    return None

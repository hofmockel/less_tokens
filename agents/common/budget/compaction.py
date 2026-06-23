"""Pressure-based compact session snapshots."""
from __future__ import annotations

import re
import time
from pathlib import Path

from .adapters import BudgetInput
from .config import BudgetConfig
from .decisions import BudgetDecision
from .estimator import estimate_tokens
from .state import load_json, save_json, session_state_path, shared_project_state_path

PRESSURE_THRESHOLD = 0.80
_MAX_ITEMS = 20


def record_session_activity(root: Path, budget_input: BudgetInput, decisions: list[BudgetDecision]) -> None:
    path = session_state_path(root, budget_input.agent)
    state = load_json(path)
    state.setdefault("agent", budget_input.agent)
    state.setdefault("session_id", budget_input.session_id)
    state.setdefault("run_id", budget_input.run_id)
    state["updated_at"] = time.time()
    _extend_unique(state, "active_files", _candidate_paths(budget_input), limit=_MAX_ITEMS)
    _extend_unique(state, "commands_run", _commands(budget_input), limit=_MAX_ITEMS)
    _extend_unique(state, "decisions_made", _decision_notes(decisions), limit=_MAX_ITEMS)
    _extend_unique(state, "test_status", _test_status(budget_input), limit=8)
    save_json(path, state)
    record_shared_project_activity(root, budget_input, decisions)


def record_shared_project_activity(root: Path, budget_input: BudgetInput, decisions: list[BudgetDecision]) -> None:
    path = shared_project_state_path(root)
    state = load_json(path)
    state["updated_at"] = time.time()
    _extend_unique(state, "agents", [budget_input.agent], limit=8)
    _extend_unique(state, "active_files", _candidate_paths(budget_input), limit=_MAX_ITEMS)
    _extend_unique(state, "commands_run", _commands(budget_input), limit=_MAX_ITEMS)
    _extend_unique(state, "decisions_made", _decision_notes(decisions), limit=_MAX_ITEMS)
    _extend_unique(state, "test_status", _test_status(budget_input), limit=8)
    save_json(path, state)


def should_compact(decisions: list[BudgetDecision], *, threshold: float = PRESSURE_THRESHOLD) -> bool:
    for decision in decisions:
        if decision.budget_limit > 0:
            pressure = max(decision.budget_used_after, decision.budget_used_before) / decision.budget_limit
            if pressure >= threshold:
                return True
        if decision.action in {"replace", "trim", "defer", "block"} and decision.estimated_tokens_saved > 0:
            return True
    return False


def refresh_compaction_snapshot(root: Path, agent: str, config: BudgetConfig) -> dict[str, object]:
    state = load_json(session_state_path(root, agent))
    before_tokens = estimate_tokens(_render_state_for_compaction(state), content_type="json")
    summary = build_compaction_snapshot(state, config)
    summary["estimated_tokens_before"] = before_tokens
    state["compact_summary"] = summary
    state["compact_summary_updated_at"] = time.time()
    save_json(session_state_path(root, agent), state)
    return summary


def build_compaction_snapshot(state: dict, config: BudgetConfig) -> dict[str, object]:
    limit = config.category_limit("session_summary")
    summary: dict[str, object] = {
        "current_objective": state.get("current_objective") or "continue current task",
        "active_files": list(state.get("active_files") or []),
        "decisions_made": list(state.get("decisions_made") or []),
        "files_changed": list(state.get("files_changed") or []),
        "commands_run": list(state.get("commands_run") or []),
        "test_status": list(state.get("test_status") or []),
        "open_questions": list(state.get("open_questions") or []),
        "next_step": state.get("next_step") or "",
    }
    while estimate_tokens(_render_summary(summary), content_type="json") > limit:
        if not _trim_longest_list(summary):
            break
    summary["estimated_tokens"] = estimate_tokens(_render_summary(summary), content_type="json")
    summary["budget_limit"] = limit
    return summary


def _candidate_paths(budget_input: BudgetInput) -> list[str]:
    return [str(candidate.path) for candidate in budget_input.candidates if candidate.path]


def _commands(budget_input: BudgetInput) -> list[str]:
    commands = []
    for candidate in budget_input.candidates:
        command = candidate.metadata.get("command")
        if command:
            commands.append(str(command))
    return commands


def _decision_notes(decisions: list[BudgetDecision]) -> list[str]:
    notes = []
    for decision in decisions:
        if decision.action == "allow":
            continue
        saved = f", saved ~{decision.estimated_tokens_saved}" if decision.estimated_tokens_saved else ""
        notes.append(f"{decision.action}: {decision.candidate_id}{saved}; {decision.reason}")
    return notes


def _test_status(budget_input: BudgetInput) -> list[str]:
    statuses = []
    for candidate in budget_input.candidates:
        if candidate.candidate_type != "tool_output":
            continue
        text = candidate.text
        if re.search(r"\bfailed\b|FAILED|AssertionError", text):
            statuses.append("failing tests detected")
        elif re.search(r"\bpassed\b|OK\b", text):
            statuses.append("tests passed")
    return statuses


def _extend_unique(state: dict, key: str, values: list[str], *, limit: int) -> None:
    existing = list(state.get(key) or [])
    for value in values:
        if value and value not in existing:
            existing.append(value)
    state[key] = existing[-limit:]


def _render_summary(summary: dict[str, object]) -> str:
    return "\n".join(f"{key}: {value}" for key, value in summary.items())


def _render_state_for_compaction(state: dict) -> str:
    keys = (
        "current_objective", "active_files", "decisions_made", "files_changed",
        "commands_run", "test_status", "open_questions", "next_step",
    )
    return "\n".join(f"{key}: {state.get(key, '')}" for key in keys)


def _trim_longest_list(summary: dict[str, object]) -> bool:
    list_keys = [key for key, value in summary.items() if isinstance(value, list) and value]
    if not list_keys:
        return False
    key = max(list_keys, key=lambda item: len(summary[item]))  # type: ignore[arg-type]
    values = list(summary[key])  # type: ignore[arg-type]
    values.pop(0)
    summary[key] = values
    return True

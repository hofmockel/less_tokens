"""Single source of truth for HP1's versioned conformance/savings workload catalog.

Each `Workload` is a claim-shaped unit of work: one thing less_tokens says it saves tokens
on, named precisely enough that a live capture against a real Claude/Codex release can prove
or refute it. This module carries no evidence — see `agents/common/conformance/matrix.json`
for captured (or explicitly not-yet-measured) results per `(workload, agent, release)`.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Workload:
    slug: str
    name: str
    description: str
    primary_surface: str


WORKLOADS: tuple[Workload, ...] = (
    Workload(
        slug="indexed_whole_file_read",
        name="Indexed whole-file read",
        description=(
            "Agent asks to read an entire source file that is already covered by the "
            "vector/symbol index; search-first and auto-slice gates should redirect to a "
            "targeted slice instead of the full file."
        ),
        primary_surface="PreToolUse:Read",
    ),
    Workload(
        slug="noisy_command_output",
        name="Noisy command output",
        description=(
            "A shell command (test runner, linter, recursive listing) returns output far "
            "larger than the task-relevant portion; lean-output/truncate-output should cut "
            "the model-visible result down to the relevant lines."
        ),
        primary_surface="PostToolUse:Bash",
    ),
    Workload(
        slug="repeated_read_search",
        name="Repeated read/search",
        description=(
            "The same file or query is read/searched again within the context-cache TTL "
            "window; context-cache should serve the cached result instead of re-reading."
        ),
        primary_surface="PreToolUse:Read|Grep",
    ),
    Workload(
        slug="edit_verification",
        name="Edit verification",
        description=(
            "After an Edit/Write, read-after-edit and post-edit-diff should surface only the "
            "diff/verification slice, not a full re-read of the modified file."
        ),
        primary_surface="PostToolUse:Edit|Write",
    ),
    Workload(
        slug="long_session_compaction",
        name="Long-session compaction",
        description=(
            "A session's transcript grows past the compaction threshold; the compact-trigger "
            "hook should nudge compaction and the resulting summary should shrink input size "
            "without losing task-critical state."
        ),
        primary_surface="PostToolUse:.* / PreCompact,PostCompact",
    ),
    Workload(
        slug="verbose_final_response",
        name="Verbose final response",
        description=(
            "The agent's final turn is prone to filler prose; terse-output mode should reduce "
            "output tokens relative to an unmodified stop response."
        ),
        primary_surface="Stop",
    ),
    Workload(
        slug="bounded_subagent_exploration",
        name="Bounded subagent exploration",
        description=(
            "A parent delegates a read-only exploration task to a subagent; only a bounded, "
            "concise result should be absorbed back into the parent's context, not the full "
            "child transcript."
        ),
        primary_surface="Task / SubagentStart,SubagentStop",
    ),
)

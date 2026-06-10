"""Shared index-refresh logic — agent-neutral."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

try:
    from .payload import HookPayload
    from .search_first import is_indexed
except ImportError:
    from payload import HookPayload  # type: ignore[no-redef]
    from search_first import is_indexed  # type: ignore[no-redef]


def check_index_refresh(
    payload: HookPayload,
    *,
    repo: Path,
    state_dir: Path,
    config: dict,
) -> tuple[int, str, str]:
    """Fire a background embeddings refresh when an indexed file changes.

    Returns (exit_code, stdout, stderr) — always 0; refresh is fire-and-forget.
    """
    tool = payload.tool_name
    edit_tools = {"Edit", "Write", "apply_patch"}
    if tool not in edit_tools:
        return 0, "", ""

    venv_py: Path | None = config.get("venv_py")
    if not venv_py or not Path(str(venv_py)).exists():
        return 0, "", ""

    embeddings_py = repo / ".claude" / "tools" / "embeddings.py"
    if not embeddings_py.exists():
        return 0, "", ""

    # For apply_patch skip is_indexed() check — can't easily enumerate touched files
    if tool != "apply_patch":
        file_path = (payload.tool_input or {}).get("file_path", "")
        if not file_path:
            return 0, "", ""
        if not is_indexed(
            Path(file_path), repo,
            excluded_prefixes=config.get("excluded_prefixes", ()),
            excluded_names=config.get("excluded_names"),
            indexed_dirs=config.get("dirs", ()),
        ):
            return 0, "", ""

    log = state_dir / "index-refresh.log"
    log.parent.mkdir(parents=True, exist_ok=True)

    kwargs: dict = (
        {"creationflags": getattr(subprocess, "DETACHED_PROCESS", 8) |
                          getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)}
        if sys.platform == "win32"
        else {"start_new_session": True}
    )
    with log.open("ab") as fh:
        subprocess.Popen(
            [str(venv_py), str(embeddings_py), "refresh"],
            cwd=repo,
            stdout=fh,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            **kwargs,
        )
    return 0, "", ""

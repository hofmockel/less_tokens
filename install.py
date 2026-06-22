#!/usr/bin/env python3
"""less_tokens project installer.

Clone this repo inside a host project, then run:

    python3 less_tokens/install.py [options]
    python3 less_tokens/install.py --agent codex
    python3 less_tokens/install.py --agent both

Default target is the parent directory of this clone. The installer copies the
shared search/indexing tools, initializes the local SQLite index, and wires the
selected agent adapters:

    --agent claude|codex|both
                        Claude Code (default), Codex, or both integrations
    --target PATH       install into PATH instead of the parent of this clone
    --venv PATH         use an existing venv instead of auto-detecting
    --create-venv       create .claude/.venv-tokens if no venv is found
    --skip-deps         skip pip install of fastembed + numpy
    --no-build          skip the initial index build
    --truncate          wire tool-output truncation hooks
    --compact           wire session-size compaction hooks
    --caveman           wire terse-output enforcement (Claude Stop hook;
                        Codex concise-reminder hook)
    --local             for Claude, write .claude/settings.local.json instead
                        of .claude/settings.json
    --dry-run           preview without writing anything
    --update            safe upgrade of generated hooks/tools
    --uninstall         remove a previous deployment

Cross-platform: works on Windows/macOS/Linux. Uses pathlib + subprocess only.
"""
from __future__ import annotations

import argparse
import ast
import difflib
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parent


def selected_agents(value: str) -> set[str]:
    if value == "both":
        return {"claude", "codex"}
    return {value}


def _dir_is_writable(target_root: Path, rel: str) -> bool:
    d = target_root / rel
    if d.is_dir():
        return os.access(d, os.W_OK)
    parent = d.parent
    return parent.is_dir() and os.access(parent, os.W_OK)


# Relative path (within target_root) where we record installed version.
_INSTALL_STATE_PATH = Path(".claude") / "state" / "install.json"

# Must stay in sync with .claude/tools/db.py SCHEMA_VERSION.
_INDEX_SCHEMA_VERSION = 2


# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------

def _source_git_hash() -> str | None:
    """Short commit hash of the less_tokens source tree, or None if unavailable."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(SOURCE), capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _read_install_state(target_root: Path) -> dict | None:
    """Read .claude/state/install.json; return dict or None if absent/corrupt."""
    p = target_root / _INSTALL_STATE_PATH
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_install_state(target_root: Path, version: str | None, dry_run: bool) -> None:
    """Write .claude/state/install.json with version + timestamp."""
    import datetime
    state = {
        "version": version or "unknown",
        "installed_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "source": str(SOURCE),
    }
    p = target_root / _INSTALL_STATE_PATH
    if not dry_run:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Venv helpers
# ---------------------------------------------------------------------------

def venv_python(venv_dir: Path) -> Path:
    """Resolve <venv>/Scripts/python.exe (Windows) or <venv>/bin/python (Unix)."""
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def detect_venv(target_root: Path) -> Path | None:
    """Look for a venv in common locations relative to target_root.

    An active venv ($VIRTUAL_ENV) is checked first: `activate` sets it and
    it reliably points at the live venv on all platforms, so it beats the
    relative-path guesses below. `.venv-tokens` is checked next so projects
    that keep less_tokens deps isolated get auto-detected on re-runs.
    """
    env = os.environ.get("VIRTUAL_ENV")
    if env:
        d = Path(env)
        if venv_python(d).exists():
            return d
    for candidate in [".claude/.venv-tokens", ".venv-tokens", ".venv", "venv", "env", "app/.venv"]:
        d = target_root / candidate
        if venv_python(d).exists():
            return d
    return None


def create_venv(target_root: Path) -> Path:
    """Create `.venv-tokens` in target_root via `python3 -m venv`.

    Refuses to overwrite a pre-existing path (it may be a partial venv we
    don't want to clobber). Returns the venv directory; caller should
    follow up with `pip install` of dependencies.
    """
    venv_dir = target_root / ".claude" / ".venv-tokens"
    if venv_dir.exists():
        raise FileExistsError(
            f"{venv_dir} already exists; pass --venv {venv_dir} to use it "
            "or remove it before re-running with --create-venv"
        )
    print(f"  Creating venv: {venv_dir}")
    subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])
    py = venv_python(venv_dir)
    pip_bin = venv_dir / ("Scripts" if sys.platform == "win32" else "bin") / "pip"
    if not pip_bin.exists():
        subprocess.check_call([str(py), "-m", "ensurepip", "--upgrade"])
    return venv_dir


def _looks_suspicious(target: Path) -> str | None:
    """Return a human description if the auto-derived target looks wrong.

    Triggered when less_tokens is cloned somewhere weird — e.g. directly in
    $HOME or at the filesystem root — so the parent-of-source default would
    splatter the install across an unintended directory. Returns None for
    normal project-shaped parents.
    """
    home = Path.home().resolve()
    if target == Path("/").resolve():
        return "filesystem root"
    if target == home:
        return "your home directory"
    return None


# ---------------------------------------------------------------------------
# File copy helpers
# ---------------------------------------------------------------------------

_SKIP_PARTS = {"__pycache__"}


def _diff_summary(src_text: str, dst_text: str) -> str:
    """Return a compact diff stat line: +N -M lines."""
    src_lines = src_text.splitlines(keepends=True)
    dst_lines = dst_text.splitlines(keepends=True)
    diff = list(difflib.unified_diff(dst_lines, src_lines, lineterm=""))
    added = sum(1 for ln in diff if ln.startswith("+") and not ln.startswith("+++"))
    removed = sum(1 for ln in diff if ln.startswith("-") and not ln.startswith("---"))
    return f"+{added} -{removed} lines vs source"


def copy_tree(
    src: Path,
    dst: Path,
    target_root: Path,
    force: bool,
    overwrite_modified: bool,
    label: str,
    exclude: frozenset[str] = frozenset(),
    dry_run: bool = False,
) -> int:
    """Copy a directory tree. Returns count of files copied.

    Without --force: skip all existing files (safe default).
    With --force: overwrite files that are identical to the source; warn and
                  skip files that differ (they have local edits).
    With --force + --overwrite-modified: overwrite everything, printing a
                  diff summary for any locally-modified file.
    With dry_run: print every action prefixed but write nothing.
    """
    if not src.exists():
        print(f"  {label}: source missing — {src}", file=sys.stderr)
        return 0
    copied = skipped = modified_skipped = 0
    if not dry_run:
        dst.mkdir(parents=True, exist_ok=True)
    for srcfile in src.rglob("*"):
        if srcfile.is_dir():
            continue
        rel = srcfile.relative_to(src)
        if any(p.startswith(".") or p in _SKIP_PARTS for p in rel.parts):
            continue
        if srcfile.suffix in (".pyc", ".pyo"):
            continue
        if srcfile.name in exclude:
            continue
        target = dst / rel
        if target.exists():
            if not force:
                print(f"  ! skip (exists): {target.relative_to(target_root)}")
                skipped += 1
                continue
            src_text = srcfile.read_text(encoding="utf-8", errors="replace")
            dst_text = target.read_text(encoding="utf-8", errors="replace")
            if src_text == dst_text:
                skipped += 1  # identical — nothing to do
                continue
            # File differs from source (locally modified)
            rel_str = target.relative_to(target_root)
            summary = _diff_summary(src_text, dst_text)
            if overwrite_modified:
                if not dry_run:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(srcfile, target)
                verb = "would overwrite" if dry_run else "overwritten"
                print(f"  ↺ {rel_str}  ({summary}, {verb})")
                copied += 1
            else:
                print(f"  ! {rel_str}  ({summary}) — differs from source; "
                      f"add --overwrite-modified to update")
                modified_skipped += 1
        else:
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(srcfile, target)
            prefix = "+ (would create)" if dry_run else "+"
            print(f"  {prefix} {target.relative_to(target_root)}")
            copied += 1
    print(f"  {label}: {copied} copied, {skipped + modified_skipped} skipped"
          + (f" ({modified_skipped} modified)" if modified_skipped else ""))
    return copied


# ---------------------------------------------------------------------------
# search_config.py — variable-level upsert
# ---------------------------------------------------------------------------

def _top_level_assignments(text: str) -> dict[str, tuple[int, int]]:
    """Parse top-level assignments; return {name: (start_line, end_line)} (1-indexed)."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    result: dict[str, tuple[int, int]] = {}
    for node in tree.body:
        name: str | None = None
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    name = t.id
                    break
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                name = node.target.id
        if name:
            result[name] = (node.lineno, getattr(node, "end_lineno", node.lineno))
    return result


def _extract_block(lines: list[str], lineno: int, end_lineno: int | None = None) -> str:
    """Extract an assignment block, including any immediately-preceding comment lines."""
    idx = lineno - 1  # convert to 0-indexed
    end_idx = (end_lineno if end_lineno is not None else lineno) - 1  # 0-indexed inclusive
    comment_start = idx
    while comment_start > 0 and lines[comment_start - 1].strip().startswith("#"):
        comment_start -= 1
    return "\n".join(lines[comment_start:end_idx + 1])


def merge_search_config(src_file: Path, dst_file: Path, dry_run: bool = False) -> list[str]:
    """Inject variables present in src but absent in dst. Returns added names."""
    src_text = src_file.read_text(encoding="utf-8")
    dst_text = dst_file.read_text(encoding="utf-8")

    src_vars = _top_level_assignments(src_text)
    dst_vars = _top_level_assignments(dst_text)

    if not src_vars:
        print("  ! search_config.py: could not parse source; skipping merge",
              file=sys.stderr)
        return []

    src_lines = src_text.splitlines()
    missing = {
        name: _extract_block(src_lines, lineno, end_lineno)
        for name, (lineno, end_lineno) in src_vars.items()
        if name not in dst_vars
    }
    if not missing:
        return []

    if not dry_run:
        with dst_file.open("a", encoding="utf-8") as f:
            f.write("\n\n# --- Added by less_tokens installer ---\n")
            for block in missing.values():
                f.write(block + "\n")
    return list(missing.keys())


def _venv_py_assign(tree: ast.Module) -> ast.Assign | None:
    """Find the top-level `VENV_PY = _venv_python(...)` assignment, if any."""
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id == "VENV_PY":
                return node
    return None


def _venv_py_arg(assign: ast.Assign) -> str | None:
    """Return the string arg of `_venv_python("X")`, or None if shape doesn't match."""
    v = assign.value
    if not (isinstance(v, ast.Call)
            and isinstance(v.func, ast.Name)
            and v.func.id == "_venv_python"
            and len(v.args) == 1
            and isinstance(v.args[0], ast.Constant)
            and isinstance(v.args[0].value, str)):
        return None
    return v.args[0].value


def _venv_config_str(venv_dir: Path, target_root: Path) -> str:
    """Render venv_dir for VENV_PY: relative to target_root when possible."""
    try:
        return venv_dir.relative_to(target_root).as_posix()
    except ValueError:
        return str(venv_dir).replace("\\", "/")


def _venv_python_call(path_str: str) -> str:
    """`_venv_python(<literal>)` with the path as a safely-escaped string.

    json.dumps yields a valid Python string literal even when the path
    contains a quote or backslash, so the written config never has a
    SyntaxError and the printed next-steps line is safe to paste verbatim.
    For ordinary paths it is byte-identical to the old `"{path}"` form.
    """
    return f"_venv_python({json.dumps(path_str)})"


def _rel_or_abs(path: Path, target_root: Path) -> str:
    try:
        return path.relative_to(target_root).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


def launcher_rel(agent: str) -> Path:
    if agent == "codex":
        return Path(".less_tokens") / "bin" / "python"
    return Path(".claude") / "bin" / "python"


def launcher_cmd(agent: str, target_root: Path) -> str:
    rel = launcher_rel(agent)
    if sys.platform == "win32":
        rel = rel.with_suffix(".cmd")
    return rel.as_posix()


def write_python_launcher(
    target_root: Path,
    rel: Path,
    venv_py: Path,
    dry_run: bool = False,
) -> int:
    """Write a tiny venv-backed launcher plus Windows .cmd sibling."""
    launcher = target_root / rel
    cmd_launcher = launcher.with_suffix(".cmd")
    venv_str = _rel_or_abs(venv_py, target_root)

    if Path(venv_str).is_absolute():
        shell_target = shlex.quote(venv_str)
    else:
        shell_target = '"$SCRIPT_DIR/../../' + venv_str.replace('"', '\\"') + '"'
    shell_text = (
        "#!/bin/sh\n"
        "# Generated by less_tokens. Runs the install-selected venv Python.\n"
        'SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\n'
        f'exec {shell_target} "$@"\n'
    )
    venv_cmd = venv_str.replace("/", "\\")
    cmd_text = (
        "@echo off\r\n"
        "REM Generated by less_tokens. Runs the install-selected venv Python.\r\n"
        f'"%~dp0\\..\\..\\{venv_cmd}" %*\r\n'
        if not Path(venv_str).is_absolute()
        else (
            "@echo off\r\n"
            "REM Generated by less_tokens. Runs the install-selected venv Python.\r\n"
            f'"{str(venv_py)}" %*\r\n'
        )
    )

    changes = 0
    for path, text, executable in (
        (launcher, shell_text, True),
        (cmd_launcher, cmd_text, False),
    ):
        rel_path = path.relative_to(target_root)
        if path.exists() and path.read_text(encoding="utf-8", errors="replace") == text:
            print(f"  + {rel_path} (launcher already current)")
            continue
        print(f"  {'would write' if dry_run else '~'} {rel_path}")
        changes += 1
        if not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="")
            if executable:
                path.chmod(0o755)
    return changes


_CODEX_TOOL_SHIM_MARKER = "# Generated by less_tokens. Codex compatibility shim."


def _codex_tool_shim_text(tool_name: str) -> str:
    return f'''#!/usr/bin/env python3
{_CODEX_TOOL_SHIM_MARKER}
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

os.environ.setdefault("LESS_TOKENS_AGENT", "codex")
BASE = Path(__file__).resolve().parents[2]
REAL = BASE / ".claude" / "tools" / {tool_name!r}
if not REAL.exists():
    raise SystemExit(f"less_tokens shim target missing: {{REAL}}")
sys.path.insert(0, str(REAL.parent))

if __name__ == "__main__":
    runpy.run_path(str(REAL), run_name="__main__")
else:
    _data = runpy.run_path(str(REAL), run_name=f"_less_tokens_real_{{REAL.stem}}")
    for _key, _value in _data.items():
        if _key not in {{"__name__", "__file__", "__cached__", "__loader__", "__package__", "__spec__"}}:
            globals()[_key] = _value
'''


def _is_codex_tool_shim(text: str) -> bool:
    return _CODEX_TOOL_SHIM_MARKER in text


def write_codex_tool_shims(
    source_tools: Path,
    target_root: Path,
    force: bool,
    overwrite_modified: bool,
    dry_run: bool = False,
) -> int:
    """Generate .less_tokens/tools/*.py shims to the single .claude/tools source.

    Existing non-shim files are treated like copy_tree targets: skipped unless
    force is set, and protected unless overwrite_modified is also set.
    """
    dst = target_root / ".less_tokens" / "tools"
    copied = skipped = modified_skipped = 0
    if not dry_run:
        dst.mkdir(parents=True, exist_ok=True)
    for srcfile in sorted(source_tools.glob("*.py")):
        target = dst / srcfile.name
        text = _codex_tool_shim_text(srcfile.name)
        rel = target.relative_to(target_root)
        if target.exists():
            old = target.read_text(encoding="utf-8", errors="replace")
            if old == text:
                skipped += 1
                continue
            if not force:
                print(f"  ! skip (exists): {rel}")
                skipped += 1
                continue
            if not _is_codex_tool_shim(old) and not overwrite_modified:
                summary = _diff_summary(text, old)
                print(f"  ! {rel}  ({summary}) — differs from generated shim; "
                      "add --overwrite-modified to replace")
                modified_skipped += 1
                continue
            if not dry_run:
                target.write_text(text, encoding="utf-8")
                target.chmod(0o755)
            verb = "would overwrite" if dry_run else "overwritten"
            print(f"  ↺ {rel}  ({verb} with shim)")
            copied += 1
        else:
            if not dry_run:
                target.write_text(text, encoding="utf-8")
                target.chmod(0o755)
            prefix = "+ (would create)" if dry_run else "+"
            print(f"  {prefix} {rel}")
            copied += 1
    print(f"  .less_tokens/tools/: {copied} shim(s), {skipped + modified_skipped} skipped"
          + (f" ({modified_skipped} modified)" if modified_skipped else ""))
    return copied


def patch_venv_py(
    config_path: Path,
    src_config: Path,
    target_root: Path,
    venv_dir: Path,
    dry_run: bool = False,
) -> str | None:
    """Rewrite VENV_PY in search_config.py to point at the detected venv.

    Only patches when the existing value matches the source default — user
    customizations are preserved. Returns the new venv-path string when a
    change is written; None on no-op or when the user has customized.

    Limitation: once patched the value no longer matches the source default,
    so a later run with a different auto-detected venv won't re-patch. Users
    who switch venvs should edit search_config.py by hand, or delete the
    VENV_PY line entirely (the variable-level merge will re-inject the
    default, and the next install will patch it).
    """
    try:
        dst_text = config_path.read_text(encoding="utf-8")
        dst_tree = ast.parse(dst_text)
        src_tree = ast.parse(src_config.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return None

    dst_assign = _venv_py_assign(dst_tree)
    src_assign = _venv_py_assign(src_tree)
    if dst_assign is None or src_assign is None:
        return None

    dst_arg = _venv_py_arg(dst_assign)
    src_arg = _venv_py_arg(src_assign)
    if dst_arg is None or src_arg is None or dst_arg != src_arg:
        return None  # user customized — leave alone

    venv_str = _venv_config_str(venv_dir, target_root)

    if venv_str == dst_arg:
        return None  # already correct

    lines = dst_text.splitlines(keepends=True)
    start = dst_assign.lineno - 1            # 0-indexed
    end = dst_assign.end_lineno              # 1-indexed, inclusive
    new_line = f"VENV_PY = {_venv_python_call(venv_str)}\n"
    new_text = "".join(lines[:start]) + new_line + "".join(lines[end:])
    if new_text == dst_text:
        return None
    if not dry_run:
        config_path.write_text(new_text, encoding="utf-8")
    return venv_str


_SOURCE_DIR_EXCLUDE = frozenset({
    ".git", ".venv", ".venv-tokens", "venv", "env", "__pycache__",
    "node_modules", "build", "dist", ".tox", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "htmlcov", "site-packages",
})

_DEFAULT_INDEXED_SOURCE_DIRS = ()


def _discover_source_dirs(target_root: Path) -> list[str]:
    """Top-level directories under target_root that contain any `.py` file.

    Skips hidden dirs (including .claude/), venvs, caches, and any
    directory that is itself a git repo (has a .git entry) — those are
    sibling repos, not source dirs of the host project. Returns paths
    with a trailing slash to match INDEXED_SOURCE_DIRS conventions,
    alpha-sorted.
    """
    found: list[str] = []
    try:
        for child in sorted(target_root.iterdir()):
            if not child.is_dir():
                continue
            name = child.name
            if name.startswith(".") or name in _SOURCE_DIR_EXCLUDE:
                continue
            # Skip directories that are themselves separate git repos.
            if (child / ".git").exists():
                continue
            try:
                has_py = next(child.rglob("*.py"), None) is not None
            except OSError:
                continue
            if has_py:
                found.append(f"{name}/")
    except OSError:
        return []
    return found


def patch_indexed_source_dirs(
    config_path: Path, target_root: Path, dry_run: bool = False,
) -> tuple[str, ...] | None:
    """Rewrite INDEXED_SOURCE_DIRS in search_config.py for the host repo.

    Conservative — same posture as patch_venv_py: only patches when the
    existing value matches the source default (empty tuple). User
    customizations are preserved.

    Returns the new tuple (sorted) on a successful write, or None if:
    - the existing value is customized
    - no host directories contain .py files
    - the discovered set equals the current value (already correct)
    """
    try:
        text = config_path.read_text(encoding="utf-8")
        tree = ast.parse(text)
    except (OSError, SyntaxError):
        return None

    current: tuple[str, ...] | None = None
    target_node = None
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                and node.target.id == "INDEXED_SOURCE_DIRS":
            target_node = node
            if isinstance(node.value, ast.Tuple):
                try:
                    current = tuple(
                        el.value for el in node.value.elts
                        if isinstance(el, ast.Constant) and isinstance(el.value, str)
                    )
                except AttributeError:
                    current = None
            break
    if target_node is None or current is None:
        return None
    if current != _DEFAULT_INDEXED_SOURCE_DIRS:
        return None  # user customized — leave alone

    discovered = tuple(_discover_source_dirs(target_root))
    if not discovered or discovered == current:
        return None

    lines = text.splitlines(keepends=True)
    start = target_node.lineno - 1
    end = target_node.end_lineno
    rendered = ", ".join(f'"{d}"' for d in discovered)
    new_line = f"INDEXED_SOURCE_DIRS: tuple[str, ...] = ({rendered},)\n"
    new_text = "".join(lines[:start]) + new_line + "".join(lines[end:])
    if not dry_run:
        config_path.write_text(new_text, encoding="utf-8")
    return discovered


def handle_search_config(
    src_config: Path,
    dst_config: Path,
    target_root: Path,
    force_config: bool,
    overwrite_modified: bool,
    dry_run: bool = False,
) -> None:
    """Copy or merge search_config.py into the target project."""
    rel = dst_config.relative_to(target_root)
    if not dst_config.exists():
        if not dry_run:
            dst_config.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_config, dst_config)
        print(f"  {'+ (would create)' if dry_run else '+'} {rel}")
        return

    # Full overwrite only when force_config + overwrite_modified both set
    if force_config and overwrite_modified:
        src_text = src_config.read_text(encoding="utf-8")
        dst_text = dst_config.read_text(encoding="utf-8")
        if src_text == dst_text:
            print(f"  + {rel} (already matches source)")
        else:
            summary = _diff_summary(src_text, dst_text)
            if not dry_run:
                shutil.copy2(src_config, dst_config)
            verb = "would replace" if dry_run else "replaced"
            print(f"  ↺ {rel}  ({summary}, {verb} by --force-config --overwrite-modified)")
        return

    # Default path: variable-level upsert
    added = merge_search_config(src_config, dst_config, dry_run=dry_run)
    if added:
        verb = "would inject" if dry_run else "injected"
        print(f"  ~ {rel}: {verb} new variables: {', '.join(added)}")
    else:
        print(f"  + {rel}: all variables present")


# ---------------------------------------------------------------------------
# Settings.local.json — idempotent hook wiring
# ---------------------------------------------------------------------------

def build_claude_hook_entries(venv_py: Path, target_root: Path, args: argparse.Namespace) -> list[tuple[str, str, str]]:
    """Return (event_type, matcher, command) tuples for all hooks to wire.

    The venv python path is rendered relative to target_root when possible
    so that re-runs produce string-identical commands regardless of whether
    the user passed --venv with a relative or absolute path (or relied on
    auto-detect, which always returns absolute). Without this, the
    idempotency check in wire_settings() would see two commands as
    different and add duplicate entries.
    """
    py = launcher_cmd("claude", target_root)
    entries: list[tuple[str, str, str]] = [
        ("PreToolUse",  "Read|Grep|Glob|Bash", f"{py} .claude/hooks/budget-observer.py"),
        ("PostToolUse", "Read|Bash|Edit|Write", f"{py} .claude/hooks/budget-observer.py"),
        ("PreToolUse",  "Read",          f"{py} .claude/hooks/search-first.py"),
        ("PreToolUse",  "Grep",          f"{py} .claude/hooks/search-first.py"),
        ("PreToolUse",  "Read",          f"{py} .claude/hooks/read-guard.py"),
        ("PreToolUse",  "Read",          f"{py} .claude/hooks/auto-slice.py"),
        ("PreToolUse",  "Read",          f"{py} .claude/hooks/grep-first-read.py"),
        ("PreToolUse",  "Read",          f"{py} .claude/hooks/read-after-edit.py"),
        ("PreToolUse",  "Read|Grep",      f"{py} .claude/hooks/context-cache.py"),
        ("PostToolUse", "Edit|Write",    f"{py} .claude/hooks/post-edit-diff.py"),
        ("PostToolUse", "Edit|Write",    f"{py} .claude/hooks/index-refresh.py"),
        ("PostToolUse", "Edit|Write",    f"{py} .claude/hooks/claudemd-budget.py"),
        ("PostToolUse", "Bash",          f"{py} .claude/hooks/lean-output.py"),
        ("PreToolUse",  "Bash",          f"{py} .claude/hooks/listing-guard.py"),
    ]
    if getattr(args, "truncate", False):
        entries.append(("PostToolUse", "Bash|Read|WebFetch|Glob",
                         f"{py} .claude/hooks/truncate-output.py"))
    if getattr(args, "compact", False):
        entries.append(("PostToolUse", ".*",
                         f"{py} .claude/hooks/compact-trigger.py"))
    if getattr(args, "caveman", False):
        entries.append(("Stop", "",
                         f"{py} .claude/hooks/caveman-reminder.py"))
    return entries


_build_hook_entries = build_claude_hook_entries  # backward compat


def build_codex_hook_entries(
    venv_py: Path,
    target_root: Path,
    args: argparse.Namespace,
) -> list[tuple[str, str, str]]:
    py = launcher_cmd("codex", target_root)
    prefix = f"LESS_TOKENS_AGENT=codex {py}"
    entries: list[tuple[str, str, str]] = [
        ("PreToolUse",  "mcp__filesystem__.*|Bash", f"{prefix} .codex/hooks/budget-observer.py"),
        ("PostToolUse", "Bash|mcp__filesystem__.*|apply_patch|Edit|Write", f"{prefix} .codex/hooks/budget-observer.py"),
        ("PreToolUse",  "mcp__filesystem__.*",    f"{prefix} .codex/hooks/search-first.py"),
        ("PreToolUse",  "mcp__filesystem__.*",    f"{prefix} .codex/hooks/read-guard.py"),
        ("PreToolUse",  "mcp__filesystem__.*",    f"{prefix} .codex/hooks/auto-slice.py"),
        ("PreToolUse",  "mcp__filesystem__.*",    f"{prefix} .codex/hooks/grep-first-read.py"),
        ("PreToolUse",  "mcp__filesystem__.*",    f"{prefix} .codex/hooks/read-after-edit.py"),
        ("PreToolUse",  "mcp__filesystem__.*",    f"{prefix} .codex/hooks/context-cache.py"),
        ("PreToolUse",  "Bash",                   f"{prefix} .codex/hooks/listing-guard.py"),
        ("PostToolUse", "Bash",                   f"{prefix} .codex/hooks/lean-output.py"),
        ("PostToolUse", "apply_patch|Edit|Write", f"{prefix} .codex/hooks/post-edit-diff.py"),
        ("PostToolUse", "apply_patch|Edit|Write", f"{prefix} .codex/hooks/index-refresh.py"),
        ("PostToolUse", "Edit|Write",             f"{prefix} .codex/hooks/agentsmd-budget.py"),
    ]
    if getattr(args, "truncate", False):
        entries.append(("PostToolUse", "Bash|mcp__filesystem__.*",
                         f"{prefix} .codex/hooks/truncate-output.py"))
    if getattr(args, "compact", False):
        entries.append(("PostToolUse", ".*", f"{prefix} .codex/hooks/compact-trigger.py"))
    if getattr(args, "caveman", False):
        entries.append(("PostToolUse", ".*", f"{prefix} .codex/hooks/terse-reminder.py"))
    return entries


def wire_settings(
    settings_path: Path,
    entries: list[tuple[str, str, str]],
    dry_run: bool = False,
) -> tuple[int, int]:
    """Merge hook entries into the target settings file. Returns (added, already_present)."""
    if settings_path.exists():
        try:
            settings: dict = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            settings = {}
    else:
        settings = {}

    hooks: dict = settings.setdefault("hooks", {})
    added = already_present = 0

    for event_type, matcher, command in entries:
        event_list: list = hooks.setdefault(event_type, [])
        found = any(
            h.get("command") == command
            for entry in event_list
            if entry.get("matcher") == matcher
            for h in entry.get("hooks", [])
        )
        if found:
            print(f"  + {event_type} {matcher!r} already wired")
            already_present += 1
        else:
            event_list.append({
                "matcher": matcher,
                "hooks": [{"type": "command", "command": command}],
            })
            print(f"  {'+ (would wire)' if dry_run else '+'} {event_type} {matcher!r}")
            added += 1

    if not dry_run:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return added, already_present


wire_claude_settings = wire_settings  # alias for agent-aware callers


def wire_codex_hooks_json(
    hooks_json_path: Path,
    entries: list[tuple[str, str, str]],
    dry_run: bool = False,
) -> tuple[int, int]:
    """Merge hook entries into .codex/hooks.json. Returns (added, already_present)."""
    if hooks_json_path.exists():
        try:
            data: dict = json.loads(hooks_json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}

    hooks: list = data.setdefault("hooks", [])
    added = already_present = 0

    for event_type, matcher, command in entries:
        found = any(
            h.get("command") == command and h.get("event") == event_type
            for h in hooks
        )
        if found:
            print(f"  + {event_type} {matcher!r} already wired (codex)")
            already_present += 1
        else:
            hooks.append({"event": event_type, "matcher": matcher,
                          "command": command})
            print(f"  {'+ (would wire)' if dry_run else '+'} codex {event_type} {matcher!r}")
            added += 1

    if not dry_run and added:
        hooks_json_path.parent.mkdir(parents=True, exist_ok=True)
        hooks_json_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return added, already_present


def unwire_codex_hooks_json(hooks_json_path: Path, source: Path, dry_run: bool) -> int:
    """Strip less_tokens hook entries from .codex/hooks.json. Returns count removed."""
    if not hooks_json_path.exists():
        return 0
    try:
        data = json.loads(hooks_json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0
    hooks = data.get("hooks")
    if not isinstance(hooks, list):
        return 0
    names = _our_hook_names(source, agents={"codex"})
    keep = [h for h in hooks if not any(
        f"hooks/{n}" in h.get("command", "") or f"hooks\\{n}" in h.get("command", "")
        for n in names
    )]
    removed = len(hooks) - len(keep)
    if removed:
        print(f"  {'would unwire' if dry_run else '-'} .codex/hooks.json: "
              f"{removed} less_tokens hook entr{'y' if removed == 1 else 'ies'}")
        if not dry_run:
            data["hooks"] = keep
            hooks_json_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return removed


# ---------------------------------------------------------------------------
# Subprocess steps
# ---------------------------------------------------------------------------

def _deps_already_present(venv_py: Path) -> bool:
    """True iff fastembed + numpy both import successfully in the venv."""
    try:
        subprocess.check_call(
            [str(venv_py), "-c", "import fastembed, numpy"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


def install_deps(venv_py: Path, dry_run: bool = False) -> tuple[int, bool]:
    """Install fastembed + numpy. Returns (exit_code, did_install)."""
    if _deps_already_present(venv_py):
        print(f"\n[3/5] fastembed + numpy already importable in {venv_py} — skipping pip install.")
        return 0, False
    if dry_run:
        print(f"\n[3/5] [DRY RUN] would pip install fastembed + numpy into {venv_py}.")
        return 0, True
    print(f"\n[3/5] Installing fastembed + numpy into {venv_py}...")
    try:
        subprocess.check_call(
            [str(venv_py), "-m", "pip", "install", "--quiet", "fastembed", "numpy"]
        )
        print("  OK")
        return 0, True
    except subprocess.CalledProcessError as e:
        print(f"  pip install failed (exit {e.returncode})", file=sys.stderr)
        return 1, False


def _index_db_at_current_schema(target_root: Path) -> bool:
    """True iff index.db exists and schema_version reports the current version."""
    db = target_root / ".claude" / "index.db"
    if not db.exists():
        return False
    try:
        import sqlite3
        with sqlite3.connect(str(db)) as c:
            row = c.execute("SELECT MAX(version) FROM schema_version").fetchone()
            return bool(row and row[0] == _INDEX_SCHEMA_VERSION)
    except sqlite3.Error:
        return False


def init_db(venv_py: Path, target_root: Path, dry_run: bool = False) -> tuple[int, bool]:
    """Initialize / migrate index.db. Returns (exit_code, did_init)."""
    if _index_db_at_current_schema(target_root):
        print("\n[4/5] index.db already initialized — skipping init.")
        return 0, False
    if dry_run:
        print("\n[4/5] [DRY RUN] would initialize / migrate index.db.")
        return 0, True
    print("\n[4/5] Initializing / migrating index.db...")
    try:
        subprocess.check_call(
            [str(venv_py), ".claude/tools/db.py", "init"], cwd=target_root
        )
        return 0, True
    except subprocess.CalledProcessError as e:
        print(f"  db init failed (exit {e.returncode})", file=sys.stderr)
        return 1, False


def build_index(venv_py: Path, target_root: Path, dry_run: bool = False) -> int:
    if dry_run:
        print("\n[DRY RUN] would build initial embeddings index "
              "(first real run downloads ~130 MB model).")
        return 0
    print("\nBuilding initial embeddings (first run downloads ~130 MB model)...")
    try:
        subprocess.check_call(
            [str(venv_py), ".claude/tools/embeddings.py", "refresh"], cwd=target_root
        )
    except subprocess.CalledProcessError as e:
        print(f"  refresh failed (exit {e.returncode})", file=sys.stderr)
        return 1
    # Smoke check: confirm the just-built index is queryable. Catches an
    # empty / broken index at install time instead of on first search.
    # `stats` is preferred over `health` because health exits non-zero on
    # any coverage gap (legitimate for a host repo whose source dirs
    # haven't been customized yet).
    print("\nVerifying index is queryable...")
    try:
        subprocess.check_call(
            [str(venv_py), ".claude/tools/embeddings.py", "stats"], cwd=target_root
        )
    except subprocess.CalledProcessError as e:
        print(f"  smoke check failed (exit {e.returncode}); "
              f"index may be empty or unreadable", file=sys.stderr)
        return 1
    return 0


# ---------------------------------------------------------------------------
# Caveman duplicate check
# ---------------------------------------------------------------------------

def _maybe_suggest_recursive_globs(target_root: Path) -> None:
    """If the target has few/no root *.py but many subdir *.md, nudge the
    user toward a recursive INDEXED_ROOT_GLOBS so docs aren't silently
    skipped. Heuristic only — purely informational, never aborts."""
    try:
        py_count = sum(1 for _ in target_root.rglob("*.py")
                       if ".venv" not in _.parts and "__pycache__" not in _.parts)
        md_root = list(target_root.glob("*.md"))
        md_sub = [p for p in target_root.rglob("*.md")
                  if p.parent != target_root and ".venv" not in p.parts]
    except OSError:
        return
    if py_count == 0 and len(md_sub) >= 5 and len(md_sub) > len(md_root):
        print(f"\n  Tip: found {len(md_sub)} markdown files in subdirectories "
              "but no .py at the repo root.")
        print('       Consider INDEXED_ROOT_GLOBS = ("**/*.md",) to index them all.')


_CM_START = "<!-- less_tokens:caveman:begin -->"
_CM_END = "<!-- less_tokens:caveman:end -->"


def _caveman_in_claude_md(target_root: Path) -> bool:
    claude_md = target_root / "CLAUDE.md"
    if not claude_md.exists():
        return False
    text = claude_md.read_text(encoding="utf-8", errors="replace")
    return _CM_START in text or "Caveman Mode" in text


def handle_caveman_claude_md(target_root: Path, dry_run: bool) -> int:
    """Idempotently append the caveman block to target_root/CLAUDE.md. Returns change count."""
    claude_md = target_root / "CLAUDE.md"
    caveman_src = SOURCE / ".claude" / "rules" / "caveman.md"

    if not caveman_src.exists():
        print("  ! caveman.md source not found; skipping CLAUDE.md append", file=sys.stderr)
        return 0

    text = claude_md.read_text(encoding="utf-8") if claude_md.exists() else ""
    if _CM_START in text or "Caveman Mode" in text:
        print("  + CLAUDE.md: caveman section already present")
        return 0

    caveman_body = caveman_src.read_text(encoding="utf-8")
    block = f"\n{_CM_START}\n{caveman_body.rstrip()}\n{_CM_END}\n"

    if not claude_md.exists():
        new = f"# CLAUDE.md\n{block}"
        verb = "would create" if dry_run else "~"
        print(f"\n  {verb} CLAUDE.md (with caveman block)")
    else:
        sep = "" if text.endswith("\n") else "\n"
        new = text + sep + block
        verb = "would update" if dry_run else "~"
        print(f"\n  {verb} CLAUDE.md (appended caveman block)")

    if not dry_run:
        claude_md.write_text(new, encoding="utf-8")
    return 1


def _remove_caveman_block(claude_md: Path, dry_run: bool) -> bool:
    if not claude_md.exists():
        return False
    text = claude_md.read_text(encoding="utf-8")
    if _CM_START not in text or _CM_END not in text:
        return False
    lines = text.splitlines(keepends=True)
    start = next(i for i, ln in enumerate(lines) if ln.strip() == _CM_START)
    end = next(i for i, ln in enumerate(lines) if ln.strip() == _CM_END)
    lead = start
    if lead > 0 and lines[lead - 1].strip() == "":
        lead -= 1
    tail = end + 1
    if tail < len(lines) and lines[tail].strip() == "":
        tail += 1
    new = "".join(lines[:lead] + lines[tail:])
    print(f"  {'would remove' if dry_run else '-'} CLAUDE.md: managed caveman block")
    if not dry_run:
        if new.strip():
            claude_md.write_text(new, encoding="utf-8")
        else:
            claude_md.unlink()
    return True


# ---------------------------------------------------------------------------
# Tree enumeration (shared by collision check and uninstall)
# ---------------------------------------------------------------------------

def _iter_tree_files(src: Path, exclude: frozenset[str] = frozenset()):
    """Yield source files copy_tree would deploy, applying the same skip rules."""
    if not src.is_dir():
        return
    for f in src.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(src)
        if any(p.startswith(".") or p in _SKIP_PARTS for p in rel.parts):
            continue
        if f.suffix in (".pyc", ".pyo"):
            continue
        if f.name in exclude:
            continue
        yield rel


# Trees the installer deploys, as (source_subdir, dest_relpath, exclude).
# Mirrors the copy calls in main(); search_config.py is excluded from the
# tools tree because it is handled (and, on uninstall, preserved) separately.
def _install_specs(
    caveman: bool,
    agents: set[str] | None = None,
    target_root: Path | None = None,
) -> list[tuple[str, str, frozenset[str]]]:
    if agents is None:
        agents = {"claude"}
    specs: list[tuple[str, str, frozenset[str]]] = [
        (".less_tokens/config", ".less_tokens/config", frozenset()),
        (".less_tokens/tools", ".less_tokens/tools", frozenset()),
        ("agents/common/budget", ".less_tokens/hooks/budget", frozenset()),
        (".claude/tools",  ".claude/tools",  frozenset({"search_config.py"})),
        (".claude/schema", ".claude/schema", frozenset()),
        (".claude/skills/claudemd", ".claude/skills/claudemd", frozenset()),
    ]
    if "claude" in agents:
        specs.append((".claude/hooks", ".claude/hooks", frozenset()))
        specs.append(("agents/common/hooks", ".claude/hooks/common", frozenset()))
    if caveman and "claude" in agents:
        specs.append((".claude/rules", ".claude/rules", frozenset()))
    if "codex" in agents:
        specs.append((".claude/schema", ".less_tokens/schema", frozenset()))
        specs.append(("agents/common/hooks", ".less_tokens/hooks", frozenset()))
        if target_root is not None and _dir_is_writable(target_root, ".codex"):
            specs.append(("agents/codex/hooks", ".codex/hooks", frozenset()))
        skill_root = (
            ".agents/skills"
            if target_root is not None and _dir_is_writable(target_root, ".agents")
            else ".less_tokens/skills"
        )
        for skill_dir in sorted((SOURCE / "agents" / "codex" / "skills").iterdir()):
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                specs.append((
                    f"agents/codex/skills/{skill_dir.name}",
                    f"{skill_root}/{skill_dir.name}",
                    frozenset(),
                ))
    return specs


def _foreign_files(source: Path, target_root: Path, caveman: bool, agents: set[str] | None = None) -> list[str]:
    """Host-owned files sitting in a tree we would merge into.

    Only runs on a fresh install (no install.json yet) — on re-install the
    files in tools/schema are ours. .claude/hooks/ and .claude/rules/ are
    intentionally NOT gated: they are shared directories where we add our
    files alongside the host's own, and copy_tree already skips existing ones.
    """
    # Previously installed — all files in those dirs are ours.
    if (target_root / _INSTALL_STATE_PATH).exists():
        return []

    foreign: list[str] = []
    for sub, dst_rel, excl in _install_specs(caveman, agents, target_root):
        if any(seg in sub for seg in ("hooks", "rules", "skills")):
            continue  # shared dirs — host files allowed
        dst_base = target_root / dst_rel
        if not dst_base.is_dir():
            continue
        # Build the set of filenames less_tokens would deploy here.
        our_names: set[str] = (
            {rel.name for rel in _iter_tree_files(source / sub, excl)} | excl
        )
        for f in dst_base.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(target_root)
            if any(p.startswith(".") or p in _SKIP_PARTS for p in rel.parts):
                continue
            if f.name not in our_names:
                foreign.append(str(rel))
    return foreign


def _deployed_targets(source: Path, target_root: Path, caveman: bool, agents: set[str] | None = None) -> list[Path]:
    """Destination files less_tokens deploys (excludes user-owned search_config.py)."""
    out: list[Path] = []
    selected = agents if agents is not None else {"claude"}
    for sub, dst_rel, excl in _install_specs(caveman, agents, target_root):
        src_dir = source / sub
        if not src_dir.exists():
            continue
        base = target_root / dst_rel
        for rel in _iter_tree_files(src_dir, excl):
            out.append(base / rel)
    if "codex" in selected:
        for srcfile in sorted((source / ".claude" / "tools").glob("*.py")):
            out.append(target_root / ".less_tokens" / "tools" / srcfile.name)
    return out


# ---------------------------------------------------------------------------
# .gitignore management (keep generated artifacts out of the host repo)
# ---------------------------------------------------------------------------

_GI_START = "# >>> less_tokens (generated artifacts) >>>"
_GI_END = "# <<< less_tokens <<<"
_GI_PATHS = ["/.claude/index.db", "/.claude/index.db-wal", "/.claude/index.db-shm", "/.claude/state/", "/.less_tokens/state/"]


def _gitignore_block() -> str:
    return "\n".join([_GI_START, *_GI_PATHS, _GI_END]) + "\n"


def handle_gitignore(target_root: Path, want: bool, dry_run: bool) -> int:
    """Add a managed .gitignore block for generated artifacts. Returns change count.

    No-op (with a tip) unless `want` and target_root is a git repo. Idempotent:
    a present managed block is left untouched.
    """
    if not (target_root / ".git").exists():
        return 0
    gi = target_root / ".gitignore"
    text = gi.read_text(encoding="utf-8") if gi.exists() else ""
    if _GI_START in text:
        print("  + .gitignore: less_tokens block already present")
        return 0
    if not want:
        print("\n  Note: --no-gitignore set; .claude/index.db and .claude/state/ will "
              "show as untracked in this git repo unless you add them to "
              ".gitignore yourself or commit them deliberately.")
        return 0
    sep = "" if (not text or text.endswith("\n")) else "\n"
    new = text + sep + ("\n" if text else "") + _gitignore_block()
    verb = "would update" if dry_run else "~"
    print(f"\n  {verb} .gitignore (managed less_tokens block)")
    if not dry_run:
        gi.write_text(new, encoding="utf-8")
    return 1


def _remove_gitignore_block(gi: Path, dry_run: bool) -> bool:
    if not gi.exists():
        return False
    text = gi.read_text(encoding="utf-8")
    if _GI_START not in text or _GI_END not in text:
        return False
    lines = text.splitlines(keepends=True)
    start = next(i for i, ln in enumerate(lines) if ln.strip() == _GI_START)
    end = next(i for i, ln in enumerate(lines) if ln.strip() == _GI_END)
    # Drop the block, one immediately-preceding blank, and one immediately-following blank.
    lead = start
    if lead > 0 and lines[lead - 1].strip() == "":
        lead -= 1
    tail = end + 1
    if tail < len(lines) and lines[tail].strip() == "":
        tail += 1
    new = "".join(lines[:lead] + lines[tail:])
    print(f"  {'would remove' if dry_run else '-'} .gitignore: managed less_tokens block")
    if not dry_run:
        if new.strip():
            gi.write_text(new, encoding="utf-8")
        else:
            gi.unlink()
    return True


# ---------------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------------

def _our_hook_names(source: Path, agents: set[str] | None = None) -> set[str]:
    if agents is None:
        agents = {"claude"}
    names = set[str]()
    if "claude" in agents:
        names |= {rel.name for rel in _iter_tree_files(source / ".claude" / "hooks")}
    if "codex" in agents:
        codex_hooks = source / "agents" / "codex" / "hooks"
        if codex_hooks.exists():
            names |= {rel.name for rel in _iter_tree_files(codex_hooks)}
    return names


def unwire_settings(settings_path: Path, source: Path, dry_run: bool) -> int:
    """Strip less_tokens hook entries from settings.json. Returns count removed."""
    if not settings_path.exists():
        return 0
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return 0
    names = _our_hook_names(source)

    def _is_ours(cmd: str) -> bool:
        # Match per-project hooks (project/.claude/hooks/foo.py) and
        # global hooks (absolute path to source/.claude/hooks/foo.py)
        return any(f"hooks/{n}" in cmd or f"hooks\\{n}" in cmd for n in names)

    removed = 0
    for event_type in list(hooks.keys()):
        kept_entries = []
        for entry in hooks[event_type]:
            inner = entry.get("hooks", [])
            keep = [h for h in inner if not _is_ours(h.get("command", ""))]
            removed += len(inner) - len(keep)
            if keep:
                entry["hooks"] = keep
                kept_entries.append(entry)
        if kept_entries:
            hooks[event_type] = kept_entries
        else:
            del hooks[event_type]
    if not hooks:
        settings.pop("hooks", None)

    if removed:
        print(f"  {'would unwire' if dry_run else '-'} settings.json: "
              f"{removed} less_tokens hook entr{'y' if removed == 1 else 'ies'}")
        if not dry_run:
            settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return removed


def handle_agents_md(fragment_path: Path, target_root: Path, dry_run: bool = False) -> int:
    """Append or update a less_tokens fragment in target_root/AGENTS.md.

    Uses HTML comment sentinels for idempotent management.
    Returns 1 if fragment_path is missing, 0 otherwise.
    """
    if not fragment_path.exists():
        print(f"  · AGENTS.md fragment not found at {fragment_path} — skipped",
              file=sys.stderr)
        return 1

    fragment = fragment_path.read_text(encoding="utf-8").strip()
    begin = "<!-- less_tokens: begin -->"
    end = "<!-- less_tokens: end -->"
    block = f"{begin}\n{fragment}\n{end}\n"

    agents_md = target_root / "AGENTS.md"
    existing = agents_md.read_text(encoding="utf-8") if agents_md.exists() else ""

    if begin in existing:
        # Replace existing block
        import re as _re
        updated = _re.sub(
            rf"{_re.escape(begin)}.*?{_re.escape(end)}\n?",
            block,
            existing,
            flags=_re.DOTALL,
        )
        if updated == existing:
            print("  · AGENTS.md less_tokens block unchanged")
            return 0
        print(f"  {'would update' if dry_run else '~'} AGENTS.md (less_tokens block)")
        if not dry_run:
            agents_md.write_text(updated, encoding="utf-8")
    else:
        new_content = (existing.rstrip("\n") + "\n\n" + block) if existing else block
        print(f"  {'would append' if dry_run else '+'} AGENTS.md (less_tokens block)")
        if not dry_run:
            agents_md.write_text(new_content, encoding="utf-8")
    return 0


def do_uninstall(target_root: Path, args: argparse.Namespace) -> int:
    dry = args.dry_run
    tag = "[DRY RUN] " if dry else ""
    agents = selected_agents(getattr(args, "agent", "claude"))
    print(f"{tag}Uninstalling less_tokens ({', '.join(sorted(agents))}) from {target_root}")
    print(f"Source: {SOURCE}\n")

    removed = 0
    for f in _deployed_targets(SOURCE, target_root, caveman=True, agents=agents):
        if f.exists():
            print(f"  {'would remove' if dry else '-'} {f.relative_to(target_root)}")
            if not dry:
                f.unlink()
            removed += 1

    launcher_agents: set[str] = set()
    if "claude" in agents or agents == {"codex"}:
        launcher_agents.add("claude")
    if "codex" in agents:
        launcher_agents.add("codex")
    for agent in launcher_agents:
        for p in (target_root / launcher_rel(agent), (target_root / launcher_rel(agent)).with_suffix(".cmd")):
            if p.exists():
                print(f"  {'would remove' if dry else '-'} {p.relative_to(target_root)}")
                if not dry:
                    p.unlink()
                removed += 1

    # Prune now-empty directories we created.
    prune_dirs = [".claude/skills/claudemd", ".claude/skills", ".claude/bin"]
    if "claude" in agents:
        prune_dirs += [".claude/tools", ".claude/schema", ".claude/hooks", ".claude/rules"]
    if "codex" in agents:
        prune_dirs += [".codex/hooks", ".codex", ".less_tokens/tools",
                       ".less_tokens/schema", ".less_tokens/hooks",
                       ".less_tokens/bin",
                       ".less_tokens/skills/less-tokens",
                       ".less_tokens/skills", ".less_tokens"]
    for sub in prune_dirs:
        d = target_root / sub
        if d.is_dir() and not any(d.iterdir()):
            print(f"  {'would remove' if dry else '-'} {sub}/ (empty)")
            if not dry:
                d.rmdir()

    if "claude" in agents:
        unwire_settings(target_root / ".claude" / "settings.json", SOURCE, dry)
    if "codex" in agents:
        unwire_codex_hooks_json(target_root / ".codex" / "hooks.json", SOURCE, dry)
    _remove_gitignore_block(target_root / ".gitignore", dry)
    _remove_caveman_block(target_root / "CLAUDE.md", dry)

    if args.purge_index:
        for n in ("index.db", "index.db-wal", "index.db-shm"):
            p = target_root / ".claude" / n
            if p.exists():
                print(f"  {'would remove' if dry else '-'} .claude/{n}")
                if not dry:
                    p.unlink()
                removed += 1
    elif (target_root / ".claude" / "index.db").exists():
        print("  · .claude/index.db preserved (pass --purge-index to also remove it)")

    if (target_root / ".claude" / "tools" / "search_config.py").exists():
        print("  · .claude/tools/search_config.py preserved (may contain your customizations)")

    print(f"\n{tag}Done — {removed} file(s) "
          f"{'would be removed' if dry else 'removed'}.")
    return 0


def do_check(target_root: Path, args: argparse.Namespace) -> int:
    """Verify a previous install is still valid. Prints [✓]/[✗] per check."""
    import subprocess
    agents = selected_agents(getattr(args, "agent", "claude"))
    settings_name = "settings.local.json" if getattr(args, "local", False) else "settings.json"
    ok = True

    def _pass(msg: str) -> None:
        print(f"  [✓] {msg}")

    def _fail(msg: str) -> None:
        nonlocal ok
        ok = False
        print(f"  [✗] {msg}")

    print(f"Checking less_tokens install in {target_root} ({', '.join(sorted(agents))})\n")

    # --- venv / interpreter ---
    tools_dir = target_root / ".claude" / "tools"
    config_path = tools_dir / "search_config.py"
    venv_py: Path | None = None
    if config_path.exists():
        try:
            import importlib.util, types
            spec = importlib.util.spec_from_file_location("_sc_check", config_path)
            assert spec and spec.loader
            sc: types.ModuleType = types.ModuleType("_sc_check")
            spec.loader.exec_module(sc)  # type: ignore[union-attr]
            venv_py = Path(sc.VENV_PY)
            if venv_py.exists():
                _pass(f"VENV_PY resolves: {venv_py}")
            else:
                _fail(f"VENV_PY missing: {venv_py}  — re-run install.py or update search_config.py")
        except Exception as exc:
            _fail(f"Could not load search_config.py: {exc}")
    else:
        _fail(f".claude/tools/search_config.py missing — install not complete")

    # fastembed importable
    if venv_py and venv_py.exists():
        r = subprocess.run([str(venv_py), "-c", "import fastembed"],
                           capture_output=True, text=True)
        if r.returncode == 0:
            _pass("fastembed importable in venv")
        else:
            _fail(f"fastembed not importable — run: {venv_py} -m pip install fastembed")

    # --- index.db ---
    index_db = target_root / ".claude" / "index.db"
    if index_db.exists():
        try:
            import sqlite3
            with sqlite3.connect(str(index_db)) as conn:
                tables = {
                    r[0] for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                table = "documents" if "documents" in tables else "chunks"
                row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()  # noqa: S608
                count = row[0] if row else 0
            if count > 0:
                _pass(f"index.db present with {count} chunk(s)")
            else:
                _fail("index.db exists but has 0 chunks — run embeddings.py refresh")
        except Exception as exc:
            _fail(f"index.db unreadable: {exc}")
    else:
        _fail(".claude/index.db missing — run embeddings.py refresh")

    # --- hook files ---
    hooks_dir = target_root / ".claude" / "hooks"
    if hooks_dir.is_dir():
        hook_files = list(hooks_dir.glob("*.py"))
        if hook_files:
            _pass(f".claude/hooks/ present ({len(hook_files)} script(s))")
        else:
            _fail(".claude/hooks/ exists but contains no .py scripts")
    else:
        _fail(".claude/hooks/ missing — install not complete")

    # --- settings wiring ---
    if "claude" in agents:
        settings_path = target_root / ".claude" / settings_name
        if settings_path.exists():
            try:
                import json as _json
                data = _json.loads(settings_path.read_text(encoding="utf-8"))
                hooks = data.get("hooks", {})
                wired = sum(len(v) for v in hooks.values()) if isinstance(hooks, dict) else 0
                if wired > 0:
                    _pass(f".claude/{settings_name} has {wired} hook entry/entries wired")
                else:
                    _fail(f".claude/{settings_name} has no hooks — re-run install.py")
            except Exception as exc:
                _fail(f"Could not parse .claude/{settings_name}: {exc}")
        else:
            _fail(f".claude/{settings_name} missing — re-run install.py")

    if "codex" in agents:
        codex_launcher = target_root / ".less_tokens" / "bin" / (
            "python.exe" if sys.platform == "win32" else "python"
        )
        if codex_launcher.exists():
            _pass(f".less_tokens/bin/python present: {codex_launcher}")
        else:
            _fail(".less_tokens/bin/python missing — re-run install.py --agent codex")

        codex_config = target_root / ".less_tokens" / "tools" / "search_config.py"
        if codex_config.exists():
            try:
                txt = codex_config.read_text(encoding="utf-8")
                if _is_codex_tool_shim(txt):
                    _pass(".less_tokens/tools/search_config.py shim points to .claude/tools/search_config.py")
                elif "_STATE_AGENT_AWARE" in txt:
                    _fail(".less_tokens/tools/search_config.py is a legacy copied config — re-run install.py --update")
                else:
                    _fail(".less_tokens/tools/search_config.py exists but is not agent-aware — re-run install.py --update")
            except OSError as exc:
                _fail(f"Could not read .less_tokens/tools/search_config.py: {exc}")
        else:
            _fail(".less_tokens/tools/search_config.py missing — re-run install.py --agent codex")

        codex_hooks_dir = target_root / ".codex" / "hooks"
        if codex_hooks_dir.is_dir():
            scripts = list(codex_hooks_dir.glob("*.py"))
            if scripts:
                _pass(f".codex/hooks/ present ({len(scripts)} script(s))")
            else:
                _fail(".codex/hooks/ exists but contains no .py scripts")
        else:
            _fail(".codex/hooks/ missing — Codex hooks are advisory only")

        hooks_json = target_root / ".codex" / "hooks.json"
        if hooks_json.exists():
            try:
                import json as _json
                data = _json.loads(hooks_json.read_text(encoding="utf-8"))
                hooks = data.get("hooks", [])
                if not isinstance(hooks, list):
                    _fail(".codex/hooks.json has unexpected format")
                else:
                    expected = build_codex_hook_entries(venv_py or Path("python"), target_root, args)
                    missing = [
                        (ev, matcher, cmd)
                        for ev, matcher, cmd in expected
                        if not any(h.get("event") == ev and h.get("command") == cmd for h in hooks)
                    ]
                    if missing:
                        names = ", ".join(Path(cmd.split()[-1]).name for _, _, cmd in missing[:5])
                        _fail(f".codex/hooks.json missing {len(missing)} less_tokens hook(s): {names}")
                    else:
                        _pass(f".codex/hooks.json has all {len(expected)} expected less_tokens hook(s)")
            except Exception as exc:
                _fail(f"Could not parse .codex/hooks.json: {exc}")
        else:
            _fail(".codex/hooks.json missing — Codex hooks are not wired")

        agents_md = target_root / "AGENTS.md"
        if agents_md.exists():
            try:
                content = agents_md.read_text(encoding="utf-8")
                if "<!-- less_tokens: begin -->" in content and "Token Discipline" in content:
                    _pass("AGENTS.md contains managed less_tokens block")
                else:
                    _fail("AGENTS.md exists but lacks managed less_tokens block")
            except OSError as exc:
                _fail(f"Could not read AGENTS.md: {exc}")
        else:
            _fail("AGENTS.md missing — Codex guidance not installed")

    # --- smoke query ---
    if venv_py and venv_py.exists() and index_db.exists():
        search_py = tools_dir / "search.py"
        if search_py.exists():
            r = subprocess.run([str(venv_py), str(search_py), "test"],
                               capture_output=True, text=True, cwd=str(target_root))
            if r.returncode == 0:
                _pass("search.py smoke query succeeded")
            else:
                _fail(f"search.py smoke query failed: {r.stderr.strip()[:120]}")

    print()
    if ok:
        print("All checks passed.")
        return 0
    print("One or more checks failed — see [✗] above.")
    return 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # Target selection
    ap.add_argument("--target", type=Path,
                    help="install into PATH instead of the parent of this less_tokens clone")
    ap.add_argument("--yes", action="store_true",
                    help="bypass the suspicious-target sanity check (parent == / or $HOME)")
    # Force flags
    ap.add_argument("--force", action="store_true",
                    help="shorthand for --force-hooks --force-tools --force-config")
    ap.add_argument("--force-hooks", action="store_true",
                    help="overwrite .claude/hooks/ files that match the source")
    ap.add_argument("--force-tools", action="store_true",
                    help="overwrite generated tool/schema files that match the source")
    ap.add_argument("--force-config", action="store_true",
                    help="overwrite search_config.py if it matches the source")
    ap.add_argument("--overwrite-modified", action="store_true",
                    help="also overwrite locally-modified files (requires a --force* flag)")
    # Venv / install
    ap.add_argument("--venv", type=Path,
                    help="path to virtualenv (auto-detected if omitted)")
    ap.add_argument("--skip-deps", action="store_true",
                    help="skip pip install step")
    ap.add_argument("--create-venv", action="store_true",
                    help="if no venv is detected, create .claude/.venv-tokens and continue "
                         "(single-pass install instead of the create-then-rerun dance)")
    ap.add_argument("--no-build", action="store_true",
                    help="skip the default initial index build (defer the ~130 MB model download)")
    # Optional strategies
    ap.add_argument("--caveman", action="store_true",
                    help="wire terse-output enforcement hooks where supported")
    ap.add_argument("--truncate", action="store_true",
                    help="wire tool output truncation hook (Strategy 3)")
    ap.add_argument("--compact", action="store_true",
                    help="wire conversation compaction trigger hook (Strategy 4)")
    # Safety / lifecycle
    ap.add_argument("--dry-run", action="store_true",
                    help="show exactly what would change without writing anything")
    ap.add_argument("--allow-merge", action="store_true",
                    help="proceed even if .claude/tools/ or .claude/schema/ already contain non-less_tokens files")
    ap.add_argument("--local", action="store_true",
                    help="wire hooks into .claude/settings.local.json (personal / "
                         "untracked) instead of the project-shared .claude/settings.json. "
                         "Note: Claude Code rewrites settings.local.json when auto-adding "
                         "Bash permissions, which can clobber the hooks block")
    ap.add_argument("--no-gitignore", action="store_true",
                    help="skip the default managed .gitignore block for generated artifacts "
                         "(index.db, state dirs); useful if you commit them deliberately")
    ap.add_argument("--update", action="store_true",
                    help="safe upgrade: re-copy hook and tool files (implies "
                         "--force-hooks --force-tools --overwrite-modified) "
                         "but never touch .claude/tools/search_config.py or index.db. "
                         "Incompatible with --force-config and --build.")
    ap.add_argument("--agent", choices=["claude", "codex", "both"], default="claude",
                    help="agent(s) to install for: claude (default), codex, or both")
    ap.add_argument("--check", action="store_true",
                    help="verify a previous install: venv, fastembed, index, hooks, settings")
    ap.add_argument("--uninstall", action="store_true",
                    help="remove a previous less_tokens deployment from the target")
    ap.add_argument("--purge-index", action="store_true",
                    help="with --uninstall, also delete index.db and its WAL sidecars")
    args = ap.parse_args()
    agents = selected_agents(args.agent)

    # --update is a safe-upgrade shortcut: re-copy hooks + tools, never
    # touch search_config.py or index.db. Forbid combinations that would
    # violate that contract.
    if args.update:
        if args.force_config or args.force:
            print("ERROR: --update cannot be combined with --force-config / --force "
                  "(--update never overwrites .claude/tools/search_config.py).",
                  file=sys.stderr)
            return 1
        # --update implies --no-build to simplify CI and manual upgrades
        args.no_build = True

    # Resolve force flags
    force_hooks  = args.force or args.force_hooks or args.update
    force_tools  = args.force or args.force_tools or args.update
    force_config = args.force or args.force_config
    overwrite_modified = args.overwrite_modified or args.update
    dry = args.dry_run
    tag = "[DRY RUN] " if dry else ""

    # ------------------------------------------------------------------
    # Resolve target_root
    #
    # Default = parent of this clone (SOURCE.parent), so re-running after
    # `git pull` always targets the same host project regardless of cwd.
    # --target PATH overrides for scratch projects and CI. The
    # suspicious-target check guards the default path (not --target) so a
    # mis-cloned less_tokens (e.g. directly in $HOME) doesn't splatter
    # files across the user's home.
    # ------------------------------------------------------------------
    if args.target is not None:
        target_root = args.target.resolve()
    else:
        target_root = SOURCE.parent.resolve()
        suspicious = _looks_suspicious(target_root)
        if suspicious and not args.yes:
            print(f"ERROR: refusing to auto-install into {target_root} ({suspicious}).",
                  file=sys.stderr)
            print("less_tokens expects to be cloned inside a host project, so its parent",
                  file=sys.stderr)
            print("directory is the install target. Either move this clone inside a",
                  file=sys.stderr)
            print("project directory, or pass --target PATH --yes to override.",
                  file=sys.stderr)
            return 1

    if SOURCE == target_root or target_root.is_relative_to(SOURCE):
        print("ERROR: refusing to operate on the source directory itself.",
              file=sys.stderr)
        return 1

    # Uninstall is a distinct mode — it reverses a deployment and shares only
    # target resolution / the suspicious-target + source-self guards above.
    if args.uninstall:
        return do_uninstall(target_root, args)

    if args.check:
        return do_check(target_root, args)

    # Resolve source version (git short hash) once; used in header + state file.
    src_version = _source_git_hash()
    prev_state = _read_install_state(target_root)
    prev_version = prev_state.get("version") if prev_state else None

    if prev_version and prev_version == src_version:
        version_line = f"version {src_version} (already current)"
    elif prev_version:
        version_line = f"version {prev_version} → {src_version or 'unknown'}"
    else:
        version_line = f"version {src_version or 'unknown'}"

    print(f"{tag}Installing less_tokens into {target_root}")
    print(f"Source: {SOURCE}  [{version_line}]\n")

    # Track whether anything actually changed so the final summary can
    # report a clean no-op on idempotent re-runs.
    changes = 0

    # ------------------------------------------------------------------
    # Step 1: Resolve & validate the venv BEFORE any filesystem writes.
    #
    # This must precede the file copy: if no venv is found we abort here,
    # and aborting after copying would leave a silent half-install (files
    # on disk, settings.json never wired, toolkit inert).
    # ------------------------------------------------------------------
    print(f"{tag}[1/5] Locating virtualenv...")
    venv_dir = args.venv or detect_venv(target_root)
    if venv_dir is None:
        if args.create_venv:
            if dry:
                venv_dir = target_root / ".claude" / ".venv-tokens"
                print(f"  [DRY RUN] would create venv: {venv_dir}")
            else:
                try:
                    venv_dir = create_venv(target_root)
                except (FileExistsError, subprocess.CalledProcessError) as e:
                    print(f"\n--create-venv failed: {e}", file=sys.stderr)
                    return 1
        else:
            print("\nNo venv detected at .claude/.venv-tokens, .venv-tokens, .venv, venv, env, or app/.venv.")
            print("Pass --venv PATH, --create-venv to make .venv-tokens here, "
                  "or create one yourself:")
            print("    python3 -m venv .venv    # macOS/Linux")
            print("    python -m venv .venv     # Windows")
            print("Then re-run the installer. (Nothing was written.)")
            return 1
    venv_py = venv_python(venv_dir)
    if not dry and not venv_py.exists():
        print(f"ERROR: venv python not found at {venv_py} (nothing written).",
              file=sys.stderr)
        return 1
    print(f"  Using venv: {venv_dir}")

    foreign = _foreign_files(SOURCE, target_root, args.caveman, agents)
    if foreign and not args.allow_merge:
        print("\nERROR: the target already contains files that are not part of "
              "less_tokens:", file=sys.stderr)
        for f in foreign:
            print(f"    {f}", file=sys.stderr)
        print("\nRe-run with --allow-merge to proceed anyway. (Nothing was written.)",
              file=sys.stderr)
        return 1

    # ------------------------------------------------------------------
    # Step 2: Copy files
    # ------------------------------------------------------------------
    print(f"\n{tag}[2/5] Copying files...")
    changes += copy_tree(SOURCE / ".less_tokens" / "config", target_root / ".less_tokens" / "config",
              target_root, force_tools, overwrite_modified, ".less_tokens/config/", dry_run=dry)
    changes += copy_tree(SOURCE / ".less_tokens" / "tools", target_root / ".less_tokens" / "tools",
              target_root, force_tools, overwrite_modified, ".less_tokens/tools/", dry_run=dry)
    changes += copy_tree(SOURCE / "agents" / "common" / "budget", target_root / ".less_tokens" / "hooks" / "budget",
              target_root, force_tools, overwrite_modified, ".less_tokens/hooks/budget/", dry_run=dry)
    changes += copy_tree(SOURCE / ".claude" / "tools",  target_root / ".claude" / "tools", target_root, force_tools,  overwrite_modified,
              ".claude/tools/", exclude=frozenset({"search_config.py"}), dry_run=dry)
    if args.update and (target_root / ".claude" / "tools" / "search_config.py").exists():
        print("  + .claude/tools/search_config.py (preserved — --update never touches it)")
    else:
        handle_search_config(
            SOURCE / ".claude" / "tools" / "search_config.py",
            target_root / ".claude" / "tools" / "search_config.py",
            target_root,
            force_config, overwrite_modified, dry_run=dry,
        )
    changes += copy_tree(SOURCE / ".claude" / "schema", target_root / ".claude" / "schema", target_root, force_tools,  overwrite_modified, ".claude/schema/", dry_run=dry)
    changes += copy_tree(SOURCE / ".claude" / "skills" / "claudemd",
              target_root / ".claude" / "skills" / "claudemd",
              target_root, force_tools, overwrite_modified, ".claude/skills/claudemd/", dry_run=dry)
    if "claude" in agents:
        changes += copy_tree(SOURCE / ".claude" / "hooks",  target_root / ".claude" / "hooks",
                  target_root, force_hooks, overwrite_modified, ".claude/hooks/", dry_run=dry)
        changes += copy_tree(SOURCE / "agents" / "common" / "hooks",
                  target_root / ".claude" / "hooks" / "common",
                  target_root, force_tools, overwrite_modified,
                  ".claude/hooks/common/", dry_run=dry)
        if args.caveman:
            changes += copy_tree(SOURCE / ".claude" / "rules", target_root / ".claude" / "rules",
                      target_root, force_tools, overwrite_modified, ".claude/rules/", dry_run=dry)
    if "codex" in agents:
        changes += write_codex_tool_shims(
            SOURCE / ".claude" / "tools",
            target_root,
            force_tools,
            overwrite_modified,
            dry_run=dry,
        )
        changes += copy_tree(SOURCE / ".claude" / "schema", target_root / ".less_tokens" / "schema",
                  target_root, force_tools, overwrite_modified, ".less_tokens/schema/", dry_run=dry)
        changes += copy_tree(SOURCE / "agents" / "common" / "hooks",
                  target_root / ".less_tokens" / "hooks",
                  target_root, force_tools, overwrite_modified,
                  ".less_tokens/hooks/", dry_run=dry)
        codex_hooks_src = SOURCE / "agents" / "codex" / "hooks"
        if codex_hooks_src.exists() and _dir_is_writable(target_root, ".codex"):
            changes += copy_tree(codex_hooks_src, target_root / ".codex" / "hooks",
                      target_root, force_hooks, overwrite_modified, ".codex/hooks/", dry_run=dry)
        skill_root = (
            target_root / ".agents" / "skills"
            if _dir_is_writable(target_root, ".agents")
            else target_root / ".less_tokens" / "skills"
        )
        codex_skills_src = SOURCE / "agents" / "codex" / "skills"
        if codex_skills_src.exists():
            for codex_skill_src in sorted(codex_skills_src.iterdir()):
                if not codex_skill_src.is_dir() or not (codex_skill_src / "SKILL.md").exists():
                    continue
                skill_tgt = skill_root / codex_skill_src.name
                changes += copy_tree(codex_skill_src, skill_tgt,
                          target_root, force_tools, overwrite_modified,
                          str(skill_tgt.relative_to(target_root)) + "/", dry_run=dry)

    # Auto-patch VENV_PY in search_config.py to match the detected venv.
    # Conservative: only fires when the existing value is the source default,
    # so a user customization is never clobbered. Skipped entirely under
    # --update (which never touches search_config.py).
    dst_cfg = target_root / ".claude" / "tools" / "search_config.py"
    if not args.update:
        venv_py_patched = patch_venv_py(
            dst_cfg, SOURCE / ".claude" / "tools" / "search_config.py", target_root, venv_dir,
            dry_run=dry,
        )
        if venv_py_patched is not None:
            print(f'  {"would patch" if dry else "~"} .claude/tools/search_config.py: '
                  f'VENV_PY -> _venv_python("{venv_py_patched}")')
            changes += 1
        dirs_patched = patch_indexed_source_dirs(dst_cfg, target_root, dry_run=dry)
        if dirs_patched is not None:
            print(f'  {"would patch" if dry else "~"} .claude/tools/search_config.py: '
                  f'INDEXED_SOURCE_DIRS -> {dirs_patched}')
            changes += 1
        if venv_py_patched is None and dry and not dst_cfg.exists():
            # Fresh dry-run install: config not copied, so patch_venv_py is a
            # no-op — still preview the value it would write.
            cfg = _venv_config_str(venv_dir, target_root)
            print(f'  would patch .claude/tools/search_config.py: '
                  f'VENV_PY -> _venv_python("{cfg}")')
            changes += 1
            if "codex" in agents:
                print("  .less_tokens/tools/search_config.py would be generated as a shim")
    else:
        venv_py_patched = None

    # Stable agent-facing Python launchers. Hooks, skills, and docs use these
    # instead of ambient python3 so package imports always come from the
    # detected/created venv.
    changes += write_python_launcher(
        target_root, launcher_rel("claude"), venv_py, dry_run=dry,
    )
    if "codex" in agents:
        changes += write_python_launcher(
            target_root, launcher_rel("codex"), venv_py, dry_run=dry,
        )

    # ------------------------------------------------------------------
    # Step 3: Install deps
    # ------------------------------------------------------------------
    if not args.skip_deps:
        rc, did_install = install_deps(venv_py, dry_run=dry)
        if rc != 0:
            return 1
        if did_install:
            changes += 1
    else:
        print("\n[3/5] Skipping dep install (--skip-deps).")

    # ------------------------------------------------------------------
    # Step 4: Init / migrate DB (skipped under --update — index.db is
    # left untouched even if the schema has drifted).
    # ------------------------------------------------------------------
    if args.update:
        print("\n[4/5] Skipping index.db init/migrate (--update never touches it).")
    else:
        rc, did_init = init_db(venv_py, target_root, dry_run=dry)
        if rc != 0:
            return 1
        if did_init:
            changes += 1

    # ------------------------------------------------------------------
    # Step 5: Wire hooks into .claude/settings.json (project-shared)
    #
    # We use settings.json rather than settings.local.json because Claude
    # Code rewrites the latter when auto-adding Bash permissions, which
    # can clobber the hooks block. settings.json is the project-shared
    # file and stays stable across permission changes.
    # ------------------------------------------------------------------
    settings_name = "settings.local.json" if args.local else "settings.json"
    settings_path = target_root / ".claude" / settings_name
    # Heads-up when we're about to edit a pre-existing, project-shared
    # settings.json — it's typically committed and sometimes change-
    # controlled. settings.local.json is personal/untracked; no notice.
    if (not args.local and settings_path.exists()
            and settings_path.read_text(encoding="utf-8").strip()):
        print(f"  Note: modifying committed .claude/{settings_name} "
              "(pass --local to write settings.local.json instead).")
    print(f"\n{tag}[5/5] Wiring hooks...")
    if "claude" in agents:
        print(f"  → .claude/{settings_name}")
        entries = build_claude_hook_entries(venv_py, target_root, args)
        added, present = wire_settings(settings_path, entries, dry_run=dry)
        print(f"  {added} hook(s) {'would be ' if dry else ''}wired, "
              f"{present} already present")
        changes += added
    if "codex" in agents:
        codex_hooks_json = target_root / ".codex" / "hooks.json"
        if _dir_is_writable(target_root, ".codex"):
            print(f"  → .codex/hooks.json")
            codex_entries = build_codex_hook_entries(venv_py, target_root, args)
            c_added, c_present = wire_codex_hooks_json(codex_hooks_json, codex_entries, dry_run=dry)
            print(f"  {c_added} codex hook(s) {'would be ' if dry else ''}wired, "
                  f"{c_present} already present")
            changes += c_added
        else:
            print("  · .codex/ not writable — hooks.json skipped; "
                  "AGENTS.md + skill installed")
        fragment = SOURCE / "agents" / "codex" / "instructions" / "AGENTS.md.fragment"
        handle_agents_md(fragment, target_root, dry_run=dry)

    # Keep generated artifacts out of the host git repo (opt-in via
    # --gitignore; otherwise just a one-time tip).
    changes += handle_gitignore(target_root, not args.no_gitignore, dry)

    # ------------------------------------------------------------------
    # Optional: build index
    # ------------------------------------------------------------------
    if not args.no_build:
        if build_index(venv_py, target_root, dry_run=dry) != 0:
            return 1

    # ------------------------------------------------------------------
    # Final summary — distinguish dry-run / fresh install / clean re-run
    # ------------------------------------------------------------------
    if dry:
        print(f"\n[DRY RUN] {changes} change(s) would be made. Nothing was written.")
        return 0

    # Always (re-)write the state file so the installed version is current,
    # even on a no-op re-run (nothing else changed but the source may differ).
    _write_install_state(target_root, src_version, dry_run=False)

    if changes == 0:
        print("\nDone — installation already current, no changes.")
        return 0

    print("\nDone.")
    print("\n" + "=" * 60)
    print("NEXT STEPS")
    print("=" * 60)
    if agents == {"codex"}:
        tool_dir = ".less_tokens/tools"
        config_desc = ".claude/tools/search_config.py"
        run_py = launcher_cmd("codex", target_root)
    elif agents == {"claude"}:
        tool_dir = ".claude/tools"
        config_desc = ".claude/tools/search_config.py"
        run_py = launcher_cmd("claude", target_root)
    else:
        tool_dir = ".claude/tools"
        config_desc = ".claude/tools/search_config.py"
        run_py = launcher_cmd("claude", target_root)
    if venv_py_patched is not None:
        print(f"\n1. Edit {config_desc} — update INDEXED_SOURCE_DIRS to list")
        print("   your source directories (the .py/.sql dirs). For markdown,")
        print("   tune INDEXED_ROOT_GLOBS (default '*.md' is root-only; use")
        print("   'docs/**/*.md' or '**/*.md' for doc-heavy repos).")
        print("   VENV_PY is already set to the detected venv.")
        _maybe_suggest_recursive_globs(target_root)
    else:
        print(f"\n1. Edit {config_desc} — set your venv and source dirs.")
        print("   Change the VENV_PY line to:")
        print(f"       VENV_PY = {_venv_python_call(str(venv_dir))}")
        print("   Also update INDEXED_SOURCE_DIRS to list your source directories.")
    if args.no_build:
        print("\n2. Build the index:")
        print(f"       {run_py} {tool_dir}/embeddings.py refresh")
        print("\n3. Test search:")
        print(f"       {run_py} {tool_dir}/search.py \"your query here\"")
    else:
        print("\n2. Test search:")
        print(f"       {run_py} {tool_dir}/search.py \"your query here\"")
    if args.caveman:
        handle_caveman_claude_md(target_root, args.dry_run)
    if "claude" in agents:
        print("\nNOTE: the Claude search-first PreToolUse hook is now active. Any")
        print("  already-running Claude session in this project will start")
        print("  blocking Read on indexed files (root *.md, configured source dirs)")
        print("  until a search runs within the gate window.")
    if "codex" in agents:
        print("\nNOTE: the Codex hooks are best-effort and now use .less_tokens/ compatibility shims.")
        print("  AGENTS.md also has the token-discipline instructions for Codex.")
    print(f"  Tune the gate via WINDOW_SECONDS in {config_desc} (default 300s).")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

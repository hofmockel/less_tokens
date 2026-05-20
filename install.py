#!/usr/bin/env python3
"""Install less_tokens into the host project that contains this clone.

less_tokens is designed to be cloned *into* a host project — e.g.
~/myproject/less_tokens/ — and then deploy its files into the host project
root (~/myproject/). The installer targets the parent directory of this
source clone, so it works regardless of the current working directory:

    # macOS / Linux
    python3 path/to/less_tokens/install.py [options]

    # Windows
    python path/to/less_tokens/install.py [options]

Re-running after `git pull` upgrades an existing install in place — files
that exist are skipped by default and hook wiring is idempotent.

What it does:
  1. Copies tools/, schema/, hooks/, and caveman/ into the host project
  2. Merges new variables into search_config.py without clobbering existing values
  3. Detects or accepts --venv PATH; installs fastembed + numpy into it
  4. Initializes or migrates index.db from schema/index.sql
  5. Wires core hooks into .claude/settings.json (idempotent, project-shared)
  6. Optionally builds the first index (skipped by default — configure first)

Target selection:
  --target PATH  install into PATH instead of the parent of this clone
  --yes          bypass the suspicious-target sanity check (root / $HOME)

Force / overwrite flags:
  --force              shorthand for --force-hooks --force-tools --force-config
  --force-hooks        overwrite .claude/hooks/ files that match the source
  --force-tools        overwrite tools/ files that match the source (not search_config.py)
  --force-config       overwrite search_config.py wholesale if it matches the source
  --overwrite-modified also overwrite files that differ from the source (requires a --force* flag)

Other options:
  --venv PATH    path to virtualenv (auto-detected if omitted)
  --skip-deps    skip pip install step
  --build        run initial index build after install
  --caveman      copy caveman/ directory and wire caveman-reminder hook
  --truncate     wire tool output truncation hook (Strategy 3)
  --compact      wire conversation compaction trigger hook (Strategy 4)

Safety / lifecycle:
  --dry-run      print exactly what would change; write nothing
  --allow-merge  proceed even if tools/ or schema/ already hold non-less_tokens files
  --no-gitignore skip the default managed .gitignore block for generated artifacts
  --uninstall    remove a previous deployment (settings.json hooks + copied files)
  --purge-index  with --uninstall, also delete index.db and its WAL sidecars

Ordering note: the venv is resolved and validated, and a namespace-collision
check runs, *before* any files are copied — a failed precondition aborts with
nothing written (no silent half-install).

Cross-platform: works on Windows/macOS/Linux. Uses pathlib + subprocess only.
"""
from __future__ import annotations

import argparse
import ast
import difflib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parent


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
    for candidate in [".venv-tokens", ".venv", "venv", "env", "app/.venv"]:
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
    venv_dir = target_root / ".venv-tokens"
    if venv_dir.exists():
        raise FileExistsError(
            f"{venv_dir} already exists; pass --venv {venv_dir} to use it "
            "or remove it before re-running with --create-venv"
        )
    py = "python" if sys.platform == "win32" else "python3"
    print(f"  Creating venv: {venv_dir}")
    subprocess.check_call([py, "-m", "venv", str(venv_dir)])
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


def _extract_block(lines: list[str], lineno: int) -> str:
    """Extract an assignment block, including any immediately-preceding comment lines."""
    idx = lineno - 1  # convert to 0-indexed
    comment_start = idx
    while comment_start > 0 and lines[comment_start - 1].strip().startswith("#"):
        comment_start -= 1
    return "\n".join(lines[comment_start:idx + 1])


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
        name: _extract_block(src_lines, lineno)
        for name, (lineno, _) in src_vars.items()
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

_DEFAULT_INDEXED_SOURCE_DIRS = ("tools/", "schema/")


def _discover_source_dirs(target_root: Path) -> list[str]:
    """Top-level directories under target_root that contain any `.py` file.

    Skips hidden dirs, venvs, caches, and the less_tokens-owned `tools/` /
    `schema/` (those are the defaults). Returns paths with a trailing
    slash to match INDEXED_SOURCE_DIRS conventions, alpha-sorted.
    """
    found: list[str] = []
    try:
        for child in sorted(target_root.iterdir()):
            if not child.is_dir():
                continue
            name = child.name
            if name.startswith(".") or name in _SOURCE_DIR_EXCLUDE:
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
    existing value still matches the source default (("tools/",
    "schema/")). User customizations are preserved.

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
            print(f"  ✓ {rel} (already matches source)")
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
        print(f"  ✓ {rel}: all variables present")


# ---------------------------------------------------------------------------
# Settings.local.json — idempotent hook wiring
# ---------------------------------------------------------------------------

def _build_hook_entries(venv_py: Path, target_root: Path, args: argparse.Namespace) -> list[tuple[str, str, str]]:
    """Return (event_type, matcher, command) tuples for all hooks to wire.

    The venv python path is rendered relative to target_root when possible
    so that re-runs produce string-identical commands regardless of whether
    the user passed --venv with a relative or absolute path (or relied on
    auto-detect, which always returns absolute). Without this, the
    idempotency check in wire_settings() would see two commands as
    different and add duplicate entries.
    """
    try:
        py = str(venv_py.relative_to(target_root))
    except ValueError:
        py = str(venv_py)
    entries: list[tuple[str, str, str]] = [
        ("PreToolUse",  "Read",          f"{py} .claude/hooks/search-first.py"),
        ("PostToolUse", "Edit|Write",    f"{py} .claude/hooks/index-refresh.py"),
    ]
    if getattr(args, "truncate", False):
        entries.append(("PostToolUse", "Bash|Read|WebFetch",
                         f"{py} .claude/hooks/truncate-output.py"))
    if getattr(args, "compact", False):
        entries.append(("PostToolUse", ".*",
                         f"{py} .claude/hooks/compact-trigger.py"))
    if getattr(args, "caveman", False):
        entries.append(("PostToolUse", ".*",
                         f"{py} .claude/hooks/caveman-reminder.py"))
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
            print(f"  ✓ {event_type} {matcher!r} already wired")
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
    db = target_root / "index.db"
    if not db.exists():
        return False
    try:
        import sqlite3
        with sqlite3.connect(str(db)) as c:
            row = c.execute("SELECT MAX(version) FROM schema_version").fetchone()
            return bool(row and row[0])
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
            [str(venv_py), "tools/db.py", "init"], cwd=target_root
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
            [str(venv_py), "tools/embeddings.py", "refresh"], cwd=target_root
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
            [str(venv_py), "tools/embeddings.py", "stats"], cwd=target_root
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


def _caveman_in_claude_md(target_root: Path) -> bool:
    claude_md = target_root / "CLAUDE.md"
    if not claude_md.exists():
        return False
    return "Caveman Mode" in claude_md.read_text(encoding="utf-8", errors="replace")


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
def _install_specs(caveman: bool) -> list[tuple[str, str, frozenset[str]]]:
    specs = [
        ("tools",  "tools",         frozenset({"search_config.py"})),
        ("schema", "schema",        frozenset()),
        ("hooks",  ".claude/hooks", frozenset()),
    ]
    if caveman:
        specs.append(("caveman", "caveman", frozenset()))
    return specs


def _foreign_files(source: Path, target_root: Path, caveman: bool) -> list[str]:
    """Host-owned files sitting in a tree we would merge into.

    Only tools/, schema/, caveman/ are gated: a host package at tools/ can
    shadow our modules on sys.path, and a host schema/ can clash. .claude/hooks/
    is intentionally NOT gated — it is a shared directory where we add our hook
    files alongside the host's own hooks, and copy_tree already skips existing
    files there.
    """
    gated = ["tools", "schema"] + (["caveman"] if caveman else [])
    foreign: list[str] = []
    for sub in gated:
        dstdir = target_root / sub
        if not dstdir.is_dir():
            continue
        ours = {
            str(rel) for rel in _iter_tree_files(source / sub)
        } | ({"search_config.py"} if sub == "tools" else set())
        for f in dstdir.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(dstdir)
            if any(p.startswith(".") or p in _SKIP_PARTS for p in rel.parts):
                continue
            if str(rel) not in ours:
                foreign.append(f"{sub}/{rel.as_posix()}")
    return sorted(foreign)


def _deployed_targets(source: Path, target_root: Path, caveman: bool) -> list[Path]:
    """Destination files less_tokens deploys (excludes user-owned search_config.py)."""
    out: list[Path] = []
    for sub, dst_rel, excl in _install_specs(caveman):
        base = target_root / dst_rel
        for rel in _iter_tree_files(source / sub, excl):
            out.append(base / rel)
    return out


# ---------------------------------------------------------------------------
# .gitignore management (keep generated artifacts out of the host repo)
# ---------------------------------------------------------------------------

_GI_START = "# >>> less_tokens (generated artifacts) >>>"
_GI_END = "# <<< less_tokens <<<"
_GI_PATHS = ["/index.db", "/index.db-wal", "/index.db-shm", "/.claude/state/"]


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
        print("  ✓ .gitignore: less_tokens block already present")
        return 0
    if not want:
        print("\n  Note: --no-gitignore set; index.db and .claude/state/ will "
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
    # Drop the block and one immediately-preceding blank separator line.
    lead = start
    if lead > 0 and lines[lead - 1].strip() == "":
        lead -= 1
    new = "".join(lines[:lead] + lines[end + 1:])
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

def _our_hook_names(source: Path) -> set[str]:
    return {rel.name for rel in _iter_tree_files(source / "hooks")}


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
        return any(f".claude/hooks/{n}" in cmd for n in names)

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


def do_uninstall(target_root: Path, args: argparse.Namespace) -> int:
    dry = args.dry_run
    tag = "[DRY RUN] " if dry else ""
    print(f"{tag}Uninstalling less_tokens from {target_root}")
    print(f"Source: {SOURCE}\n")

    removed = 0
    for f in _deployed_targets(SOURCE, target_root, caveman=True):
        if f.exists():
            print(f"  {'would remove' if dry else '-'} {f.relative_to(target_root)}")
            if not dry:
                f.unlink()
            removed += 1

    # Prune now-empty directories we created.
    for sub in ("tools", "schema", ".claude/hooks", "caveman"):
        d = target_root / sub
        if d.is_dir() and not any(d.iterdir()):
            print(f"  {'would remove' if dry else '-'} {sub}/ (empty)")
            if not dry:
                d.rmdir()

    unwire_settings(target_root / ".claude" / "settings.json", SOURCE, dry)
    _remove_gitignore_block(target_root / ".gitignore", dry)

    if args.purge_index:
        for n in ("index.db", "index.db-wal", "index.db-shm"):
            p = target_root / n
            if p.exists():
                print(f"  {'would remove' if dry else '-'} {n}")
                if not dry:
                    p.unlink()
                removed += 1
    elif (target_root / "index.db").exists():
        print("  · index.db preserved (pass --purge-index to also remove it)")

    if (target_root / "tools" / "search_config.py").exists():
        print("  · tools/search_config.py preserved (may contain your customizations)")

    print(f"\n{tag}Done — {removed} file(s) "
          f"{'would be removed' if dry else 'removed'}.")
    return 0


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
                    help="overwrite tools/ and schema/ files that match the source")
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
                    help="if no venv is detected, create .venv-tokens and continue "
                         "(single-pass install instead of the create-then-rerun dance)")
    ap.add_argument("--build", action="store_true",
                    help="run initial index build (skipped by default — configure first)")
    # Optional strategies
    ap.add_argument("--caveman", action="store_true",
                    help="copy caveman/ and wire caveman-reminder hook")
    ap.add_argument("--truncate", action="store_true",
                    help="wire tool output truncation hook (Strategy 3)")
    ap.add_argument("--compact", action="store_true",
                    help="wire conversation compaction trigger hook (Strategy 4)")
    # Safety / lifecycle
    ap.add_argument("--dry-run", action="store_true",
                    help="show exactly what would change without writing anything")
    ap.add_argument("--allow-merge", action="store_true",
                    help="proceed even if tools/ or schema/ already contain non-less_tokens files")
    ap.add_argument("--local", action="store_true",
                    help="wire hooks into .claude/settings.local.json (personal / "
                         "untracked) instead of the project-shared .claude/settings.json. "
                         "Note: Claude Code rewrites settings.local.json when auto-adding "
                         "Bash permissions, which can clobber the hooks block")
    ap.add_argument("--no-gitignore", action="store_true",
                    help="skip the default managed .gitignore block for generated artifacts "
                         "(index.db, .claude/state/); useful if you commit them deliberately")
    ap.add_argument("--update", action="store_true",
                    help="safe upgrade: re-copy hook and tool files (implies "
                         "--force-hooks --force-tools --overwrite-modified) "
                         "but never touch tools/search_config.py or index.db. "
                         "Incompatible with --force-config and --build.")
    ap.add_argument("--uninstall", action="store_true",
                    help="remove a previous less_tokens deployment from the target")
    ap.add_argument("--purge-index", action="store_true",
                    help="with --uninstall, also delete index.db and its WAL sidecars")
    args = ap.parse_args()

    # --update is a safe-upgrade shortcut: re-copy hooks + tools, never
    # touch search_config.py or index.db. Forbid combinations that would
    # violate that contract.
    if args.update:
        if args.force_config or args.force:
            print("ERROR: --update cannot be combined with --force-config / --force "
                  "(--update never overwrites tools/search_config.py).",
                  file=sys.stderr)
            return 1
        if args.build:
            print("ERROR: --update cannot be combined with --build "
                  "(--update never touches index.db).",
                  file=sys.stderr)
            return 1

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

    print(f"{tag}Installing less_tokens into {target_root}")
    print(f"Source: {SOURCE}\n")

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
        if args.create_venv and not dry:
            try:
                venv_dir = create_venv(target_root)
            except (FileExistsError, subprocess.CalledProcessError) as e:
                print(f"\n--create-venv failed: {e}", file=sys.stderr)
                return 1
        else:
            print("\nNo venv detected at .venv-tokens, .venv, venv, env, or app/.venv.")
            print("Pass --venv PATH, --create-venv to make .venv-tokens here, "
                  "or create one yourself:")
            print("    python3 -m venv .venv    # macOS/Linux")
            print("    python -m venv .venv     # Windows")
            print("Then re-run the installer. (Nothing was written.)")
            return 1
    venv_py = venv_python(venv_dir)
    if not venv_py.exists():
        print(f"ERROR: venv python not found at {venv_py} (nothing written).",
              file=sys.stderr)
        return 1
    print(f"  Using venv: {venv_dir}")

    # Namespace-collision guard: refuse to merge into a host's own tools/ or
    # schema/ (sys.path shadowing / schema clashes) unless --allow-merge.
    # Still before any writes.
    foreign = _foreign_files(SOURCE, target_root, args.caveman)
    if foreign and not args.allow_merge:
        print("\nERROR: the target already contains files that are not part of "
              "less_tokens:", file=sys.stderr)
        for f in foreign:
            print(f"    {f}", file=sys.stderr)
        print("\nMerging less_tokens into these directories could shadow them on "
              "sys.path", file=sys.stderr)
        print("or clash with the host schema. Re-run with --allow-merge to proceed "
              "anyway,", file=sys.stderr)
        print("or install into a project without a top-level tools//schema/ of its "
              "own. (Nothing was written.)", file=sys.stderr)
        return 1

    # ------------------------------------------------------------------
    # Step 2: Copy files
    # ------------------------------------------------------------------
    print(f"\n{tag}[2/5] Copying files...")
    changes += copy_tree(SOURCE / "tools",  target_root / "tools", target_root, force_tools,  overwrite_modified,
              "tools/", exclude=frozenset({"search_config.py"}), dry_run=dry)
    if args.update and (target_root / "tools" / "search_config.py").exists():
        print("  ✓ tools/search_config.py (preserved — --update never touches it)")
    else:
        handle_search_config(
            SOURCE / "tools" / "search_config.py",
            target_root / "tools" / "search_config.py",
            target_root,
            force_config, overwrite_modified, dry_run=dry,
        )
    changes += copy_tree(SOURCE / "schema", target_root / "schema", target_root, force_tools,  overwrite_modified, "schema/", dry_run=dry)
    changes += copy_tree(SOURCE / "hooks",  target_root / ".claude" / "hooks",
              target_root, force_hooks, overwrite_modified, ".claude/hooks/", dry_run=dry)
    if args.caveman:
        changes += copy_tree(SOURCE / "caveman", target_root / "caveman",
                  target_root, force_tools, overwrite_modified, "caveman/", dry_run=dry)

    # Auto-patch VENV_PY in search_config.py to match the detected venv.
    # Conservative: only fires when the existing value is the source default,
    # so a user customization is never clobbered. Skipped entirely under
    # --update (which never touches search_config.py).
    dst_cfg = target_root / "tools" / "search_config.py"
    if not args.update:
        venv_py_patched = patch_venv_py(
            dst_cfg, SOURCE / "tools" / "search_config.py", target_root, venv_dir,
            dry_run=dry,
        )
        if venv_py_patched is not None:
            print(f'  {"would patch" if dry else "~"} tools/search_config.py: '
                  f'VENV_PY → _venv_python("{venv_py_patched}")')
            changes += 1
        dirs_patched = patch_indexed_source_dirs(dst_cfg, target_root, dry_run=dry)
        if dirs_patched is not None:
            print(f'  {"would patch" if dry else "~"} tools/search_config.py: '
                  f'INDEXED_SOURCE_DIRS → {dirs_patched}')
            changes += 1
        if venv_py_patched is None and dry and not dst_cfg.exists():
            # Fresh dry-run install: config not copied, so patch_venv_py is a
            # no-op — still preview the value it would write.
            cfg = _venv_config_str(venv_dir, target_root)
            print(f'  would patch tools/search_config.py: '
                  f'VENV_PY → _venv_python("{cfg}")')
            changes += 1
    else:
        venv_py_patched = None

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
    print(f"\n{tag}[5/5] Wiring .claude/{settings_name}...")
    entries = _build_hook_entries(venv_py, target_root, args)
    added, present = wire_settings(settings_path, entries, dry_run=dry)
    print(f"  {added} hook(s) {'would be ' if dry else ''}wired, "
          f"{present} already present")
    changes += added

    # Keep generated artifacts out of the host git repo (opt-in via
    # --gitignore; otherwise just a one-time tip).
    changes += handle_gitignore(target_root, not args.no_gitignore, dry)

    # ------------------------------------------------------------------
    # Optional: build index
    # ------------------------------------------------------------------
    if args.build:
        if build_index(venv_py, target_root, dry_run=dry) != 0:
            return 1

    # ------------------------------------------------------------------
    # Final summary — distinguish dry-run / fresh install / clean re-run
    # ------------------------------------------------------------------
    if dry:
        print(f"\n[DRY RUN] {changes} change(s) would be made. Nothing was written.")
        return 0
    if changes == 0:
        print("\nDone — installation already current, no changes.")
        return 0

    print("\nDone.")
    print("\n" + "=" * 60)
    print("NEXT STEPS")
    print("=" * 60)
    if venv_py_patched is not None:
        print("\n1. Edit tools/search_config.py — update INDEXED_SOURCE_DIRS to list")
        print("   your source directories (the .py/.sql dirs). For markdown,")
        print("   tune INDEXED_ROOT_GLOBS (default '*.md' is root-only; use")
        print("   'docs/**/*.md' or '**/*.md' for doc-heavy repos).")
        print("   VENV_PY is already set to the detected venv.")
        _maybe_suggest_recursive_globs(target_root)
    else:
        print("\n1. Edit tools/search_config.py — set your venv and source dirs.")
        print("   Change the VENV_PY line to:")
        print(f"       VENV_PY = {_venv_python_call(str(venv_dir))}")
        print("   Also update INDEXED_SOURCE_DIRS to list your source directories.")
    if not args.build:
        print("\n2. Build the index:")
        print(f"       {venv_py} tools/embeddings.py refresh")
        print("\n3. Test search:")
        print(f"       {venv_py} tools/search.py \"your query here\"")
    else:
        print("\n2. Test search:")
        print(f"       {venv_py} tools/search.py \"your query here\"")
    if args.caveman:
        step = 4 if not args.build else 3
        if _caveman_in_claude_md(target_root):
            print(f"\n{step}. Caveman section already present in CLAUDE.md — skipping.")
        else:
            print(f"\n{step}. Append caveman mode to your CLAUDE.md:")
            print("       cat caveman/caveman.md >> CLAUDE.md")
    print("\nNOTE: the search-first PreToolUse hook is now active. Any")
    print("  already-running Claude session in this project will start")
    print("  blocking Read on indexed files (tools/, schema/, root *.md)")
    print("  until a search runs within the gate window. Tune the window")
    print("  via WINDOW_SECONDS in tools/search_config.py (default 300s).")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

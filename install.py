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

Cross-platform: works on Windows/macOS/Linux. Uses pathlib + subprocess only.
"""
from __future__ import annotations

import argparse
import ast
import difflib
import json
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

    `.venv-tokens` is checked first so projects that keep less_tokens deps
    isolated from the project's main venv get auto-detected on re-runs.
    """
    for candidate in [".venv-tokens", ".venv", "venv", "env", "app/.venv"]:
        d = target_root / candidate
        if venv_python(d).exists():
            return d
    return None


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
) -> int:
    """Copy a directory tree. Returns count of files copied.

    Without --force: skip all existing files (safe default).
    With --force: overwrite files that are identical to the source; warn and
                  skip files that differ (they have local edits).
    With --force + --overwrite-modified: overwrite everything, printing a
                  diff summary for any locally-modified file.
    """
    if not src.exists():
        print(f"  {label}: source missing — {src}", file=sys.stderr)
        return 0
    copied = skipped = modified_skipped = 0
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
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(srcfile, target)
                print(f"  ↺ {rel_str}  ({summary}, overwritten)")
                copied += 1
            else:
                print(f"  ! {rel_str}  ({summary}) — differs from source; "
                      f"add --overwrite-modified to update")
                modified_skipped += 1
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(srcfile, target)
            print(f"  + {target.relative_to(target_root)}")
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


def merge_search_config(src_file: Path, dst_file: Path) -> list[str]:
    """Inject variables present in src but absent in dst. Returns added names."""
    src_text = src_file.read_text(encoding="utf-8")
    dst_text = dst_file.read_text(encoding="utf-8")

    src_vars = _top_level_assignments(src_text)
    dst_vars = _top_level_assignments(dst_text)

    if not src_vars:
        print(f"  ! search_config.py: could not parse source; skipping merge",
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


def patch_venv_py(
    config_path: Path,
    src_config: Path,
    target_root: Path,
    venv_dir: Path,
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

    try:
        venv_str = venv_dir.relative_to(target_root).as_posix()
    except ValueError:
        venv_str = str(venv_dir).replace("\\", "/")

    if venv_str == dst_arg:
        return None  # already correct

    lines = dst_text.splitlines(keepends=True)
    start = dst_assign.lineno - 1            # 0-indexed
    end = dst_assign.end_lineno              # 1-indexed, inclusive
    new_line = f'VENV_PY = _venv_python("{venv_str}")\n'
    new_text = "".join(lines[:start]) + new_line + "".join(lines[end:])
    if new_text == dst_text:
        return None
    config_path.write_text(new_text, encoding="utf-8")
    return venv_str


def handle_search_config(
    src_config: Path,
    dst_config: Path,
    target_root: Path,
    force_config: bool,
    overwrite_modified: bool,
) -> None:
    """Copy or merge search_config.py into the target project."""
    rel = dst_config.relative_to(target_root)
    if not dst_config.exists():
        dst_config.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_config, dst_config)
        print(f"  + {rel}")
        return

    # Full overwrite only when force_config + overwrite_modified both set
    if force_config and overwrite_modified:
        src_text = src_config.read_text(encoding="utf-8")
        dst_text = dst_config.read_text(encoding="utf-8")
        if src_text == dst_text:
            print(f"  ✓ {rel} (already matches source)")
        else:
            summary = _diff_summary(src_text, dst_text)
            shutil.copy2(src_config, dst_config)
            print(f"  ↺ {rel}  ({summary}, replaced by --force-config --overwrite-modified)")
        return

    # Default path: variable-level upsert
    added = merge_search_config(src_config, dst_config)
    if added:
        print(f"  ~ {rel}: injected new variables: {', '.join(added)}")
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
            print(f"  + {event_type} {matcher!r}")
            added += 1

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


def install_deps(venv_py: Path) -> tuple[int, bool]:
    """Install fastembed + numpy. Returns (exit_code, did_install)."""
    if _deps_already_present(venv_py):
        print(f"\n[3/5] fastembed + numpy already importable in {venv_py} — skipping pip install.")
        return 0, False
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


def init_db(venv_py: Path, target_root: Path) -> tuple[int, bool]:
    """Initialize / migrate index.db. Returns (exit_code, did_init)."""
    if _index_db_at_current_schema(target_root):
        print("\n[4/5] index.db already initialized — skipping init.")
        return 0, False
    print("\n[4/5] Initializing / migrating index.db...")
    try:
        subprocess.check_call(
            [str(venv_py), "tools/db.py", "init"], cwd=target_root
        )
        return 0, True
    except subprocess.CalledProcessError as e:
        print(f"  db init failed (exit {e.returncode})", file=sys.stderr)
        return 1, False


def build_index(venv_py: Path, target_root: Path) -> int:
    print("\nBuilding initial embeddings (first run downloads ~130 MB model)...")
    try:
        subprocess.check_call(
            [str(venv_py), "tools/embeddings.py", "refresh"], cwd=target_root
        )
        return 0
    except subprocess.CalledProcessError as e:
        print(f"  refresh failed (exit {e.returncode})", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# Caveman duplicate check
# ---------------------------------------------------------------------------

def _caveman_in_claude_md(target_root: Path) -> bool:
    claude_md = target_root / "CLAUDE.md"
    if not claude_md.exists():
        return False
    return "Caveman Mode" in claude_md.read_text(encoding="utf-8", errors="replace")


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
    ap.add_argument("--build", action="store_true",
                    help="run initial index build (skipped by default — configure first)")
    # Optional strategies
    ap.add_argument("--caveman", action="store_true",
                    help="copy caveman/ and wire caveman-reminder hook")
    ap.add_argument("--truncate", action="store_true",
                    help="wire tool output truncation hook (Strategy 3)")
    ap.add_argument("--compact", action="store_true",
                    help="wire conversation compaction trigger hook (Strategy 4)")
    args = ap.parse_args()

    # Resolve force flags
    force_hooks  = args.force or args.force_hooks
    force_tools  = args.force or args.force_tools
    force_config = args.force or args.force_config
    overwrite_modified = args.overwrite_modified

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

    print(f"Installing less_tokens into {target_root}")
    print(f"Source: {SOURCE}\n")

    if SOURCE == target_root or target_root.is_relative_to(SOURCE):
        print("ERROR: refusing to install into the source directory itself.",
              file=sys.stderr)
        return 1

    # Track whether anything actually changed so the final summary can
    # report a clean no-op on idempotent re-runs.
    changes = 0

    # ------------------------------------------------------------------
    # Step 1: Copy files
    # ------------------------------------------------------------------
    print("[1/5] Copying files...")
    changes += copy_tree(SOURCE / "tools",  target_root / "tools", target_root, force_tools,  overwrite_modified,
              "tools/", exclude=frozenset({"search_config.py"}))
    handle_search_config(
        SOURCE / "tools" / "search_config.py",
        target_root / "tools" / "search_config.py",
        target_root,
        force_config, overwrite_modified,
    )
    changes += copy_tree(SOURCE / "schema", target_root / "schema", target_root, force_tools,  overwrite_modified, "schema/")
    changes += copy_tree(SOURCE / "hooks",  target_root / ".claude" / "hooks",
              target_root, force_hooks, overwrite_modified, ".claude/hooks/")
    if args.caveman:
        changes += copy_tree(SOURCE / "caveman", target_root / "caveman",
                  target_root, force_tools, overwrite_modified, "caveman/")

    # ------------------------------------------------------------------
    # Step 2: Detect venv
    # ------------------------------------------------------------------
    print("\n[2/5] Locating virtualenv...")
    venv_dir = args.venv or detect_venv(target_root)
    if venv_dir is None:
        print("\nNo venv detected at .venv, venv, env, or app/.venv.")
        print("Pass --venv PATH or create a venv first:")
        print("    python3 -m venv .venv    # macOS/Linux")
        print("    python -m venv .venv     # Windows")
        print("Then re-run the installer.")
        return 1
    venv_py = venv_python(venv_dir)
    if not venv_py.exists():
        print(f"ERROR: venv python not found at {venv_py}", file=sys.stderr)
        return 1
    print(f"  Using venv: {venv_dir}")

    # Auto-patch VENV_PY in search_config.py to match the detected venv.
    # Conservative: only fires when the existing value is the source default,
    # so a user customization is never clobbered.
    venv_py_patched = patch_venv_py(
        target_root / "tools" / "search_config.py",
        SOURCE / "tools" / "search_config.py",
        target_root,
        venv_dir,
    )
    if venv_py_patched is not None:
        print(f'  ~ tools/search_config.py: VENV_PY → _venv_python("{venv_py_patched}")')
        changes += 1

    # ------------------------------------------------------------------
    # Step 3: Install deps
    # ------------------------------------------------------------------
    if not args.skip_deps:
        rc, did_install = install_deps(venv_py)
        if rc != 0:
            return 1
        if did_install:
            changes += 1
    else:
        print("\n[3/5] Skipping dep install (--skip-deps).")

    # ------------------------------------------------------------------
    # Step 4: Init / migrate DB
    # ------------------------------------------------------------------
    rc, did_init = init_db(venv_py, target_root)
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
    print("\n[5/5] Wiring .claude/settings.json...")
    settings_path = target_root / ".claude" / "settings.json"
    entries = _build_hook_entries(venv_py, target_root, args)
    added, present = wire_settings(settings_path, entries)
    print(f"  {added} hook(s) wired, {present} already present")
    changes += added

    # ------------------------------------------------------------------
    # Optional: build index
    # ------------------------------------------------------------------
    if args.build:
        if build_index(venv_py, target_root) != 0:
            return 1

    # ------------------------------------------------------------------
    # Final summary — distinguish a fresh install from a clean re-run
    # ------------------------------------------------------------------
    if changes == 0:
        print("\nDone — installation already current, no changes.")
        return 0

    print("\nDone.")
    print("\n" + "=" * 60)
    print("NEXT STEPS")
    print("=" * 60)
    if venv_py_patched is not None:
        print("\n1. Edit tools/search_config.py — update INDEXED_SOURCE_DIRS to list")
        print("   your source directories. VENV_PY is already set to the detected venv.")
    else:
        print("\n1. Edit tools/search_config.py — set your venv and source dirs.")
        print(f"   Change the VENV_PY line to:")
        print(f'       VENV_PY = _venv_python("{venv_dir}")')
        print(f"   Also update INDEXED_SOURCE_DIRS to list your source directories.")
    if not args.build:
        print(f"\n2. Build the index:")
        print(f"       {venv_py} tools/embeddings.py refresh")
        print(f"\n3. Test search:")
        print(f"       {venv_py} tools/search.py \"your query here\"")
    else:
        print(f"\n2. Test search:")
        print(f"       {venv_py} tools/search.py \"your query here\"")
    if args.caveman:
        step = 4 if not args.build else 3
        if _caveman_in_claude_md(target_root):
            print(f"\n{step}. Caveman section already present in CLAUDE.md — skipping.")
        else:
            print(f"\n{step}. Append caveman mode to your CLAUDE.md:")
            print(f"       cat caveman/caveman.md >> CLAUDE.md")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

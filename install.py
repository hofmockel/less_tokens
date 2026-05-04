#!/usr/bin/env python3
"""Install less_tokens into the current project.

Run from your project root:
    python3 path/to/export_less_tokens/install.py [--force] [--venv PATH]

What it does:
  1. Copies tools/, schema/, hooks/ into your project (skips existing files unless --force)
  2. Detects or accepts --venv PATH; installs fastembed + numpy into it
  3. Initializes index.db from schema/index.sql
  4. Builds the first index

Cross-platform: works on Windows/macOS/Linux. Uses pathlib + subprocess only.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parent
TARGET_ROOT = Path.cwd().resolve()


def venv_python(venv_dir: Path) -> Path:
    """Resolve <venv>/Scripts/python.exe (Windows) or <venv>/bin/python (Unix)."""
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def detect_venv() -> Path | None:
    """Look for a venv in common locations relative to TARGET_ROOT."""
    for candidate in [".venv", "venv", "env", "app/.venv"]:
        d = TARGET_ROOT / candidate
        if venv_python(d).exists():
            return d
    return None


def copy_tree(src: Path, dst: Path, force: bool, label: str) -> int:
    """Copy a directory tree. Returns count of files copied. Skips existing files unless force."""
    if not src.exists():
        print(f"  {label}: source missing — {src}", file=sys.stderr)
        return 0
    copied = skipped = 0
    dst.mkdir(parents=True, exist_ok=True)
    for srcfile in src.rglob("*"):
        if srcfile.is_dir():
            continue
        rel = srcfile.relative_to(src)
        target = dst / rel
        if target.exists() and not force:
            print(f"  ! skip (exists): {target.relative_to(TARGET_ROOT)}")
            skipped += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(srcfile, target)
        print(f"  + {target.relative_to(TARGET_ROOT)}")
        copied += 1
    print(f"  {label}: {copied} copied, {skipped} skipped")
    return copied


def install_deps(venv_py: Path) -> int:
    print(f"\n[2/4] Installing fastembed + numpy into {venv_py}...")
    try:
        subprocess.check_call(
            [str(venv_py), "-m", "pip", "install", "--quiet", "fastembed", "numpy"]
        )
        print("  OK")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"  pip install failed (exit {e.returncode})", file=sys.stderr)
        return 1


def init_db(venv_py: Path) -> int:
    print("\n[3/4] Initializing index.db...")
    try:
        subprocess.check_call(
            [str(venv_py), "tools/db.py", "init"], cwd=TARGET_ROOT
        )
        return 0
    except subprocess.CalledProcessError as e:
        print(f"  db init failed (exit {e.returncode})", file=sys.stderr)
        return 1


def build_index(venv_py: Path) -> int:
    print("\n[4/4] Building initial embeddings (first run downloads ~130MB model)...")
    try:
        subprocess.check_call(
            [str(venv_py), "tools/embeddings.py", "refresh"], cwd=TARGET_ROOT
        )
        return 0
    except subprocess.CalledProcessError as e:
        print(f"  refresh failed (exit {e.returncode})", file=sys.stderr)
        return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true",
                    help="overwrite existing files in target")
    ap.add_argument("--venv", type=Path,
                    help="path to virtualenv (auto-detected if omitted)")
    ap.add_argument("--skip-deps", action="store_true",
                    help="skip pip install step")
    ap.add_argument("--skip-build", action="store_true",
                    help="skip initial index build (run embeddings.py refresh manually later)")
    args = ap.parse_args()

    print(f"Installing less_tokens into {TARGET_ROOT}")
    print(f"Source: {SOURCE}\n")

    if SOURCE == TARGET_ROOT or TARGET_ROOT.is_relative_to(SOURCE):
        print("ERROR: refusing to install into the export directory itself.",
              file=sys.stderr)
        return 1

    print("[1/4] Copying files...")
    copy_tree(SOURCE / "tools", TARGET_ROOT / "tools", args.force, "tools/")
    copy_tree(SOURCE / "schema", TARGET_ROOT / "schema", args.force, "schema/")
    copy_tree(SOURCE / "hooks", TARGET_ROOT / ".claude" / "hooks",
              args.force, ".claude/hooks/")

    venv_dir = args.venv or detect_venv()
    if venv_dir is None:
        print("\nNo venv detected at .venv, venv, env, or app/.venv.")
        print("Pass --venv PATH or create a venv and re-run with --skip-deps:")
        print("    python3 -m venv .venv")
        return 0 if args.skip_deps else 1

    venv_py = venv_python(venv_dir)
    if not venv_py.exists():
        print(f"ERROR: venv python not found at {venv_py}", file=sys.stderr)
        return 1
    print(f"\nUsing venv: {venv_dir}")

    if not args.skip_deps:
        if install_deps(venv_py) != 0:
            return 1

    if init_db(venv_py) != 0:
        return 1

    if not args.skip_build:
        if build_index(venv_py) != 0:
            return 1

    print("\nDone.")
    print(f"\nNext steps:")
    print(f"  1. Edit tools/search_config.py for your project layout")
    print(f"     (especially VENV_PY if your venv isn't at {venv_dir.name})")
    print(f"  2. Add the 'Search Before Read' section to CLAUDE.md")
    print(f"  3. Wire hooks into .claude/settings.local.json (see README.md)")
    print(f"  4. Try: {venv_py} tools/search.py \"your query\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())

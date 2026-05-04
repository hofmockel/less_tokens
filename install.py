#!/usr/bin/env python3
"""Install less_tokens into the current project.

Run from your project root:
    # macOS / Linux
    python3 path/to/less_tokens_claude/install.py [options]

    # Windows
    python path/to/less_tokens_claude/install.py [options]

What it does:
  1. Copies tools/, schema/, hooks/, and caveman/ into your project
  2. Detects or accepts --venv PATH; installs fastembed + numpy into it
  3. Initializes index.db from schema/index.sql
  4. Optionally builds the first index (skipped by default — configure first)

Options:
  --force        overwrite existing files in target
  --venv PATH    path to virtualenv (auto-detected if omitted)
  --skip-deps    skip pip install step
  --skip-build   skip initial index build (default; run embeddings.py refresh manually)
  --build        run initial index build after install
  --caveman      copy caveman/ directory and wire caveman-reminder hook

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
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true",
                    help="overwrite existing files in target")
    ap.add_argument("--venv", type=Path,
                    help="path to virtualenv (auto-detected if omitted)")
    ap.add_argument("--skip-deps", action="store_true",
                    help="skip pip install step")
    ap.add_argument("--skip-build", action="store_true", default=True,
                    help="skip initial index build (default; configure search_config.py first)")
    ap.add_argument("--build", action="store_true",
                    help="run initial index build (overrides --skip-build)")
    ap.add_argument("--caveman", action="store_true",
                    help="copy caveman/ directory (terse output mode for Claude)")
    args = ap.parse_args()

    # --build overrides the default --skip-build
    do_build = args.build and not args.skip_build or args.build

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
    if args.caveman:
        copy_tree(SOURCE / "caveman", TARGET_ROOT / "caveman", args.force, "caveman/")

    venv_dir = args.venv or detect_venv()
    if venv_dir is None:
        print("\nNo venv detected at .venv, venv, env, or app/.venv.")
        print("Pass --venv PATH or create a venv first:")
        print("    python3 -m venv .venv    # macOS/Linux")
        print("    python -m venv .venv     # Windows")
        print("Then re-run the installer.")
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

    if do_build:
        if build_index(venv_py) != 0:
            return 1
    else:
        print("\n[4/4] Skipping initial index build (configure first, then build manually).")

    print("\nDone.")
    print("\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    print("\n1. Edit tools/search_config.py — set your venv and source dirs.")
    print(f"   Change the VENV_PY line to:")
    print(f'       VENV_PY = _venv_python("{venv_dir}")')
    print(f"   Also update INDEXED_SOURCE_DIRS to list your source directories.")
    print(f"\n2. Build the index:")
    print(f"       {venv_py} tools/embeddings.py refresh")
    print(f"\n3. Test search:")
    print(f"       {venv_py} tools/search.py \"your query here\"")
    print(f"\n4. Wire hooks into .claude/settings.local.json (see README.md).")
    print(f"   Use this python path in your hook commands:")
    print(f"       {venv_py}")
    if args.caveman:
        print(f"\n5. Append caveman mode to your CLAUDE.md:")
        print(f"       cat caveman/caveman.md >> CLAUDE.md")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

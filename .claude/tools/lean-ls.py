#!/usr/bin/env python3
"""Scoped directory lister: depth-limited, .gitignore-aware, dir-count summary.

Usage: lean-ls.py [path] [--depth N] [--max-per-dir M] [--max-total T]
  path          directory to list (default: .)
  --depth N     max depth to traverse (default: 2)
  --max-per-dir M  max files shown per dir; extras collapsed to count (default: 10)
  --max-total T    cap total output lines with "N more..." tail (default: 200)

Returns a tree-like listing without noise: skips .git, __pycache__, node_modules,
venvs; respects root .gitignore patterns; collapses fat dirs to "N items" counts.
Designed to replace bare `ls -R` / `find . -type f` / `tree` in Bash tool calls.
"""

from __future__ import annotations

import argparse
import sys
from fnmatch import fnmatch
from pathlib import Path

# Directories always skipped regardless of .gitignore
_SKIP_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        ".env",
        "dist",
        "build",
        ".next",
        ".nuxt",
        "coverage",
        ".tox",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".hypothesis",
        "eggs",
        ".eggs",
    }
)

# Glob patterns for noisy dir names (e.g. "*.egg-info")
_SKIP_DIR_GLOBS: tuple[str, ...] = ("*.egg-info", "*.dist-info")


def _load_gitignore(root: Path) -> list[str]:
    """Return non-comment, non-empty patterns from root/.gitignore."""
    gi = root / ".gitignore"
    if not gi.exists():
        return []
    patterns: list[str] = []
    for line in gi.read_text(errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            patterns.append(line.rstrip("/"))
    return patterns


def _is_gitignored(name: str, patterns: list[str]) -> bool:
    return any(fnmatch(name, p) for p in patterns)


def _skip_dir(name: str) -> bool:
    if name in _SKIP_DIR_NAMES:
        return True
    return any(fnmatch(name, g) for g in _SKIP_DIR_GLOBS)


def _count_dir(path: Path) -> int | str:
    try:
        return sum(1 for _ in path.iterdir())
    except PermissionError:
        return "?"


def _walk(
    root: Path,
    depth: int,
    max_depth: int,
    max_per_dir: int,
    gitignore: list[str],
    lines: list[str],
    prefix: str,
) -> None:
    try:
        entries = sorted(root.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
    except PermissionError:
        lines.append(f"{prefix}[permission denied]")
        return

    dirs: list[Path] = []
    files: list[Path] = []
    for e in entries:
        if _skip_dir(e.name) or _is_gitignored(e.name, gitignore):
            continue
        if e.is_dir():
            dirs.append(e)
        elif e.is_file():
            files.append(e)
        # broken symlinks: is_dir()=False and is_file()=False — skip

    shown = files[:max_per_dir]
    hidden = len(files) - len(shown)
    for f in shown:
        lines.append(f"{prefix}{f.name}")
    if hidden:
        lines.append(f"{prefix}  ... {hidden} more file(s)")

    for d in dirs:
        if depth < max_depth:
            lines.append(f"{prefix}{d.name}/")
            _walk(d, depth + 1, max_depth, max_per_dir, gitignore, lines, prefix + "  ")
        else:
            count = _count_dir(d)
            lines.append(f"{prefix}{d.name}/  ({count} items)")


def lean_ls(
    path: str = ".",
    depth: int = 2,
    max_per_dir: int = 10,
    max_total: int = 200,
) -> str:
    """Return a compact directory listing as a string."""
    root = Path(path).resolve()
    if not root.exists():
        return f"lean-ls: path not found: {root}"

    gitignore = _load_gitignore(root)
    lines: list[str] = [str(root) + "/"]
    _walk(root, 1, depth, max_per_dir, gitignore, lines, "  ")

    total = len(lines)
    if max_total and total > max_total:
        lines = lines[:max_total]
        lines.append(
            f"  ... {total - max_total} more line(s) omitted"
            f" (use --depth or --max-per-dir to tune)"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Depth-limited, .gitignore-aware directory lister"
    )
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument(
        "--depth", type=int, default=2, help="Max recursion depth (default: 2)"
    )
    parser.add_argument(
        "--max-per-dir",
        type=int,
        default=10,
        help="Max files shown per dir before count collapse (default: 10)",
    )
    parser.add_argument(
        "--max-total",
        type=int,
        default=200,
        help="Cap total output lines (default: 200; 0=unlimited)",
    )
    args = parser.parse_args()
    print(lean_ls(args.path, args.depth, args.max_per_dir, args.max_total))
    return 0


if __name__ == "__main__":
    sys.exit(main())

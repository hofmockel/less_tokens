#!/usr/bin/env python3
"""Audit for the recurring "hardcoded POSIX assumption" bug class (WIN1).

`CHANGELOG.md` carries a long tail of Windows-only CI breaks, each patched in
isolation at the one call site a failing test happened to exercise: bare
launcher paths handed to `subprocess` with no platform-suffix check (PT9's
`WinError 193`, and the earlier `python` vs `python.exe` installer-check bug),
and POSIX-only `subprocess` kwargs (`start_new_session=True`) used with no
`sys.platform`/`os.name` branch (the pre-`_detach_kwargs` `index-refresh.py`
bug). Both are mechanically detectable: walk every function, and flag either
pattern when that function contains no comparison against the literal
platform strings `"win32"`/`"nt"` anywhere in its body.

Deliberately narrow: this does not attempt to catch console-encoding
(`cp1252`), path-separator (`Path.relative_to`), or environment-stripping
(`SYSTEMROOT`) bugs — see WIN1's `DECISIONS.md` entry for why those are left
as one-off fixes rather than folded into a generic mechanism.
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SCAN_TARGETS = ["agents", "install.py", ".claude/tools"]
EXCLUDE_DIR_NAMES = {
    "tests", "__pycache__", ".venv-tokens", ".less_tokens", ".codex", "docs-site",
}
LAUNCHER_DIR_SEGMENTS = {"bin", "Scripts"}
PLATFORM_LITERALS = {"win32", "nt"}
POSIX_ONLY_KWARGS = {"start_new_session", "preexec_fn"}


def iter_py_files(root: Path):
    for target in SCAN_TARGETS:
        p = root / target
        if p.is_file():
            yield p
            continue
        if not p.is_dir():
            continue
        for f in sorted(p.rglob("*.py")):
            if any(part in EXCLUDE_DIR_NAMES for part in f.parts):
                continue
            if f.name.startswith("test_"):
                continue
            yield f


def _function_has_platform_check(func: ast.AST) -> bool:
    for node in ast.walk(func):
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            for operand in operands:
                if isinstance(operand, ast.Constant) and operand.value in PLATFORM_LITERALS:
                    return True
    return False


def _path_join_parts(node: ast.AST) -> list[str] | None:
    """Collect literal string segments of a `a / "b" / "c"` chain, root first.

    Returns None if any segment isn't a plain string literal (so a dynamic
    segment like a variable can't be misread as a fixed name).
    """
    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.BinOp) and isinstance(cur.op, ast.Div):
        right = cur.right
        if not (isinstance(right, ast.Constant) and isinstance(right.value, str)):
            return None
        parts.append(right.value)
        cur = cur.left
    if isinstance(cur, ast.Constant) and isinstance(cur.value, str):
        parts.append(cur.value)
    elif isinstance(cur, (ast.Name, ast.Attribute)):
        pass  # root is a variable/attribute (e.g. REPO, self.repo) — fine, not a literal to check
    else:
        return None
    parts.reverse()
    return parts


def _is_bare_launcher_chain(parts: list[str]) -> bool:
    if not parts:
        return False
    last = parts[-1]
    if "." in last:
        return False  # has an extension (python.exe, python.cmd) — already platform-specific
    return any(seg in LAUNCHER_DIR_SEGMENTS for seg in parts[:-1])


def check_bare_launcher_exists(tree: ast.Module, filename: str) -> list[str]:
    """Flag `<bare-launcher-path>.exists()` with no platform check in scope.

    Narrowed to `.exists()` (not just any Path join) because a bare relative
    name is fine to *construct* — e.g. `install.py`'s `launcher_rel()` returns
    one for a caller to suffix later. The bug is deciding whether to *use* an
    extensionless launcher via existence alone.
    """
    violations = []
    for func in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        if _function_has_platform_check(func):
            continue
        bare_vars: set[str] = set()
        for node in ast.walk(func):
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                parts = _path_join_parts(node.value)
                if parts and _is_bare_launcher_chain(parts):
                    bare_vars.add(node.targets[0].id)
        for node in ast.walk(func):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "exists"):
                continue
            target = node.func.value
            hit = False
            if isinstance(target, ast.Name) and target.id in bare_vars:
                hit = True
            else:
                parts = _path_join_parts(target)
                if parts and _is_bare_launcher_chain(parts):
                    hit = True
            if hit:
                violations.append(
                    f"{filename}:{node.lineno}: bare launcher path `.exists()`-checked in "
                    f"`{func.name}` with no win32/nt platform check in scope"
                )
    return violations


def check_posix_only_subprocess_kwargs(tree: ast.Module, filename: str) -> list[str]:
    violations = []
    for func in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        if _function_has_platform_check(func):
            continue
        for node in ast.walk(func):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if kw.arg in POSIX_ONLY_KWARGS:
                    violations.append(
                        f"{filename}:{node.lineno}: POSIX-only kwarg `{kw.arg}` used in "
                        f"`{func.name}` with no win32/nt platform check in scope"
                    )
    return violations


def audit(root: Path) -> list[str]:
    violations: list[str] = []
    for f in iter_py_files(root):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        except SyntaxError as exc:
            violations.append(f"{f}: could not parse ({exc})")
            continue
        rel = f.relative_to(root).as_posix() if f.is_absolute() else str(f)
        violations.extend(check_bare_launcher_exists(tree, rel))
        violations.extend(check_posix_only_subprocess_kwargs(tree, rel))
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO)
    args = parser.parse_args()
    violations = audit(args.root)
    if violations:
        print("win_platform_audit: found unguarded platform-sensitive patterns:")
        for v in violations:
            print(f"  {v}")
        print(f"\n{len(violations)} problem(s). See .claude/tools/win_platform_audit.py docstring for scope.")
        return 1
    print("win_platform_audit: clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

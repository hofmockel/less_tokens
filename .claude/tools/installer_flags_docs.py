#!/usr/bin/env python3
"""Generate the installer optional-flags table from install.py's argparse
metadata, so DOCUMENTATION.md can't drift from the actual CLI (P4)."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INSTALL_PY = REPO / "install.py"
DOCS = (REPO / "DOCUMENTATION.md",)
BEGIN = "<!-- installer-flags: begin -->"
END = "<!-- installer-flags: end -->"


def _load_install_module():
    sys.path.insert(0, str(REPO))
    spec = importlib.util.spec_from_file_location("less_tokens_install", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _placeholder(action: argparse.Action) -> str:
    if action.choices:
        return "|".join(str(c) for c in action.choices)
    if action.nargs == 0:
        return ""
    if action.type is Path:
        return "PATH"
    return action.dest.upper()


def _row(action: argparse.Action) -> str:
    flag = action.option_strings[-1]
    placeholder = _placeholder(action)
    name = f"`{flag} {placeholder}`" if placeholder else f"`{flag}`"
    help_text = (action.help or "").strip()
    if help_text:
        help_text = help_text[0].upper() + help_text[1:]
    return f"| {name} | {help_text} |"


def render() -> str:
    ap = _load_install_module().build_arg_parser()
    lines = [BEGIN, "", "| Flag | Effect |", "|---|---|"]
    for action in ap._actions:
        if not action.option_strings or "-h" in action.option_strings:
            continue
        lines.append(_row(action))
    lines.extend(["", END])
    return "\n".join(lines)


def _replace_block(text: str, block: str) -> str:
    pattern = rf"{re.escape(BEGIN)}.*?{re.escape(END)}"
    if not re.search(pattern, text, flags=re.DOTALL):
        raise ValueError("missing installer-flags markers")
    return re.sub(pattern, block, text, flags=re.DOTALL)


def update_docs(*, check: bool) -> int:
    block = render()
    dirty: list[Path] = []
    for path in DOCS:
        text = path.read_text(encoding="utf-8")
        updated = _replace_block(text, block)
        if updated != text:
            dirty.append(path)
            if not check:
                path.write_text(updated, encoding="utf-8")

    if dirty and check:
        for path in dirty:
            print(f"{path.relative_to(REPO)} is out of date", file=sys.stderr)
        return 1
    if not check:
        for path in dirty:
            print(f"updated {path.relative_to(REPO)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    return update_docs(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())

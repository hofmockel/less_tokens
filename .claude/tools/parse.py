#!/usr/bin/env python3
"""Structured output parsers for noisy CLI tools.

Usage (stdin → stdout):
    python parse.py pytest  < output.txt
    python parse.py ruff    < output.txt
    python parse.py git     < output.txt
    python parse.py eslint  < output.txt
"""

from __future__ import annotations

import re
import sys


def parse_pytest(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    for line in lines:
        if re.match(r"^(FAILED|ERROR) ", line):
            out.append(line)
        elif re.match(r"^E\s+", line):
            out.append(line.strip())
        elif re.search(r"(passed|failed|error)", line) and "===" in line:
            out.append(line)
    if not out:
        for line in lines:
            if re.match(r"^=+.*passed.*=+$", line):
                return line
        return text
    return "\n".join(dict.fromkeys(out))


def parse_ruff(text: str) -> str:
    out: list[str] = []
    for line in text.splitlines():
        if re.match(r"^.+:\d+:\d+: [A-Z]\d+ ", line):
            out.append(line)
        elif re.match(r"^(Found \d+|All checks)", line):
            out.append(line)
    return "\n".join(out) if out else text


def parse_eslint(text: str) -> str:
    out: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if re.match(r"^\d+:\d+\s+(error|warning)\s+", s):
            out.append(line)
        elif re.match(r"^[✖✓]|\d+ (error|warning|problem)", s):
            out.append(line)
    return "\n".join(out) if out else text


def parse_git(text: str) -> str:
    out: list[str] = []
    for line in text.splitlines():
        if re.match(r"^[\s?MADRUC]{1,2}\s+\S", line):
            out.append(line)
        elif re.match(r"^\s*.+\|\s*\d+", line):
            out.append(line)
        elif re.match(r"^\s*\d+ file", line):
            out.append(line)
        elif line.startswith("On branch") or "nothing to commit" in line:
            out.append(line)
    return "\n".join(out) if out else text


_PARSERS = {
    "pytest": parse_pytest,
    "ruff": parse_ruff,
    "eslint": parse_eslint,
    "git": parse_git,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in _PARSERS:
        print(f"Usage: parse.py <{'|'.join(_PARSERS)}>", file=sys.stderr)
        sys.exit(1)
    print(_PARSERS[sys.argv[1]](sys.stdin.read()), end="")

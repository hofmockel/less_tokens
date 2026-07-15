#!/usr/bin/env python3
"""Validate links in built docs-site HTML."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

REPO = Path(__file__).resolve().parents[2]
SITE = REPO / "docs-site" / "site"
HREF_RE = re.compile(r'href="([^"]+)"')
ID_RE = re.compile(r'id="([^"]+)"')


def anchors(path: Path) -> set[str]:
    if path.suffix.lower() not in {".html", ".svg"}:
        return set()
    return set(ID_RE.findall(path.read_text(encoding="utf-8")))


def validate_href(page: Path, href: str) -> str | None:
    parsed = urlparse(href)
    if parsed.scheme in {"http", "https", "mailto"}:
        return None
    if href.startswith("#"):
        target = page
        fragment = href[1:]
    else:
        href_path, _, fragment = href.partition("#")
        if not href_path:
            target = page
        else:
            target = (page.parent / unquote(href_path)).resolve()
    try:
        target.relative_to(REPO)
    except ValueError:
        return f"{page.relative_to(REPO)} links outside repo: {href}"
    if not target.exists():
        return f"{page.relative_to(REPO)} missing target: {href}"
    if fragment and target.suffix.lower() in {".html", ".svg"} and fragment not in anchors(target):
        return f"{page.relative_to(REPO)} missing anchor {fragment}: {href}"
    return None


def main() -> int:
    if not SITE.exists():
        print("docs-site/site missing; run build_docs.py first", file=sys.stderr)
        return 1
    errors: list[str] = []
    for page in SITE.rglob("*.html"):
        text = page.read_text(encoding="utf-8")
        for href in HREF_RE.findall(text):
            error = validate_href(page, href)
            if error:
                errors.append(error)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("docs links ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

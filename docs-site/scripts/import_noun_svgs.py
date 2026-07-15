#!/usr/bin/env python3
"""Import original Noun Project SVG downloads without their printed credit lines."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

def clean_svg(source: Path, destination: Path) -> None:
    svg = source.read_text(encoding="utf-8")

    def remove_credit(match: re.Match[str]) -> str:
        text = " ".join(re.sub(r"<[^>]+>", " ", match.group(0)).lower().split())
        return "" if text.startswith("created by") or "noun project" in text else match.group(0)

    svg = re.sub(r"<text\b[^>]*>.*?</text>", remove_credit, svg, flags=re.IGNORECASE | re.DOTALL)

    def square_viewbox(match: re.Match[str]) -> str:
        values = re.split(r"[\s,]+", match.group(1).strip())
        if len(values) != 4:
            raise ValueError(f"unsupported viewBox in {source}: {match.group(1)}")
        x, y, width, _height = values
        return f'viewBox="{x} {y} {width} {width}"'

    svg, replacements = re.subn(r'viewBox="([^"]+)"', square_viewbox, svg, count=1)
    if replacements != 1:
        raise ValueError(f"missing viewBox in {source}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(svg.rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--downloads", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()

    records = json.loads(args.metadata.read_text(encoding="utf-8"))
    for record in records:
        matches = sorted(args.downloads.glob(f"noun-*-{record['id']}*.svg"))
        if not matches:
            raise FileNotFoundError(f"missing SVG download for Noun Project icon {record['id']}")
        if any(match.read_bytes() != matches[0].read_bytes() for match in matches[1:]):
            raise ValueError(f"downloaded SVG variants differ for icon {record['id']}")
        clean_svg(matches[0], args.destination / f"{record['anchor']}.svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

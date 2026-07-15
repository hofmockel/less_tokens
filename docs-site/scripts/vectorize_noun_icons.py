#!/usr/bin/env python3
"""Vectorize black Noun Project preview PNGs into standalone attributed SVGs."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image

Point = tuple[int, int]
Edge = tuple[Point, Point]


def direction(a: Point, b: Point) -> int:
    dx, dy = b[0] - a[0], b[1] - a[1]
    return {(1, 0): 0, (0, 1): 1, (-1, 0): 2, (0, -1): 3}[(dx, dy)]


def boundary_edges(image: Image.Image) -> set[Edge]:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    alpha = rgba.getchannel("A")
    filled = [[alpha.getpixel((x, y)) >= 128 for x in range(width)] for y in range(height)]
    edges: set[Edge] = set()
    for y, row in enumerate(filled):
        for x, on in enumerate(row):
            if not on:
                continue
            if y == 0 or not filled[y - 1][x]:
                edges.add(((x, y), (x + 1, y)))
            if x == width - 1 or not row[x + 1]:
                edges.add(((x + 1, y), (x + 1, y + 1)))
            if y == height - 1 or not filled[y + 1][x]:
                edges.add(((x + 1, y + 1), (x, y + 1)))
            if x == 0 or not row[x - 1]:
                edges.add(((x, y + 1), (x, y)))
    return edges


def trace_loops(edges: set[Edge]) -> list[list[Point]]:
    outgoing: dict[Point, list[Point]] = {}
    for start, end in edges:
        outgoing.setdefault(start, []).append(end)
    unused = set(edges)
    loops: list[list[Point]] = []
    while unused:
        first = min(unused)
        start, current = first
        previous = start
        points = [start]
        unused.remove(first)
        while current != start:
            points.append(current)
            candidates = [end for end in outgoing.get(current, []) if (current, end) in unused]
            if not candidates:
                raise ValueError(f"Open contour at {current}")
            incoming = direction(previous, current)
            preference = {1: 0, 0: 1, 3: 2, 2: 3}
            next_point = min(candidates, key=lambda end: preference[(direction(current, end) - incoming) % 4])
            unused.remove((current, next_point))
            previous, current = current, next_point
        loops.append(points)
    return loops


def perpendicular_distance(point: Point, start: Point, end: Point) -> float:
    if start == end:
        return math.dist(point, start)
    numerator = abs((end[1] - start[1]) * point[0] - (end[0] - start[0]) * point[1] + end[0] * start[1] - end[1] * start[0])
    return numerator / math.dist(start, end)


def rdp(points: list[Point], epsilon: float) -> list[Point]:
    if len(points) <= 2:
        return points
    distances = [perpendicular_distance(point, points[0], points[-1]) for point in points[1:-1]]
    if not distances:
        return points
    maximum = max(distances)
    index = distances.index(maximum) + 1
    if maximum <= epsilon:
        return [points[0], points[-1]]
    left = rdp(points[: index + 1], epsilon)
    right = rdp(points[index:], epsilon)
    return left[:-1] + right


def simplify_loop(points: list[Point], epsilon: float = 0.9) -> list[Point]:
    if len(points) < 4:
        return points
    first = min(range(len(points)), key=lambda index: (points[index][0], points[index][1]))
    rotated = points[first:] + points[:first]
    farthest = max(range(1, len(rotated)), key=lambda index: math.dist(rotated[0], rotated[index]))
    left = rdp(rotated[: farthest + 1], epsilon)
    right = rdp(rotated[farthest:] + [rotated[0]], epsilon)
    return left[:-1] + right[:-1]


def svg_path(loops: list[list[Point]]) -> str:
    commands: list[str] = []
    for loop in loops:
        points = simplify_loop(loop)
        if len(points) < 3:
            continue
        commands.append(f"M{points[0][0]} {points[0][1]}" + "".join(f"L{x} {y}" for x, y in points[1:]) + "Z")
    return "".join(commands)


def vectorize(source: Path, destination: Path, attribution: dict[str, str]) -> None:
    image = Image.open(source)
    width, height = image.size
    path = svg_path(trace_loops(boundary_edges(image)))
    title = f"{attribution['title']} by {attribution['creator']}"
    credit = f"{title} from Noun Project ({attribution['license']})"
    metadata = json.dumps({**attribution, "vectorizedFrom": attribution["png"]}, ensure_ascii=False)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">{escape(title)}</title>
  <desc id="desc">{escape(credit)}</desc>
  <metadata>{escape(metadata)}</metadata>
  <path fill="#000" fill-rule="evenodd" d="{path}"/>
</svg>
'''
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(svg, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--png-dir", type=Path, required=True)
    parser.add_argument("--svg-dir", type=Path, required=True)
    args = parser.parse_args()
    records = json.loads(args.metadata.read_text(encoding="utf-8"))
    for record in records:
        vectorize(args.png_dir / f"{record['anchor']}.png", args.svg_dir / f"{record['anchor']}.svg", record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

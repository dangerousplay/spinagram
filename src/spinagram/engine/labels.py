"""Edge label placement: candidate positions along and beside an edge (roadmap E1)."""
from __future__ import annotations

import math

Point = tuple[float, float]
ALONG = (0.5, 0.3, 0.7, 0.15, 0.85)  # midpoint, then ±20 %, ±35 % of the length (towards the source first)
SIDE_GAP = 6.0                       # beside the edge: half the label height + this


def _point_at(points: list[Point], t: float) -> tuple[Point, tuple[float, float]]:
    """Point at fraction ``t`` of the polyline's length and the unit direction of its segment."""
    segs = [(a, b, math.dist(a, b)) for a, b in zip(points, points[1:])]
    total = sum(n for _, _, n in segs) or 1.0
    want = t * total
    for a, b, n in segs:
        if n and want <= n + 1e-9:
            k = want / n
            return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k), ((b[0] - a[0]) / n, (b[1] - a[1]) / n)
        want -= n
    a, b, n = segs[-1]
    return b, (((b[0] - a[0]) / n, (b[1] - a[1]) / n) if n else (1.0, 0.0))


def candidates(points: list[Point], label_h: float) -> list[Point]:
    """Label centres to try, in order: on the edge at :data:`ALONG`, then each of those shifted to either side
    (first the side above / right of the travel direction) by ``label_h / 2 + SIDE_GAP``."""
    on = [_point_at(points, t) for t in ALONG]
    off = label_h / 2 + SIDE_GAP
    out = [p for p, _ in on]
    for (x, y), (dx, dy) in on:
        nx, ny = dy, -dx  # normal: up for a rightward edge, right for a downward one
        out += [(x + nx * off, y + ny * off), (x - nx * off, y - ny * off)]
    return out

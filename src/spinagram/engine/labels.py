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


Rect = tuple[float, float, float, float]
ARROWHEAD = 14.0  # the last px of an edge belong to its arrowhead
FREE = 0.5        # px² of overlap that count as none (float noise)


def overlap(a: Rect, b: Rect) -> float:
    """Intersection area of two rectangles (x, y, w, h)."""
    w = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    h = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


def outside(r: Rect, bounds: Rect) -> float:
    """Area of ``r`` outside ``bounds``."""
    return r[2] * r[3] - overlap(r, bounds)


def arrowheads(connectors) -> list[Rect]:
    """A square around the last ``ARROWHEAD`` px of every arrow end (and start)."""
    out = []
    for c in connectors:
        pts = list(c.points)
        for on, a, b in ((c.arrow_end, pts[-2], pts[-1]), (c.arrow_start, pts[1], pts[0])):
            n = math.dist(a, b)
            if not on or not n:
                continue
            k = min(1.0, ARROWHEAD / n)
            bx, by = b[0] - (b[0] - a[0]) * k, b[1] - (b[1] - a[1]) * k
            pad = max(6.0, c.width * 1.5)
            x0, x1, y0, y1 = min(b[0], bx) - pad, max(b[0], bx) + pad, min(b[1], by) - pad, max(b[1], by) + pad
            out.append((x0, y0, x1 - x0, y1 - y0))
    return out


def _rect(s) -> Rect:
    return (s.x, s.y, s.w, s.h)


def move(pill, cx: float, cy: float) -> None:
    """Centre a label pill on (cx, cy), text box included."""
    dx, dy = cx - (pill.x + pill.w / 2), cy - (pill.y + pill.h / 2)
    pill.x += dx
    pill.y += dy
    if pill.label is not None:
        x, y, w, h = pill.label.box
        pill.label.box = (x + dx, y + dy, w, h)


def place(connectors, fixed: set[str], obstacles: list[Rect], bounds: Rect, path=lambda c: c.points
          ) -> list[tuple[str, str, str]]:
    """Move each free label (not in ``fixed``) to its first candidate clear of ``obstacles``, the arrowheads,
    labels placed so far and ``bounds``; with none clear, to the least-overlapping one and report it."""
    issues = []
    heads = arrowheads(connectors)
    placed = [_rect(c.label) for c in connectors if c.label is not None and c.id in fixed]
    for c in connectors:
        if c.label is None or c.id in fixed:
            continue
        lab = c.label
        best, best_cost = None, None
        cands = candidates(path(c), lab.h)
        for cx, cy in cands:
            r = (cx - lab.w / 2, cy - lab.h / 2, lab.w, lab.h)
            cost = sum(overlap(r, o) for o in (*obstacles, *heads, *placed)) + outside(r, bounds)
            if best_cost is None or cost < best_cost - 1e-9:
                best, best_cost = (cx, cy), cost
            if cost < FREE:
                break
        move(lab, *best)
        placed.append(_rect(lab))
        if best_cost >= FREE:
            issues.append((c.id, "label-collision", f"label {lab.label.blocks[0].lines[0]!r} overlaps "
                           f"{best_cost:.0f}px² at its best position ({len(cands)} candidates tried)"))
    return issues


def free_spot(c, obstacles: list[Rect], bounds: Rect, path=lambda c: c.points) -> Point | None:
    """A wider search than :func:`candidates` for a label with no free candidate: along the edge every 10 %,
    up to six label-heights to either side. The first clear centre, or None."""
    lab = c.label
    pts = path(c)
    for k in range(1, 7):
        off = k * (lab.h / 2 + SIDE_GAP)
        for t in (0.5, 0.4, 0.6, 0.3, 0.7, 0.2, 0.8, 0.1, 0.9):
            (x, y), (dx, dy) = _point_at(pts, t)
            for sgn in (1, -1):
                cx, cy = x + dy * off * sgn, y - dx * off * sgn
                r = (cx - lab.w / 2, cy - lab.h / 2, lab.w, lab.h)
                if sum(overlap(r, o) for o in obstacles) + outside(r, bounds) < FREE:
                    return cx, cy
    return None

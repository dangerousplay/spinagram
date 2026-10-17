"""Orthogonal edge routing around obstacles, for edges a layout engine cannot route itself.

The router builds a sparse grid from the obstacle borders (plus a margin) and the port coordinates,
then runs A* over it with a penalty per bend. Grid lines include every obstacle border, so a grid
segment is either entirely inside an obstacle or entirely outside: one midpoint test per segment.
"""
from __future__ import annotations

import heapq
from bisect import bisect_left

Box = tuple[float, float, float, float]
Point = tuple[float, float]

MARGIN = 14.0
BEND = 60.0  # cost of a bend, in px of length
BUSY = 400.0  # cost of attaching to a side another edge already uses: arrowheads would pile up there
CLOSE = 4.0  # extra cost per px of a segment closer than ``margin`` to a box it does not start or end at


def _ports(b: Box) -> dict[str, tuple[Point, Point]]:
    """side → (point on the border, unit direction outward)."""
    x, y, w, h = b
    return {"top": ((x + w / 2, y), (0, -1)), "bottom": ((x + w / 2, y + h), (0, 1)),
            "left": ((x, y + h / 2), (-1, 0)), "right": ((x + w, y + h / 2), (1, 0))}


def _inside(px: float, py: float, b: Box, pad: float = 0.5) -> bool:
    x, y, w, h = b
    return x + pad < px < x + w - pad and y + pad < py < y + h - pad


def route(src: Box, dst: Box, obstacles: list[Box], *, margin: float = MARGIN,
          sides: tuple[str | None, str | None] = (None, None),
          busy: dict[Box, set[str]] | None = None) -> list[Point]:
    """Orthogonal polyline from a side of ``src`` to a side of ``dst`` that enters no obstacle.

    ``obstacles`` may include ``src`` and ``dst``; they are always avoided except at the ports.
    Without ``sides`` every side pair is tried and the cheapest route wins. ``busy`` maps a box to the
    sides other edges already attach to; those cost ``BUSY`` so the route prefers a free side.
    """
    obs = [b for b in obstacles if b != src and b != dst] + [src, dst]
    sp, dp = _ports(src), _ports(dst)
    s_sides = [sides[0]] if sides[0] else list(sp)
    d_sides = [sides[1]] if sides[1] else list(dp)
    busy = busy or {}
    best: tuple[float, list[Point]] | None = None
    for ss in s_sides:
        for ds in d_sides:
            got = _search(sp[ss], dp[ds], obs, margin)
            if got:
                extra = BUSY * ((ss in busy.get(src, ())) + (ds in busy.get(dst, ())))
                got = (got[0] + extra, got[1])
            if got and (best is None or got[0] < best[0] - 1e-9):
                best = got
    if best is None:  # boxed in: straight elbow as a last resort
        (ax, ay), _ = sp["bottom"]
        (bx, by), _ = dp["top"]
        return [(ax, ay), (ax, (ay + by) / 2), (bx, (ay + by) / 2), (bx, by)]
    return best[1]


def _search(sport, dport, obs: list[Box], margin: float):
    (sx, sy), (sdx, sdy) = sport
    (tx, ty), (tdx, tdy) = dport
    s_stub = (sx + sdx * margin, sy + sdy * margin)
    t_stub = (tx + tdx * margin, ty + tdy * margin)
    if any(_inside(*s_stub, b) for b in obs) or any(_inside(*t_stub, b) for b in obs):
        return None
    xs = {s_stub[0], t_stub[0]}
    ys = {s_stub[1], t_stub[1]}
    for x, y, w, h in obs:
        xs.update((x - margin, x + w + margin))
        ys.update((y - margin, y + h + margin))
    xs_l, ys_l = sorted(xs), sorted(ys)
    nx, ny = len(xs_l), len(ys_l)
    blocked = [[any(_inside(xs_l[i], ys_l[j], b) for b in obs) for j in range(ny)] for i in range(nx)]

    def seg_ok(i1, j1, i2, j2) -> bool:
        mx, my = (xs_l[i1] + xs_l[i2]) / 2, (ys_l[j1] + ys_l[j2]) / 2
        return not any(_inside(mx, my, b) for b in obs)

    # boxes grown by the margin, minus the two ends: a segment inside one runs along a box border.
    # Grid lines include every grown border, so the midpoint test holds for whole segments here too.
    grown = [(x - margin, y - margin, w + 2 * margin, h + 2 * margin) for x, y, w, h in obs[:-2]]

    def seg_close(i1, j1, i2, j2) -> bool:
        mx, my = (xs_l[i1] + xs_l[i2]) / 2, (ys_l[j1] + ys_l[j2]) / 2
        return any(_inside(mx, my, b) for b in grown)

    start = (bisect_left(xs_l, s_stub[0]), bisect_left(ys_l, s_stub[1]))
    goal = (bisect_left(xs_l, t_stub[0]), bisect_left(ys_l, t_stub[1]))
    first_dir = (sdx, sdy)
    # state: (i, j, dir) ; dir = incoming unit direction
    h0 = abs(xs_l[start[0]] - xs_l[goal[0]]) + abs(ys_l[start[1]] - ys_l[goal[1]])
    heap = [(h0, 0.0, start, first_dir, None)]
    seen: dict[tuple, float] = {}
    came: dict[tuple, tuple | None] = {}
    end_state = None
    while heap:
        f, g, (i, j), d, prev = heapq.heappop(heap)
        key = (i, j, d)
        if key in seen:
            continue
        seen[key] = g
        came[key] = prev
        if (i, j) == goal:
            # the final leg must arrive pointing into the target
            if d != (-tdx, -tdy):
                g += BEND
            end_state = (key, g)
            break
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ni, nj = i + di, j + dj
            if not (0 <= ni < nx and 0 <= nj < ny) or blocked[ni][nj] or not seg_ok(i, j, ni, nj):
                continue
            if (di, dj) == (-d[0], -d[1]):
                continue
            step = abs(xs_l[ni] - xs_l[i]) + abs(ys_l[nj] - ys_l[j])
            ng = g + step + (BEND if (di, dj) != d else 0.0) + (CLOSE * step if seg_close(i, j, ni, nj) else 0.0)
            nk = (ni, nj, (di, dj))
            if nk in seen:
                continue
            hh = abs(xs_l[ni] - xs_l[goal[0]]) + abs(ys_l[nj] - ys_l[goal[1]])
            heapq.heappush(heap, (ng + hh, ng, (ni, nj), (di, dj), key))
    if end_state is None:
        return None
    key, cost = end_state
    cells = []
    while key is not None:
        cells.append((xs_l[key[0]], ys_l[key[1]]))
        key = came[key]
    cells.reverse()
    pts = [(sx, sy)] + cells + [(tx, ty)]
    return cost, _simplify(pts)


def _simplify(pts: list[Point]) -> list[Point]:
    out: list[Point] = []
    for p in pts:
        p = (round(p[0], 2), round(p[1], 2))
        if out and out[-1] == p:
            continue
        if len(out) >= 2:
            (ax, ay), (bx, by) = out[-2], out[-1]
            if (ax == bx == p[0]) or (ay == by == p[1]):
                out[-1] = p
                continue
        out.append(p)
    return out


def loop(b: Box, side: str = "right", size: float = 40.0) -> list[Point]:
    """Self-transition: leaves ``side`` at 30 % and re-enters it at 70 %, bulging out by ``size``."""
    x, y, w, h = b
    if side == "right":
        return [(x + w, y + 0.3 * h), (x + w + size, y + 0.3 * h), (x + w + size, y + 0.7 * h), (x + w, y + 0.7 * h)]
    if side == "left":
        return [(x, y + 0.3 * h), (x - size, y + 0.3 * h), (x - size, y + 0.7 * h), (x, y + 0.7 * h)]
    if side == "bottom":
        return [(x + 0.3 * w, y + h), (x + 0.3 * w, y + h + size), (x + 0.7 * w, y + h + size), (x + 0.7 * w, y + h)]
    return [(x + 0.3 * w, y), (x + 0.3 * w, y - size), (x + 0.7 * w, y - size), (x + 0.7 * w, y)]

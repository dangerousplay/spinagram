"""Orthogonal, crossing-aware routing for hand-placed diagrams (roadmap E4) and shared trunks (E3)."""
from __future__ import annotations

from ..autolayout.route import MARGIN, route
from ..scene import Binding, Connector, Shape

CROSSING = 120.0  # cost of crossing an edge already routed, in px of length (two bends)


def crosses(p, q, a, b) -> bool:
    """Strict crossing of segment p→q with a→b (axis-aligned with perpendicular, else general)."""
    def orient(u, v, w):
        return (v[0] - u[0]) * (w[1] - u[1]) - (v[1] - u[1]) * (w[0] - u[0])
    d1, d2, d3, d4 = orient(a, b, p), orient(a, b, q), orient(p, q, a), orient(p, q, b)
    return d1 * d2 < 0 and d3 * d4 < 0


def segments(c: Connector) -> list[tuple]:
    from ..qa import polyline

    pts = polyline(c)
    return list(zip(pts, pts[1:]))


def crossings(connectors: list[Connector]) -> int:
    """Pairs of segments from different edges that cross."""
    segs = [(i, s) for i, c in enumerate(connectors) for s in segments(c)]
    return sum(1 for k, (i, a) in enumerate(segs) for j, b in segs[k + 1:] if i != j and crosses(*a, *b))


def _box(s: Shape) -> tuple[float, float, float, float]:
    return (s.x, s.y, s.w, s.h)


def _side(p, q) -> str:
    """The side of a box a segment leaves from (p on the box) or arrives at (q on the box, reversed)."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    d = ((dx > 0) - (dx < 0), (dy > 0) - (dy < 0))
    return {(1, 0): "right", (-1, 0): "left", (0, 1): "bottom", (0, -1): "top"}.get(d, "right")


def route_ortho(connectors: list[Connector], todo: list[int], shapes: dict[str, Shape],
                targets: dict[str, Shape], penalty: float = CROSSING) -> None:
    """Route connectors ``todo`` (indices, in declaration order) orthogonally around node shapes, each paying
    ``penalty`` per crossing with every edge drawn so far. Edges without a bound shape at both ends stay."""
    obstacles = [_box(s) for s in shapes.values() if s.role == "node"]
    placed = [segments(c) for i, c in enumerate(connectors) if i not in todo]
    for i in todo:
        c = connectors[i]
        if c.src is None or c.dst is None:
            continue
        a, b = targets[c.src.shape_id], targets[c.dst.shape_id]
        drawn = [seg for segs in placed for seg in segs]
        guides = [(x + dx, y + dy) for seg in drawn for (x, y) in seg for dx, dy in ((-MARGIN, -MARGIN),
                                                                                    (MARGIN, MARGIN))]

        def cost(p, q, drawn=drawn):
            return penalty * sum(crosses(p, q, *s) for s in drawn)
        sides = (c.src.side if c.src.target == "node" and c.src.__dict__.get("explicit") else None,
                 c.dst.side if c.dst.target == "node" and c.dst.__dict__.get("explicit") else None)
        pts = route(_box(a), _box(b), obstacles, sides=sides, penalty=cost, guides=guides)
        c.points, c.route = [tuple(p) for p in pts], "poly"
        c.src = Binding(c.src.shape_id, _side(pts[0], pts[1]), 0.5, c.src.target)
        c.dst = Binding(c.dst.shape_id, _side(pts[-1], pts[-2]), 0.5, c.dst.target)
        placed.append(segments(c))

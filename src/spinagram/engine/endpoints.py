"""Edge endpoint resolution: ``node``, ``node.side``, ``node.side@frac``, ``zone:<id>[.side[@frac]]`` or a point."""
from __future__ import annotations

from ..scene import Binding, Shape

Point = tuple[float, float]
ZONE = "zone:"
CORNER = 24.0  # zone endpoints stay this far from the corners


def _split(ref: str) -> tuple[str, str, str]:
    """``name.side@frac`` → (name, side, frac); a zone name keeps its ``zone:`` prefix."""
    name, _, side = ref.partition(".")
    side, _, frac = side.partition("@")
    return name, side, frac


def _zone(name: str, zones: dict[str, Shape], diagram_id: str) -> Shape:
    zid = name[len(ZONE):]
    if zid not in zones:
        raise KeyError(f"{diagram_id}: edge refers to unknown zone {zid!r}")
    return zones[zid]


def center(ref, shapes: dict[str, Shape], zones: dict[str, Shape] | None = None) -> Point:
    """The point an endpoint aims at: the anchor when a side is given, else the shape centre."""
    if not isinstance(ref, str):
        return float(ref[0]), float(ref[1])
    name, side, frac = _split(ref)
    s = _zone(name, zones or {}, "") if name.startswith(ZONE) else shapes[name]
    if side:
        return s.anchor(side, float(frac) if frac else 0.5)
    return s.x + s.w / 2, s.y + s.h / 2


def _facing(s: Shape, ox: float, oy: float) -> str:
    cx, cy = s.x + s.w / 2, s.y + s.h / 2
    dx, dy = ox - cx, oy - cy
    return ("right" if dx > 0 else "left") if abs(dx) * s.h >= abs(dy) * s.w else ("bottom" if dy > 0 else "top")


def _zone_side(z: Shape, ox: float, oy: float) -> str:
    """The side facing a point outside the zone; for a point inside, the nearest side (inner face)."""
    if z.x < ox < z.x + z.w and z.y < oy < z.y + z.h:
        d = {"left": ox - z.x, "right": z.x + z.w - ox, "top": oy - z.y, "bottom": z.y + z.h - oy}
        return min(d, key=lambda k: (d[k], ("top", "bottom", "left", "right").index(k)))
    return _facing(z, ox, oy)


def _clamped_frac(z: Shape, side: str, ox: float, oy: float) -> float:
    """Fraction along ``side`` of the point closest to (ox, oy), kept ``CORNER`` px from the corners."""
    if side in ("top", "bottom"):
        lo, hi, v, span = z.x + CORNER, z.x + z.w - CORNER, ox, z.w
        start = z.x
    else:
        lo, hi, v, span = z.y + CORNER, z.y + z.h - CORNER, oy, z.h
        start = z.y
    v = min(max(v, lo), hi) if lo <= hi else start + span / 2
    return (v - start) / span


def resolve(ref, other, shapes: dict[str, Shape], diagram_id: str = "",
            zones: dict[str, Shape] | None = None) -> tuple[Point, Binding | None]:
    """Point and connector binding of ``ref``; without a side a node faces ``other`` and a zone takes the
    point of its facing side closest to ``other``."""
    if not isinstance(ref, str):
        return (float(ref[0]), float(ref[1])), None
    name, side, frac = _split(ref)
    if name.startswith(ZONE):
        z = _zone(name, zones or {}, diagram_id)
        ox, oy = center(other, shapes, zones)
        side = side or _zone_side(z, ox, oy)
        f = float(frac) if frac else _clamped_frac(z, side, ox, oy)
        return z.anchor(side, f), Binding(z.id, side, f, "zone")
    if name not in shapes:
        raise KeyError(f"{diagram_id}: edge refers to unknown node {name!r}")
    s = shapes[name]
    explicit = bool(side)
    if not side:  # auto: face the other endpoint
        side = _facing(s, *center(other, shapes, zones))
    f = float(frac) if frac else 0.5
    pt = s.anchor(side, f)
    if side == "center":
        return pt, None
    b = Binding(name, side, f)
    b.__dict__["explicit"] = explicit  # a side the author chose (routers keep it)
    return pt, b


BUS_INSET = 10.0


def bus(z: Shape, side: str, children: list[Shape], end: Point) -> tuple[Point, Point]:
    """A bar inside zone ``z``, ``BUS_INSET`` px from ``side``, spanning the children's centres projected on that
    side (the whole side minus the corners without children); it always reaches the edge's border point."""
    horizontal = side in ("top", "bottom")
    if children:
        cs = [c.x + c.w / 2 if horizontal else c.y + c.h / 2 for c in children]
        lo, hi = min(cs), max(cs)
    else:
        lo, hi = (z.x + CORNER, z.x + z.w - CORNER) if horizontal else (z.y + CORNER, z.y + z.h - CORNER)
    v = end[0] if horizontal else end[1]
    lo, hi = min(lo, v), max(hi, v)
    off = {"top": z.y + BUS_INSET, "bottom": z.y + z.h - BUS_INSET, "left": z.x + BUS_INSET,
           "right": z.x + z.w - BUS_INSET}[side]
    return ((lo, off), (hi, off)) if horizontal else ((off, lo), (off, hi))


def straight_refs(a: Shape, b: Shape) -> tuple[str, str] | None:
    """Anchors (``a.side@f``, ``b.side@f``) that make an edge from ``a`` to ``b`` vertical or horizontal: the
    middle of the span the boxes share on one axis. None when they share no span."""
    x0, x1 = max(a.x, b.x), min(a.x + a.w, b.x + b.w)
    y0, y1 = max(a.y, b.y), min(a.y + a.h, b.y + b.h)
    if x1 - x0 > 0.5 and (a.y + a.h <= b.y or b.y + b.h <= a.y):  # stacked: vertical edge
        mx = (x0 + x1) / 2
        down = a.y < b.y
        return (f"{a.id}.{'bottom' if down else 'top'}@{(mx - a.x) / a.w:.6g}",
                f"{b.id}.{'top' if down else 'bottom'}@{(mx - b.x) / b.w:.6g}")
    if y1 - y0 > 0.5 and (a.x + a.w <= b.x or b.x + b.w <= a.x):  # side by side: horizontal edge
        my = (y0 + y1) / 2
        right = a.x < b.x
        return (f"{a.id}.{'right' if right else 'left'}@{(my - a.y) / a.h:.6g}",
                f"{b.id}.{'left' if right else 'right'}@{(my - b.y) / b.h:.6g}")
    return None

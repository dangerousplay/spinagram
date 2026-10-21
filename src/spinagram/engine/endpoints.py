"""Edge endpoint resolution: ``node``, ``node.side``, ``node.side@frac`` or an absolute point."""
from __future__ import annotations

from ..scene import Binding, Shape

Point = tuple[float, float]


def center(ref, shapes: dict[str, Shape]) -> Point:
    """The point an endpoint aims at: the anchor when a side is given, else the shape centre."""
    if not isinstance(ref, str):
        return float(ref[0]), float(ref[1])
    name, _, side = ref.partition(".")
    s = shapes[name]
    if side:
        side, _, frac = side.partition("@")
        return s.anchor(side, float(frac) if frac else 0.5)
    return s.x + s.w / 2, s.y + s.h / 2


def resolve(ref, other, shapes: dict[str, Shape], diagram_id: str = "") -> tuple[Point, Binding | None]:
    """Point and connector binding of ``ref``; without a side the shape faces ``other``."""
    if not isinstance(ref, str):
        return (float(ref[0]), float(ref[1])), None
    name, _, side = ref.partition(".")
    side, _, frac = side.partition("@")
    if name not in shapes:
        raise KeyError(f"{diagram_id}: edge refers to unknown node {name!r}")
    s = shapes[name]
    if not side:  # auto: face the other endpoint
        ox, oy = center(other, shapes)
        cx, cy = s.x + s.w / 2, s.y + s.h / 2
        dx, dy = ox - cx, oy - cy
        side = ("right" if dx > 0 else "left") if abs(dx) * s.h >= abs(dy) * s.w else ("bottom" if dy > 0 else "top")
    f = float(frac) if frac else 0.5
    pt = s.anchor(side, f)
    return pt, (Binding(name, side, f) if side != "center" else None)

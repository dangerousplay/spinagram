"""Automatic legend: one row per edge or zone style that carries a ``meaning`` (roadmap L1)."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..model import Diagram
from ..scene import Connector, Scene, Shape


@dataclass
class Row:
    kind: str                       # edge | zone
    label: str                      # the meaning
    color: str | None = None        # edge colour / zone stroke
    dash: tuple | None = None       # dash pattern; () for the default dash, None for solid
    fill: str | None = None         # zones
    width: float = 2.0
    cap: str | None = None
    sources: list[str] = field(default_factory=list)  # scene ids drawn with this style


def _dash(dashed: bool, pattern) -> tuple | None:
    return tuple(pattern) if pattern else (() if dashed else None)


def collect(d: Diagram, scene: Scene) -> list[Row]:
    """Rows in declaration order: edges first, then zones; a style seen again joins its first row."""
    items = {i.id: i for i in scene.items if isinstance(i, (Connector, Shape))}
    rows: dict[tuple, Row] = {}
    for k, e in enumerate(d.edges):
        c = items.get(f"e{k}")
        if not e.meaning or not isinstance(c, Connector):
            continue
        key = ("edge", c.color, _dash(c.dashed, c.dash))
        rows.setdefault(key, Row("edge", e.meaning, c.color, _dash(c.dashed, c.dash), width=c.width)).sources \
            .append(c.id)
    for k, z in enumerate(d.zones):
        s = items.get(f"z{k}")
        if not z.meaning or not isinstance(s, Shape):
            continue
        key = ("zone", s.fill, s.stroke, _dash(s.dashed, s.dash))
        rows.setdefault(key, Row("zone", z.meaning, s.stroke, _dash(s.dashed, s.dash), s.fill, s.stroke_width or 2,
                                 s.cap)).sources.append(s.id)
    return list(rows.values())

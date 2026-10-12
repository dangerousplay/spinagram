"""Backend-neutral layout graph handed to engines, and their result."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

Box = tuple[float, float, float, float]  # x, y, w, h


@dataclass
class LNode:
    id: str
    w: float
    h: float
    kind: str = "box"  # node kind: engines may place ports by shape (diamonds, circles)


@dataclass
class LGroup:
    id: str
    children: list["LNode | LGroup"] = field(default_factory=list)
    pad: tuple[float, float, float, float] = (0, 0, 0, 0)  # top (incl. label band), right, bottom, left
    hints: dict[str, Any] = field(default_factory=dict)    # direction, columns, gap, align
    label: str | None = None

    def walk(self):
        """Pre-order: this group, then every descendant."""
        yield self
        for c in self.children:
            if isinstance(c, LGroup):
                yield from c.walk()
            else:
                yield c


@dataclass
class LEdge:
    id: str
    src: str
    dst: str
    label_w: float = 0.0  # width of the edge's label pill (engines may reserve room for it)


@dataclass
class LGraph:
    root: LGroup                      # synthetic, no padding; its children are the top-level items
    edges: list[LEdge] = field(default_factory=list)
    direction: str = "right"          # right | down
    spacing: dict[str, float] = field(default_factory=dict)   # gap, node_gap, rank_gap
    options: dict[str, Any] = field(default_factory=dict)     # engine passthrough
    loops: list[LEdge] = field(default_factory=list)          # self-edges; engines may route them or not

    def node_ids(self) -> list[str]:
        return [c.id for c in self.root.walk() if isinstance(c, LNode)]


@dataclass
class LResult:
    boxes: dict[str, Box]                                   # every node and group (root excluded); absolute
    routes: dict[str, list[tuple[float, float]]] = field(default_factory=dict)  # edge id → polyline incl. ends

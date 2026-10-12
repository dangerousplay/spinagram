"""Backend-neutral scene: absolute geometry, hex colours, resolved fonts, wrapped text.

Backends read only these types. Items are drawn in list order (back to front).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .theme import FontRef

Point = tuple[float, float]


@dataclass
class TextBlock:
    lines: list[str]            # wrapped for the box width (SVG, Figma)
    paragraphs: list[str]       # source text (PowerPoint reflows it natively)
    font: FontRef
    color: str
    leading: float              # line height in px

    @property
    def height(self) -> float:
        return len(self.lines) * self.leading

    def baseline_offset(self) -> float:
        """First baseline measured from the top of the block."""
        return (self.leading - self.font.size) / 2 + self.font.size * 0.8


@dataclass
class Label:
    """Text inside a shape: blocks stacked and centred vertically in ``box``."""
    blocks: list[TextBlock]
    box: tuple[float, float, float, float]   # x, y, w, h of the text area
    align: str = "left"                       # left | center
    gap: float = 10                           # space between blocks
    valign: str = "middle"

    def place(self) -> list[tuple[TextBlock, float, float]]:
        """(block, x, top) for each block, honouring align/valign."""
        x, y, w, h = self.box
        total = sum(b.height for b in self.blocks) + self.gap * max(0, len(self.blocks) - 1)
        top = y + (h - total) / 2 if self.valign == "middle" else y
        out = []
        for b in self.blocks:
            bx = x + w / 2 if self.align == "center" else x
            out.append((b, bx, top))
            top += b.height + self.gap
        return out


@dataclass
class Icon:
    path: Path
    x: float
    y: float
    size: float

    @property
    def mime(self) -> str:
        return {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg"}.get(self.path.suffix.lower(), "image/png")


_MIDPOINT_KINDS = frozenset({"decision", "merge", "choice", "connector", "initial", "final", "flow_final",
                             "history", "deep_history"})  # outline touches the box only at side midpoints


@dataclass
class Shape:
    id: str
    kind: str                  # rect | diamond | pill
    x: float
    y: float
    w: float
    h: float
    fill: str | None
    stroke: str | None = None
    stroke_width: float = 0
    radius: float = 0
    dashed: bool = False
    opacity: float = 1.0
    label: Label | None = None
    icon: Icon | None = None
    role: str = "node"         # node | zone | pill | swatch | chrome
    parts: list | None = None  # symbol geometry (``shapes.Part``) for flow/activity/state kinds
    dash: list[float] | None = None    # explicit dash pattern (CSS stroke-dasharray); None = default dash
    shadow: tuple | None = None        # (dx, dy, blur, colour, alpha) drop shadow (CSS box-shadow)
    fill_opacity: float = 1.0          # alpha of the fill only (CSS fill-opacity)

    def anchor(self, side: str, frac: float = 0.5) -> Point:
        x, y, w, h = self.x, self.y, self.w, self.h
        if self.kind == "diamond" or self.kind in _MIDPOINT_KINDS:
            pts = {"top": (x + w / 2, y), "bottom": (x + w / 2, y + h), "left": (x, y + h / 2),
                   "right": (x + w, y + h / 2)}
            return pts.get(side, (x + w / 2, y + h / 2))
        return {"top": (x + w * frac, y), "bottom": (x + w * frac, y + h), "left": (x, y + h * frac),
                "right": (x + w, y + h * frac)}.get(side, (x + w / 2, y + h / 2))


@dataclass
class Binding:
    shape_id: str
    side: str
    frac: float = 0.5


@dataclass
class Connector:
    id: str
    points: list[Point]        # polyline; for route="curve": [start, control, end] (quadratic)
    route: str                 # straight | poly | curve
    color: str
    width: float
    dashed: bool = False
    arrow_start: bool = False
    arrow_end: bool = True
    src: Binding | None = None
    dst: Binding | None = None
    label: Shape | None = None
    dash: list[float] | None = None
    marker_start: str = "arrow"        # arrow | open-arrow | diamond | open-diamond | circle | bar | none
    marker_end: str = "arrow"
    opacity: float = 1.0


@dataclass
class Text:
    id: str
    x: float                   # anchor x (see ``anchor``)
    y: float                   # first baseline
    block: TextBlock
    anchor: str = "start"      # start | middle | end
    letter_spacing: float = 0
    width: float | None = None

    @property
    def top(self) -> float:
        return self.y - self.block.baseline_offset()


@dataclass
class Line:
    id: str
    x1: float
    y1: float
    x2: float
    y2: float
    color: str
    width: float = 1


@dataclass
class Image:
    id: str
    path: Path
    x: float
    y: float
    w: float
    h: float


@dataclass
class Cell:
    block: TextBlock
    fill: str | None
    icon: Icon | None = None
    pad_left: float = 16
    bold: bool = False


@dataclass
class TableGrid:
    id: str
    x: float
    y: float
    col_widths: list[float]
    row_heights: list[float]
    cells: list[list[Cell]]    # row 0 is the header
    border: str
    header_radius: float = 0

    @property
    def w(self) -> float:
        return sum(self.col_widths)

    @property
    def h(self) -> float:
        return sum(self.row_heights)


Item = Shape | Connector | Text | Line | Image | TableGrid


@dataclass
class Scene:
    id: str
    title: str
    slug: str
    width: float
    height: float
    background: str
    items: list[Item] = field(default_factory=list)
    notes: str | None = None
    item_facts: dict[str, list[str]] = field(default_factory=dict)  # item id → fact ids shown on it
    sources: list[dict] = field(default_factory=list)               # review records of every fact used
    meta_tooltips: dict[str, str] = field(default_factory=dict)     # fact id → one-line provenance
    layout_overflow: tuple[int, int] | None = None  # auto layout exceeding its area (px wide, px tall)
    model_issues: list[tuple[str, str]] = field(default_factory=list)  # (item, message) from model rules
    style_warnings: list[str] = field(default_factory=list)            # stylesheet diagnostics

    def shapes(self) -> dict[str, Shape]:
        return {i.id: i for i in self.items if isinstance(i, Shape)}

    def fonts(self) -> list[FontRef]:
        """Distinct fonts used (for embedding / loading)."""
        seen: dict[tuple, FontRef] = {}

        def add(b: TextBlock):
            f = b.font
            seen.setdefault((f.family, f.weight, f.italic), f)

        for it in self.items:
            if isinstance(it, Shape) and it.label:
                for b in it.label.blocks:
                    add(b)
            elif isinstance(it, Text):
                add(it.block)
            elif isinstance(it, Connector) and it.label and it.label.label:
                for b in it.label.label.blocks:
                    add(b)
            elif isinstance(it, TableGrid):
                for row in it.cells:
                    for c in row:
                        add(c.block)
        return list(seen.values())

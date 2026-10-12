"""Annotations as scene primitives: the legend card, numbered steps, callouts.

Legends and step panels sit in a band reserved at the right or bottom of the layout area (``band``), so they
never overlap content. Everything is drawn with the scene's own shapes, connectors and text, which every
backend already renders natively and editably.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .model import Diagram
from .scene import Connector, Icon, Label, Shape, Text, TextBlock
from .text import measure, wrap_paragraphs
from .theme import Theme


@dataclass
class Entry:
    key: str            # as written: ``.web``, ``edge.async``, ``style:dark``, ``aws:s3``
    label: str
    kind: str           # node | edge | style | icon
    ref: str | None     # style-tree key of the first element carrying the key (``node:a``, ``edge:0``)
    used: bool = True
    value: str = ""     # class, style or icon name


def humanize(name: str) -> str:
    """``edge-svc`` → ``Edge svc``."""
    s = re.sub(r"[-_]+", " ", name).strip()
    return s[:1].upper() + s[1:]


def _classes(cls: str | None) -> list[str]:
    return (cls or "").split()


def _parse_key(key: str) -> tuple[str, str]:
    """``(kind, value)`` of a legend key."""
    if key.startswith("edge."):
        return "edge", key[5:]
    if key.startswith("node."):
        return "node", key[5:]
    if key.startswith("."):
        return "node", key[1:]
    if key.startswith("style:"):
        return "style", key[6:]
    if ":" in key:
        return "icon", key
    return "node", key


def _first(d: Diagram, kind: str, value: str) -> str | None:
    if kind == "edge":
        return next((f"edge:{i}" for i, e in enumerate(d.edges) if value in _classes(e.cls)), None)
    if kind == "node":
        return next((f"node:{n.id}" for n in d.nodes if value in _classes(n.cls) or n.style == value), None)
    if kind == "style":
        return next((f"node:{n.id}" for n in d.nodes
                     if (n.style or "default") == value and n.kind in ("box", "note")), None)
    return next((f"node:{n.id}" for n in d.nodes if n.icon == value), None)


def legend_entries(d: Diagram) -> list[Entry]:
    """The legend's entries: the given items in order, or every node class, non-default node style and edge
    class the diagram uses, once each, in first-use order (nodes, then edges)."""
    lg = d.annotations.legend
    if lg is None:
        return []
    if lg.items is not None:
        out = []
        for key, label in lg.items.items():
            kind, value = _parse_key(key)
            ref = _first(d, kind, value)
            out.append(Entry(key, str(label), kind, ref, ref is not None, value))
        return out
    out, seen = [], set()

    def add(key: str, kind: str, value: str, ref: str) -> None:
        if key not in seen:
            seen.add(key)
            out.append(Entry(key, humanize(value), kind, ref, True, value))

    for n in d.nodes:
        for c in _classes(n.cls):
            add(f".{c}", "node", c, f"node:{n.id}")
        if n.style and n.style != "default":
            add(f"style:{n.style}", "style", n.style, f"node:{n.id}")
    for i, e in enumerate(d.edges):
        for c in _classes(e.cls):
            add(f"edge.{c}", "edge", c, f"edge:{i}")
    return out


# geometry -----------------------------------------------------------------------------------------
def settings(theme: Theme) -> dict:
    base = {"band": 360, "gap": 32, "padding": 22, "radius": 18, "title_size": 20, "text_size": 16, "row_gap": 12,
            "swatch_w": 46, "swatch_h": 28, "badge": 30, "badge_size": 15, "callout_width": 320,
            "callout_gap": 36}
    return base | (theme.defaults("annotations") or {})


def _head(a: dict) -> float:
    """Card padding plus the title line."""
    return a["padding"] + a["title_size"] * 1.3 + 10


def legend_rows(entries: list[Entry], width: float, theme: Theme, columns: int = 1) -> list[list[Entry]]:
    """Entries packed into rows: ``columns`` per row in a right band, or flowed by label width when
    ``columns`` is 0 (bottom band)."""
    if columns:
        return [entries[i:i + columns] for i in range(0, len(entries), columns)]
    a = settings(theme)
    font = theme.font("body", 400, a["text_size"])
    inner = width - 2 * a["padding"]
    rows: list[list[Entry]] = [[]]
    used = 0.0
    for e in entries:
        w = a["swatch_w"] + 10 + measure(e.label, font)
        if rows[-1] and used + 28 + w > inner:
            rows.append([])
            used = 0.0
        used += (28 if rows[-1] else 0) + w
        rows[-1].append(e)
    return rows if rows[0] else []


def legend_height(rows: list[list[Entry]], theme: Theme) -> float:
    a = settings(theme)
    n = len(rows)
    return _head(a) + n * a["swatch_h"] + max(0, n - 1) * a["row_gap"] + a["padding"]


def step_lines(text: str, width: float, theme: Theme) -> list[str]:
    a = settings(theme)
    font = theme.font("body", 400, a["text_size"])
    return wrap_paragraphs([text], font, width - 2 * a["padding"] - a["badge"] - 12)


def step_row_height(lines: list[str], theme: Theme) -> float:
    a = settings(theme)
    return max(a["badge"], len(lines) * a["text_size"] * 1.35)


def steps_height(d: Diagram, width: float, theme: Theme) -> float:
    a = settings(theme)
    steps = d.annotations.steps
    rows = [step_row_height(step_lines(s.text, width, theme), theme) for s in steps]
    return _head(a) + sum(rows) + max(0, len(rows) - 1) * a["row_gap"] + a["padding"]


def band(d: Diagram, theme: Theme, width: float) -> tuple[str, float] | None:
    """``(side, thickness)`` reserved for the legend and steps panels (thickness includes the gap to the
    content), or ``None``. ``width`` is the layout area's width (for a bottom band's rows)."""
    ann = d.annotations
    if not (ann.legend or ann.steps):
        return None
    a = settings(theme)
    side = ann.legend.position if ann.legend else "right"
    if side == "right":
        return "right", a["band"] + a["gap"]
    steps_w = a["band"] if ann.steps else 0
    legend_w = width - (steps_w + a["gap"] if steps_w and ann.legend else 0) if ann.legend else 0
    h = 0.0
    if ann.legend:
        h = legend_height(legend_rows(legend_entries(d), legend_w, theme, columns=0), theme)
    if ann.steps:
        h = max(h, steps_height(d, steps_w, theme))
    return "bottom", h + a["gap"]


# scene ----------------------------------------------------------------------------------------------
Rect = tuple[float, float, float, float]

PANEL_SHADOW = (0.0, 6.0, 18.0, "#0F172A", 0.10)


class Annotator:
    """Draws a diagram's annotations with a layout ``_Builder`` (its theme, computed CSS and node shapes)."""

    def __init__(self, builder) -> None:
        from .autolayout import _area

        self.b, self.d, self.t = builder, builder.d, builder.t
        self.a = settings(self.t)
        self.area: Rect = _area(self.d, self.t, reserve=False)
        self.rects: list[Rect] = []       # panels and callouts already placed (callouts avoid them)
        self.issues: list[tuple[str, str, str]] = []  # (item, kind, detail) for ``spinagram check``
        self.overflow = 0.0

    # pieces ------------------------------------------------------------------------------------------
    def _font(self, role: str, weight: int, size: float, italic: bool = False):
        return self.t.font(role, weight, size, italic)

    def _text(self, id: str, x: float, top: float, lines: list[str], font, color: str) -> Text:

        blk = TextBlock(lines=lines, paragraphs=[" ".join(lines)], font=font, color=color, leading=font.size * 1.35)
        width = max((measure(ln, font) for ln in lines), default=0)
        return Text(id=id, x=x, y=top + blk.baseline_offset(), block=blk, width=width)

    def card(self, id: str, x: float, y: float, w: float, h: float, key: str) -> list:

        cs = self.b._css(key)
        s = Shape(id=id, kind="rect", x=x, y=y, w=w, h=h, fill=self.t.color(self.t.get("canvas", "background")),
                  stroke=self.t.color("border"), stroke_width=1.5, radius=self.a["radius"], shadow=PANEL_SHADOW,
                  role="panel")
        self.b._decorate(s, cs.get(""))
        return [s]

    def title(self, id: str, x: float, y: float, text: str, key: str) -> Text:
        cs = self.b._css(key)
        col, wt, it = self.b._text(cs, "title", self.t.color("text"), 700)
        size = (cs.get("title") or {}).get("font-size") or self.a["title_size"]
        return self._text(id, x, y, [text], self._font("heading", wt, size, it), col)

    def badge(self, id: str, cx: float, cy: float, n: int, key: str) -> Shape:
        """A numbered circle centred on (cx, cy), styled by ``step`` rules."""

        cs = self.b._css(key)
        size = self.a["badge"]
        col, wt, it = self.b._text(cs, "label", "#FFFFFF", 700)
        font = self._font("body", wt, (cs.get("label") or {}).get("font-size") or self.a["badge_size"], it)
        blk = TextBlock([str(n)], [str(n)], font, col, font.size * 1.2)
        x, y = cx - size / 2, cy - size / 2
        s = Shape(id=id, kind="pill", x=x, y=y, w=size, h=size, fill=self.t.color("primary"),
                  stroke=self.t.color(self.t.get("canvas", "background")), stroke_width=2, radius=size / 2,
                  role="pill", label=Label([blk], (x, y, size, size), align="center"))
        self.b._decorate(s, cs.get(""))
        return s

    # legend and steps -----------------------------------------------------------------------------
    def _swatch(self, j: int, e: Entry, x: float, y: float, connectors: list) -> list:

        a = self.a
        w, h = a["swatch_w"], a["swatch_h"]
        if e.kind == "edge":
            ref = connectors[int(e.ref.split(":")[1])] if e.ref else None
            ed = self.t.defaults("edge")
            c = Connector(id=f"legend-{j}-sample", points=[(x + 2, y + h / 2), (x + w - 2, y + h / 2)],
                          route="straight", color=ref.color if ref else self.t.edge_color(None),
                          width=ref.width if ref else ed.get("width", 3.5), dashed=ref.dashed if ref else False,
                          dash=ref.dash if ref else None, arrow_start=ref.arrow_start if ref else False,
                          arrow_end=ref.arrow_end if ref else True,
                          marker_start=ref.marker_start if ref else "none",
                          marker_end=ref.marker_end if ref else "arrow", opacity=ref.opacity if ref else 1.0)
            return [c]
        if e.kind == "icon":
            p = self.t.icon(e.value, "light", self.d.base_dir)
            s = Shape(id=f"legend-{j}-swatch", kind="rect", x=x, y=y, w=w, h=h, fill=None, role="swatch",
                      icon=Icon(p, x + (w - h) / 2, y, h) if p is not None else None)
            return [s]
        node = self.b.shapes.get(e.ref.split(":", 1)[1]) if e.ref else None
        st = self.t.node_style(e.value if e.kind == "style" else None)
        s = Shape(id=f"legend-{j}-swatch", kind="rect", x=x, y=y, w=w, h=h,
                  fill=node.fill if node else st["fill"], stroke=node.stroke if node else st["stroke"],
                  stroke_width=node.stroke_width if node else self.t.defaults("node").get("stroke_width", 3),
                  radius=node.radius if node else 6, dashed=node.dashed if node else False,
                  dash=node.dash if node else None, fill_opacity=node.fill_opacity if node else 1.0,
                  role="swatch")
        return [s]

    def _legend(self, x: float, y: float, w: float, rows: list[list[Entry]], connectors: list,
                flow: bool = False) -> list:
        """The legend card; entries sit in equal columns, or one after another when ``flow`` (bottom band)."""
        a = self.a
        h = legend_height(rows, self.t)
        out = self.card("legend", x, y, w, h, "legend") + [
            self.title("legend-title", x + a["padding"], y + a["padding"], self.d.annotations.legend.title, "legend")]
        cs = self.b._css("legend")
        col, wt, it = self.b._text(cs, "body", self.t.color("text-muted"), 400)
        font = self._font("body", wt, a["text_size"], it)
        cols = max((len(r) for r in rows), default=1)
        inner = w - 2 * a["padding"]
        top = y + _head(a)
        j = 0
        for row in rows:
            cx = x + a["padding"]
            for e in row:
                out += self._swatch(j, e, cx, top, connectors)
                ty = top + (a["swatch_h"] - a["text_size"] * 1.35) / 2
                out.append(self._text(f"legend-{j}-label", cx + a["swatch_w"] + 10, ty, [e.label], font, col))
                cx += a["swatch_w"] + 10 + measure(e.label, font) + 28 if flow else inner / cols
                j += 1
            top += a["swatch_h"] + a["row_gap"]
        self.rects.append((x, y, w, h))
        return out

    def _steps(self, x: float, y: float, w: float) -> list:
        a = self.a
        steps = sorted(enumerate(self.d.annotations.steps), key=lambda p: p[1].n)
        h = steps_height(self.d, w, self.t)
        out = self.card("steps", x, y, w, h, "diagram") + [
            self.title("steps-title", x + a["padding"], y + a["padding"], "Steps", "diagram")]
        font = self._font("body", 400, a["text_size"])
        top = y + _head(a)
        for k, (i, st) in enumerate(steps):
            lines = step_lines(st.text, w, self.t)
            rh = step_row_height(lines, self.t)
            out.append(self.badge(f"steps-{k}-badge", x + a["padding"] + a["badge"] / 2, top + a["badge"] / 2,
                                  st.n, f"step:{i}"))
            th = len(lines) * a["text_size"] * 1.35
            out.append(self._text(f"steps-{k}-text", x + a["padding"] + a["badge"] + 12,
                                  top + max(0.0, (a["badge"] - th) / 2) if len(lines) == 1 else top, lines, font,
                                  self.t.color("text")))
            top += rh + a["row_gap"]
        self.rects.append((x, y, w, h))
        return out

    def panels(self, connectors: list) -> list:
        """The legend card and the steps panel inside the reserved band."""
        ann = self.d.annotations
        b = band(self.d, self.t, self.area[2])
        if b is None:
            return []
        a = self.a
        ax, ay, aw, ah = self.area
        side, thickness = b
        out: list = []
        entries = legend_entries(self.d)
        if side == "right":
            x, w = ax + aw - a["band"], a["band"]
            steps_h = steps_height(self.d, w, self.t) + a["gap"] if ann.steps else 0.0
            rows = legend_rows(entries, w, self.t, columns=1)
            if ann.legend and legend_height(rows, self.t) + steps_h > ah:
                rows = legend_rows(entries, w, self.t, columns=2)
            y = ay
            if ann.legend:
                out += self._legend(x, y, w, rows, connectors)
                y += legend_height(rows, self.t) + a["gap"]
            if ann.steps:
                out += self._steps(x, y, w)
                y += steps_h
            used = y - a["gap"] - ay
        else:
            y = ay + ah - (thickness - a["gap"])
            steps_w = a["band"] if ann.steps else 0
            legend_w = aw - (steps_w + a["gap"] if steps_w and ann.legend else 0)
            if ann.legend:
                out += self._legend(ax, y, legend_w, legend_rows(entries, legend_w, self.t, columns=0), connectors,
                                    flow=True)
            if ann.steps:
                out += self._steps(ax + aw - steps_w, y, steps_w)
            used = thickness - a["gap"]
        self.overflow = max(0.0, used - ah)  # px the panels exceed the area height
        return out

    # step badges ----------------------------------------------------------------------------------
    @staticmethod
    def _midpoint(points: list[tuple[float, float]]) -> tuple[float, float]:
        """Halfway along a polyline, by length."""
        segs = [(p, q, ((q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2) ** 0.5) for p, q in zip(points, points[1:])]
        half = sum(s[2] for s in segs) / 2
        for (x1, y1), (x2, y2), ln in segs:
            if half <= ln and ln > 0:
                f = half / ln
                return x1 + (x2 - x1) * f, y1 + (y2 - y1) * f
            half -= ln
        return points[len(points) // 2]

    def badges(self, connectors: list) -> list:
        """A numbered badge per step: beside the edge label, at the edge's midpoint, or on a node's corner."""
        out = []
        for i, st in enumerate(self.d.annotations.steps):
            if st.edge is not None:
                c = connectors[st.edge]
                if c.label is not None:
                    lab = c.label
                    cx, cy = lab.x + lab.w + 6 + self.a["badge"] / 2, lab.y + lab.h / 2
                else:
                    cx, cy = self._midpoint(c.points) if c.route != "curve" else c.points[1]
            else:
                node = self.b.shapes[st.node]
                cx, cy = node.x, node.y
            out.append(self.badge(f"step-{i}-badge", cx, cy, st.n, f"step:{i}"))
        return out

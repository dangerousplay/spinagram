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
                  radius=node.radius * h / node.h if node and node.h else 6, dashed=node.dashed if node else False,
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

    def _fits_two_columns(self, entries: list[Entry], w: float) -> bool:
        """Every label fits half the card next to its swatch (else one column, and ``check`` reports overflow)."""
        a = self.a
        font = self._font("body", 400, a["text_size"])
        room = (w - 2 * a["padding"]) / 2 - a["swatch_w"] - 10 - 12
        return all(measure(e.label, font) <= room for e in entries)

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
            if ann.legend and legend_height(rows, self.t) + steps_h > ah and self._fits_two_columns(entries, w):
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
                    lab = c.label  # before the label: after it the badge would cover the arrowhead
                    cx, cy = lab.x - 6 - self.a["badge"] / 2, lab.y + lab.h / 2
                else:
                    cx, cy = self._midpoint(c.points) if c.route != "curve" else c.points[1]
            else:
                node = self.b.shapes[st.node]
                cx, cy = node.x, node.y
            out.append(self.badge(f"step-{i}-badge", cx, cy, st.n, f"step:{i}"))
        return out

    # callouts -------------------------------------------------------------------------------------
    KIND_TOKENS = {"info": ("primary", "primary-bg", "i"), "tip": ("success", "success-bg", "+"),
                   "warning": ("warning", "warning-bg", "!"), "risk": ("alert", "alert-bg", "×")}
    SIDES = ("top", "right", "bottom", "left")

    def _bubble_size(self, c, key: str) -> tuple[float, list[TextBlock], float]:
        """Height, text blocks and glyph size of callout ``c`` at the theme's callout width."""
        a = self.a
        cs = self.b._css(key)
        w, glyph = a["callout_width"], 26
        avail = w - 2 * a["padding"] + 6 - glyph - 10
        blocks = []
        if c.title:
            col, wt, it = self.b._text(cs, "title", self.t.color("text"), 700)
            f = self._font("heading", wt, (cs.get("title") or {}).get("font-size") or a["text_size"] + 2, it)
            blocks.append(self.b.block([c.title], f, col, f.size * 1.25, avail))
        col, wt, it = self.b._text(cs, "body", self.t.color("text-muted"), 400)
        f = self._font("body", wt, (cs.get("body") or {}).get("font-size") or a["text_size"], it)
        blocks.append(self.b.block([c.text], f, col, f.size * 1.35, avail))
        text_h = sum(b.height for b in blocks) + 6 * (len(blocks) - 1)
        return max(glyph, text_h) + 2 * (a["padding"] - 6), blocks, glyph

    def _candidate(self, side: str, node: Shape, w: float, h: float, align: str = "center") -> Rect:
        """The bubble rect on ``side`` of ``node``: centred on it, or flush with its start or end edge."""
        gap = self.a["callout_gap"]
        ax, ay, aw, ah = self.area
        if side in ("top", "bottom"):
            x = {"center": node.x + node.w / 2 - w / 2, "start": node.x, "end": node.x + node.w - w}[align]
            x = min(max(x, ax), ax + aw - w)
            y = node.y - gap - h if side == "top" else node.y + node.h + gap
        else:
            y = {"center": node.y + node.h / 2 - h / 2, "start": node.y, "end": node.y + node.h - h}[align]
            y = min(max(y, ay), ay + ah - h)
            x = node.x + node.w + gap if side == "right" else node.x - gap - w
        return x, y, w, h

    def _place(self, side: str, node: Shape, w: float, h: float, obstacles: list[Rect]) -> Rect | None:
        """The first free alignment (centre, start, end) on ``side``, or None."""
        for align in ("center", "start", "end"):
            r = self._candidate(side, node, w, h, align)
            if self._free(r, obstacles):
                return r
        return None

    def _free(self, r: Rect, obstacles: list[Rect]) -> bool:
        ax, ay, aw, ah = self.area
        inside = ax <= r[0] and ay <= r[1] and r[0] + r[2] <= ax + aw and r[1] + r[3] <= ay + ah
        return inside and not any(_overlaps(r, o) for o in obstacles)

    def callouts(self, shapes: list[Shape]) -> list:
        """Bubbles with a leader line to their node, on the first free side (top, right, bottom, left)."""
        out = []
        for i, c in enumerate(self.d.annotations.callouts):
            key = f"callout:{i}"
            node = self.b.shapes[c.target]
            h, blocks, glyph = self._bubble_size(c, key)
            w = self.a["callout_width"]
            obstacles = [(s.x, s.y, s.w, s.h) for s in shapes
                         if not (s.role == "zone" and _contains((s.x, s.y, s.w, s.h), node))] + self.rects
            sides = self.SIDES if c.side == "auto" else (c.side,)
            side, rect = next(((s, r) for s in sides if (r := self._place(s, node, w, h, obstacles))), (None, None))
            if side is None:
                side = sides[0]
                rect = self._candidate(side, node, w, h)
                if c.side == "auto":
                    self.issues.append(("callout", "overlap", f"no free side around {c.target!r}; placed on {side}"))
            self.rects.append(rect)
            out += self._callout(i, c, rect, side, node, blocks, glyph, key)
        return out

    def _callout(self, i, c, rect: Rect, side: str, node: Shape, blocks, glyph: float, key: str) -> list:
        a = self.a
        x, y, w, h = rect
        stroke_tok, fill_tok, mark = self.KIND_TOKENS[c.kind]
        accent = self.t.color(stroke_tok)
        pad = a["padding"] - 6
        text_x = x + pad + glyph + 10
        label = Label(blocks, (text_x, y + pad, w - (text_x - x) - pad, h - 2 * pad), gap=6)
        bubble = Shape(id=f"callout-{i}", kind="rect", x=x, y=y, w=w, h=h, fill=self.t.color(fill_tok),
                       stroke=accent, stroke_width=2, radius=14, shadow=PANEL_SHADOW, role="callout", label=label)
        self.b._decorate(bubble, self.b._css(key).get(""))
        gfont = self._font("body", 700, 15)
        gblk = TextBlock([mark], [mark], gfont, "#FFFFFF", gfont.size * 1.2)
        gy = y + pad + (blocks[0].leading - glyph) / 2 if blocks else y + pad
        g = Shape(id=f"callout-{i}-glyph", kind="pill", x=x + pad, y=gy, w=glyph, h=glyph, fill=accent,
                  radius=glyph / 2, role="pill", label=Label([gblk], (x + pad, gy, glyph, glyph), align="center"))
        start = {"top": (x + w / 2, y + h), "bottom": (x + w / 2, y), "right": (x, y + h / 2),
                 "left": (x + w, y + h / 2)}[side]
        end = {"top": node.anchor("top"), "bottom": node.anchor("bottom"), "right": node.anchor("right"),
               "left": node.anchor("left")}[side]
        if side in ("top", "bottom"):
            end = (min(max(start[0], node.x + 12), node.x + node.w - 12), end[1])
        else:
            end = (end[0], min(max(start[1], node.y + 12), node.y + node.h - 12))
        leader = Connector(id=f"callout-{i}-leader", points=[start, end], route="straight",
                           color=bubble.stroke or accent, width=2, arrow_end=True, marker_start="none",
                           marker_end="circle")
        return [leader, bubble, g]

    # checks ---------------------------------------------------------------------------------------
    def check(self, shapes: list[Shape]) -> list[tuple[str, str, str]]:
        """Issues for ``spinagram check``: unused legend entries, duplicate step numbers, panels overflowing
        the band, and (manual layouts) the band covering content; plus the callout overlaps found earlier."""
        out: list[tuple[str, str, str]] = []
        for e in legend_entries(self.d):
            if not e.used:
                out.append(("legend", f"unused entry {e.key!r}", "matches no element; drawn from the theme default"))
        counts: dict[int, int] = {}
        for st in self.d.annotations.steps:
            counts[st.n] = counts.get(st.n, 0) + 1
        out += [("steps", f"duplicate number {n}", f"{k} steps share it") for n, k in sorted(counts.items()) if k > 1]
        if self.overflow > 0.5:
            out.append(("annotations", "overflow", f"panels exceed the band by {round(self.overflow)}px"))
        b = band(self.d, self.t, self.area[2])
        if b and not self.d.auto and not self.d.meta.get("laid_out"):
            ax, ay, aw, ah = self.area
            side, thick = b
            rect = (ax + aw - thick, ay, thick, ah) if side == "right" else (ax, ay + ah - thick, aw, thick)
            for s in shapes:
                if s.role in ("node", "zone") and _overlaps(rect, (s.x, s.y, s.w, s.h)):
                    out.append(("annotations", "overlap", f"the band covers {s.id!r}"))
        return out + self.issues


def _overlaps(r: Rect, s: Rect) -> bool:
    return r[0] < s[0] + s[2] and s[0] < r[0] + r[2] and r[1] < s[1] + s[3] and s[1] < r[1] + r[3]


def _contains(outer: Rect, inner: Shape) -> bool:
    ox, oy, ow, oh = outer
    return ox <= inner.x and oy <= inner.y and inner.x + inner.w <= ox + ow and inner.y + inner.h <= oy + oh

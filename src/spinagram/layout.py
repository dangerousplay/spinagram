"""Resolve a :class:`Diagram` against a :class:`Theme` into a backend-neutral :class:`Scene`."""
from __future__ import annotations

import re
import unicodedata
import warnings

import copy
from functools import lru_cache
from pathlib import Path

from . import shapes
from .autolayout.sizing import TEXT_PAD
from .facts import FactRegistry, has_placeholders
from .model import Diagram, Edge, Node, Table
from .qa import behavior_issues
from .scene import (Binding, Cell, Connector, Icon, Image, Label, Line, Scene, Shape, TableGrid, Text,
                    TextBlock)
from .text import measure, wrap_paragraphs
from .theme import FontRef, Theme


def slugify(text: str, max_len: int = 60) -> str:
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:max_len].rstrip("-")


def _as_list(v) -> list[str]:
    if v is None:
        return []
    return [str(x) for x in v] if isinstance(v, (list, tuple)) else [str(v)]


class _Builder:
    def __init__(self, diagram: Diagram, theme: Theme):
        self.d = diagram
        self.t = theme
        self.W, self.H = theme.canvas
        self.shapes: dict[str, Shape] = {}
        self.warnings: list[str] = []
        self.styles = diagram.meta.get("css") or {}
        self.annotation_issues: list[tuple[str, str, str]] = []
        self.extras: dict[str, list] = {}  # items drawn right after a node (note accent bar, quote mark)

    # css ----------------------------------------------------------------------
    def _css(self, key: str) -> dict:
        return self.styles.get(key) or {}

    def _text(self, cs: dict, pe: str, color: str, weight: int) -> tuple[str, int, bool]:
        """Colour, weight and italic of a text part after the cascade (``pe``: title, body, label)."""
        st = cs.get(pe) or {}
        fam = st.get("font-family")
        if fam and fam not in {f.get("family") for f in (self.t.get("fonts") or {}).values() if isinstance(f, dict)}:
            msg = f"font-family {fam!r} is not embedded in the theme; using the theme font"
            if msg not in self.warnings:
                self.warnings.append(msg)
        return st.get("color", color), int(st.get("font-weight", weight)), st.get("font-style") == "italic"

    @staticmethod
    def _decorate(s: Shape, st: dict) -> Shape:
        """Box-level computed properties onto a scene shape."""
        if not st:
            return s
        s.fill = st.get("fill", s.fill)
        s.stroke = st.get("stroke", s.stroke)
        s.stroke_width = st.get("stroke-width", s.stroke_width or (2.0 if "stroke" in st else 0))
        s.radius = st.get("border-radius", s.radius)
        s.opacity = st.get("opacity", s.opacity)
        s.fill_opacity = st.get("fill-opacity", s.fill_opacity)
        if "stroke-dasharray" in st:
            s.dash = st["stroke-dasharray"] or None
            s.dashed = bool(st["stroke-dasharray"])
        if "box-shadow" in st:
            s.shadow = st["box-shadow"]
        return s

    # helpers ------------------------------------------------------------------
    def block(self, paragraphs: list[str], font: FontRef, color: str, leading: float, width: float | None,
              ) -> TextBlock:
        lines = wrap_paragraphs(paragraphs, font, width) if width else list(paragraphs)
        return TextBlock(lines=lines, paragraphs=paragraphs, font=font, color=color, leading=leading)

    def text(self, id: str, x: float, y: float, s: str, font: FontRef, color: str, anchor: str = "start",
             leading: float | None = None, letter_spacing: float = 0) -> Text:
        blk = TextBlock(lines=[s], paragraphs=[s], font=font, color=color, leading=leading or font.size * 1.3)
        return Text(id=id, x=x, y=y, block=blk, anchor=anchor, letter_spacing=letter_spacing,
                    width=measure(s, font) + letter_spacing * len(s))

    def pill(self, id: str, cx: float, cy: float, label: str, color: str, size: float) -> Shape:
        font = self.t.font("body", 700, size)
        w = measure(label, font) + 24
        h = size + 14
        x, y = cx - w / 2, cy - size - 3
        blk = TextBlock([label], [label], font, color, size * 1.2)
        return Shape(id=id, kind="pill", x=x, y=y, w=w, h=h, fill=self.t.color(self.t.get("canvas", "background")),
                     stroke=color, stroke_width=1.6, radius=h / 2, role="pill",
                     label=Label([blk], (x, y, w, h), align="center"))

    # elements -----------------------------------------------------------------
    def node(self, n: Node) -> Shape | Text:
        if n.kind == "pill":
            size = n.title_size or self.t.defaults("edge").get("label_size", 17)
            s = self.pill(n.id, n.x, n.y, " ".join(_as_list(n.title)), self.t.edge_color(n.color), size)
            self.shapes[n.id] = s
            return s
        if n.kind == "text":
            weight = int(n.extra.get("weight", 400))
            size = n.title_size or n.body_size or 18
            font = self.t.font(n.extra.get("font", "body"), weight, size)
            color = self.t.color(n.color, self.t.color("text-muted"))
            return self.text(n.id, n.x, n.y, " ".join(_as_list(n.title)), font, color,
                             anchor={"center": "middle", "right": "end"}.get(n.align, "start"))
        if n.kind == "diamond":
            return self.diamond(n)
        if n.kind in shapes.KINDS:
            return self.symbol(n)
        return self.box(n)

    @staticmethod
    def _icon_size(h: float, nd: dict, base: float) -> float:
        """Icons grow with tall boxes: max(base, h * icon_scale), capped at icon_max."""
        return min(nd.get("icon_max", 88), max(base, h * nd.get("icon_scale", 0.26)))

    def box(self, n: Node) -> Shape:
        nd = self.t.defaults("node")
        st = self.t.node_style(n.style)
        x, y, w, h = n.x, n.y, n.w, n.h
        pad = nd.get("padding", 22)
        ts, bs = n.title_size or nd.get("title_size", 24), n.body_size or nd.get("body_size", 18)
        center = n.align == "center"
        icon_path = self.t.icon(n.icon, st["tone"], self.d.base_dir)
        if n.icon and icon_path is None:
            warnings.warn(f"{self.d.id}: icon {n.icon!r} not found in theme {self.t.data.get('name')}", stacklevel=2)
        icon, offset, top = None, 0.0, 0.0
        if icon_path is not None:
            if center:
                isz = n.icon_size or self._icon_size(h, nd, nd.get("icon_size_center", 40))
                icon = Icon(icon_path, x + w / 2 - isz / 2, y + 16, isz)
                top = 16 + isz - 12
            else:
                isz = n.icon_size or self._icon_size(h, nd, nd.get("icon_size", 44))
                icon = Icon(icon_path, x + pad, y + (h - isz) / 2, isz)
                offset = isz + nd.get("icon_gap", 14)
        variant = n.extra.get("variant") if n.kind == "note" else None
        if variant == "quote":
            offset += 46  # room for the quote mark
            ts, bs = bs, ts - 2  # the quote reads larger than its attribution
        avail = w - 2 * pad - offset
        blocks = []
        cs = self._css(f"node:{n.id}")
        titles = _as_list(n.title)
        if titles:
            col, wt, it = self._text(cs, "title", st["title"], 700)
            f = self.t.font("heading", wt, ts, it)
            blocks.append(self.block(titles, f, col, ts * nd.get("title_leading", 1.15), avail))
        body = n.lines if n.lines is not None else ([n.text] if n.text else [])
        if body:
            col, wt, it = self._text(cs, "body", st["body"], 400)
            f = self.t.font("body", wt, bs, it or variant == "quote")
            blocks.append(self.block([str(b) for b in body], f, col, bs * nd.get("body_leading", 1.32), avail))
        if variant == "quote" and len(blocks) == 2:  # the quote first, the title as its attribution
            title, body = blocks
            title.lines = [f"— {ln}" if i == 0 else ln for i, ln in enumerate(title.lines)]
            blocks = [body, title]
        sw = nd.get("note_stroke_width", 2) if n.kind == "note" else nd.get("stroke_width", 3)
        label = Label(blocks, (x + pad + offset, y + top, avail, h - top), align="center" if center else "left",
                      gap=nd.get("title_body_gap", 10)) if blocks else None
        s = Shape(id=n.id, kind="rect", x=x, y=y, w=w, h=h, fill=st["fill"], stroke=st["stroke"], stroke_width=sw,
                  radius=n.radius if n.radius is not None else nd.get("radius", 22), dashed=n.dashed,
                  label=label, icon=icon)
        if variant:
            self._note_variant(s, variant)
        self._decorate(s, cs.get(""))
        self.shapes[n.id] = s
        return s

    def _note_variant(self, s: Shape, variant: str) -> None:
        """``card``: a white card with a primary accent bar; ``quote``: a tinted panel with a large quote mark."""
        t = self.t
        primary = t.color("primary")
        if variant == "card":
            s.fill, s.stroke, s.stroke_width, s.radius = t.color(t.get("canvas", "background")), t.color("border"), \
                1.5, 14
            s.shadow = (0.0, 6.0, 18.0, "#0F172A", 0.10)
            inset = min(14.0, s.h / 4)  # clear of the rounded corners
            self.extras[s.id] = [Shape(id=f"{s.id}-accent", kind="rect", x=s.x, y=s.y + inset, w=6, h=s.h - 2 * inset,
                                       fill=primary, radius=3, role="node-part")]
        elif variant == "quote":
            s.fill, s.stroke, s.stroke_width, s.radius = t.color("primary-bg"), None, 0, 18
            font = t.font("heading", 700, 72)
            pad = t.defaults("node").get("padding", 22)
            self.extras[s.id] = [self.text(f"{s.id}-mark", s.x + pad, s.y + pad + 52, "\u201c", font, primary)]

    def symbol(self, n: Node) -> Shape:
        """Flow/activity/state symbol: geometry from ``shapes``, centred text inside its text box."""
        nd = self.t.defaults("node")
        default = self.t.defaults("diamond").get("style", "soft") if n.kind in shapes.DIAMOND_KINDS else None
        st = self.t.node_style(n.style or default)
        x, y, w, h = n.x, n.y, n.w, n.h
        blocks = []
        tx, ty, tw, th = shapes.text_box(n.kind, x, y, w, h)
        pad = TEXT_PAD if n.kind not in shapes.ROUND_KINDS else 0
        avail = max(1.0, tw - 2 * pad)
        cs = self._css(f"node:{n.id}")
        titles = _as_list(n.title)
        if titles:
            ts = n.title_size or nd.get("title_size", 24)
            if n.kind in shapes.ROUND_KINDS:  # "H", "H*", connector letters scale with the circle
                ts = n.title_size or max(10, h * 0.42)
            col, wt, it = self._text(cs, "title", st["title"], 700)
            f = self.t.font("heading", wt, ts, it)
            blocks.append(self.block(titles, f, col, ts * nd.get("title_leading", 1.15), avail))
        body = n.lines if n.lines is not None else ([n.text] if n.text else [])
        if body:
            bs = n.body_size or nd.get("body_size", 18)
            col, wt, it = self._text(cs, "body", st["body"], 400)
            f = self.t.font("body", wt, bs, it)
            blocks.append(self.block([str(b) for b in body], f, col, bs * nd.get("body_leading", 1.32), avail))
        label = Label(blocks, (tx + pad, ty, avail, th), align="center",
                      gap=nd.get("title_body_gap", 10)) if blocks else None
        s = Shape(id=n.id, kind=n.kind, x=x, y=y, w=w, h=h, fill=st["fill"], stroke=st["stroke"],
                  stroke_width=nd.get("stroke_width", 3), dashed=n.dashed, label=label,
                  parts=shapes.parts(n.kind, x, y, w, h))
        self._decorate(s, cs.get(""))
        self.shapes[n.id] = s
        return s

    def diamond(self, n: Node) -> Shape:
        dd = self.t.defaults("diamond")
        st = self.t.node_style(n.style or dd.get("style", "soft"))
        size = n.title_size or dd.get("title_size", 21)
        inner = n.w * dd.get("text_width", 0.72)
        cs = self._css(f"node:{n.id}")
        col, wt, it = self._text(cs, "title", st["title"], 700)
        f = self.t.font("heading", wt, size, it)
        blk = self.block(_as_list(n.title), f, col, size * dd.get("leading", 1.22), inner)
        s = Shape(id=n.id, kind="diamond", x=n.x, y=n.y, w=n.w, h=n.h, fill=st["fill"], stroke=st["stroke"],
                  stroke_width=self.t.defaults("node").get("stroke_width", 3), dashed=n.dashed,
                  label=Label([blk], (n.x + (n.w - inner) / 2, n.y, inner, n.h), align="center"))
        self._decorate(s, cs.get(""))
        self.shapes[n.id] = s
        return s

    def endpoint(self, ref, other) -> tuple[tuple[float, float], Binding | None]:
        if not isinstance(ref, str):
            return (float(ref[0]), float(ref[1])), None
        name, _, side = ref.partition(".")
        side, _, frac = side.partition("@")
        if name not in self.shapes:
            raise KeyError(f"{self.d.id}: edge refers to unknown node {name!r}")
        s = self.shapes[name]
        if not side:  # auto: face the other endpoint
            ox, oy = self._center(other)
            cx, cy = s.x + s.w / 2, s.y + s.h / 2
            dx, dy = ox - cx, oy - cy
            side = ("right" if dx > 0 else "left") if abs(dx) * s.h >= abs(dy) * s.w else ("bottom" if dy > 0 else "top")
        f = float(frac) if frac else 0.5
        pt = s.anchor(side, f)
        return pt, (Binding(name, side, f) if side != "center" else None)

    def _center(self, ref) -> tuple[float, float]:
        if not isinstance(ref, str):
            return float(ref[0]), float(ref[1])
        name, _, side = ref.partition(".")
        s = self.shapes[name]
        if side:
            side, _, frac = side.partition("@")
            return s.anchor(side, float(frac) if frac else 0.5)
        return s.x + s.w / 2, s.y + s.h / 2

    def edge(self, i: int, e: Edge) -> Connector:
        ed = self.t.defaults("edge")
        p1, b1 = self.endpoint(e.src, e.via[0] if e.via else e.dst)
        p2, b2 = self.endpoint(e.dst, e.via[-1] if e.via else e.src)
        cs = self._css(f"edge:{i}")
        est = cs.get("") or {}
        color = est.get("stroke") or self.t.edge_color(e.color)
        if e.via:
            pts, route = [p1, *e.via, p2], "poly"
        elif e.curve:
            pts, route = [p1, (float(e.curve[0]), float(e.curve[1])), p2], "curve"
        else:
            pts, route = [p1, p2], "straight"
        label = None
        if e.label:
            lx, ly = e.label_at or ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2 - 8)
            lst = cs.get("label") or {}
            size = lst.get("font-size") or e.label_size or ed.get("label_size", 17)
            label = self.pill(f"e{i}-label", lx, ly, e.label, lst.get("color", color), size)
        m_start = est.get("marker-start", "arrow" if e.arrow in ("start", "both") else "none")
        m_end = est.get("marker-end", "arrow" if e.arrow in ("end", "both") else "none")
        dash = est.get("stroke-dasharray")
        return Connector(id=f"e{i}", points=pts, route=route, color=color,
                         width=est.get("stroke-width") or e.width or ed.get("width", 3.5),
                         dashed=bool(dash) if dash is not None else e.dashed, arrow_start=m_start != "none",
                         arrow_end=m_end != "none", src=b1, dst=b2, label=label, dash=dash or None,
                         marker_start=m_start, marker_end=m_end, opacity=est.get("opacity", 1.0))

    def table(self, i: int, t: Table) -> TableGrid:
        td = self.t.defaults("table")
        ts = self.t.get("styles", "table") or {}
        rh, hh = t.row_height or td.get("row_height", 100), t.header_height or td.get("header_height", 52)
        size = t.font_size or td.get("font_size", 16)
        hsize = td.get("header_size", 19)
        fills = [self.t.color(c) for c in ts.get("row_fills", ["white"])]
        head_font = self.t.font("heading", 700, hsize)
        header = [Cell(self.block([h], head_font, self.t.color(ts.get("header_text", "white")), hsize * 1.2,
                                  w - 36), self.t.color(ts.get("header_fill")), pad_left=18, bold=True)
                  for w, h in zip(t.widths, t.header)]
        rows = [header]
        isz = td.get("icon_size", 36)
        for r, row in enumerate(t.rows):
            cells = []
            for c, (w, txt) in enumerate(zip(t.widths, row)):
                first = c == 0
                icon = None
                pad = 16
                if first and t.icons and r < len(t.icons) and t.icons[r]:
                    p = self.t.icon(t.icons[r], "light", self.d.base_dir)
                    if p:
                        icon = Icon(p, 0, 0, isz)  # positioned by backends relative to the cell
                        pad = 16 + isz + 10
                font = self.t.font("heading", 700, size + 1) if first else self.t.font("body", 400, size)
                color = self.t.color(ts.get("first_col_text") if first else ts.get("text", "text-muted"))
                blk = self.block([str(txt)], font, color, font.size * 1.28, w - pad - 14)
                cells.append(Cell(blk, fills[r % len(fills)], icon, pad, first))
            rows.append(cells)
        return TableGrid(id=t.id or f"t{i}", x=t.x, y=t.y, col_widths=list(t.widths),
                         row_heights=[hh] + [rh] * len(t.rows), cells=rows,
                         border=self.t.color(ts.get("border", "border")), header_radius=td.get("radius", 14))

    # assembly -----------------------------------------------------------------
    def build(self) -> Scene:
        t, d, W, H = self.t, self.d, self.W, self.H
        ch = t.get("chrome") or {}
        sc = Scene(id=d.id, title=d.title, slug=f"{d.id}-{slugify(d.title)}", width=W, height=H,
                   background=t.color(t.get("canvas", "background"), "#FFFFFF"), notes=d.source)
        items = sc.items
        bar = ch.get("bar")
        if bar:
            items.append(Shape(id="chrome-bar", kind="rect", x=0, y=0, w=W, h=bar.get("height", 10),
                               fill=t.color(bar.get("color")), role="chrome"))
        zd = t.defaults("zone")
        for i, z in enumerate(d.zones):
            zs = t.zone_style(z.color)
            radius = zs["radius"] if zs["radius"] is not None else zd.get("radius", 26)
            opacity = zs["opacity"] if zs["opacity"] is not None else (zd.get("opacity", 0.6) if zs["fill"] else 1.0)
            zcs = self._css(f"group:{z.gid}") if z.gid else {}
            items.append(self._decorate(Shape(id=f"z{i}", kind="rect", x=z.x, y=z.y, w=z.w, h=z.h, fill=zs["fill"],
                                              stroke=zs["stroke"], stroke_width=zs["stroke_width"],
                                              dashed=zs["dashed"], radius=radius, opacity=opacity, role="zone"),
                                        zcs.get("")))
            lx = z.x + 24
            icon_name = z.icon or zs["icon"]
            if icon_name:
                isz = zd.get("icon_size", 32)
                p = t.icon(icon_name, "light", d.base_dir)
                if p is not None:  # corner icon flush with the outline, AWS group style
                    items.append(Shape(id=f"z{i}-icon", kind="rect", x=z.x, y=z.y, w=isz, h=isz, fill=None,
                                       icon=Icon(p, z.x, z.y, isz), role="zone"))
                    lx = z.x + isz + 10
            if z.label:
                lab = z.label.upper() if zs["upper"] else z.label
                ly = z.y + (22 if icon_name else 36)
                col, wt, it = self._text(zcs, "label", (zcs.get("") or {}).get("color", zs["label"]), 700)
                size = (zcs.get("label") or {}).get("font-size") or zd.get("label_size", 16)
                items.append(self.text(f"z{i}-label", lx, ly, lab, t.font("body", wt, size, it), col))
        for n in d.nodes:
            items.append(self.node(n))
            items.extend(self.extras.pop(n.id, []))
        items.extend(self.table(i, tb) for i, tb in enumerate(d.tables))
        edges = [self.edge(i, e) for i, e in enumerate(d.edges)]
        items.extend(edges)
        if d.annotations:  # badges over edges, then the band's panels, then callouts placed around everything
            from .annotate import Annotator

            ann = Annotator(self)
            items.extend(ann.badges(edges))
            items.extend(ann.panels(edges))
            items.extend(ann.callouts([s for s in items if isinstance(s, Shape) and s.role in ("node", "zone")]))
            self.annotation_issues = ann.issues
        if d.legend:
            ld = t.defaults("legend")
            x, y, sz, sw = d.legend.x, d.legend.y, ld.get("size", 18), ld.get("swatch", 20)
            font = t.font("body", 400, sz)
            for j, (col, lab) in enumerate(d.legend.items):
                items.append(Shape(id=f"legend-{j}", kind="rect", x=x, y=y - 15, w=sw, h=sw,
                                   fill=t.legend_color(col), radius=5, role="swatch"))
                items.append(self.text(f"legend-{j}-label", x + sw + 10, y + 1, lab, font, t.color("text-muted")))
                x += sw + 10 + measure(lab, font) + 40
        # header texts
        ti = ch.get("title")
        if ti:
            items.append(self.text("chrome-title", ti["x"], ti["y"], d.title,
                                   t.font(ti.get("font", "heading"), 700, ti["size"]), t.color(ti.get("color"))))
        su = ch.get("subtitle")
        if su and d.subtitle:
            items.append(self.text("chrome-subtitle", su["x"], su["y"], d.subtitle,
                                   t.font(su.get("font", "body"), 400, su["size"]), t.color(su.get("color"))))
        ki = ch.get("kicker")
        if ki:
            kicker = d.kicker if d.kicker is not None else ki.get("text", "")
            s = ki.get("template", "{id}").format(id=d.id, kicker=kicker, title=d.title).strip(" ·-")
            if s:
                items.append(self.text("chrome-kicker", W - ki.get("x_right", 80), ki["y"], s,
                                       t.font("body", 700, ki["size"]), t.color(ki.get("color")), anchor="end",
                                       letter_spacing=ki.get("letter_spacing", 0)))
        fo = ch.get("footer")
        if fo:
            m = (t.get("canvas") or {}).get("margin", 80)
            if fo.get("rule_y_from_bottom"):
                ry = H - fo["rule_y_from_bottom"]
                items.append(Line("chrome-rule", m, ry, W - m, ry, t.color(fo.get("rule_color")), 1.5))
            if fo.get("logo"):
                lw, lh = fo.get("logo_size", [128, 38])
                items.append(Image("chrome-logo", __import__("pathlib").Path(fo["logo"]), m,
                                   H - fo.get("logo_y_from_bottom", 56), lw, lh))
            if d.source:
                items.append(self.text("chrome-source", W - m, H - fo.get("source_y_from_bottom", 30), d.source,
                                       t.font("body", 400, fo.get("source_size", 15)),
                                       t.color(fo.get("source_color")), anchor="end"))
        return sc


@lru_cache(maxsize=16)
def _registry(path: str, locale: str | None) -> FactRegistry:
    return FactRegistry.load(path, locale)


def _sub(reg: FactRegistry, value, used: list[str]):
    """Substitute {{fact}} placeholders in a string or list of strings."""
    if isinstance(value, str) and has_placeholders(value):
        out, ids = reg.substitute(value)
        used.extend(ids)
        return out
    if isinstance(value, list):
        return [_sub(reg, v, used) for v in value]
    return value


def apply_facts(diagram: Diagram) -> tuple[Diagram, dict[str, list[str]], FactRegistry | None]:
    """Copy of the diagram with facts resolved, plus element id → fact ids."""
    if not diagram.facts:
        return diagram, {}, None
    path = Path(diagram.facts)
    if not path.is_absolute() and diagram.base_dir is not None:
        path = (diagram.base_dir / path).resolve()
    reg = _registry(str(path), diagram.locale)
    d = copy.deepcopy(diagram)
    refs: dict[str, list[str]] = {}

    def track(key: str, used: list[str]) -> None:
        if used:
            refs.setdefault(key, []).extend(u for u in used if u not in refs.get(key, []))

    for attr in ("title", "subtitle", "source"):
        used: list[str] = []
        setattr(d, attr, _sub(reg, getattr(d, attr), used))
        track(f"chrome-{attr}", used)
    for n in d.nodes:
        used = []
        n.title, n.text, n.lines = _sub(reg, n.title, used), _sub(reg, n.text, used), _sub(reg, n.lines, used)
        track(n.id, used)
    for i, e in enumerate(d.edges):
        used = []
        e.label = _sub(reg, e.label, used)
        track(f"e{i}-label", used)
    for i, t in enumerate(d.tables):
        used = []
        t.header = _sub(reg, t.header, used)
        t.rows = [_sub(reg, r, used) for r in t.rows]
        track(t.id or f"t{i}", used)
    if d.legend:
        used = []
        d.legend.items = [(c, _sub(reg, lab, used)) for c, lab in d.legend.items]
        track("legend", used)
    return d, refs, reg


def build_scene(diagram: Diagram, theme: Theme) -> Scene:
    from .autolayout import apply_layout

    diagram = apply_layout(diagram, theme)  # resolves the CSS cascade first (css.prepare)
    resolved, refs, reg = apply_facts(diagram)
    builder = _Builder(resolved, theme)
    scene = builder.build()
    scene.style_warnings = list(diagram.meta.get("css_warnings") or []) + builder.warnings
    scene.annotation_issues = builder.annotation_issues
    scene.layout_overflow = diagram.meta.get("layout_overflow")
    scene.model_issues = behavior_issues(diagram)
    if reg is not None:
        scene.item_facts = refs
        seen: list[str] = []
        for ids in refs.values():
            seen.extend(i for i in ids if i not in seen)
        scene.sources = [reg.review(i) for i in seen]
        scene.meta_tooltips = {i: reg.tooltip(i) for i in seen}
    return scene

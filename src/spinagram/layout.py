"""Resolve a :class:`Diagram` against a :class:`Theme` into a backend-neutral :class:`Scene`."""
from __future__ import annotations

import re
import unicodedata
import warnings

import copy
from functools import lru_cache
from pathlib import Path

from . import shapes
from .engine import endpoints, glyphs, labels, model_passes, textfit, zones
from .engine import icons as icon_fit
from .autolayout.sizing import TEXT_PAD
from .facts import FactRegistry, has_placeholders
from .model import Diagram, Edge, Node, Table
from .qa import behavior_issues
from .scene import (Binding, Cell, Connector, Icon, Image, Label, Line, Scene, Shape, TableGrid, Text,
                    TextBlock)
from .text import measure, wrap_paragraphs
from .theme import FontRef, Theme


# free label roles: theme typography for labels used as headers, captions and footnotes (defaults.label.roles
# overrides them per role)
LABEL_ROLES = {
    "zone-label": {"size": 16, "weight": 700, "upper": True, "tracking": 0.06},
    "caption": {"size": 15, "weight": 400, "color": "text-muted"},
    "footnote": {"size": 13, "weight": 400, "color": "text-muted"},
}


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
        self.fits: dict[str, tuple[str, float]] = {}  # node id → (last fitting strategy, final first-block size)
        self.headers: dict[str, tuple[float, float, float, float]] = {}  # zone shape id → header rect
        self.content_tops: dict[str, float] = {}  # zone id → first free y below its header
        self.zone_shapes: dict[str, Shape] = {}  # zone model id → its outline shape (edge targets)
        self.edge_extras: list = []  # bus bars, drawn right after the edges
        self.fixed_labels: set[str] = set()  # connector ids whose label has an explicit label_at
        self.label_issues: list[tuple[str, str, str]] = []
        self.flush: set[str] = set()  # zones with a flush corner icon (AWS style)
        self.not_straight: list[str] = []  # straight=True edges whose boxes share no span

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
        if "color" in st and st["color"] is None:
            # SPEC_DEVIATION: STY-01 accepts `color: none`; text has no transparent paint in every backend,
            # so the text keeps its colour and a warning says so.
            msg = "color: none is not supported on text; using the default colour"
            if msg not in self.warnings:
                self.warnings.append(msg)
            st = {k: v for k, v in st.items() if k != "color"}
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

    def fit(self, n: Node, specs: list, width: float, height: float, gap: float) -> textfit.FitResult:
        """Fit a node's text blocks with its ``fit``/``min_scale``/``break_on`` (node, else theme defaults)."""
        nd = self.t.defaults("node")
        opt = {k: n.extra.get(k, nd.get(k)) for k in ("fit", "min_scale", "break_on")}
        res = textfit.fit_blocks(specs, width, height, mode=opt["fit"] or "shrink",
                                 min_scale=opt["min_scale"] or textfit.MIN_SCALE,
                                 break_on=opt["break_on"] if opt["break_on"] is not None else textfit.BREAK_ON,
                                 gap=gap)
        self.fits[n.id] = (res.strategy, res.size)
        return res

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
            role = LABEL_ROLES.get(n.extra.get("role")) or {}
            role = {**role, **((self.t.defaults("label").get("roles") or {}).get(n.extra.get("role")) or {})}
            if n.extra.get("role") == "zone-label" and "color" not in role:
                role["color"] = self.t.zone_style(None)["label"]
            st = self._css(f"node:{n.id}").get("") or {}  # CSS on the label element (label, text, #id)
            weight = int(st.get("font-weight") or n.extra.get("weight", role.get("weight", 400)))
            size = st.get("font-size") or n.title_size or n.extra.get("size") or n.body_size or role.get("size", 18)
            font = self.t.font(n.extra.get("font", "body"), weight, size)
            color = st.get("color") or self.t.color(n.color or role.get("color"), self.t.color("text-muted"))
            text = " ".join(_as_list(n.title))
            if role.get("upper"):
                text = text.upper()
            anchor = {"center": "middle", "right": "end"}.get(n.align, "start")
            tracking = role.get("tracking", 0) * size
            t = self.text(n.id, n.x, n.y, text, font, color, anchor=anchor, letter_spacing=tracking)
            if n.extra.get("max_width"):  # wrapped to max_width (spaces, then safe token breaks)
                lines = textfit.wrap_fit([text], font, float(n.extra["max_width"]))
                t.block.lines = lines
                t.width = max(measure(ln, font) + tracking * len(ln) for ln in lines)
            return t
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
        icon_name = n.icon if n.kind == "note" else icon_fit.variant_name(self.t, n.icon, n.extra.get("variant"))
        icon_path = self.t.icon(icon_name, st["tone"], self.d.base_dir)
        if n.icon and icon_path is None:
            warnings.warn(f"{self.d.id}: icon {n.icon!r} not found in theme {self.t.data.get('name')}", stacklevel=2)
        icon, offset, top = None, 0.0, 0.0
        if icon_path is not None:  # fitted by height, wordmarks keep their aspect ratio (up to 4 heights wide)
            has_text = bool(_as_list(n.title)) or bool(n.lines) or bool(n.text)
            if center:
                isz = n.icon_size or self._icon_size(h, nd, nd.get("icon_size_center", 40))
                if has_text:  # provisional: centre_layout settles size and text top once the text is known
                    icon = icon_fit.place(icon_path, x, y + 16, isz, isz, center_x=x + w / 2)
                else:  # icon-only box: centred both ways
                    icon = icon_fit.place(icon_path, x, y, h, isz, max_width=w, center_x=x + w / 2)
            else:
                isz = n.icon_size or self._icon_size(h, nd, nd.get("icon_size", 44))
                icon = icon_fit.place(icon_path, x + pad, y, h, isz)
                offset = icon.width + nd.get("icon_gap", 14)
        variant = n.extra.get("variant") if n.kind == "note" else None
        if variant == "quote":
            offset += 46  # room for the quote mark
            # the quote reads larger than its attribution (theme sizes only; CSS or explicit sizes win)
            ts = n.title_size or nd.get("body_size", 18)
            bs = n.body_size or nd.get("title_size", 24) - 2
        avail = w - 2 * pad - offset
        names = n.extra.get("badges") or []
        bpaths = [p for p in (self.t.icon(b, "light", self.d.base_dir) for b in names) if p is not None]
        if bpaths:  # corner badges: the text ends before the leftmost one
            main = icon.size if icon else (n.icon_size or self._icon_size(h, nd, nd.get("icon_size", 44)))
            parts, left = icon_fit.badges(n.id, bpaths, (x, y, w, h), icon_fit.badge_size(main))
            self.extras.setdefault(n.id, []).extend(parts)
            avail = min(avail, left - icon_fit.BADGE_GAP - (x + pad + offset))
        specs = []
        cs = self._css(f"node:{n.id}")
        titles = _as_list(n.title)
        if titles:
            col, wt, it = self._text(cs, "title", st["title"], 700)
            f = self.t.font("heading", wt, ts, it)
            specs.append(textfit.BlockSpec(titles, f, nd.get("title_leading", 1.15), col))
        body = n.lines if n.lines is not None else ([n.text] if n.text else [])
        if body:
            col, wt, it = self._text(cs, "body", st["body"], 400)
            f = self.t.font("body", wt, bs, it or variant == "quote")
            specs.append(textfit.BlockSpec([str(b) for b in body], f, nd.get("body_leading", 1.32), col))
        if center and icon is not None and specs:  # the icon reserves its height, shrinking before the text
            brk = n.extra.get("break_on", nd.get("break_on"))
            isz = icon.size
            icon, top, _ = icon_fit.centre_layout(icon_path, (x, y, w, h), isz, min(isz, nd.get("icon_min", 24)),
                                                  specs, avail, nd.get("icon_text_gap", 8),
                                                  nd.get("title_body_gap", 10),
                                                  brk if brk is not None else textfit.BREAK_ON)
        fitted = self.fit(n, specs, avail, h - top, nd.get("title_body_gap", 10))
        blocks = fitted.blocks
        h = max(h, fitted.height + top) if fitted.strategy == "grow" else h
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
        if icon is not None and not blocks and not variant:  # icon-only box (a chip): no outline unless styled
            s.stroke, s.stroke_width, s.shadow = None, 0, None
        self._decorate(s, cs.get(""))
        self.shapes[n.id] = s
        return s

    def zone_header(self, i: int, z, zs: dict, zcs: dict) -> list:
        """Header icon and label of zone ``i`` (see :func:`engine.zones.header_layout`)."""
        t, zd = self.t, self.t.defaults("zone")
        opts = zones.header_options(z, zs, t)
        if opts["align"] == "none":  # no icon, no label, no header rect (HDR-07); the strip stays
            self.content_tops[z.id or f"z{i}"] = zones.content_top(z, 0, opts=opts)
            return self._strip(i, z, zs, opts)
        names = z.icon or zs["icon"]
        names = [names] if isinstance(names, str) else list(names or [])
        names = [icon_fit.variant_name(t, nm, opts.get("variant")) for nm in names]
        paths = [p for p in (t.icon(n, "light", self.d.base_dir) for n in names) if p is not None]
        size = (zcs.get("label") or {}).get("font-size") or zd.get("label_size", 16)
        isz_hdr = opts["icon_size"] if opts["inset"] else zd.get("icon_size", 32)
        fits = [icon_fit.fit(p, isz_hdr) for p in paths]
        geo = zones.header_layout(z, opts, [w for w, _ in fits], size, zd.get("icon_size", 32))
        if paths and not opts["inset"]:
            self.flush.add(f"z{i}")
        items: list = self._strip(i, z, zs, opts)
        for k, (p, (ix, iy, isz), (fw, fh)) in enumerate(zip(paths, geo["icons"], fits)):
            iy += (isz - fh) / 2  # centred in the header slot
            items.append(Shape(id=f"z{i}-icon" if k == 0 else f"z{i}-icon{k}", kind="rect", x=ix, y=iy, w=fw,
                               h=fh, fill=None, icon=Icon(p, ix, iy, fh, w=fw), role="zone"))
        if z.label:
            upper = opts["upper"] if opts["upper"] is not None else zs["upper"]
            lab = z.label.upper() if upper else z.label
            col, wt, it = self._text(zcs, "label", (zcs.get("") or {}).get("color") or zs["label"], 700)
            track = zd.get("label_tracking", 0) * size if upper else 0  # em → px, uppercase labels only
            lx, ly = geo["label"]
            items.append(self.text(f"z{i}-label", lx, ly, lab, t.font("body", wt, size, it), col,
                                   anchor=geo["anchor"], letter_spacing=track))
        if opts["align"] == "right":  # mirrored: from the leftmost item to the right outline
            left = min([z.x + z.w - 24] + [it.x - (it.width or 0) for it in items if isinstance(it, Text)] +
                       [it.x for it in items if isinstance(it, Shape)])
            self.headers[f"z{i}"] = (left, z.y, z.x + z.w - left, geo["bottom"] - z.y)
        else:
            right = max([z.x + 24] + [it.x + (it.width or 0) for it in items if isinstance(it, Text)] +
                        [it.x + it.w for it in items if isinstance(it, Shape)])
            self.headers[f"z{i}"] = (z.x, z.y, right - z.x, geo["bottom"] - z.y)
        self.content_tops[z.id or f"z{i}"] = geo["bottom"] + opts["gap"]
        return items

    def _strip(self, i: int, z, zs: dict, opts: dict) -> list:
        """The header accent bar along the top, clear of the rounded corners (``strip`` option)."""
        if not opts["strip"]:
            return []
        r = min(z.w / 4, zs["radius"] if zs["radius"] is not None else self.t.defaults("zone").get("radius", 26))
        return [Shape(id=f"z{i}-strip", kind="rect", x=z.x + r, y=z.y, w=z.w - 2 * r, h=5,
                      fill=self.t.color(opts["strip"]), radius=2.5, role="zone")]

    def _note_variant(self, s: Shape, variant: str) -> None:
        """``card``: a white card with a primary accent bar; ``quote``: a tinted panel with a large quote mark."""
        t = self.t
        primary = t.color("primary")
        if variant == "card":
            s.fill, s.stroke, s.stroke_width, s.radius = t.color(t.get("canvas", "background")), t.color("border"), \
                1.5, 14
            s.shadow = (0.0, 6.0, 18.0, "#0F172A", 0.10)
            inset = min(14.0, s.h / 4)  # clear of the rounded corners
            self.extras.setdefault(s.id, [])[:0] = [Shape(id=f"{s.id}-accent", kind="rect", x=s.x, y=s.y + inset, w=6, h=s.h - 2 * inset,
                                       fill=primary, radius=3, role="node-part")]
        elif variant == "quote":
            s.fill, s.stroke, s.stroke_width, s.radius = t.color("primary-bg"), None, 0, 18
            font = t.font("heading", 700, 72)
            pad = t.defaults("node").get("padding", 22)
            self.extras.setdefault(s.id, [])[:0] = [self.text(f"{s.id}-mark", s.x + pad, s.y + pad + 52, "\u201c", font, primary)]

    def symbol(self, n: Node) -> Shape:
        """Flow/activity/state symbol: geometry from ``shapes``, centred text inside its text box."""
        nd = self.t.defaults("node")
        default = self.t.defaults("diamond").get("style", "soft") if n.kind in shapes.DIAMOND_KINDS else None
        st = self.t.node_style(n.style or default)
        x, y, w, h = n.x, n.y, n.w, n.h
        tx, ty, tw, th = shapes.text_box(n.kind, x, y, w, h)
        pad = TEXT_PAD if n.kind not in shapes.ROUND_KINDS else 0
        avail = max(1.0, tw - 2 * pad)
        cs = self._css(f"node:{n.id}")
        titles = _as_list(n.title)
        specs = []
        if titles:
            ts = n.title_size or nd.get("title_size", 24)
            if n.kind in shapes.ROUND_KINDS:  # "H", "H*", connector letters scale with the circle
                ts = n.title_size or max(10, h * 0.42)
            col, wt, it = self._text(cs, "title", st["title"], 700)
            f = self.t.font("heading", wt, ts, it)
            specs.append(textfit.BlockSpec(titles, f, nd.get("title_leading", 1.15), col))
        body = n.lines if n.lines is not None else ([n.text] if n.text else [])
        if body:
            bs = n.body_size or nd.get("body_size", 18)
            col, wt, it = self._text(cs, "body", st["body"], 400)
            f = self.t.font("body", wt, bs, it)
            specs.append(textfit.BlockSpec([str(b) for b in body], f, nd.get("body_leading", 1.32), col))
        blocks = self.fit(n, specs, avail, th, nd.get("title_body_gap", 10)).blocks
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
        fitted = self.fit(n, [textfit.BlockSpec(_as_list(n.title), f, dd.get("leading", 1.22), col)], inner, n.h, 0)
        blk = fitted.blocks[0] if fitted.blocks else self.block([], f, col, size * dd.get("leading", 1.22), inner)
        s = Shape(id=n.id, kind="diamond", x=n.x, y=n.y, w=n.w, h=n.h, fill=st["fill"], stroke=st["stroke"],
                  stroke_width=self.t.defaults("node").get("stroke_width", 3), dashed=n.dashed,
                  label=Label([blk], (n.x + (n.w - inner) / 2, n.y, inner, n.h), align="center"))
        self._decorate(s, cs.get(""))
        self.shapes[n.id] = s
        return s

    def endpoint(self, ref, other) -> tuple[tuple[float, float], Binding | None]:
        return endpoints.resolve(ref, other, self.shapes, self.d.id, self.zone_shapes)

    def edge(self, i: int, e: Edge) -> Connector:
        ed = self.t.defaults("edge")
        if e.straight and not e.via and isinstance(e.src, str) and isinstance(e.dst, str):
            a, b = self.shapes.get(e.src.partition(".")[0]), self.shapes.get(e.dst.partition(".")[0])
            refs = endpoints.straight_refs(a, b) if a is not None and b is not None else None
            if refs is None:
                self.not_straight.append(f"e{i}")
            else:
                e = copy.copy(e)
                e.src, e.dst = refs
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
            if e.label_at:
                self.fixed_labels.add(f"e{i}")
            lx, ly = e.label_at or ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2 - 8)
            lst = cs.get("label") or {}
            size = lst.get("font-size") or e.label_size or ed.get("label_size", 17)
            label = self.pill(f"e{i}-label", lx, ly, e.label, lst.get("color", color), size)
        if e.fan == "bus" and b2 is not None and b2.target == "zone":
            self.edge_extras.append(self._bus(i, e, b2, p2, color, est.get("stroke-width") or e.width or
                                              ed.get("width", 3.5)))
        m_start = est.get("marker-start", "arrow" if e.arrow in ("start", "both") else "none")
        m_end = est.get("marker-end", "arrow" if e.arrow in ("end", "both") else "none")
        dash = est.get("stroke-dasharray")
        return Connector(id=f"e{i}", points=pts, route=route, color=color,
                         width=est.get("stroke-width") or e.width or ed.get("width", 3.5),
                         dashed=bool(dash) if dash is not None else e.dashed, arrow_start=m_start != "none",
                         arrow_end=m_end != "none", src=b1, dst=b2, label=label, dash=dash or None,
                         marker_start=m_start, marker_end=m_end, opacity=est.get("opacity", 1.0))

    def route_edges(self, edges: list[Connector]) -> None:
        """``route="ortho"`` edges (or ``defaults.edge.route``) without via/curve, in declaration order."""
        from .engine import route as router

        default = self.t.defaults("edge").get("route")
        todo = [i for i, e in enumerate(self.d.edges)
                if (e.route or default) == "ortho" and not e.via and not e.curve]
        targets = {**self.shapes, **{s.id: s for s in self.zone_shapes.values()}}
        bundles = [(list(b.edges), b.trunk) for b in self.d.bundles]
        fan: dict[str, list[int]] = {}
        for i, e in enumerate(self.d.edges):  # fan_in edges into one target form an implicit bundle
            if e.fan_in:
                fan.setdefault(str(e.dst).partition(".")[0], []).append(i)
        bundles += [(idx, None) for idx in fan.values() if len(idx) > 1]
        bundled = {i for idx, _ in bundles for i in idx}
        todo = [i for i in todo if i not in bundled]
        if todo:
            router.route_ortho(edges, todo, self.shapes, targets, headers=self.headers)
        for idx, trunk in bundles:
            router.route_bundle(edges, idx, trunk, targets)

    def place_labels(self, edges: list[Connector]) -> None:
        """Move edge labels clear of nodes, zone headers, arrowheads, other labels and the canvas margin."""
        from .qa import polyline

        m = (self.t.get("canvas") or {}).get("margin", 80)
        obstacles = [(s.x, s.y, s.w, s.h) for s in self.shapes.values() if s.role == "node"]
        obstacles += list(self.headers.values())
        self.label_issues = labels.place(edges, self.fixed_labels, obstacles, (m, m, self.W - 2 * m, self.H - 2 * m),
                                         path=polyline)

    def _bus(self, i: int, e: Edge, b: Binding, end, color: str, width: float) -> Line:
        """The bus bar of a ``fan="bus"`` edge inside its target zone."""
        zid = e.dst.partition(".")[0][len(endpoints.ZONE):]
        zm = next((z for z in self.d.zones if z.id == zid), None)
        zs = self.zone_shapes[zid]
        if zm is not None and zm.children:
            kids = [self.shapes[c] for c in zm.children if c in self.shapes]
        else:  # nodes inside the zone outline
            kids = [s for s in self.shapes.values() if zs.x <= s.x and s.x + s.w <= zs.x + zs.w and
                    zs.y <= s.y and s.y + s.h <= zs.y + zs.h]
        (x1, y1), (x2, y2) = endpoints.bus(zs, b.side, kids, end)
        return Line(f"e{i}-bus", x1, y1, x2, y2, color, width)

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
        sc = Scene(id=d.id, title=d.title, slug=d.output or f"{d.id}-{slugify(d.title)}", width=W, height=H,
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
            ol = zones.outline(z, zs, t)
            opacity = zs["opacity"] if zs["opacity"] is not None else (zd.get("opacity", 0.6) if ol["fill"] else 1.0)
            zcs = self._css(f"group:{z.gid}") if z.gid else self._css(f"zone:{z.id or f'z{i}'}")
            items.append(self._decorate(Shape(id=f"z{i}", kind="rect", x=z.x, y=z.y, w=z.w, h=z.h, fill=ol["fill"],
                                              stroke=ol["stroke"], stroke_width=ol["stroke_width"],
                                              dashed=ol["dashed"], dash=ol["dash"], cap=ol["cap"], radius=radius,
                                              opacity=opacity, role="zone"),
                                        zcs.get("")))
            self.zone_shapes[z.id or f"z{i}"] = items[-1]
            items.extend(self.zone_header(i, z, zs, zcs))
        for n in d.nodes:
            items.append(self.node(n))
            items.extend(self.extras.pop(n.id, []))
        items.extend(self.table(i, tb) for i, tb in enumerate(d.tables))
        edges = [self.edge(i, e) for i, e in enumerate(d.edges)]
        self.route_edges(edges)
        self.place_labels(edges)
        items.extend(edges)
        items.extend(self.edge_extras)
        if d.annotations:  # badges over edges, then the band's panels, then callouts placed around everything
            from .annotate import Annotator

            ann = Annotator(self)
            items.extend(ann.badges(edges))
            items.extend(ann.panels(edges))
            if d.annotations.legend is not None and d.annotations.legend.place is not None:
                items.extend(ann.cell_legend(edges))
            content = [s for s in items if isinstance(s, Shape) and s.role in ("node", "zone")]
            items.extend(ann.callouts(content))
            self.annotation_issues = ann.check(content)
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
    diagram = model_passes.apply(diagram, theme)  # hand-placed diagrams: content sizes, containers, grids
    resolved, refs, reg = apply_facts(diagram)
    builder = _Builder(resolved, theme)
    theme.icon_trace = {}  # records how each icon name resolved while this scene is built
    try:
        scene = builder.build()
    finally:
        trace, theme.icon_trace = theme.icon_trace, None
    scene.icon_sources = trace
    if diagram.requires:
        from .engine import version

        have = version.installed()
        if not version.satisfies(have, diagram.requires):
            scene.version_mismatch = (diagram.requires, have)
            warnings.warn(f"{diagram.id}: written for spinagram {diagram.requires}, running {have}", stacklevel=2)
    scene.style_warnings = list(diagram.meta.get("css_warnings") or []) + builder.warnings
    scene.annotation_issues = builder.annotation_issues
    scene.fits = builder.fits
    scene.zone_headers = builder.headers
    scene.zone_content_tops = builder.content_tops
    scene.laid_out = bool(diagram.meta.get("laid_out"))
    scene.flush_headers = builder.flush
    scene.not_straight = builder.not_straight
    scene.check_options = {**theme.defaults("check"), "margin": (theme.get("canvas") or {}).get("margin", 80),
                           "icon_text_gap": theme.defaults("node").get("icon_text_gap", 8)}
    glyphs.apply(scene, theme)
    scene.rows = [(f"{c.axis}{k}", list(c.children), c.same_icon_size) for k, c in enumerate(diagram.containers)]
    shape_of = {(z.id or f"z{k}"): f"z{k}" for k, z in enumerate(diagram.zones)}
    scene.zone_children = {f"z{k}": [shape_of.get(c, c) for c in z.children]
                           for k, z in enumerate(diagram.zones) if z.children}
    if not scene.laid_out:  # engines size gaps themselves; collisions are reported for hand-placed diagrams
        scene.annotation_issues = scene.annotation_issues + builder.label_issues
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

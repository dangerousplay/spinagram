"""Geometry decided on the model before the scene is built (roadmap B1, G1, Z3).

Each pass works on a copy of a hand-placed diagram; diagrams laid out by an engine are returned as they are."""
from __future__ import annotations

import copy

from ..model import Diagram
from ..theme import Theme

SIZED_KINDS_SKIP = ("text", "pill")  # free labels and pills size themselves from their text


def content_size(d: Diagram, theme: Theme) -> None:
    """Boxes placed by hand without ``w``/``h`` get the size of their content (icon, title, body, padding)."""
    from ..autolayout.sizing import auto_size

    for n in d.nodes:
        if n.kind in SIZED_KINDS_SKIP or (n.w and n.h):
            continue
        n.w, n.h = auto_size(n, theme)


def min_width(n, theme: Theme) -> float:
    """Narrowest box whose text still fits once fitting has shrunk it to ``min_scale`` and broken every token
    at its safe points: the widest unbreakable piece, plus padding and the icon."""
    from ..autolayout.sizing import _lines
    from ..text import measure
    from . import textfit

    nd = theme.defaults("node")
    scale = n.extra.get("min_scale") or nd.get("min_scale") or textfit.MIN_SCALE
    ts, bs = n.title_size or nd.get("title_size", 24), n.body_size or nd.get("body_size", 18)
    tf, bf = theme.font("heading", 700, ts * scale), theme.font("body", 400, bs * scale)
    title, body = _lines(n)
    pieces = [(p, tf) for t in title for w in t.split() for p in textfit.break_token(w, tf, 1)]
    pieces += [(p, bf) for b in body for w in b.split() for p in textfit.break_token(w, bf, 1)]
    widest = max([measure(p, f) for p, f in pieces] + [0])
    isz = (n.icon_size or nd.get("icon_size", 44)) + nd.get("icon_gap", 14) if n.icon and n.align != "center" else 0
    return widest + 2 * nd.get("padding", 22) + isz


def containers(d: Diagram, theme: Theme) -> None:
    """Size and place the nodes of each ``row``/``column`` container."""
    from ..autolayout.sizing import auto_size
    from .zones import content_area

    nodes = {n.id: n for n in d.nodes}
    zones = {z.id: z for z in d.zones}
    for c in d.containers:
        members = [nodes[i] for i in c.children if i in nodes]
        if not members:
            continue
        k = len(members)
        area = content_area(zones[c.zone], theme) if c.zone is not None else None  # zone rows: (x0, y0, x1, y1)
        if area and c.cols and k > c.cols:
            raise ValueError(f"{d.id}: {c.axis} in zone {c.zone!r} has {k} members, more than cols={c.cols}")
        max_width = c.max_width if c.max_width is not None or area is None else area[2] - area[0]
        fixed_h = {m.id: bool(m.h) for m in members}
        for m in members:
            if not (m.w and m.h):
                m.w, m.h = auto_size(m, theme)
        if c.axis == "row":
            room = None if max_width is None else (max_width - c.gap * (k - 1))
            if area and c.cols:  # each member 1/cols of the content width
                for m in members:
                    m.w = (area[2] - area[0] - c.gap * (c.cols - 1)) / c.cols
            elif c.same_size:
                width = max(m.w for m in members)
                if room is not None:
                    width = min(width, room / k)
                for m in members:
                    m.w = width
            elif room is not None and sum(m.w for m in members) > room:
                f = room / sum(m.w for m in members)
                for m in members:
                    m.w *= f
        elif max_width is not None or c.same_size:
            width = max(m.w for m in members) if c.same_size else None
            for m in members:
                m.w = min(width or m.w, max_width or float("inf"))
        widest = max(members, key=lambda m: min_width(m, theme) - m.w)
        if min_width(widest, theme) > widest.w + 0.5:
            raise ValueError(f"{d.id}: {c.axis} cannot fit {widest.id!r} in {widest.w:.0f}px "
                             f"(needs {min_width(widest, theme):.0f}px); raise max_width or shorten the text")
        for m in members:  # heights follow the final widths unless given
            if not fixed_h[m.id]:
                m.h = auto_size(_with_h0(m), theme)[1]
        if c.same_size:
            height = max(m.h for m in members)
            for m in members:
                m.h = height
        if c.same_icon_size:  # the smallest icon of the container for all of them
            nd = theme.defaults("node")
            sizes = [m.icon_size or icon_size(m, nd) for m in members if m.icon]
            for m in members:
                if m.icon and sizes:
                    m.icon_size = min(sizes)
        cx, cy = c.x, c.y
        if area:  # place the block in the zone's content area by align (default center)
            row = c.axis == "row"
            bw = sum(m.w for m in members) + c.gap * (k - 1) if row else max(m.w for m in members)
            bh = max(m.h for m in members) if row else sum(m.h for m in members) + c.gap * (k - 1)
            align = c.align or "center"
            cx = {"start": area[0], "center": (area[0] + area[2] - bw) / 2, "end": area[2] - bw}[align]
            cy = area[1] if align == "start" else (area[1] + area[3] - bh) / 2
        pos = cx if c.axis == "row" else cy
        for m in members:
            if c.axis == "row":
                m.x, m.y, pos = pos, cy, pos + m.w + c.gap
            else:
                m.x, m.y, pos = cx, pos, pos + m.h + c.gap


def icon_size(n, nd: dict) -> float:
    """The icon size the builder gives a node without ``icon_size`` (it grows with tall boxes)."""
    base = nd.get("icon_size_center", 40) if n.align == "center" else nd.get("icon_size", 44)
    return min(nd.get("icon_max", 88), max(base, n.h * nd.get("icon_scale", 0.26)))


def constraints(d: Diagram) -> None:
    """``align_x`` / ``align_y`` / ``center_on`` in declaration order, on final sizes."""
    nodes = {n.id: n for n in d.nodes}
    for op, *ids in d.constraints:
        if op == "center_on":
            a, b, axis = nodes[ids[0]], nodes[ids[1]], ids[2]
            if axis in ("x", "both"):
                a.x = b.x + b.w / 2 - a.w / 2
            if axis in ("y", "both"):
                a.y = b.y + b.h / 2 - a.h / 2
            continue
        first = nodes[ids[0]]
        for i in ids[1:]:
            n = nodes[i]
            if op == "align_x":
                n.x = first.x + first.w / 2 - n.w / 2
            else:
                n.y = first.y + first.h / 2 - n.h / 2


def snakes(d: Diagram, theme: Theme) -> None:
    """Place each snake: rows of ``cols`` cards stacked ``row_gap`` apart from ``y`` (between zone outlines when
    each row has a zone), odd rows right to left in boustrophedon; in-row edges anchored on facing sides."""
    from .zones import FIT_PADDING, content_top, header_options

    m = (theme.get("canvas") or {}).get("margin", 80)
    label_size = theme.defaults("zone").get("label_size", 16)
    nodes, zones = {n.id: n for n in d.nodes}, {z.id: z for z in d.zones}
    for s in d.snakes:
        x0 = m if s.x is None else s.x
        width = s.w or theme.canvas[0] - 2 * m
        top, row_of, gaps = s.y, {}, []
        for r in range(-(-len(s.nodes) // s.cols)):
            ids = s.nodes[r * s.cols:(r + 1) * s.cols]
            z = zones[s.zones[r]] if s.zones else None
            pad = (z.padding if z.padding is not None else FIT_PADDING) if z else 0
            cy = top
            if z:  # the zone spans the row; the cards sit in its content area
                z.x, z.y, z.w = x0, top, width
                icons = len(z.icon) if isinstance(z.icon, list) else int(bool(z.icon or theme.zone_style(z.color)["icon"]))
                cy = content_top(z, icons, label_size, header_options(z, theme.zone_style(z.color), theme))
                z.h = cy - top + s.h + pad
            cw = (width - 2 * pad - (s.cols - 1) * s.gap) / s.cols
            back = s.mode == "boustrophedon" and r % 2 == 1
            for j, i in enumerate(ids):
                slot = s.cols - 1 - j if back else j
                n = nodes[i]
                n.x, n.y, n.w, n.h = x0 + pad + slot * (cw + s.gap), cy, cw, s.h
                row_of[i] = (r, back)
            gaps.append((z.y + z.h if z else cy + s.h) + s.row_gap / 2)  # middle of the gap below row r
            top = gaps[-1] + s.row_gap / 2
        lane = x0 - s.gap / 2  # left of the row (outside its zones): restart returns run down here
        for e in d.edges:
            a, b = row_of.get(e.src), row_of.get(e.dst)
            if not (a and b) or e.via is not None:
                continue
            if a[0] == b[0]:  # in-row edges: straight between facing sides
                e.src, e.dst = (f"{e.src}.left", f"{e.dst}.right") if a[1] else (f"{e.src}.right", f"{e.dst}.left")
            elif s.mode == "restart":  # return to the row start: down, left through the row gap, down the lane
                # SPEC_DEVIATION: SNK-05 routes turn edges with route="ortho"; restart returns get explicit via
                # points instead. Reason: the ortho router squeezes them between the next header and its cards
                # (12 px) and overlaps the in-row arrows; the row gap and the lane hold no header and no box.
                src, dst = nodes[e.src], nodes[e.dst]
                gy, by = gaps[a[0]], dst.y + dst.h / 2
                e.src, e.dst, e.route = f"{e.src}.bottom", f"{e.dst}.left", None
                e.via = [(src.x + src.w / 2, gy), (lane, gy), (lane, by)]


def _texts(d: Diagram, fn) -> None:
    """Every diagram text (GLM-01) through ``fn`` (value → value), in place."""
    for attr in ("title", "subtitle", "kicker", "source"):
        setattr(d, attr, fn(getattr(d, attr)))
    for n in d.nodes:
        n.title, n.text, n.lines = fn(n.title), fn(n.text), fn(n.lines)
    for e in d.edges:
        e.label = fn(e.label)
    for z in d.zones:
        z.label = fn(z.label)
    for g in d.groups:
        g.label = fn(g.label)
    for t in d.tables:
        t.header, t.rows = fn(t.header), [fn(r) for r in t.rows]
    if d.legend:
        d.legend.items = [(c, fn(lab)) for c, lab in d.legend.items]
    a = d.annotations
    if a.legend:
        a.legend.title = fn(a.legend.title)
        if a.legend.items:
            a.legend.items = {k: fn(v) for k, v in a.legend.items.items()}
    for st in a.steps:
        st.text = fn(st.text)
    for c in a.callouts:
        c.text, c.title = fn(c.text), fn(c.title)


def glyph_map(d: Diagram, theme: Theme) -> Diagram:
    """A copy of ``d`` with the theme's ``text.glyph_map`` applied to every text (``d`` when no text holds a
    mapped character); the characters replaced are in ``copy.__dict__["_glyph_mapped"]`` (char → replacement,
    theme order) for ``qa``'s ``glyph-mapped`` issues."""
    gm = {k: v for k, v in ((theme.get("text") or {}).get("glyph_map") or {}).items() if k != v}  # identity: no-op
    if not gm:
        return d
    seen: set[str] = set()

    def scan(v):
        if isinstance(v, str):
            seen.update(ch for ch in v if ch in gm)
        elif isinstance(v, list):
            for x in v:
                scan(x)
        return v

    _texts(d, scan)
    if not seen:
        return d
    table = str.maketrans(gm)

    def sub(v):
        if isinstance(v, str):
            return v.translate(table)
        return [sub(x) for x in v] if isinstance(v, list) else v

    out = copy.deepcopy(d)
    _texts(out, sub)
    out.__dict__["_glyph_mapped"] = {k: v for k, v in gm.items() if k in seen}
    return out


def _with_h0(n):
    m = copy.copy(n)
    m.h = 0
    return m


def apply(d: Diagram, theme: Theme) -> Diagram:
    """A copy of ``d`` with every model pass applied (``d`` itself when there is nothing to do). The glyph map
    runs on every diagram, engine-laid-out ones included; the placement passes on hand-placed ones."""
    source, d = d, glyph_map(d, theme)
    if d.auto or d.meta.get("laid_out"):
        return d
    unsized = any(not (n.w and n.h) and n.kind not in SIZED_KINDS_SKIP for n in d.nodes)
    fitted = any(z.fit or z.equalize or z.band for z in d.zones)
    if not unsized and not d.containers and not fitted and not d.constraints and not d.snakes:
        return d
    from .zones import bands, fit_children

    if d is source:
        d = copy.deepcopy(d)
    snakes(d, theme)  # before bands: rows read the zone header height
    bands(d, theme)  # before containers: zone rows read the zone rect
    containers(d, theme)
    content_size(d, theme)
    constraints(d)
    fit_children(d, theme)
    return d

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


def _with_h0(n):
    m = copy.copy(n)
    m.h = 0
    return m


def apply(d: Diagram, theme: Theme) -> Diagram:
    """A copy of ``d`` with every model pass applied (``d`` itself when there is nothing to do)."""
    if d.auto or d.meta.get("laid_out"):
        return d
    unsized = any(not (n.w and n.h) and n.kind not in SIZED_KINDS_SKIP for n in d.nodes)
    fitted = any(z.fit or z.equalize or z.band for z in d.zones)
    if not unsized and not d.containers and not fitted and not d.constraints:
        return d
    from .zones import bands, fit_children

    d = copy.deepcopy(d)
    bands(d, theme)  # before containers: zone rows read the zone rect
    containers(d, theme)
    content_size(d, theme)
    constraints(d)
    fit_children(d, theme)
    return d

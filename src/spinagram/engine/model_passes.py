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

    nodes = {n.id: n for n in d.nodes}
    for c in d.containers:
        members = [nodes[i] for i in c.children if i in nodes]
        if not members:
            continue
        fixed_h = {m.id: bool(m.h) for m in members}
        for m in members:
            if not (m.w and m.h):
                m.w, m.h = auto_size(m, theme)
        k = len(members)
        if c.axis == "row":
            room = None if c.max_width is None else (c.max_width - c.gap * (k - 1))
            if c.same_size:
                width = max(m.w for m in members)
                if room is not None:
                    width = min(width, room / k)
                for m in members:
                    m.w = width
            elif room is not None and sum(m.w for m in members) > room:
                f = room / sum(m.w for m in members)
                for m in members:
                    m.w *= f
        elif c.max_width is not None or c.same_size:
            width = max(m.w for m in members) if c.same_size else None
            for m in members:
                m.w = min(width or m.w, c.max_width or float("inf"))
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
        pos = c.x if c.axis == "row" else c.y
        for m in members:
            if c.axis == "row":
                m.x, m.y, pos = pos, c.y, pos + m.w + c.gap
            else:
                m.x, m.y, pos = c.x, pos, pos + m.h + c.gap


def icon_size(n, nd: dict) -> float:
    """The icon size the builder gives a node without ``icon_size`` (it grows with tall boxes)."""
    base = nd.get("icon_size_center", 40) if n.align == "center" else nd.get("icon_size", 44)
    return min(nd.get("icon_max", 88), max(base, n.h * nd.get("icon_scale", 0.26)))


def _with_h0(n):
    m = copy.copy(n)
    m.h = 0
    return m


def apply(d: Diagram, theme: Theme) -> Diagram:
    """A copy of ``d`` with every model pass applied (``d`` itself when there is nothing to do)."""
    if d.auto or d.meta.get("laid_out"):
        return d
    unsized = any(not (n.w and n.h) and n.kind not in SIZED_KINDS_SKIP for n in d.nodes)
    if not unsized and not d.containers:
        return d
    d = copy.deepcopy(d)
    containers(d, theme)
    content_size(d, theme)
    return d

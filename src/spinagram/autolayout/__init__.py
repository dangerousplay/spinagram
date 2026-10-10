"""Automatic layout: a diagram with ``layout:`` gets node positions, group zones and edge routes computed.

    Diagram (groups, unsized/unplaced nodes) ─► LGraph ─► engine (flex | dot | elk | d2 | plugin)
        ─► LResult ─► placed in ``layout.area`` ─► nodes x/y/w/h, groups → zones, routes → edge ``via``

The result is an ordinary absolute :class:`~spinagram.model.Diagram`, so every backend works unchanged.
Diagrams without ``layout`` are returned as-is.
"""
from __future__ import annotations

import copy
import os
from typing import Any

from ..model import Diagram, Group, Node, Zone
from ..theme import Theme
from .engines import EngineUnavailable, get_engine
from .graph import Box, LEdge, LGraph, LGroup, LNode, LResult
from ..text import measure
from .sizing import auto_size

__all__ = ["apply_layout", "build_graph", "EngineUnavailable"]

FREE_KINDS = ("pill", "text")  # positioned by their anchor point; never laid out


def _node_id(ref: Any) -> tuple[str | None, str]:
    """``"a.right@0.3"`` → (``"a"``, ``"right@0.3"``); points → (None, "")."""
    if not isinstance(ref, str):
        return None, ""
    name, _, side = ref.partition(".")
    return name, side


def validate_groups(d: Diagram) -> None:
    by_id = {g.id: g for g in d.groups}
    nodes = {n.id for n in d.nodes}
    owner: dict[str, str] = {}
    for g in d.groups:
        for c in g.children:
            if c not in nodes and c not in by_id:
                raise ValueError(f"{d.id}: group {g.id!r} lists unknown child {c!r}")
            if c in owner:
                raise ValueError(f"{d.id}: {c!r} is in two groups ({owner[c]!r} and {g.id!r})")
            owner[c] = g.id
    for g in d.groups:
        seen, cur = {g.id}, g.id
        while cur in owner:
            cur = owner[cur]
            if cur in seen:
                raise ValueError(f"{d.id}: group cycle through {cur!r}")
            seen.add(cur)


# graph ------------------------------------------------------------------------------------------
def _band(g: Group, theme: Theme) -> float:
    """Height reserved above a group's content for its label / corner icon."""
    zd, zs = theme.defaults("zone"), theme.zone_style(g.style)
    if g.icon or zs["icon"]:
        return zd.get("icon_size", 32) + 14
    return zd.get("label_size", 16) * 1.2 + 22 if g.label else 0


def _laid_out(d: Diagram, in_group: set[str]) -> list[Node]:
    """Nodes the engine places: every grouped node, plus free nodes with no explicit position."""
    return [n for n in d.nodes if n.kind not in FREE_KINDS and (n.id in in_group or (not n.x and not n.y))]


def _rank_order(items: list[str], owner_top: dict[str, str], d: Diagram) -> list[str]:
    """Order top-level items by longest path over edges between them (stable; cycles keep input order)."""
    succ: dict[str, set[str]] = {i: set() for i in items}
    for e in d.edges:
        a, b = owner_top.get(_node_id(e.src)[0] or ""), owner_top.get(_node_id(e.dst)[0] or "")
        if a and b and a != b:
            succ[a].add(b)
    rank: dict[str, int] = {}

    def depth(i: str, stack: frozenset) -> int:
        if i in rank:
            return rank[i]
        preds = [p for p in items if i in succ[p] and p not in stack]
        rank[i] = 1 + max((depth(p, stack | {i}) for p in preds), default=-1)
        return rank[i]

    for i in items:
        depth(i, frozenset())
    return sorted(items, key=lambda i: (rank[i], items.index(i)))


def build_graph(d: Diagram, theme: Theme) -> tuple[LGraph, dict[str, Node]]:
    """LGraph of the laid-out part of ``d`` (node sizes resolved) and the nodes it covers."""
    validate_groups(d)
    lay, ld = d.layout or {}, theme.defaults("layout")
    by_group = {g.id: g for g in d.groups}
    child_of = {c: g.id for g in d.groups for c in g.children}
    nodes = {n.id: n for n in _laid_out(d, set(child_of))}
    for n in nodes.values():
        if not (n.w and n.h):
            n.w, n.h = auto_size(n, theme)
    pad_default = float(lay.get("padding", ld.get("padding", 24)))

    def build(gid: str) -> LGroup:
        g = by_group[gid]
        p = float(g.padding if g.padding is not None else pad_default)
        kids = [build(c) if c in by_group else LNode(c, nodes[c].w, nodes[c].h) for c in g.children]
        hints = {k: getattr(g, k) for k in ("direction", "columns", "gap", "align") if getattr(g, k) is not None}
        return LGroup(g.id, kids, (p + _band(g, theme), p, p, p), hints, g.label)

    tops = [g.id for g in d.groups if g.id not in child_of] + [i for i in nodes if i not in child_of]
    owner_top: dict[str, str] = {}
    for t in tops:
        owner_top[t] = t
        cur = [t]
        while cur:
            nxt = []
            for c in cur:
                for k in (by_group[c].children if c in by_group else []):
                    owner_top[k] = t
                    nxt.append(k)
            cur = nxt
    order = lay.get("order") or _rank_order(tops, owner_top, d)
    root = LGroup("__root__", [build(i) if i in by_group else LNode(i, nodes[i].w, nodes[i].h) for i in order],
                  hints={k: lay[k] for k in ("columns", "align") if k in lay})
    edges = []
    for i, e in enumerate(d.edges):
        a, b = _node_id(e.src)[0], _node_id(e.dst)[0]
        if a in nodes and b in nodes and a != b:
            edges.append(LEdge(f"e{i}", a, b))
    # ranks leave room for the widest edge label pill (+ arrow heads on both sides)
    ed = theme.defaults("edge")
    labels = [measure(e.label, theme.font("body", 700, e.label_size or ed.get("label_size", 17))) + 24
              for e in d.edges if e.label]
    rank_gap = float(lay.get("rank_gap", ld.get("rank_gap", 80)))
    if "rank_gap" not in lay:
        rank_gap = max([rank_gap] + [w + 32 for w in labels])
    spacing = {"gap": float(lay.get("gap", ld.get("gap", 40))),
               "node_gap": float(lay.get("node_gap", ld.get("node_gap", 48))), "rank_gap": rank_gap}
    return LGraph(root, edges, lay.get("direction", "right"), spacing, dict(lay.get("options") or {})), nodes


# placement --------------------------------------------------------------------------------------
def _area(d: Diagram, theme: Theme) -> Box:
    lay = d.layout or {}
    if lay.get("area"):
        x, y, w, h = (float(v) for v in lay["area"])
        return x, y, w, h
    W, H = theme.canvas
    m = (theme.get("canvas") or {}).get("margin", 80)
    ch = theme.get("chrome") or {}
    top = m
    for key in ("title", "subtitle"):
        if ch.get(key) and (key == "title" or d.subtitle):
            top = max(top, ch[key]["y"] + 48)
    bottom = H - m
    if (ch.get("footer") or {}).get("rule_y_from_bottom"):
        bottom = H - ch["footer"]["rule_y_from_bottom"] - 24
    return m, top, W - 2 * m, bottom - top


def _offset(res: LResult, area: Box, align: str) -> tuple[float, float, float, float]:
    xs = [b[0] for b in res.boxes.values()] + [b[0] + b[2] for b in res.boxes.values()]
    ys = [b[1] for b in res.boxes.values()] + [b[1] + b[3] for b in res.boxes.values()]
    x0, y0, bw, bh = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
    ax, ay, aw, ah = area
    v, _, h = align.partition("-")
    fx = {"left": 0, "right": 1}.get(h, 0.5)
    fy = {"top": 0, "bottom": 1}.get(v, 0.5)
    return ax + max(0, aw - bw) * fx - x0, ay + max(0, ah - bh) * fy - y0, bw - aw, bh - ah


def _side(box: Box, pt: tuple[float, float]) -> str:
    """``side@frac`` of the box edge nearest to ``pt``; snaps to the centre (bound PPTX connectors)."""
    x, y, w, h = box
    px, py = pt
    dists = {"left": abs(px - x), "right": abs(px - x - w), "top": abs(py - y), "bottom": abs(py - y - h)}
    side = min(dists, key=dists.get)
    frac = (py - y) / h if side in ("left", "right") else (px - x) / w
    frac = min(1.0, max(0.0, frac))
    span = h if side in ("left", "right") else w
    return side if abs(frac - 0.5) * span <= 3 else f"{side}@{frac:.3f}"


def _simplify(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        (ax, ay), (bx, by), (cx, cy) = out[-1], pts[i], pts[i + 1]
        if abs((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)) > 1.0:  # keep bends only
            out.append(pts[i])
    out.append(pts[-1])
    return out


def apply_layout(diagram: Diagram, theme: Theme, engine: str | None = None) -> Diagram:
    """A copy of ``diagram`` with automatic positions, or ``diagram`` itself when it has no ``layout``."""
    if diagram.layout is None:
        return diagram
    d = copy.deepcopy(diagram)
    graph, nodes = build_graph(d, theme)
    if not graph.root.children:
        return d
    name = engine or os.environ.get("SPINAGRAM_LAYOUT") or d.layout.get("engine") or "flex"
    res = get_engine(name).run(graph)
    dx, dy, over_x, over_y = _offset(res, _area(d, theme), d.layout.get("align", "top-center"))
    if over_x > 1 or over_y > 1:
        d.meta["layout_overflow"] = (round(max(0, over_x)), round(max(0, over_y)))
    # 0.1 px grid: frozen specs (`spinagram layout`) reproduce the render exactly
    boxes = {k: (round(x + dx, 1), round(y + dy, 1), round(w, 1), round(h, 1)) for k, (x, y, w, h) in res.boxes.items()}
    for nid, n in nodes.items():
        n.x, n.y, n.w, n.h = boxes[nid]
    by_group = {g.id: g for g in d.groups}
    zones = []
    for item in graph.root.walk():  # pre-order: outer zones first (drawn behind inner ones)
        if isinstance(item, LGroup) and item.id in by_group:
            g = by_group[item.id]
            x, y, w, h = boxes[g.id]
            zones.append(Zone(x=x, y=y, w=w, h=h, label=g.label, color=g.style or "soft", icon=g.icon))
    d.zones = zones + d.zones
    for le in graph.edges:
        e = d.edges[int(le.id[1:])]
        if e.via or e.curve or _node_id(e.src)[1] or _node_id(e.dst)[1]:
            continue  # the author routed or anchored it
        pts = res.routes.get(le.id)
        if not pts or len(pts) < 2:
            continue
        pts = _simplify([(round(x + dx, 1), round(y + dy, 1)) for x, y in pts])
        e.src = f"{le.src}.{_side(boxes[le.src], pts[0])}"
        e.dst = f"{le.dst}.{_side(boxes[le.dst], pts[-1])}"
        e.via = pts[1:-1] or None
    if d.layout.get("route") == "ortho":
        routed = {le.id for le in graph.edges if res.routes.get(le.id)}
        for le in graph.edges:
            e = d.edges[int(le.id[1:])]
            if le.id not in routed and not (e.via or e.curve or _node_id(e.src)[1] or _node_id(e.dst)[1]):
                _elbow(e, boxes[le.src], boxes[le.dst], le)
    for le in graph.edges:  # labels of routed edges sit on the route, not on the endpoints' midpoint
        e = d.edges[int(le.id[1:])]
        if e.label and e.via and not e.label_at:
            e.label_at = _label_point(boxes, e)
    d.meta["layout_engine"] = name
    d.layout = None  # positions are final; applying again is a no-op
    return d


def _label_point(boxes: dict[str, Box], e) -> tuple[float, float]:
    """Middle of the longest segment of the routed edge (pill centre, 8 px above like straight edges)."""
    def anchor(ref: str) -> tuple[float, float]:
        nid, side = _node_id(ref)
        side, _, frac = side.partition("@")
        x, y, w, h = boxes[nid]
        f = float(frac) if frac else 0.5
        return {"left": (x, y + h * f), "right": (x + w, y + h * f), "top": (x + w * f, y),
                "bottom": (x + w * f, y + h)}.get(side, (x + w / 2, y + h / 2))

    pts = [anchor(e.src), *e.via, anchor(e.dst)]
    (ax, ay), (bx, by) = max(zip(pts, pts[1:]), key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
    return round((ax + bx) / 2, 1), round((ay + by) / 2 - 8, 1)


def _elbow(e, a: Box, b: Box, le: LEdge) -> None:
    """Z-shaped orthogonal route between two boxes (straight when they face each other)."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    acx, acy, bcx, bcy = ax + aw / 2, ay + ah / 2, bx + bw / 2, by + bh / 2
    if ax + aw <= bx or bx + bw <= ax:  # side by side → leave/enter through left/right
        right = bx >= ax + aw
        s, t = ("right", "left") if right else ("left", "right")
        x1, x2 = (ax + aw, bx) if right else (ax, bx + bw)
        if abs(acy - bcy) > 3:
            mx = (x1 + x2) / 2
            e.via = [(mx, acy), (mx, bcy)]
    else:  # stacked → top/bottom
        down = by >= ay + ah
        s, t = ("bottom", "top") if down else ("top", "bottom")
        y1, y2 = (ay + ah, by) if down else (ay, by + bh)
        if abs(acx - bcx) > 3:
            my = (y1 + y2) / 2
            e.via = [(acx, my), (bcx, my)]
    e.src, e.dst = f"{le.src}.{s}", f"{le.dst}.{t}"

"""Diagram model and Python DSL.

The model is plain data: nodes, edges, zones, tables and a legend placed on an
absolute canvas. The same objects are produced by the YAML loader and by the
builder methods on :class:`Diagram`, so both front-ends share every feature.
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

Point = tuple[float, float]
# An edge endpoint: "node", "node.side", "node.side@0.3", a Node, or an absolute point.
EndpointLike = "str | Node | Sequence[float]"

SIDES = ("top", "bottom", "left", "right", "center")


@dataclass
class Node:
    id: str
    kind: str = "box"  # box | note | pill | diamond | text
    x: float = 0
    y: float = 0
    w: float = 0
    h: float = 0
    title: str | list[str] | None = None
    text: str | None = None
    lines: list[str] | None = None
    style: str | None = None
    icon: str | None = None
    icon_size: float | None = None  # px; default scales with the box (theme defaults.node.icon_*)
    align: str = "left"  # left | center
    title_size: float | None = None
    body_size: float | None = None
    radius: float | None = None
    dashed: bool = False
    color: str | None = None  # pill / text colour (edge-style name, token or hex)
    extra: dict[str, Any] = field(default_factory=dict)

    # side anchors for edges -------------------------------------------------
    def at(self, side: str, frac: float = 0.5) -> str:
        if side not in SIDES:
            raise ValueError(f"unknown side {side!r}; use one of {SIDES}")
        return f"{self.id}.{side}" + ("" if frac == 0.5 else f"@{frac:g}")

    @property
    def top(self) -> str:
        return self.at("top")

    @property
    def bottom(self) -> str:
        return self.at("bottom")

    @property
    def left(self) -> str:
        return self.at("left")

    @property
    def right(self) -> str:
        return self.at("right")

    @property
    def center(self) -> str:
        return self.at("center")


@dataclass
class Edge:
    src: str | Point
    dst: str | Point
    label: str | None = None
    label_at: Point | None = None
    color: str | None = None
    dashed: bool = False
    width: float | None = None
    via: list[Point] | None = None
    curve: Point | None = None
    arrow: str = "end"  # end | start | both | none
    label_size: float | None = None


@dataclass
class Zone:
    x: float
    y: float
    w: float
    h: float
    label: str | None = None
    color: str = "soft"
    icon: str | None = None   # group icon in the top-left corner (AWS-style groups); overrides the style's icon


@dataclass
class Group:
    """A container laid out automatically (``layout:``); rendered as a zone around its children.

    ``children`` holds node ids and group ids in order. Layout hints are read by the engines:
    ``direction`` (row | column), ``columns`` (grid), ``gap``, ``padding``, ``align`` (start | center | end).
    """
    id: str
    label: str | None = None
    style: str | None = None   # zone style (aws-region, aws-az, soft…)
    icon: str | None = None
    children: list[str] = field(default_factory=list)
    direction: str | None = None
    columns: int | None = None
    gap: float | None = None
    padding: float | None = None
    align: str | None = None


@dataclass
class Table:
    x: float
    y: float
    widths: list[float]
    header: list[str]
    rows: list[list[str]]
    row_height: float | None = None
    header_height: float | None = None
    font_size: float | None = None
    icons: list[str | None] | None = None
    id: str | None = None


@dataclass
class Legend:
    x: float
    y: float
    items: list[tuple[str, str]]  # (colour/style, label)


_EDGE_RE = re.compile(r"^\s*(?P<src>.+?)\s*(?P<op><->|->|<-|--)\s*(?P<dst>[^:]+?)\s*(?::\s*(?P<label>.*))?$")


def parse_edge(text: str) -> Edge:
    """Parse ``"a -> b"``, ``"a.right@0.3 -> b.left: label"``, ``"a -- b"`` (no arrow), ``"a <-> b"``."""
    m = _EDGE_RE.match(text)
    if not m:
        raise ValueError(f"cannot parse edge {text!r}; expected 'a -> b[: label]'")
    op = m["op"]
    src, dst = m["src"], m["dst"]
    if op == "<-":
        src, dst = dst, src
    arrow = {"->": "end", "<-": "end", "<->": "both", "--": "none"}[op]
    return Edge(src=src, dst=dst, label=(m["label"] or None), arrow=arrow)


def _endpoint(v: Any) -> str | Point:
    if isinstance(v, Node):
        return v.id
    if isinstance(v, str):
        return v
    return (float(v[0]), float(v[1]))


@dataclass
class Diagram:
    """A diagram and a fluent builder.

    >>> d = Diagram("D01", "Routing")
    >>> a = d.box("Request", x=80, y=200, w=400, h=240)
    >>> b = d.box("Engine", x=600, y=200, w=400, h=240, style="dark")
    >>> d.edge(a, b, label="classify")
    """

    id: str
    title: str
    subtitle: str | None = None
    source: str | None = None
    kicker: str | None = None
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    zones: list[Zone] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    legend: Legend | None = None
    groups: list[Group] = field(default_factory=list)
    layout: dict[str, Any] | None = None  # {engine, direction, area, align, options}; None = absolute positions
    base_dir: Path | None = None  # resolves relative icon paths and the facts file
    facts: str | None = None      # path to a facts JSON; text may use {{fact_id}}
    locale: str | None = None     # number formatting for facts (e.g. pt-BR)
    meta: dict[str, Any] = field(default_factory=dict)

    _open: list[Group] = field(default_factory=list, repr=False, compare=False)

    # lookup -------------------------------------------------------------------
    def node(self, node_id: str) -> Node:
        for n in self.nodes:
            if n.id == node_id:
                return n
        raise KeyError(f"{self.id}: no node {node_id!r}")

    def _auto_id(self, title: Any) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", str(title or "n").lower()).strip("-")[:24] or "n"
        ids = {n.id for n in self.nodes}
        cand, i = base, 2
        while cand in ids:
            cand, i = f"{base}-{i}", i + 1
        return cand

    # builders -----------------------------------------------------------------
    def add(self, kind: str, title: Any = None, *, id: str | None = None, x: float = 0, y: float = 0,
            w: float = 0, h: float = 0, **kw: Any) -> Node:
        known = {f for f in Node.__dataclass_fields__}  # noqa: SIM118
        extra = {k: kw.pop(k) for k in list(kw) if k not in known}
        n = Node(id=id or self._auto_id(title), kind=kind, x=x, y=y, w=w, h=h, title=title, extra=extra, **kw)
        if any(o.id == n.id for o in self.nodes):
            raise ValueError(f"{self.id}: duplicate node id {n.id!r}")
        self.nodes.append(n)
        if self._open:
            self._open[-1].children.append(n.id)
        return n

    def box(self, title: Any = None, **kw: Any) -> Node:
        return self.add("box", title, **kw)

    def note(self, title: Any = None, **kw: Any) -> Node:
        return self.add("note", title, **kw)

    def diamond(self, title: Any = None, **kw: Any) -> Node:
        return self.add("diamond", title, **kw)

    def pill(self, title: str, *, x: float, y: float, **kw: Any) -> Node:
        """A rounded tag centred on (x, y)."""
        return self.add("pill", title, x=x, y=y, **kw)

    def label(self, text: str, *, x: float, y: float, **kw: Any) -> Node:
        """Free text; (x, y) is the first baseline."""
        return self.add("text", text, x=x, y=y, **kw)

    def edge(self, src: Any, dst: Any = None, **kw: Any) -> Edge:
        """``d.edge(a, b)``, ``d.edge(a.right, b.left@0.3)``, or ``d.edge("a -> b: label")``."""
        if dst is None and isinstance(src, str):
            e = parse_edge(src)
            for k, v in kw.items():
                setattr(e, k, v)
        else:
            e = Edge(src=_endpoint(src), dst=_endpoint(dst), **kw)
        if e.via:
            e.via = [(float(p[0]), float(p[1])) for p in e.via]
        self.edges.append(e)
        return e

    def chain(self, *nodes: Any, **kw: Any) -> list[Edge]:
        """Connect consecutive nodes: ``d.chain(a, b, c)``."""
        return [self.edge(a, b, **kw) for a, b in zip(nodes, nodes[1:])]

    def zone(self, label: str | None = None, *, x: float, y: float, w: float, h: float, color: str = "soft",
             icon: str | None = None) -> Zone:
        z = Zone(x=x, y=y, w=w, h=h, label=label, color=color, icon=icon)
        self.zones.append(z)
        return z

    @contextmanager
    def group(self, label: str | None = None, *, id: str | None = None, style: str | None = None,
              **hints: Any) -> Iterator[Group]:
        """Nodes and groups created inside the ``with`` block become its children::

            with d.group("us-east-1", style="aws-region"):
                with d.group("AZ a", style="aws-az"):
                    d.box("Vault 1")
        """
        gid = id or "g-" + (re.sub(r"[^a-z0-9]+", "-", str(label or "").lower()).strip("-")[:24] or
                            str(len(self.groups) + 1))
        if any(g.id == gid for g in self.groups):
            raise ValueError(f"{self.id}: duplicate group id {gid!r}")
        g = Group(id=gid, label=label, style=style, **hints)
        self.groups.append(g)
        if self._open:
            self._open[-1].children.append(g.id)
        self._open.append(g)
        try:
            yield g
        finally:
            self._open.pop()

    def table(self, header: list[str], rows: list[list[str]], *, x: float, y: float, widths: list[float],
              **kw: Any) -> Table:
        t = Table(x=x, y=y, widths=widths, header=header, rows=rows, **kw)
        self.tables.append(t)
        return t

    def set_legend(self, items: Iterable[tuple[str, str]], *, x: float, y: float) -> Legend:
        self.legend = Legend(x=x, y=y, items=list(items))
        return self.legend

    # layout helpers -----------------------------------------------------------
    def _seq(self, items: Sequence[Any], axis: str, x: float, y: float, w: float, h: float, gap: float,
             kind: str, styles: Sequence[str | None] | None, **common: Any) -> list[Node]:
        out = []
        for i, item in enumerate(items):
            spec = dict(common)
            if isinstance(item, dict):
                spec.update(item)
            else:
                spec["title"] = item
            if styles and i < len(styles) and styles[i]:
                spec.setdefault("style", styles[i])
            pos = {"x": x + i * (w + gap), "y": y} if axis == "x" else {"x": x, "y": y + i * (h + gap)}
            spec.setdefault("w", w)
            spec.setdefault("h", h)
            spec.update({k: v for k, v in pos.items() if k not in spec})
            title = spec.pop("title", None)
            out.append(self.add(spec.pop("kind", kind), title, **spec))
        return out

    def row(self, items: Sequence[Any], *, x: float, y: float, w: float, h: float, gap: float = 60,
            kind: str = "box", styles: Sequence[str | None] | None = None, **common: Any) -> list[Node]:
        """Place nodes left to right. Items are titles or dicts of node fields."""
        return self._seq(items, "x", x, y, w, h, gap, kind, styles, **common)

    def column(self, items: Sequence[Any], *, x: float, y: float, w: float, h: float, gap: float = 40,
               kind: str = "box", styles: Sequence[str | None] | None = None, **common: Any) -> list[Node]:
        """Place nodes top to bottom."""
        return self._seq(items, "y", x, y, w, h, gap, kind, styles, **common)

    # rendering shortcut -------------------------------------------------------
    def save(self, out_dir: str | Path, *, theme: Any = None, formats: Sequence[str] = ("svg",)) -> list[Path]:
        from .api import render

        return render([self], out_dir, theme=theme, formats=formats)

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
    cls: str | None = None    # CSS classes (``class_=`` in builders, ``class:`` in YAML)
    css: str | None = None    # inline CSS declarations
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

    # edges by operator ----------------------------------------------------------
    # ``a >> b`` draws a -> b, ``a << b`` draws b -> a, ``a - b`` a plain line. Each returns its right-hand
    # side, so ``a >> b >> c`` chains, and lists fan out or in: ``lb >> [web1, web2] >> db``.
    def _diagram_or_raise(self) -> "Diagram":
        d = self.__dict__.get("_diagram")
        if d is None:
            raise TypeError(f"node {self.id!r} is not in a diagram: create it with d.box(...)")
        return d

    def to(self, other: Any, label: str | None = None, **kw: Any) -> Any:
        """Connect to ``other`` (a node or a list) and return it: ``users.to(lb, "HTTPS").to(api)``."""
        d = self._diagram_or_raise()
        for t in other if isinstance(other, (list, tuple)) else [other]:
            d.edge(self, t, label, **kw)
        return other

    def yes(self, target: Any, **kw: Any) -> Any:
        """Decision branch labelled ``Yes``."""
        return self.to(target, "Yes", **kw)

    def no(self, target: Any, **kw: Any) -> Any:
        """Decision branch labelled ``No``."""
        return self.to(target, "No", **kw)

    def on(self, event: str | None, target: Any, guard: str | None = None, action: str | None = None,
           **kw: Any) -> Any:
        """Transition labelled ``event [guard] / action`` (empty parts omitted)."""
        label = " ".join(p for p in (event or "", f"[{guard}]" if guard else "") if p)
        if action:
            label = f"{label} / {action}".strip()
        return self.to(target, label or None, **kw)

    def __rshift__(self, other: Any) -> Any:
        return self.to(other)

    def __lshift__(self, other: Any) -> Any:
        for t in other if isinstance(other, (list, tuple)) else [other]:
            t.to(self)
        return other

    def __sub__(self, other: Any) -> Any:
        return self.to(other, arrow="none")

    def __rrshift__(self, other: Any) -> "Node":  # [a, b] >> c
        for s in other:
            s.to(self)
        return self

    def __rlshift__(self, other: Any) -> "Node":  # [a, b] << c
        self.to(other)
        return self

    def __rsub__(self, other: Any) -> "Node":  # [a, b] - c
        for s in other:
            s.to(self, arrow="none")
        return self


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
    cls: str | None = None
    css: str | None = None


@dataclass
class Zone:
    x: float
    y: float
    w: float
    h: float
    label: str | None = None
    color: str = "soft"
    icon: str | None = None   # group icon in the top-left corner (AWS-style groups); overrides the style's icon
    gid: str | None = None    # the group this zone was laid out from (styles target it)


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
    engine: str | None = None      # lay this group's content out with its own engine (typed regions)
    lanes: bool = False            # children groups are swimlanes (layered engine)
    region: str | None = None      # flowchart | state_machine | activity (set by the builders)
    cls: str | None = None
    css: str | None = None


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


def normalize_tags(tags: Any, owner: str) -> list[str]:
    """Catalog tags as a sorted list of unique, trimmed, lower-case strings; a single string is one tag."""
    if isinstance(tags, str):
        tags = [tags]
    if not isinstance(tags, (list, tuple, set)) or not all(isinstance(t, str) for t in tags):
        raise ValueError(f"{owner}: tags must be a list of strings, got {tags!r}")
    return sorted({t.strip().lower() for t in tags} - {""})


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
    css: str | None = None        # stylesheet text for this diagram (after theme and folder sheets)
    stylesheets: list[str] = field(default_factory=list)  # paths or stylesheet texts, in cascade order
    category: str | None = None   # catalog grouping (``group`` is taken by layout zones)
    tags: list[str] = field(default_factory=list)  # catalog tags, normalised: trimmed, lower-case, unique, sorted

    _open: list[Group] = field(default_factory=list, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.category is not None and not isinstance(self.category, str):
            raise ValueError(f"{self.id}: category must be a string, got {self.category!r}")
        self.tags = normalize_tags(self.tags, self.id)

    @property
    def auto(self) -> bool:
        """Laid out automatically: ``layout`` is set, or no node has a position or a size."""
        return self.layout is not None or (bool(self.nodes) and
                                           not any(n.x or n.y or n.w or n.h for n in self.nodes))

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
        if "class_" in kw:
            kw["cls"] = kw.pop("class_")
        known = {f for f in Node.__dataclass_fields__}  # noqa: SIM118
        extra = {k: kw.pop(k) for k in list(kw) if k not in known}
        n = Node(id=id or self._auto_id(title), kind=kind, x=x, y=y, w=w, h=h, title=title, extra=extra, **kw)
        if any(o.id == n.id for o in self.nodes):
            raise ValueError(f"{self.id}: duplicate node id {n.id!r}")
        self.nodes.append(n)
        n.__dict__["_diagram"] = self  # for a >> b; not a dataclass field, so dumps and asdict skip it
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

    def edge(self, src: Any, dst: Any = None, label: str | None = None, **kw: Any) -> Edge:
        """``d.edge(a, b)``, ``d.edge(a, b, "label")``, ``d.edge(a.right, b.left@0.3)``, or
        ``d.edge("a -> b: label")``. ``a >> b`` on nodes is the short form."""
        if label is not None:
            kw["label"] = label
        if "class_" in kw:
            kw["cls"] = kw.pop("class_")
        if dst is None and isinstance(src, str):
            e = parse_edge(src)
            for k, v in kw.items():
                setattr(e, k, v)
        else:
            e = Edge(src=_endpoint(src), dst=_endpoint(dst), **kw)
        if e.via:
            e.via = [(float(p[0]), float(p[1])) for p in e.via]
        self._check_pseudo(e)
        kinds = {n.id: n.kind for n in self.nodes}
        if "dashed" not in kw and "object" in (kinds.get(str(e.src).partition(".")[0]),
                                              kinds.get(str(e.dst).partition(".")[0])):
            e.dashed = True  # object flows (UML activity) are dashed
        self.edges.append(e)
        return e

    def _check_pseudo(self, e: Edge) -> None:
        """Finals have no outgoing edges and initials no incoming ones (UML)."""
        kinds = {n.id: n.kind for n in self.nodes}
        src = e.src.partition(".")[0] if isinstance(e.src, str) else None
        dst = e.dst.partition(".")[0] if isinstance(e.dst, str) else None
        if kinds.get(src) in ("final", "flow_final"):
            raise ValueError(f"final node {src} cannot have outgoing edges")
        if kinds.get(dst) == "initial":
            raise ValueError(f"initial node {dst} cannot have incoming edges")

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
        if "class_" in hints:
            hints["cls"] = hints.pop("class_")
        g = Group(id=gid, label=label, style=style, **hints)
        self.groups.append(g)
        if self._open:
            self._open[-1].children.append(g.id)
        self._open.append(g)
        try:
            yield g
        finally:
            self._open.pop()

    def stylesheet(self, sheet: str | Path) -> "Diagram":
        """Add a stylesheet (a ``.css`` path or CSS text) to this diagram's cascade, after earlier ones."""
        self.stylesheets.append(str(sheet))
        return self

    # typed regions: one diagram can mix architecture and behavior ------------------------------
    @contextmanager
    def flowchart(self, title: str | None = None, *, id: str | None = None, direction: str = "down",
                  **kw: Any) -> Iterator[Any]:
        """``with d.flowchart("Checkout") as fc:`` — flowchart verbs inside a region of this diagram."""
        from .behavior import region
        with region(self, "flowchart", title, id, direction, **kw) as r:
            yield r

    @contextmanager
    def state_machine(self, title: str | None = None, *, id: str | None = None, direction: str = "down",
                      **kw: Any) -> Iterator[Any]:
        """``with d.state_machine("Order") as sm:`` — state machine verbs inside a region."""
        from .behavior import region
        with region(self, "state_machine", title, id, direction, **kw) as r:
            yield r

    @contextmanager
    def activity(self, title: str | None = None, *, id: str | None = None, direction: str = "down",
                 **kw: Any) -> Iterator[Any]:
        """``with d.activity("Fulfilment") as act:`` — activity verbs (lanes, forks) inside a region."""
        from .behavior import region
        with region(self, "activity", title, id, direction, **kw) as r:
            yield r

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
    def save(self, out_dir: str | Path = "out", *, theme: Any = None, formats: Sequence[str] = ("svg",),
             layout: str | None = None) -> list[Path]:
        """Render to ``out_dir``: ``d.save()``, ``d.save("out/", formats=["svg", "png", "pptx"])``."""
        from .api import render

        return render([self], out_dir, theme=theme, formats=formats, layout=layout)

    def svg(self, *, theme: Any = None, layout: str | None = None) -> str:
        """The rendered SVG as a string."""
        from .api import scenes
        from .backends.svg import to_svg

        return to_svg(scenes([self], theme, layout)[0])

    def _repr_svg_(self) -> str:  # Jupyter shows the diagram inline
        return self.svg()

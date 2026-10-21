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
        step = kw.pop("step", None)
        for t in other if isinstance(other, (list, tuple)) else [other]:
            e = d.edge(self, t, label, **kw)
            if step is not None:
                d.step(step, on=e)
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
    fan: str | None = None      # "bus": into a zone through a bar spanning the zone's children
    route: str | None = None    # "ortho": routed around boxes, avoiding crossings; None: straight (or defaults)
    fan_in: bool = False        # edges into the same target with fan_in share one trunk and one arrowhead
    meaning: str | None = None  # legend label for this edge style (``d.legend(items="auto")``)

    def step(self, text: str, n: int | None = None) -> "Step":
        """Number this edge as a step of the flow: a badge on the edge and a line in the steps panel."""
        d = self.__dict__.get("_diagram")
        if d is None:
            raise TypeError("edge is not in a diagram: create it with d.edge(...)")
        return d.step(text, on=self, n=n)


@dataclass
class Zone:
    x: float
    y: float
    w: float
    h: float
    label: str | None = None
    color: str = "soft"
    icon: str | list[str] | None = None  # header icon (a list: header chips); overrides the style's icon
    gid: str | None = None    # the group this zone was laid out from (styles target it)
    id: str | None = None     # CSS ``zone#id`` and edge target ``zone:<id>``; builders assign ``z<index>``
    dash: str | list[float] | None = None  # solid | dashed | dotted | [pattern]; None: the style's
    stroke: str | None = None
    stroke_width: float | None = None
    fill: str | None = None   # token, hex or "none"
    header: dict[str, Any] | None = None   # padding, icon_size, strip, upper, inset
    fit: str | None = None    # "children": sized to its children
    padding: float | None = None
    equalize: str | None = None            # "siblings": same height as sibling zones
    children: list[str] = field(default_factory=list)  # node and zone ids inside (``with d.zone(...)``)
    meaning: str | None = None             # legend label for this zone style
    cls: str | None = None

    def __enter__(self) -> "Zone":  # ``with d.zone(...) as z:``: nodes and zones created inside are children
        d = self.__dict__.get("_diagram")
        if d is None:
            raise TypeError("zone is not in a diagram: create it with d.zone(...)")
        d._open_zones.append(self)
        return self

    def __exit__(self, *exc: Any) -> None:
        self.__dict__["_diagram"]._open_zones.pop()

    @property
    def content_top(self) -> float:
        """First y below this zone's header (header bottom + 12 px) with the built-in header defaults; the
        scene's ``zone_content_tops`` has the value after theme and style header settings."""
        from .engine.zones import content_top

        icons = len(self.icon) if isinstance(self.icon, list) else int(bool(self.icon))
        return content_top(self, icons)


# kinds a ``node_size`` default applies to: content boxes, not markers (start/end dots, fork bars, decisions,
# terminators), free text or pills, which keep the size of their symbol or their text
SIZED_KINDS = frozenset({"box", "note", "process", "io", "document", "predefined", "data", "state", "action",
                         "object", "signal_send", "signal_receive"})


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
class Bundle:
    """Edges into one target that share an orthogonal trunk on the ``trunk`` side of their sources."""
    edges: list[int]               # indexes into ``Diagram.edges``
    trunk: str | None = None       # right | left | top | bottom; None: the side facing the target


@dataclass
class Container:
    """Nodes placed side by side (``row``) or stacked (``column``) from (x, y), sized by the model passes."""
    axis: str                      # row | column
    x: float
    y: float
    gap: float = 20
    same_size: bool = False
    max_width: float | None = None
    same_icon_size: bool = False
    children: list[str] = field(default_factory=list)


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


NOTE_VARIANTS = ("sticky", "card", "quote")
CALLOUT_KINDS = ("info", "tip", "warning", "risk")
CALLOUT_SIDES = ("auto", "top", "right", "bottom", "left")
BAND_POSITIONS = ("right", "bottom", "left", "top")


@dataclass
class LegendSpec:
    """A legend card in the annotation band; ``items`` maps keys (``.class``, ``edge.class``, ``style:name``,
    ``pack:icon``) to labels, or ``None`` to list what the diagram uses."""
    title: str = "Legend"
    items: dict[str, str] | None = None
    position: str | None = None  # right | bottom | left | top; None: the stylesheet's `placement`, else right
    auto: bool = False           # items="auto": one row per edge/zone style that carries a ``meaning``
    place: tuple[float, float, float, float] | None = None  # a cell (x, y, w, h) instead of the band


@dataclass
class Step:
    n: int
    text: str
    edge: int | None = None   # index into ``Diagram.edges``
    node: str | None = None


@dataclass
class Callout:
    target: str               # node id
    text: str
    title: str | None = None
    kind: str = "info"        # info | tip | warning | risk
    side: str = "auto"        # auto | top | right | bottom | left
    cls: str | None = None
    css: str | None = None


@dataclass
class Annotations:
    legend: LegendSpec | None = None
    steps: list[Step] = field(default_factory=list)
    callouts: list[Callout] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.legend or self.steps or self.callouts)


_EDGE_RE = re.compile(r"^\s*(?P<src>.+?)\s*(?P<op><->|->|<-|--)\s*(?P<dst>(?:zone:)?[^:]+?)\s*(?::\s*(?P<label>.*))?$")


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
    if isinstance(v, Zone):
        if v.id is None:
            raise ValueError("zone has no id: create it with d.zone(...) to use it as an edge endpoint")
        return f"zone:{v.id}"
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
    annotations: Annotations = field(default_factory=lambda: Annotations())
    category: str | None = None   # catalog grouping (``group`` is taken by layout zones)
    tags: list[str] = field(default_factory=list)  # catalog tags, normalised: trimmed, lower-case, unique, sorted
    node_size: tuple[float, float] | None = None  # (w, h) for every node created without a size
    containers: list[Container] = field(default_factory=list)  # ``with d.row(...)`` / ``with d.column(...)``
    bundles: list[Bundle] = field(default_factory=list)        # ``d.bundle([e1, e2], trunk="right")``

    _open: list[Group] = field(default_factory=list, repr=False, compare=False)
    _sizes: list[tuple[float, float] | None] = field(default_factory=list, repr=False, compare=False)
    _open_containers: list[Container] = field(default_factory=list, repr=False, compare=False)
    _open_zones: list[Zone] = field(default_factory=list, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.category is not None and not isinstance(self.category, str):
            raise ValueError(f"{self.id}: category must be a string, got {self.category!r}")
        self.tags = normalize_tags(self.tags, self.id)

    @property
    def auto(self) -> bool:
        """Laid out automatically: ``layout`` is set, or no node has a position (a size alone is a hint)."""
        return self.layout is not None or (bool(self.nodes) and not self.containers and
                                           not any(n.x or n.y for n in self.nodes))

    # lookup -------------------------------------------------------------------
    def node(self, node_id: str) -> Node:
        for n in self.nodes:
            if n.id == node_id:
                return n
        raise KeyError(f"{self.id}: no node {node_id!r}")

    def _auto_id(self, title: Any) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", str(title or "n").lower()).strip("-")[:24] or "n"
        ids = {n.id for n in self.nodes} | {g.id for g in self.groups}  # a box and a group never share an id
        cand, i = base, 2
        while cand in ids:
            cand, i = f"{base}-{i}", i + 1
        return cand

    # builders -----------------------------------------------------------------
    def add(self, kind: str, title: Any = None, *, id: str | None = None, x: float = 0, y: float = 0,
            w: float = 0, h: float = 0, size: tuple[float, float] | None = None, **kw: Any) -> Node:
        """A node of ``kind``. ``size=(w, h)`` sets both; without a size the innermost ``node_size`` of the
        open groups (or the diagram's) applies, and failing that the node is sized from its text."""
        if size is not None:
            w, h = size
        elif not (w or h) and kind in SIZED_KINDS:
            default = next((s for s in reversed(self._sizes) if s), None) or self.node_size
            if default:
                w, h = default
        if "class_" in kw:
            kw["cls"] = kw.pop("class_")
        known = {f for f in Node.__dataclass_fields__}  # noqa: SIM118
        extra = {k: kw.pop(k) for k in list(kw) if k not in known}
        if len(extra.get("badges") or []) > 3:
            raise ValueError(f"{self.id}: node {id or title!r} has {len(extra['badges'])} badges; at most 3")
        n = Node(id=id or self._auto_id(title), kind=kind, x=x, y=y, w=w, h=h, title=title, extra=extra, **kw)
        if any(o.id == n.id for o in self.nodes):
            raise ValueError(f"{self.id}: duplicate node id {n.id!r}")
        if any(g.id == n.id for g in self.groups):
            raise ValueError(f"{self.id}: node id {n.id!r} is already a group id")
        self.nodes.append(n)
        n.__dict__["_diagram"] = self  # for a >> b; not a dataclass field, so dumps and asdict skip it
        if self._open:
            self._open[-1].children.append(n.id)
        if self._open_containers:
            self._open_containers[-1].children.append(n.id)
        if self._open_zones:
            self._open_zones[-1].children.append(n.id)
        return n

    def box(self, title: Any = None, **kw: Any) -> Node:
        return self.add("box", title, **kw)

    def note(self, title: Any = None, *, variant: str | None = None, **kw: Any) -> Node:
        """A note: ``variant`` is ``sticky`` (default), ``card`` (accent bar) or ``quote``."""
        n = self.add("note", title, **kw)
        if variant is not None:
            if variant not in NOTE_VARIANTS:
                self.nodes.remove(n)
                if self._open:
                    self._open[-1].children.remove(n.id)
                raise ValueError(f"{self.id}: note variant {variant!r}; use one of {', '.join(NOTE_VARIANTS)}")
            if variant != "sticky":
                n.extra["variant"] = variant
        return n

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
        e.__dict__["_diagram"] = self  # for edge.step(...); not a dataclass field
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

    def bundle(self, edges: Sequence[Any], trunk: str | None = None) -> Bundle:
        """Route ``edges`` (Edge objects or indexes) into their common target through one shared trunk."""
        idx = [e if isinstance(e, int) else next(i for i, o in enumerate(self.edges) if o is e) for e in edges]
        targets = {str(self.edges[i].dst).partition(".")[0] for i in idx}
        if len(targets) != 1:
            raise ValueError(f"{self.id}: bundled edges must share one target, got {sorted(targets)}")
        if trunk not in (None, "right", "left", "top", "bottom"):
            raise ValueError(f"{self.id}: bundle trunk {trunk!r}; use right, left, top or bottom")
        b = Bundle(idx, trunk)
        self.bundles.append(b)
        return b

    def chain(self, *nodes: Any, **kw: Any) -> list[Edge]:
        """Connect consecutive nodes: ``d.chain(a, b, c)``."""
        return [self.edge(a, b, **kw) for a, b in zip(nodes, nodes[1:])]

    def zone(self, label: str | None = None, *, x: float = 0, y: float = 0, w: float = 0, h: float = 0,
             color: str = "soft", icon: str | list[str] | None = None, **kw: Any) -> Zone:
        if "class_" in kw:
            kw["cls"] = kw.pop("class_")
        z = Zone(x=x, y=y, w=w, h=h, label=label, color=color, icon=icon, **kw)
        return self._add_zone(z)

    def _add_zone(self, z: Zone) -> Zone:
        if z.id is None:
            z.id = f"z{len(self.zones)}"
        if any(o.id == z.id for o in self.zones):
            raise ValueError(f"{self.id}: duplicate zone id {z.id!r}")
        self.zones.append(z)
        z.__dict__["_diagram"] = self  # for ``with d.zone(...)``; not a dataclass field
        if self._open_zones:
            self._open_zones[-1].children.append(z.id)
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
        if any(n.id == gid for n in self.nodes):
            raise ValueError(f"{self.id}: group id {gid!r} is already a node id")
        if "class_" in hints:
            hints["cls"] = hints.pop("class_")
        node_size = hints.pop("node_size", None)  # builder default for the nodes created inside
        g = Group(id=gid, label=label, style=style, **hints)
        self.groups.append(g)
        if self._open:
            self._open[-1].children.append(g.id)
        self._open.append(g)
        self._sizes.append(tuple(node_size) if node_size else None)
        try:
            yield g
        finally:
            self._open.pop()
            self._sizes.pop()

    # annotations ---------------------------------------------------------------------------------
    def add_legend(self, items: dict[str, str] | str | None = None, *, title: str = "Legend",
                   position: str | None = None, place: Any = "band") -> LegendSpec:
        """A legend card in the annotation band: ``items`` maps ``.class``, ``edge.class``, ``style:name`` or
        ``pack:icon`` to a label; without items it lists the classes and styles the diagram uses; ``"auto"`` lists
        one row per edge or zone style that carries a ``meaning``. ``place`` is ``"band"`` or a cell (x, y, w, h).

        SPEC_DEVIATION: the roadmap's ``d.legend(...)`` is taken by the 0.1 fixed-legend field ``Diagram.legend``,
        so the automatic legend is ``add_legend(items="auto", place=...)``."""
        if position is not None and position not in BAND_POSITIONS:
            raise ValueError(f"{self.id}: legend position {position!r}; use one of {', '.join(BAND_POSITIONS)}")
        auto = items == "auto"
        if place != "band" and (not isinstance(place, (list, tuple)) or len(place) != 4):
            raise ValueError(f"{self.id}: legend place {place!r}; use 'band' or (x, y, w, h)")
        cell = None if place == "band" else tuple(float(v) for v in place)
        self.annotations.legend = LegendSpec(title, None if auto or items is None else dict(items), position, auto,
                                             cell)
        return self.annotations.legend

    def _node_id(self, ref: Any) -> str:
        if isinstance(ref, Node):
            if ref.__dict__.get("_diagram") is not self:
                raise ValueError(f"{self.id}: node {ref.id!r} is not in diagram {self.id}")
            return ref.id
        if isinstance(ref, str) and any(n.id == ref for n in self.nodes):
            return ref
        raise ValueError(f"{self.id}: unknown node {ref!r}")

    def step(self, text: str, *, on: Any, n: int | None = None) -> Step:
        """Number a step of the flow on an edge, a node, a node id or a ``(src, dst)`` pair; without ``n`` it
        takes the next number after the highest so far."""
        edge = node = None
        if isinstance(on, Edge):
            edge = next((i for i, e in enumerate(self.edges) if e is on), None)
            if edge is None:
                raise ValueError(f"{self.id}: edge is not in diagram {self.id}")
        elif isinstance(on, (tuple, list)):
            a, b = (self._node_id(x) for x in on)
            edge = next((i for i, e in enumerate(self.edges)
                         if str(e.src).partition(".")[0] == a and str(e.dst).partition(".")[0] == b), None)
            if edge is None:
                raise ValueError(f"{self.id}: no edge from {a!r} to {b!r}")
        else:
            node = self._node_id(on)
        if n is None:
            n = max((s.n for s in self.annotations.steps), default=0) + 1
        st = Step(int(n), str(text), edge, node)
        self.annotations.steps.append(st)
        return st

    def callout(self, target: Any, text: str, *, title: str | None = None, kind: str = "info",
                side: str = "auto", **kw: Any) -> Callout:
        """A note bubble pointing at a node with a leader line; ``kind`` sets its colour and glyph."""
        if kind not in CALLOUT_KINDS:
            raise ValueError(f"{self.id}: callout kind {kind!r}; use one of {', '.join(CALLOUT_KINDS)}")
        if side not in CALLOUT_SIDES:
            raise ValueError(f"{self.id}: callout side {side!r}; use one of {', '.join(CALLOUT_SIDES)}")
        c = Callout(self._node_id(target), str(text), title, kind, side, kw.pop("class_", kw.pop("cls", None)),
                    kw.pop("css", None))
        if kw:
            raise TypeError(f"callout() got unexpected arguments {sorted(kw)}")
        self.annotations.callouts.append(c)
        return c

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

    @contextmanager
    def _container(self, axis: str, x: float, y: float, gap: float, same_size: bool, max_width: float | None,
                   same_icon_size: bool) -> Iterator[Container]:
        c = Container(axis, x, y, gap, same_size, max_width, same_icon_size)
        self.containers.append(c)
        self._open_containers.append(c)
        try:
            yield c
        finally:
            self._open_containers.pop()

    def row(self, items: Sequence[Any] | None = None, *, x: float, y: float, w: float | None = None,
            h: float | None = None, gap: float | None = None, kind: str = "box",
            styles: Sequence[str | None] | None = None, same_size: bool = False, max_width: float | None = None,
            same_icon_size: bool = False, **common: Any) -> Any:
        """Place nodes left to right. With ``items`` (titles or dicts of node fields) and ``w``/``h``: the nodes.
        Without items: ``with d.row(x=, y=, gap=, same_size=, max_width=):`` places the nodes created inside."""
        if items is None:
            return self._container("row", x, y, 20 if gap is None else gap, same_size, max_width, same_icon_size)
        if w is None or h is None:
            raise TypeError("row(items, ...) needs w and h")
        return self._seq(items, "x", x, y, w, h, 60 if gap is None else gap, kind, styles, **common)

    def column(self, items: Sequence[Any] | None = None, *, x: float, y: float, w: float | None = None,
               h: float | None = None, gap: float | None = None, kind: str = "box",
               styles: Sequence[str | None] | None = None, same_size: bool = False, max_width: float | None = None,
               same_icon_size: bool = False, **common: Any) -> Any:
        """Place nodes top to bottom; without items, a ``with`` container like :meth:`row`."""
        if items is None:
            return self._container("column", x, y, 20 if gap is None else gap, same_size, max_width,
                                   same_icon_size)
        if w is None or h is None:
            raise TypeError("column(items, ...) needs w and h")
        return self._seq(items, "y", x, y, w, h, 40 if gap is None else gap, kind, styles, **common)

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

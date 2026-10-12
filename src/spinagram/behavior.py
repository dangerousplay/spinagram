"""Builders for flowcharts, state machines and activity diagrams.

Each builder is a :class:`~spinagram.model.Diagram` (use it on its own) whose verbs create nodes of the
behavior symbol kinds (``spinagram.shapes``) and default to the ``layered`` engine::

    fc = Flowchart("F01", "Checkout")
    ok = fc.decision("Card valid?")
    fc.start() >> fc.process("Read card") >> ok
    ok.yes(fc.process("Charge")) >> fc.end()
    ok.no(fc.io("Show error"))

The same verbs work on a typed region inside any diagram (``with d.state_machine("Order") as sm:``):
the region is a group with its own engine, so one slide can mix architecture and behavior.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from .model import Diagram, Group, Node


class _Verbs:
    """Shared machinery: node creation inside the builder's scope (its region group, if any)."""

    _d: Diagram
    _group: Group | None

    def _bind(self, d: Diagram, group: Group | None, direction: str) -> None:
        self._d, self._group, self._direction = d, group, direction
        self._pseudo: dict[str, Node] = {}

    @contextmanager
    def _scope(self) -> Iterator[None]:
        d, g = self._d, self._group
        if g is None or any(o is g for o in d._open):  # already inside it (directly or via a lane)
            yield
            return
        d._open.append(g)
        try:
            yield
        finally:
            d._open.pop()

    def _add(self, kind: str, title: Any = None, **kw: Any) -> Node:
        with self._scope():
            n = self._d.add(kind, title, **kw)
        collect = getattr(self, "_collect", None)
        if collect:
            collect[-1].append((n, n))
        return n

    def _once(self, key: str, kind: str, title: Any = None, **kw: Any) -> Node:
        """One pseudostate per scope (``sm.initial``, ``sm.final``)."""
        if key not in self._pseudo:
            prefix = f"{self._group.id}-" if self._group is not None else ""
            self._pseudo[key] = self._add(kind, title, id=self._d._auto_id(prefix + key), **kw)
        return self._pseudo[key]


class _FlowVerbs(_Verbs):
    def start(self, title: str = "Start", **kw: Any) -> Node:
        return self._add("terminator", title, **kw)

    def end(self, title: str = "End", **kw: Any) -> Node:
        return self._add("terminator", title, **kw)

    def process(self, title: Any, **kw: Any) -> Node:
        return self._add("process", title, **kw)

    def decision(self, title: Any, **kw: Any) -> Node:
        return self._add("decision", title, **kw)

    def io(self, title: Any, **kw: Any) -> Node:
        return self._add("io", title, **kw)

    def document(self, title: Any, **kw: Any) -> Node:
        return self._add("document", title, **kw)

    def predefined(self, title: Any, **kw: Any) -> Node:
        return self._add("predefined", title, **kw)

    def data(self, title: Any, **kw: Any) -> Node:
        return self._add("data", title, **kw)


class _StateVerbs(_Verbs):
    def state(self, title: Any, *, entry: str | None = None, do: str | None = None, exit: str | None = None,
              **kw: Any) -> Node:
        lines = [f"{k} / {v}" for k, v in (("entry", entry), ("do", do), ("exit", exit)) if v]
        if lines:
            kw.setdefault("lines", lines)
        return self._add("state", title, **kw)

    def choice(self, title: Any = None, **kw: Any) -> Node:
        return self._add("choice", title, **kw)

    @contextmanager
    def composite(self, title: Any, **kw: Any) -> Iterator["_StateScope"]:
        """Composite state: substates created on the yielded scope live inside it."""
        kw.setdefault("style", "state")
        with self._scope(), self._d.group(title, **kw) as g:
            yield _StateScope(self._d, g, self._direction)

    @contextmanager
    def region(self, title: Any = None, **kw: Any) -> Iterator["_StateScope"]:
        """Orthogonal region of a composite state (drawn as a dashed box)."""
        # SPEC_DEVIATION: BHV-14 asks for dashed dividers; regions are dashed boxes until zones get dividers.
        kw.setdefault("style", "region")
        with self._scope(), self._d.group(title, **kw) as g:
            yield _StateScope(self._d, g, self._direction)

    def history(self, deep: bool = False, **kw: Any) -> Node:
        return self._add("deep_history" if deep else "history", "H*" if deep else "H", **kw)

    @property
    def initial(self) -> Node:
        return self._once("initial", "initial")

    @property
    def final(self) -> Node:
        return self._once("final", "final")


class _Parallel:
    """``with act.parallel() as p:`` — a fork, branches opened with ``p.branch()``, and a join on exit."""

    def __init__(self, act: "_ActivityVerbs") -> None:
        self._act = act
        self.fork: Node | None = None
        self.join: Node | None = None
        self._branches: list[list[tuple[Node, Node]]] = []

    @contextmanager
    def branch(self) -> Iterator[None]:
        units: list[tuple[Node, Node]] = []
        self._act._collect.append(units)
        try:
            yield
        finally:
            self._act._collect.pop()
            _chain_units(units)
            if units:
                self._branches.append(units)


def _chain_units(units: list[tuple[Node, Node]]) -> None:
    for (_, out), (inn, _) in zip(units, units[1:]):
        out >> inn


class _ActivityVerbs(_Verbs):
    def _bar(self, kind: str) -> Node:
        extra = {"orient": "v"} if self._direction == "right" else {}
        with self._scope():
            return self._d.add(kind, None, **extra)

    def action(self, title: Any, **kw: Any) -> Node:
        return self._add("action", title, **kw)

    def decision(self, title: Any, **kw: Any) -> Node:
        return self._add("decision", title, **kw)

    def merge(self, title: Any = None, **kw: Any) -> Node:
        return self._add("merge", title, **kw)

    def start(self, **kw: Any) -> Node:
        return self._add("initial", None, **kw)

    def end(self, **kw: Any) -> Node:
        return self._add("final", None, **kw)

    def flow_end(self, **kw: Any) -> Node:
        return self._add("flow_final", None, **kw)

    def send(self, title: Any, **kw: Any) -> Node:
        return self._add("signal_send", title, **kw)

    def receive(self, title: Any, **kw: Any) -> Node:
        return self._add("signal_receive", title, **kw)

    def object(self, title: Any, **kw: Any) -> Node:
        return self._add("object", title, **kw)

    @contextmanager
    def sequence(self) -> Iterator[None]:
        """Nodes (and parallel blocks) created inside are connected in creation order."""
        units: list[tuple[Node, Node]] = []
        self._collect.append(units)
        try:
            yield
        finally:
            self._collect.pop()
            _chain_units(units)
            if units and self._collect:
                self._collect[-1].append((units[0][0], units[-1][1]))

    @contextmanager
    def parallel(self) -> Iterator[_Parallel]:
        p = _Parallel(self)
        p.fork = self._bar("fork")
        hold = self._collect
        self._collect = []  # branches collect their own units
        try:
            yield p
        finally:
            self._collect = hold
            p.join = self._bar("join")
            for units in p._branches:
                p.fork >> units[0][0]
                units[-1][1] >> p.join
            if self._collect:
                self._collect[-1].append((p.fork, p.join))

    @contextmanager
    def _lane_cm(self, g: Group) -> Iterator[Group]:
        d = self._d
        with self._scope():
            d._open.append(g)
            try:
                yield g
            finally:
                d._open.pop()

    def lane(self, title: str, **kw: Any):
        """Swimlane: ``with act.lane("Customer"):`` puts the nodes created inside into that lane.
        Re-entering a lane reuses it; calling it without ``with`` just declares it."""
        d = self._d
        container = self._group
        for g in d.groups:
            if g.style == "lane" and g.label == title and (
                    container is None and not any(g.id in o.children for o in d.groups)
                    or container is not None and g.id in container.children):
                return self._lane_cm(g)
        if container is None:
            d.layout = dict(d.layout or {}, lanes=True)
        else:
            container.lanes = True
        kw.setdefault("style", "lane")
        with self._scope(), d.group(title, **kw) as g:
            pass
        return self._lane_cm(g)


class _StateScope(_StateVerbs):
    def __init__(self, d: Diagram, group: Group, direction: str) -> None:
        self._bind(d, group, direction)


class _FlowScope(_FlowVerbs):
    def __init__(self, d: Diagram, group: Group, direction: str) -> None:
        self._bind(d, group, direction)


class _ActivityScope(_ActivityVerbs):
    def __init__(self, d: Diagram, group: Group, direction: str) -> None:
        self._bind(d, group, direction)
        self._collect = []


_SCOPES = {"flowchart": _FlowScope, "state_machine": _StateScope, "activity": _ActivityScope}


@contextmanager
def region(d: Diagram, kind: str, title: Any, id: str | None, direction: str, **kw: Any) -> Iterator[Any]:
    """A typed region inside ``d``: a group laid out by the layered engine, with the builder's verbs."""
    kw.setdefault("style", "behavior")
    with d.group(title, id=id, engine="layered", direction=direction, region=kind, **kw) as g:
        yield _SCOPES[kind](d, g, direction)


def _layout(direction: str) -> dict[str, str]:
    return {"engine": "layered", "direction": direction}


class Flowchart(Diagram, _FlowVerbs):
    """A flowchart: ``start``, ``process``, ``decision`` (``.yes()`` / ``.no()``), ``io``, ``document``, ``end``."""

    def __init__(self, id: str, title: str, *, direction: str = "down", **kw: Any) -> None:
        kw.setdefault("layout", _layout(direction))
        super().__init__(id, title, **kw)
        self._bind(self, None, direction)


class StateMachine(Diagram, _StateVerbs):
    """A state machine: ``state``, ``initial``, ``final`` and transitions with ``s.on(event, target)``."""

    def __init__(self, id: str, title: str, *, direction: str = "down", **kw: Any) -> None:
        kw.setdefault("layout", _layout(direction))
        super().__init__(id, title, **kw)
        self._bind(self, None, direction)


class Activity(Diagram, _ActivityVerbs):
    """An activity diagram (actions, decisions, forks and joins, swimlanes)."""

    def __init__(self, id: str, title: str, *, direction: str = "down", **kw: Any) -> None:
        kw.setdefault("layout", _layout(direction))
        super().__init__(id, title, **kw)
        self._bind(self, None, direction)
        self._collect = []


__all__ = ["Activity", "Flowchart", "StateMachine"]

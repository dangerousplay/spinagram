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
        if g is None or (d._open and d._open[-1] is g):
            yield
            return
        d._open.append(g)
        try:
            yield
        finally:
            d._open.pop()

    def _add(self, kind: str, title: Any = None, **kw: Any) -> Node:
        with self._scope():
            return self._d.add(kind, title, **kw)

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

    @property
    def initial(self) -> Node:
        return self._once("initial", "initial")

    @property
    def final(self) -> Node:
        return self._once("final", "final")


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


class Activity(Diagram, _FlowVerbs):
    """An activity diagram (actions, decisions, forks and joins, swimlanes)."""

    def __init__(self, id: str, title: str, *, direction: str = "down", **kw: Any) -> None:
        kw.setdefault("layout", _layout(direction))
        super().__init__(id, title, **kw)
        self._bind(self, None, direction)


__all__ = ["Activity", "Flowchart", "StateMachine"]

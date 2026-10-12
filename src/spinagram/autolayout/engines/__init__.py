"""Layout engine protocol and registry.

An engine turns an :class:`~spinagram.autolayout.graph.LGraph` into absolute boxes (and optional edge
routes). Third-party engines register through the ``spinagram.layouts`` entry-point group.
"""
from __future__ import annotations

from importlib import import_module
from importlib.metadata import entry_points
from typing import Protocol

from ..graph import LGraph, LResult

_BUILTIN = {
    "flex": "spinagram.autolayout.engines.flex:FlexEngine",
    "layered": "spinagram.autolayout.engines.layered:LayeredEngine",
    "dot": "spinagram.autolayout.engines.dot:DotEngine",
    "elk": "spinagram.autolayout.engines.elk:ElkEngine",
    "d2": "spinagram.autolayout.engines.d2:D2Engine",
}


class EngineUnavailable(RuntimeError):
    """The engine's runtime (binary, package) is missing; the message says how to install it."""


class Engine(Protocol):
    name: str

    def available(self) -> str | None:
        """None when ready; otherwise a one-line install hint."""
        ...

    def run(self, graph: LGraph) -> LResult:
        ...


def available() -> dict[str, str]:
    found = dict(_BUILTIN)
    for ep in entry_points(group="spinagram.layouts"):
        found.setdefault(ep.name, ep.value)
    return found


def get_engine(name: str) -> Engine:
    reg = available()
    if name not in reg:
        raise KeyError(f"unknown layout engine {name!r}; available: {', '.join(sorted(reg))}")
    mod, _, attr = reg[name].partition(":")
    eng = getattr(import_module(mod), attr)()
    hint = eng.available()
    if hint:
        raise EngineUnavailable(f"layout engine {name!r} unavailable: {hint}")
    return eng

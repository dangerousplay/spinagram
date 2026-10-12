"""Layered layout engine (spec: .specs/features/layered-layout/spec.md)."""
from __future__ import annotations

from spinagram.autolayout import build_graph
from spinagram.model import Diagram
from spinagram.theme import Theme


def _theme() -> Theme:
    return Theme.load(None)


# T1: layout graph -------------------------------------------------------------------------------
def test_self_edges_go_to_loops_not_edges():  # LAY-09 input
    d = Diagram("x", "t", layout={"engine": "layered"})
    a, b = d.box("a"), d.box("b")
    a >> b
    d.edge(b, b, "retry")
    g, _ = build_graph(d, _theme())
    assert [(e.src, e.dst) for e in g.edges] == [("a", "b")]
    assert [(e.id, e.src, e.dst) for e in g.loops] == [("e1", "b", "b")]


def test_group_hints_carry_lanes_engine_direction():  # LAY-16 input, regions
    d = Diagram("x", "t", layout={"engine": "flex"})
    with d.group("Flow", id="flow", engine="layered", direction="down", lanes=True):
        d.box("a")
    g, _ = build_graph(d, _theme())
    grp = g.root.children[0]
    assert grp.hints["engine"] == "layered"
    assert grp.hints["direction"] == "down"
    assert grp.hints["lanes"] is True

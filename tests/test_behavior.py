"""Behavior diagrams: symbols, builders, regions (spec: .specs/features/behavior-diagrams/spec.md)."""
from __future__ import annotations

import pytest

from spinagram import shapes

KINDS = ["terminator", "process", "decision", "io", "document", "predefined", "data", "connector", "initial",
         "final", "flow_final", "fork", "join", "merge", "choice", "history", "deep_history", "state", "action",
         "object", "signal_send", "signal_receive"]  # BHV-01 (note keeps its existing renderer)
PSEUDO = ["initial", "final", "flow_final", "fork", "join", "choice", "history"]


def _coords(d: str):
    nums = [float(t) for t in d.replace(",", " ").split() if t not in "MLCZ" and t.strip()]
    return list(zip(nums[0::2], nums[1::2]))


# T1: geometry library ---------------------------------------------------------------------------
@pytest.mark.parametrize("kind", KINDS)
def test_every_kind_has_geometry_inside_its_box(kind):  # BHV-01, BHV-02
    x, y, w, h = 100.0, 50.0, 200.0, 120.0
    parts = shapes.parts(kind, x, y, w, h)
    assert parts and all(p.paint in ("shape", "solid", "stroke") for p in parts)
    for p in parts:
        for px, py in _coords(p.d):
            assert x - 0.5 <= px <= x + w + 0.5 and y - 0.5 <= py <= y + h + 0.5, (kind, px, py)
    tx, ty, tw, th = shapes.text_box(kind, x, y, w, h)
    assert x - 0.5 <= tx and y - 0.5 <= ty and tx + tw <= x + w + 0.5 and ty + th <= y + h + 0.5
    assert kind in shapes.KINDS


def test_symbol_paints():  # BHV-02 (shape table)
    assert [p.paint for p in shapes.parts("initial", 0, 0, 24, 24)] == ["solid"]
    assert [p.paint for p in shapes.parts("final", 0, 0, 32, 32)] == ["stroke", "solid"]
    assert [p.paint for p in shapes.parts("fork", 0, 0, 140, 8)] == ["solid"]
    assert [p.paint for p in shapes.parts("flow_final", 0, 0, 28, 28)] == ["shape", "stroke"]


@pytest.mark.parametrize("kind", PSEUDO)
def test_pseudostates_have_fixed_sizes(kind):  # BHV-05
    assert shapes.fixed_size(kind) is not None


def test_fixed_size_values():  # BHV-02 sizes from the shape table
    assert shapes.fixed_size("initial") == (24, 24)
    assert shapes.fixed_size("final") == (32, 32)
    assert shapes.fixed_size("fork") == (140, 8)
    assert shapes.fixed_size("fork", vertical=True) == (8, 140)
    assert shapes.fixed_size("state") is None


@pytest.mark.parametrize("kind", KINDS)
def test_every_kind_has_a_pptx_plan(kind):  # BHV-03 plan
    plan = shapes.pptx_plan(kind)
    assert plan in ("freeform", "group") or plan.isupper()


def test_path_parser_round_trip():
    subs = shapes.parse("M 0 0 L 10 0 C 10 5 5 10 0 10 Z M 1 1 L 2 2")
    assert subs[0].closed and not subs[1].closed
    assert subs[0].start == (0, 0)
    assert subs[0].segments[1] == ("C", [(10, 5), (5, 10), (0, 10)])

"""Shared text scale in rows and columns (TSC-01, TSC-02, TSC-04).

Sizes at the default theme (title 24 px, body 18 px) in 300 × 120 cards, fitted alone:
"Interoperabilityxxxx" shrinks to 21 px; a card whose 16-word body overflows shrinks both blocks 2 px (22/16).
"""
from __future__ import annotations

import pytest

from spinagram import Diagram, Theme, build_scene
from spinagram.backends.svg import to_svg

THEME = Theme.load("default")
LONG = "Interoperabilityxxxx"
BODY = "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen"


def _diagram(cards, axis="row", **kw):
    d = Diagram("R", "Row")
    pos = {"row": {"x": 100, "y": 300}, "column": {"x": 100, "y": 200}}[axis]
    with getattr(d, axis)(gap=20, **pos, **kw):
        for i, (title, body) in enumerate(cards):
            d.box(title, text=body, id=f"n{i}", w=300, h=120)
    return d


def _sizes(d):
    sc = build_scene(d, THEME)
    return [[b.font.size for b in sc.shapes()[f"n{i}"].label.blocks] for i in range(len(d.nodes))]


FIVE = [("Alpha", None), ("Beta", None), (LONG, None), ("Gamma", None), ("Delta", None)]
BODIES = [("Alpha", BODY), ("Beta", "x"), ("Gamma", "y")]

SCENARIOS = [  # (id, cards, axis, container kwargs, expected [title, body?] size per card)
    ("one-long-title-flag-on", FIVE, "row", {"same_text_scale": True}, [[21]] * 5),
    ("one-long-title-flag-off", FIVE, "row", {"same_text_scale": False}, [[24], [24], [21], [24], [24]]),
    ("default-off", FIVE, "row", {}, [[24], [24], [21], [24], [24]]),
    ("same-size-turns-it-on", FIVE, "row", {"same_size": True}, [[21]] * 5),
    ("same-size-opt-out", FIVE, "row", {"same_size": True, "same_text_scale": False},
     [[24], [24], [21], [24], [24]]),
    ("per-role-minimum", BODIES, "row", {"same_text_scale": True}, [[22, 16]] * 3),
    ("per-role-flag-off", BODIES, "row", {}, [[22, 16], [24, 18], [24, 18]]),
    ("column", FIVE[:3], "column", {"same_text_scale": True}, [[21]] * 3),
    ("all-equal", FIVE[:2], "row", {"same_text_scale": True}, [[24], [24]]),
]


@pytest.mark.parametrize("cards,axis,kw,want", [s[1:] for s in SCENARIOS], ids=[s[0] for s in SCENARIOS])
def test_member_sizes(cards, axis, kw, want):
    assert _sizes(_diagram(cards, axis, **kw)) == want


def test_long_title_alone_size_is_the_row_size():
    """The expected 21 px is the long card's own fitted size when it stands alone (TSC-02)."""
    assert _sizes(_diagram([(LONG, None)])) == [[21]]


def test_spec_is_not_mutated():
    d = _diagram(FIVE, same_text_scale=True)
    build_scene(d, THEME)
    assert [(n.title_size, n.body_size) for n in d.nodes] == [(None, None)] * 5


EQUAL_ROWS = [  # (id, cards) rows whose members already share their sizes (TSC-04)
    ("short-titles", FIVE[:2] + FIVE[3:]),
    ("titles-and-bodies", [("Alpha", "x"), ("Beta", "y")]),
    ("all-shrunk-alike", [(LONG, None), (LONG, None)]),
]


@pytest.mark.parametrize("cards", [r[1] for r in EQUAL_ROWS], ids=[r[0] for r in EQUAL_ROWS])
def test_flag_leaves_equal_rows_byte_identical(cards):
    on = to_svg(build_scene(_diagram(cards, same_text_scale=True), THEME))
    off = to_svg(build_scene(_diagram(cards, same_text_scale=False), THEME))
    assert on == off


# TSC-03: text-scale-mismatch ----------------------------------------------------------------------------------------
from spinagram.qa import Issue, check  # noqa: E402


def _sized(axis="row", **kw):
    """Cards with short text (no shrinking) at explicit sizes: ``sizes`` = [(title_size, body_size), ...]."""
    sizes = kw.pop("sizes")
    d = Diagram("R", "Row")
    pos = {"row": {"x": 100, "y": 300}, "column": {"x": 100, "y": 200}}[axis]
    with getattr(d, axis)(gap=20, **pos, **kw):
        for i, (ts, bs) in enumerate(sizes):
            d.box("Ok", text="x" if bs else None, id=f"n{i}", w=300, h=120, title_size=ts, body_size=bs)
    return d


MISMATCH = [  # (id, axis, container kwargs, (title, body) sizes, expected (item, detail) issues)
    ("title-1.09-no", "row", {}, [(24, None), (22, None)], []),                     # 24 / 22 = 1.091
    ("title-1.10-no", "row", {}, [(22, None), (20, None)], []),                     # 22 / 20 = 1.100, not above
    ("title-1.11-yes", "row", {}, [(20, None), (18, None), (20, None)],             # 20 / 18 = 1.111
     [("row0", "title sizes differ: [18, 20] px; use same_text_scale")]),
    ("body-1.06-no", "row", {}, [(24, 18), (24, 17)], []),                          # 18 / 17 = 1.059
    ("body-1.125-yes", "row", {}, [(24, 18), (24, 16)],                             # 18 / 16 = 1.125
     [("row0", "body sizes differ: [16, 18] px; use same_text_scale")]),
    ("both-roles", "row", {}, [(24, 18), (20, 16)],
     [("row0", "title sizes differ: [20, 24] px; use same_text_scale"),
      ("row0", "body sizes differ: [16, 18] px; use same_text_scale")]),
    ("three-sizes", "row", {}, [(24, None), (21, None), (18, None)],
     [("row0", "title sizes differ: [18, 21, 24] px; use same_text_scale")]),
    ("column", "column", {}, [(24, None), (20, None)],
     [("column0", "title sizes differ: [20, 24] px; use same_text_scale")]),
    ("flag-on", "row", {"same_text_scale": True}, [(24, None), (20, None)], []),
    ("same-size-on", "row", {"same_size": True}, [(24, None), (20, None)], []),
]


@pytest.mark.parametrize("axis,kw,sizes,want", [m[1:] for m in MISMATCH], ids=[m[0] for m in MISMATCH])
def test_text_scale_mismatch(axis, kw, sizes, want):
    issues = [i for i in check(build_scene(_sized(axis, sizes=sizes, **kw), THEME)) if i.kind == "text-scale-mismatch"]
    assert [(i.item, i.detail) for i in issues] == want
    assert all(i.severity == "P2" for i in issues)


def test_text_scale_mismatch_severity():
    assert Issue("R", "row0", "text-scale-mismatch", "x").severity == "P2"


def test_scene_records_final_text_sizes():
    sc = build_scene(_diagram([(LONG, None), ("Alpha", BODY)]), THEME)
    assert sc.text_sizes == {"n0": (21, None), "n1": (22, 16)}


def test_flagged_rows_are_listed():
    d = Diagram("R", "Row")
    with d.row(x=100, y=100, gap=20, same_text_scale=True):
        d.box("A", w=200, h=100)
    with d.row(x=100, y=400, gap=20):
        d.box("B", w=200, h=100)
    with d.column(x=1000, y=100, gap=20, same_size=True):
        d.box("C", w=200, h=100)
    assert build_scene(d, THEME).text_scale_rows == {"row0", "column2"}

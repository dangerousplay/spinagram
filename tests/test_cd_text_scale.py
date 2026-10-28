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

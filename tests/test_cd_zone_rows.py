"""Rows and columns inside zones: the DSL (BND-04, BND-05)."""
import pytest

from spinagram import Diagram
from spinagram.model import Container

ITEMS = ["ca-cert", {"title": "cert", "id": "crt"}, "key"]


def _zone_row(axis, **kw):
    d = Diagram("R", "Rows")
    with d.zone("Secrets", id="sm", band=(330, 500)):
        out = getattr(d, axis)(ITEMS, **kw)
    return d, out


CALL_SHAPES = [  # (id, axis, kwargs, expected container fields (axis, x, y, gap, zone, align, cols, same_text_scale))
    ("row-in-zone", "row", {}, ("row", None, None, 20, "sm", None, None, None)),
    ("column-in-zone", "column", {}, ("column", None, None, 20, "sm", None, None, None)),
    ("row-in-zone-opts", "row", {"gap": 16, "align": "start", "cols": 4, "same_text_scale": True},
     ("row", None, None, 16, "sm", "start", 4, True)),
    ("row-in-zone-wh", "row", {"w": 200, "h": 90}, ("row", None, None, 20, "sm", None, None, None)),
    ("row-in-zone-xy", "row", {"x": 100, "y": 400}, ("row", 100, 400, 20, None, None, None, None)),
]


@pytest.mark.parametrize("axis,kw,expected", [s[1:] for s in CALL_SHAPES], ids=[s[0] for s in CALL_SHAPES])
def test_items_in_zone_make_a_container(axis, kw, expected):
    d, nodes = _zone_row(axis, **kw)
    c = d.containers[0]
    assert (c.axis, c.x, c.y, c.gap, c.zone, c.align, c.cols, c.same_text_scale) == expected
    assert [n.id for n in nodes] == ["ca-cert", "crt", "key"]                       # the nodes are returned
    assert c.children == ["ca-cert", "crt", "key"]                                  # and are the members
    assert d.zones[0].children == ["ca-cert", "crt", "key"]                         # and children of the zone
    wh = (kw.get("w", 0), kw.get("h", 0))
    assert [(n.w, n.h) for n in nodes] == [wh] * 3                                  # w/h given: each node's size


def test_items_with_styles_and_common_fields():
    d = Diagram("R", "Rows")
    with d.zone("Secrets", id="sm"):
        nodes = d.row(["a", "b"], styles=["dark", None], align="center", icon="lock")
    assert [n.style for n in nodes] == ["dark", None]
    assert [n.icon for n in nodes] == ["lock", "lock"]
    assert d.containers[0].align == "center"


def test_with_block_in_zone_records_the_zone():
    d = Diagram("R", "Rows")
    with d.zone("Secrets", id="sm"), d.row(gap=12, cols=3) as c:
        d.box("A", id="a")
    assert (c.x, c.y, c.zone, c.cols, c.children) == (None, None, "sm", 3, ["a"])


def test_nested_zones_use_the_innermost():
    d = Diagram("R", "Rows")
    with d.zone("VPC", id="vpc"), d.zone("SG", id="sg"):
        d.row(["a"])
    assert d.containers[0].zone == "sg"


def test_absolute_items_path_unchanged():  # the 0.4 form: no container, nodes at x + i * (w + gap)
    d = Diagram("R", "Rows")
    nodes = d.row(["a", "b", "c"], x=100, y=200, w=200, h=90)
    assert d.containers == []
    assert [(n.x, n.y, n.w, n.h) for n in nodes] == [(100, 200, 200, 90), (360, 200, 200, 90), (620, 200, 200, 90)]
    nodes = d.column(["d", "e"], x=100, y=400, w=200, h=90, gap=10)
    assert [(n.x, n.y, n.w, n.h) for n in nodes] == [(100, 400, 200, 90), (100, 500, 200, 90)]


def test_absolute_items_without_size_make_a_container():
    d = Diagram("R", "Rows")
    nodes = d.row(["a", "b"], x=100, y=200)
    c = d.containers[0]
    assert (c.x, c.y, c.zone, c.children) == (100, 200, None, ["a", "b"])
    assert [n.id for n in nodes] == ["a", "b"]


ERRORS = [  # (id, axis, kwargs, in zone, exception, message)
    ("row-no-xy", "row", {}, False, TypeError, "R: row outside a zone needs x and y (missing: x, y)"),
    ("row-no-y", "row", {"x": 10}, False, TypeError, "R: row outside a zone needs x and y (missing: y)"),
    ("column-no-x", "column", {"y": 10}, False, TypeError, "R: column outside a zone needs x and y (missing: x)"),
    ("items-no-xy", "row", {"items": ["a"], "w": 100, "h": 50}, False, TypeError,
     "R: row outside a zone needs x and y (missing: x, y)"),
    ("partial-in-zone", "row", {"x": 10}, True, TypeError, "R: row in zone 'sm' takes both x and y or neither (missing: y)"),
    ("bad-align", "row", {"align": "middle"}, True, ValueError, "R: row align 'middle'; use center, start or end"),
    ("bad-cols", "row", {"cols": 0}, True, ValueError, "R: row cols 0; use 1 or more"),
    ("cols-outside-zone", "row", {"x": 10, "y": 10, "cols": 2}, False, ValueError,
     "R: row cols and align need a zone (call it inside `with d.zone(...)`)"),
]


@pytest.mark.parametrize("axis,kw,in_zone,exc,msg", [s[1:] for s in ERRORS], ids=[s[0] for s in ERRORS])
def test_errors(axis, kw, in_zone, exc, msg):
    d = Diagram("R", "Rows")
    with pytest.raises(exc) as err:
        if in_zone:
            with d.zone("Secrets", id="sm"):
                getattr(d, axis)(**kw)
        else:
            getattr(d, axis)(**kw)
    assert str(err.value) == msg
    assert d.containers == []                                       # nothing half-built


def test_container_new_fields_default():
    c = Container("row", 0, 0)
    assert (c.zone, c.align, c.cols, c.same_text_scale) == (None, None, None, None)

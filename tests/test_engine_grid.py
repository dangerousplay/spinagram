"""Grid, alignment, straight edges and anchor helpers (layout-engine GRD-01..05)."""
import pytest

from spinagram import Diagram, Theme, build_scene
from spinagram.scene import Shape

THEME = Theme.load("default")
COLS, ROWS = [80, 280, 900, 1600], [175, 772]

CELLS = [
    # id, (c, r), gutter, expected (x, y, w, h); last column/row have no size
    ("first", (0, 0), 20, (80, 175, 180, 577)),
    ("inner", (2, 1), 0, (900, 772, 700, None)),
    ("last-col", (3, 0), 20, (1600, 175, None, 577)),
]


@pytest.mark.parametrize("cell,gutter,expected", [c[1:] for c in CELLS], ids=[c[0] for c in CELLS])
def test_grid_cells(cell, gutter, expected):  # GRD-01
    d = Diagram("G", "Grid")
    g = d.grid(cols=COLS, rows=ROWS, gutter=gutter)
    c = g[cell]
    assert (c.x, c.y, c.w, c.h) == expected and tuple(c) == expected[:2]


@pytest.mark.parametrize("what", ["node", "zone"])
@pytest.mark.parametrize("size", [None, (120, 60)], ids=["cell-size", "own-size"])
def test_cell_places_nodes_and_zones(what, size):  # GRD-01
    d = Diagram("G", "Grid")
    g = d.grid(cols=COLS, rows=ROWS, gutter=20)
    kw = {"w": size[0], "h": size[1]} if size else {}
    obj = d.box("N", id="n", cell=g[1, 0], **kw) if what == "node" else d.zone("Z", cell=g[1, 0], **kw)
    assert (obj.x, obj.y) == (280, 175)
    assert (obj.w, obj.h) == (size or (600, 577))


def test_cell_from_yaml():  # GRD-01 YAML parity
    from spinagram.yaml_io import from_dict
    d = from_dict({"id": "G", "title": "G", "grid": {"cols": COLS, "rows": ROWS, "gutter": 20},
                   "zones": [{"label": "Z", "cell": [0, 0]}],
                   "nodes": [{"id": "n", "title": "N", "cell": [2, 0], "h": 90}]})
    assert (d.zones[0].x, d.zones[0].y, d.zones[0].w) == (80, 175, 180)
    assert (d.nodes[0].x, d.nodes[0].y, d.nodes[0].w, d.nodes[0].h) == (900, 175, 680, 90)


@pytest.mark.parametrize("bad", [(9, 0), (0, 5)], ids=["col", "row"])
def test_cell_outside_grid_raises(bad):
    d = Diagram("G", "Grid")
    g = d.grid(cols=COLS, rows=ROWS)
    with pytest.raises(IndexError, match="outside 4 columns x 2 rows"):
        g[bad]


def test_cell_without_grid_raises():
    with pytest.raises(ValueError, match="needs a grid"):
        Diagram("G", "Grid").box("N", cell=(0, 0))


# alignment helpers (GRD-02) -----------------------------------------------------------------------------------
def _shapes(d):
    return {i.id: i for i in build_scene(d, THEME).items if isinstance(i, Shape)}


ALIGN = [
    ("align_x", lambda d, a, b, c: d.align_x(a, b, c), lambda s: {s[k].x + s[k].w / 2 for k in "abc"}),
    ("align_y", lambda d, a, b, c: d.align_y(a, b, c), lambda s: {s[k].y + s[k].h / 2 for k in "abc"}),
    ("center_on", lambda d, a, b, c: d.center_on(b, a), lambda s: {(s[k].x + s[k].w / 2, s[k].y + s[k].h / 2)
                                                                  for k in "ab"}),
    ("center_on_x", lambda d, a, b, c: d.center_on(b, a, axis="x"), lambda s: {s[k].x + s[k].w / 2 for k in "ab"}),
]


@pytest.mark.parametrize("apply,measure", [a[1:] for a in ALIGN], ids=[a[0] for a in ALIGN])
@pytest.mark.parametrize("sized", [True, False], ids=["sized", "content-sized"])
def test_alignment_helpers(apply, measure, sized):
    d = Diagram("G", "Grid")
    kw = (lambda w, h: {"w": w, "h": h}) if sized else (lambda w, h: {})
    a = d.box("Alpha", id="a", x=300, y=200, **kw(300, 120))
    b = d.box("Bravo with a longer title", id="b", x=900, y=500, **kw(200, 80))
    c = d.box("C", id="c", x=600, y=800, **kw(120, 60))
    apply(d, a, b, c)
    assert len(measure(_shapes(d))) == 1


def test_alignment_from_yaml():
    from spinagram.yaml_io import from_dict
    d = from_dict({"id": "G", "title": "G",
                   "nodes": [{"id": "a", "title": "A", "x": 300, "y": 200, "w": 300, "h": 120},
                             {"id": "b", "title": "B", "x": 900, "y": 500, "w": 200, "h": 80}],
                   "align": [{"x": ["a", "b"]}]})
    s = _shapes(d)
    assert s["a"].x + 150 == s["b"].x + 100


# straight edges (GRD-03, GRD-04) ------------------------------------------------------------------------------
from spinagram.qa import check  # noqa: E402
from spinagram.scene import Connector  # noqa: E402

STRAIGHT = [
    # id, a rect, b rect, expected points
    ("down", (100, 100, 300, 80), (250, 400, 200, 80), [(325, 180), (325, 400)]),
    ("up", (250, 400, 200, 80), (100, 100, 300, 80), [(325, 400), (325, 180)]),
    ("right", (100, 100, 200, 100), (600, 150, 200, 100), [(300, 175), (600, 175)]),
    ("left", (600, 150, 200, 100), (100, 100, 200, 100), [(600, 175), (300, 175)]),
    ("narrow-overlap", (100, 100, 200, 80), (290, 400, 200, 80), [(295, 180), (295, 400)]),
]


@pytest.mark.parametrize("ra,rb,points", [s[1:] for s in STRAIGHT], ids=[s[0] for s in STRAIGHT])
def test_straight_edge_is_axis_aligned(ra, rb, points):  # GRD-03
    d = Diagram("G", "Grid")
    a = d.box("A", id="a", x=ra[0], y=ra[1], w=ra[2], h=ra[3])
    b = d.box("B", id="b", x=rb[0], y=rb[1], w=rb[2], h=rb[3])
    d.edge(a, b, straight=True)
    sc = build_scene(d, THEME)
    c = next(i for i in sc.items if isinstance(i, Connector))
    assert [tuple(p) for p in c.points] == [pytest.approx(p) for p in points]
    assert [i for i in check(sc) if i.kind == "not-straight"] == []


def test_no_shared_span_reports_not_straight():  # GRD-04
    d = Diagram("G", "Grid")
    a = d.box("A", id="a", x=100, y=100, w=200, h=80)
    b = d.box("B", id="b", x=600, y=500, w=200, h=80)
    d.edge(a, b, straight=True)
    got = [i for i in check(build_scene(d, THEME)) if i.kind == "not-straight"]
    assert [(i.item, i.severity) for i in got] == [("e0", "P2")]


# anchor helpers (GRD-05) --------------------------------------------------------------------------------------
@pytest.mark.parametrize("method,frac,ref,point", [
    ("at_left", 0.35, "n.left@0.35", (100, 135)),
    ("at_right", 0.5, "n.right", (300, 150)),
    ("at_top", 0.25, "n.top@0.25", (150, 100)),
    ("at_bottom", 0.9, "n.bottom@0.9", (280, 200)),
], ids=["left", "right-mid", "top", "bottom"])
def test_anchor_methods(method, frac, ref, point):
    d = Diagram("G", "Grid")
    n = d.box("N", id="n", x=100, y=100, w=200, h=100)
    assert getattr(n, method)(frac) == ref
    d.edge(getattr(n, method)(frac), (900, 900))
    c = next(i for i in build_scene(d, THEME).items if isinstance(i, Connector))
    assert tuple(c.points[0]) == pytest.approx(point)


def test_anchor_properties_unchanged():
    n = Diagram("G", "Grid").box("N", id="n", x=0, y=0, w=10, h=10)
    assert (n.left, n.right, n.top, n.bottom, n.center) == ("n.left", "n.right", "n.top", "n.bottom", "n.center")

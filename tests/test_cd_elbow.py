"""Elbow edges and route validation (HLP-04, HLP-05)."""
from __future__ import annotations

import pytest

from spinagram import Diagram, Theme, build_scene
from spinagram.scene import Connector
from spinagram.yaml_io import dump, from_dict

THEME = Theme.load("default")
# a: (100, 100, 200, 100) → top (200, 100), bottom (200, 200), left (100, 150), right (300, 150), centre (200, 150)
# b: (500, 400, 200, 100) → top (600, 400), bottom (600, 500), left (500, 450), right (700, 450), centre (600, 450)
ELBOWS = [  # (id, src, dst, mid, expected points)
    ("bottom-top", "a.bottom", "b.top", None, [(200, 200), (200, 300), (600, 300), (600, 400)]),
    ("bottom-top-mid", "a.bottom", "b.top", 250, [(200, 200), (200, 250), (600, 250), (600, 400)]),
    ("top-bottom", "b.top", "a.bottom", None, [(600, 400), (600, 300), (200, 300), (200, 200)]),
    ("top-bottom-mid", "b.top", "a.bottom", 380, [(600, 400), (600, 380), (200, 380), (200, 200)]),
    ("right-left", "a.right", "b.left", None, [(300, 150), (400, 150), (400, 450), (500, 450)]),
    ("right-left-mid", "a.right", "b.left", 350, [(300, 150), (350, 150), (350, 450), (500, 450)]),
    ("left-right", "b.left", "a.right", None, [(500, 450), (400, 450), (400, 150), (300, 150)]),
    ("bottom-left", "a.bottom", "b.left", None, [(200, 200), (200, 325), (500, 325), (500, 450)]),  # mid (200+450)/2
    ("right-top", "a.right", "b.top", None, [(300, 150), (450, 150), (450, 400), (600, 400)]),      # mid (300+600)/2
    ("fraction", "a.bottom@0.25", "b.top@0.75", None, [(150, 200), (150, 300), (650, 300), (650, 400)]),
    ("auto-sides", "a", "b", None, [(200, 200), (200, 300), (600, 300), (600, 400)]),  # a faces b from its bottom
    ("point-wide", (100, 700), (900, 800), None, [(100, 700), (500, 700), (500, 800), (900, 800)]),  # |dx| > |dy|
    ("point-tall", (100, 700), (200, 1000), None, [(100, 700), (100, 850), (200, 850), (200, 1000)]),
    ("point-mid", (100, 700), (900, 800), 300, [(100, 700), (300, 700), (300, 800), (900, 800)]),
    ("aligned", "a.bottom", (200, 400), None, [(200, 200), (200, 400)]),       # no bend: duplicate points dropped
]


def _d(src, dst, **kw):
    d = Diagram("E", "Elbow")
    d.box("A", id="a", x=100, y=100, w=200, h=100)
    d.box("B", id="b", x=500, y=400, w=200, h=100)
    d.edge(src, dst, **kw)
    return d


def _conn(sc):
    return next(i for i in sc.items if isinstance(i, Connector))


@pytest.mark.parametrize("src,dst,mid,points", [e[1:] for e in ELBOWS], ids=[e[0] for e in ELBOWS])
def test_elbow_points(src, dst, mid, points):
    c = _conn(build_scene(_d(src, dst, route="elbow", mid=mid), THEME))
    assert [tuple(round(v, 3) for v in p) for p in c.points] == points
    assert c.route == "poly"


def test_elbow_unit():
    from spinagram.engine.endpoints import elbow
    from spinagram.scene import Binding

    assert elbow((0, 0), Binding("a", "right", 0.5), (100, 50), None) == [(0, 0), (50, 0), (50, 50), (100, 50)]
    assert elbow((0, 0), Binding("a", "top", 0.5), (100, -50), -10) == [(0, 0), (0, -10), (100, -10), (100, -50)]


def test_via_and_curve_win_over_elbow():
    via = _conn(build_scene(_d("a.bottom", "b.top", route="elbow", via=[(200, 350)]), THEME))
    assert via.points == [(200, 200), (200, 350), (600, 400)]
    curve = _conn(build_scene(_d("a.bottom", "b.top", route="elbow", curve=(400, 300)), THEME))
    assert curve.route == "curve"


def test_theme_ortho_default_leaves_elbows_alone(tmp_path):
    (tmp_path / "theme.yaml").write_text("extends: default\ndefaults:\n  edge: {route: ortho}\n")
    c = _conn(build_scene(_d("a.bottom", "b.top", route="elbow"), Theme.load(tmp_path)))
    assert c.points == [(200, 200), (200, 300), (600, 300), (600, 400)]


@pytest.mark.parametrize("route", [None, "ortho", "elbow"], ids=["none", "ortho", "elbow"])
def test_valid_routes(route):
    assert _d("a", "b", route=route).edges[0].route == route


@pytest.mark.parametrize("route", ["poly", "straight", "curve", "Elbow", ""])
def test_invalid_route(route):
    with pytest.raises(ValueError) as err:
        _d("a", "b", route=route)
    assert str(err.value) == f"E: edge route {route!r}; use ortho, elbow or none"


def test_invalid_route_in_edge_string():
    d = Diagram("E", "Elbow")
    with pytest.raises(ValueError, match=r"E: edge route 'zigzag'; use ortho, elbow or none"):
        d.edge("a -> b", route="zigzag")


YAML = [  # (id, YAML edge extras, DSL kwargs)
    ("elbow", {"route": "elbow"}, {"route": "elbow"}),
    ("elbow-mid", {"route": "elbow", "mid": 250}, {"route": "elbow", "mid": 250}),
]


@pytest.mark.parametrize("extra,kw", [y[1:] for y in YAML], ids=[y[0] for y in YAML])
def test_yaml_parity(extra, kw):
    y = from_dict({"id": "E", "title": "Elbow",
                   "nodes": [{"id": "a", "title": "A", "at": [100, 100, 200, 100]},
                             {"id": "b", "title": "B", "at": [500, 400, 200, 100]}],
                   "edges": [{"from": "a.bottom", "to": "b.top", **extra}]})
    d = _d("a.bottom", "b.top", **kw)
    assert y.edges == d.edges
    assert _conn(build_scene(y, THEME)).points == _conn(build_scene(d, THEME)).points
    assert from_dict(dump(y)).edges == y.edges


def test_yaml_invalid_route():
    with pytest.raises(ValueError, match=r"E: edge route 'poly'; use ortho, elbow or none"):
        from_dict({"id": "E", "title": "Elbow", "nodes": [{"id": "a", "title": "A"}, {"id": "b", "title": "B"}],
                   "edges": [{"from": "a", "to": "b", "route": "poly"}]})

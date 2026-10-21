"""Routing: crossing penalty, ortho routes, crossings check, bundles (layout-engine EDG-13..21)."""
import pytest

from spinagram.autolayout.route import route


def _crosses(p, q, a, b):
    """Strict crossing of an axis-aligned segment p→q with a perpendicular one a→b."""
    if p[0] == q[0] and a[1] == b[1]:
        return min(a[0], b[0]) < p[0] < max(a[0], b[0]) and min(p[1], q[1]) < a[1] < max(p[1], q[1])
    if p[1] == q[1] and a[0] == b[0]:
        return min(p[0], q[0]) < a[0] < max(p[0], q[0]) and min(a[1], b[1]) < p[1] < max(a[1], b[1])
    return False


WALL = ((500, 400), (500, 600))     # an edge already routed: vertical, between the two boxes
SRC, DST = (100, 475, 100, 50), (800, 475, 100, 50)


def _n_cross(pts):
    return sum(_crosses(p, q, *WALL) for p, q in zip(pts, pts[1:]))


@pytest.mark.parametrize("cost,crosses", [(120, 1), (2000, 0)], ids=["cheap-crossing", "costly-crossing"])
def test_crossing_penalty_trades_against_detours(cost, crosses):  # EDG-18
    pts = route(SRC, DST, [SRC, DST], penalty=lambda a, b: cost * _crosses(a, b, *WALL),
                guides=[(500 - 14, 400 - 14), (500 + 14, 600 + 14)])
    assert _n_cross(pts) == crosses
    assert _on_outline(pts[0], SRC) and _on_outline(pts[-1], DST)


def _on_outline(p, b):
    x, y, w, h = b
    return (p[0] in (x, x + w) and y <= p[1] <= y + h) or (p[1] in (y, y + h) and x <= p[0] <= x + w)


def test_without_penalty_routes_are_unchanged():  # default stays identical (layered goldens)
    assert route(SRC, DST, [SRC, DST]) == route(SRC, DST, [SRC, DST], penalty=None, guides=[])


# ortho routing pass (EDG-17, EDG-19, EDG-21) -------------------------------------------------------------------
from spinagram import Diagram, Theme, build_scene  # noqa: E402
from spinagram.engine.route import crossings  # noqa: E402
from spinagram.qa import segment_hits  # noqa: E402
from spinagram.scene import Connector, Shape  # noqa: E402

THEME = Theme.load("default")


def _conns(sc):
    return [i for i in sc.items if isinstance(i, Connector)]


def _axis_aligned(pts):
    return all(p[0] == q[0] or p[1] == q[1] for p, q in zip(pts, pts[1:]))


def _blocker(d, **kw):
    a = d.box("A", id="a", x=200, y=400, w=200, h=100)
    d.box("C", id="c", x=600, y=380, w=200, h=140)
    b = d.box("B", id="b", x=1000, y=400, w=200, h=100)
    return d.edge(a, b, **kw)


@pytest.mark.parametrize("source", ["edge", "theme"])
def test_ortho_routes_around_boxes(tmp_path, source):  # EDG-17
    th = THEME
    d = Diagram("R", "Route")
    if source == "edge":
        _blocker(d, route="ortho")
    else:
        (tmp_path / "theme.yaml").write_text("extends: default\ndefaults: {edge: {route: ortho}}\n")
        th = Theme.load(tmp_path)
        _blocker(d)
    sc = build_scene(d, th)
    c = _conns(sc)[0]
    c_box = next(s for s in sc.items if isinstance(s, Shape) and s.id == "c")
    assert c.route == "poly" and _axis_aligned(c.points)
    assert not any(segment_hits(p, q, (c_box.x, c_box.y, c_box.w, c_box.h)) for p, q in zip(c.points, c.points[1:]))


def test_straight_default_still_crosses_the_box():  # control: without ortho nothing changes
    d = Diagram("R", "Route")
    _blocker(d)
    c = _conns(build_scene(d, THEME))[0]
    assert c.route == "straight" and len(c.points) == 2


@pytest.mark.parametrize("kw", [{"via": [(700, 300)]}, {"curve": (700, 250)}], ids=["via", "curve"])
def test_explicit_route_is_kept(kw):  # EDG-21
    d = Diagram("R", "Route")
    _blocker(d, route="ortho", **kw)
    c = _conns(build_scene(d, THEME))[0]
    assert c.route in ("poly", "curve") and len(c.points) == 3 and tuple(c.points[1]) == tuple(
        kw.get("via", [kw.get("curve")])[0])


def test_explicit_side_is_kept():
    d = Diagram("R", "Route")
    d.box("A", id="a", x=200, y=400, w=200, h=100)
    d.box("B", id="b", x=1000, y=400, w=200, h=100)
    d.edge("a.bottom", "b", route="ortho")
    c = _conns(build_scene(d, THEME))[0]
    assert c.points[0] == (300, 500) and c.points[1][0] == 300 and c.points[1][1] > 500 and c.src.side == "bottom"


def _two_pools_two_sites(route=None):
    """Roadmap E4: two pools × two sites — the straight fan-out crosses itself."""
    d = Diagram("R", "Route")
    p1 = d.box("pool-1", id="p1", x=200, y=300, w=200, h=90)
    p2 = d.box("pool-2", id="p2", x=200, y=600, w=200, h=90)
    s1 = d.box("site-a", id="s1", x=900, y=300, w=200, h=90)
    s2 = d.box("site-b", id="s2", x=900, y=600, w=200, h=90)
    for a, b in ((p1, s1), (p1, s2), (p2, s1), (p2, s2)):
        d.edge(a, b, route=route)
    return d


def test_ortho_does_not_add_crossings():  # EDG-18 on a real fan-out
    straight = crossings(_conns(build_scene(_two_pools_two_sites(), THEME)))
    ortho = crossings(_conns(build_scene(_two_pools_two_sites("ortho"), THEME)))
    assert (straight, ortho) == (1, 0)


DETERMINISM = """
import hashlib, json, sys
sys.path.insert(0, {tests!r})
from test_engine_route import _two_pools_two_sites, _conns, THEME
from spinagram import build_scene
pts = [c.points for c in _conns(build_scene(_two_pools_two_sites("ortho"), THEME))]
print(hashlib.sha256(json.dumps(pts).encode()).hexdigest())
"""


def test_ortho_routes_identical_across_hash_seeds():  # EDG-19
    import os
    import subprocess
    import sys
    from pathlib import Path
    code = DETERMINISM.format(tests=str(Path(__file__).parent))
    out = {subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                          env={**os.environ, "PYTHONHASHSEED": str(s)}).stdout.strip() for s in range(4)}
    assert len(out) == 1


# edge-crossings diagnostic (EDG-20) ----------------------------------------------------------------------------
from spinagram.qa import check  # noqa: E402


def _lines(d, n_h, n_v):
    for k in range(n_h):
        d.edge((300, 300 + 100 * k), (900, 300 + 100 * k))
    for k in range(n_v):
        d.edge((450 + 200 * k, 200), (450 + 200 * k, 700))


@pytest.mark.parametrize("n_h,n_v,n", [(1, 0, 0), (1, 1, 1), (2, 2, 4)], ids=["0", "1", "4"])
def test_edge_crossings_reported_with_count(n_h, n_v, n):
    d = Diagram("R", "Route")
    _lines(d, n_h, n_v)
    got = [i for i in check(build_scene(d, THEME)) if i.kind == "edge-crossings"]
    if n:
        assert len(got) == 1 and got[0].detail.startswith(f"{n} crossing(s)") and got[0].severity == "P2"
    else:
        assert got == []


# bundles (EDG-13..16) -----------------------------------------------------------------------------------------
def _sources_left(d, n):
    return [d.box(f"S{k}", id=f"s{k}", x=200, y=250 + 150 * k, w=200, h=80) for k in range(n)]


def _sources_top(d, n):
    return [d.box(f"S{k}", id=f"s{k}", x=200 + 300 * k, y=200, w=200, h=80) for k in range(n)]


TRUNKS = [
    # id, source layout, target rect, trunk, expected trunk coordinate (x for left/right, y for top/bottom)
    ("right", _sources_left, (1000, 400, 240, 100), "right", (400 + 1000) / 2),
    ("auto-right", _sources_left, (1000, 400, 240, 100), None, (400 + 1000) / 2),
    ("bottom", _sources_top, (500, 700, 240, 100), "bottom", (280 + 700) / 2),
]


BUNDLE_SCENARIOS = [pytest.param(n, *x[1:], how, id=f"{how}-{x[0]}-{n}sources")
                    for how in ("bundle", "fan_in") for x in TRUNKS for n in (2, 3)
                    if how == "bundle" or x[3] is None]   # fan_in picks the trunk side itself


@pytest.mark.parametrize("n,layout,target,trunk,t,how", BUNDLE_SCENARIOS)
def test_bundle_shares_one_trunk_and_one_arrowhead(n, layout, target, trunk, t, how):  # EDG-13, 14, 15
    d = Diagram("R", "Route")
    srcs = layout(d, n)
    x, y, w, h = target
    tgt = d.box("obs", id="obs", x=x, y=y, w=w, h=h)
    es = [d.edge(s, tgt, fan_in=how == "fan_in") for s in srcs]
    if how == "bundle":
        d.bundle(es, trunk=trunk)
    cs = _conns(build_scene(d, THEME))
    vertical = layout is _sources_left
    for c in cs:
        assert _axis_aligned(c.points)
        on_trunk = [p for p in c.points if (p[0] if vertical else p[1]) == pytest.approx(t)]
        assert len(on_trunk) >= 2                                            # every edge runs along the trunk
    assert [c.arrow_end for c in cs] == [False] * (n - 1) + [True]             # one arrowhead
    end = cs[-1].points[-1]
    assert end == pytest.approx((x, y + h / 2) if vertical else (x + w / 2, y))  # at the target's facing side
    junction = cs[-1].points[-2]
    assert all(c.points[-1] == junction for c in cs[:-1])                     # the others stop at the junction


def test_bundle_with_two_targets_raises():  # EDG-16
    d = Diagram("R", "Route")
    a, b, c = (d.box(t, id=t, x=100 + 300 * k, y=300, w=200, h=80) for k, t in enumerate("abc"))
    e1, e2 = d.edge(a, b), d.edge(a, c)
    with pytest.raises(ValueError, match="share one target"):
        d.bundle([e1, e2])


def test_bundle_from_yaml():  # EDG-13 YAML parity
    from spinagram.yaml_io import from_dict
    d = from_dict({"id": "R", "title": "R",
                   "nodes": [{"id": "s0", "title": "S0", "x": 200, "y": 250, "w": 200, "h": 80},
                             {"id": "s1", "title": "S1", "x": 200, "y": 400, "w": 200, "h": 80},
                             {"id": "obs", "title": "O", "x": 1000, "y": 400, "w": 240, "h": 100}],
                   "edges": ["s0 -> obs", "s1 -> obs"], "bundles": [{"edges": [0, 1], "trunk": "right"}]})
    cs = _conns(build_scene(d, THEME))
    assert [c.arrow_end for c in cs] == [False, True] and all(any(p[0] == 700 for p in c.points) for c in cs)

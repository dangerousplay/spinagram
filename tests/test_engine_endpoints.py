"""Edge endpoints: node anchors, zone targets, bus fans (layout-engine EDG-07..12)."""
import pytest

from spinagram import Diagram, build_scene, Theme
from spinagram.scene import Connector

THEME = Theme.load("default")

# box "b" at (400, 400, 200, 100); the other end is an absolute point
ANCHOR_SCENARIOS = [
    # id, b endpoint, other point, expected point on b, expected binding (side, frac) or None
    ("auto-right", "b", (900, 450), (600, 450), ("right", 0.5)),
    ("auto-left", "b", (100, 450), (400, 450), ("left", 0.5)),
    ("auto-top", "b", (500, 100), (500, 400), ("top", 0.5)),
    ("auto-bottom", "b", (500, 900), (500, 500), ("bottom", 0.5)),
    ("side", "b.top", (900, 900), (500, 400), ("top", 0.5)),
    ("side-frac", "b.left@0.25", (0, 0), (400, 425), ("left", 0.25)),
    ("center-unbound", "b.center", (0, 0), (500, 450), None),
    ("absolute", (123, 456), (0, 0), (123, 456), None),
]


def _edge_scene(src, dst):
    d = Diagram("EP", "Endpoints")
    d.box("B", id="b", x=400, y=400, w=200, h=100)
    d.edge(src, dst)
    return [i for i in build_scene(d, THEME).items if isinstance(i, Connector)][0]


@pytest.mark.parametrize("ref,other,point,binding", [s[1:] for s in ANCHOR_SCENARIOS],
                         ids=[s[0] for s in ANCHOR_SCENARIOS])
def test_node_anchor_resolution(ref, other, point, binding):
    c = _edge_scene(ref, other)
    assert c.points[0] == pytest.approx(point)
    got = (c.src.side, c.src.frac) if c.src else None
    assert got == binding


def test_unknown_node_raises():
    with pytest.raises(KeyError, match="unknown node 'nope'"):
        _edge_scene("nope", (0, 0))


# zone endpoints (EDG-07, EDG-08, EDG-12) ----------------------------------------------------------------------
# zone "net" at (400, 400, 400, 300): centre (600, 550); points stay 24 px from corners
ZONE_SCENARIOS = [
    # id, source point, zone ref, expected end point, expected side
    ("left", (100, 550), "zone:net", (400, 550), "left"),
    ("right", (1100, 450), "zone:net", (800, 450), "right"),
    ("above", (600, 100), "zone:net", (600, 400), "top"),
    ("below", (600, 1000), "zone:net", (600, 700), "bottom"),
    ("top-left-corner-clamped", (100, 100), "zone:net", (424, 400), "top"),
    ("bottom-right-corner-clamped", (1100, 1000), "zone:net", (776, 700), "bottom"),
    ("left-clamped-low", (100, 690), "zone:net", (400, 676), "left"),
    ("inside-inner-face", (450, 600), "zone:net", (400, 600), "left"),
    ("explicit-side-frac", (0, 0), "zone:net.top@0.25", (500, 400), "top"),
]


def _zone_edge(src, dst, **kw):
    d = Diagram("EP", "Endpoints")
    z = d.zone("Net", id="net", x=400, y=400, w=400, h=300)
    d.edge(src, z if dst == "ZONE" else dst, **kw)
    return [i for i in build_scene(d, THEME).items if isinstance(i, Connector)][0]


@pytest.mark.parametrize("src,ref,point,side", [s[1:] for s in ZONE_SCENARIOS], ids=[s[0] for s in ZONE_SCENARIOS])
def test_zone_endpoint_side_and_point(src, ref, point, side):
    c = _zone_edge(src, ref)
    assert c.points[-1] == pytest.approx(point)
    assert (c.dst.shape_id, c.dst.side) == ("z0", side)


def test_zone_object_and_node_source():
    d = Diagram("EP", "Endpoints")
    z = d.zone("Net", id="net", x=400, y=400, w=400, h=300)
    pool = d.box("Pool", id="pool", x=1000, y=500, w=200, h=100)
    d.edge(pool, z)
    c = [i for i in build_scene(d, THEME).items if isinstance(i, Connector)][0]
    assert c.points == [pytest.approx((1000, 550)), pytest.approx((800, 550))]
    assert (c.src.shape_id, c.src.side, c.dst.shape_id, c.dst.side) == ("pool", "left", "z0", "right")


def test_zone_endpoint_from_yaml():
    from spinagram.yaml_io import from_dict
    d = from_dict({"id": "EP", "title": "E", "zones": [{"id": "net", "x": 400, "y": 400, "w": 400, "h": 300}],
                   "edges": ["zone:net.left -> zone:net.right"]})
    c = [i for i in build_scene(d, THEME).items if isinstance(i, Connector)][0]
    assert c.points == [pytest.approx((400, 550)), pytest.approx((800, 550))]


def test_unknown_zone_raises():
    with pytest.raises(KeyError, match="unknown zone 'nope'"):
        _zone_edge((0, 0), "zone:nope")


@pytest.mark.parametrize("text,expected", [
    ("pool -> zone:net", ("pool", "zone:net", None)),
    ("pool -> zone:net.top@0.3: HTTPS", ("pool", "zone:net.top@0.3", "HTTPS")),
    ("zone:a.right -> b: x", ("zone:a.right", "b", "x")),
], ids=["zone-target", "zone-target-label", "zone-source"])
def test_edge_shorthand_with_zone_refs(text, expected):
    from spinagram.model import parse_edge
    e = parse_edge(text)
    assert (e.src, e.dst, e.label) == expected

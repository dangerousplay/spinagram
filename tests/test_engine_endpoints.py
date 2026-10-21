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

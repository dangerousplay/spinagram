"""Zone anchors (ZAN-01..03): ``z.top``, ``z.at_left(0.3)`` … return ``zone:<id>.<side>[@frac]``."""
import pytest

from spinagram import Diagram, Theme, build_scene
from spinagram.model import Zone
from spinagram.scene import Connector

THEME = Theme.load("default")
ZX, ZY, ZW, ZH = 400, 400, 600, 300  # zone under test
SOURCE = {"top": (600, 120), "bottom": (600, 840), "left": (100, 500), "right": (1200, 500)}  # box (x, y), 200 x 100


def _zone(zid="sg"):
    d = Diagram("Z", "Zone anchors")
    return d, d.zone("Security group", id=zid, x=ZX, y=ZY, w=ZW, h=ZH)


REFS = [  # (id, call, expected ref)
    ("top", lambda z: z.top, "zone:sg.top"),
    ("bottom", lambda z: z.bottom, "zone:sg.bottom"),
    ("left", lambda z: z.left, "zone:sg.left"),
    ("right", lambda z: z.right, "zone:sg.right"),
    ("at-top-0.8", lambda z: z.at_top(0.8), "zone:sg.top@0.8"),
    ("at-bottom-0.25", lambda z: z.at_bottom(0.25), "zone:sg.bottom@0.25"),
    ("at-left-0.3", lambda z: z.at_left(0.3), "zone:sg.left@0.3"),
    ("at-right-0.65", lambda z: z.at_right(0.65), "zone:sg.right@0.65"),
    ("at-right-default", lambda z: z.at_right(), "zone:sg.right"),
    ("at-top-half", lambda z: z.at("top", 0.5), "zone:sg.top"),
    ("at-left-0", lambda z: z.at("left", 0), "zone:sg.left@0"),
]


@pytest.mark.parametrize("call,expected", [r[1:] for r in REFS], ids=[r[0] for r in REFS])
def test_zone_anchor_refs(call, expected):
    _, z = _zone()
    assert call(z) == expected


def test_builder_assigned_id():
    d = Diagram("Z", "Zone anchors")
    d.zone("A", x=0, y=0, w=10, h=10)
    assert d.zone("B", x=0, y=0, w=10, h=10).at_top(0.3) == "zone:z1.top@0.3"


def test_zone_without_id_raises():
    with pytest.raises(ValueError) as err:
        Zone(x=0, y=0, w=10, h=10, label="Loose").top
    assert str(err.value) == "zone 'Loose' has no id; create it with d.zone(...) or give it id="


@pytest.mark.parametrize("side", ["center", "middle", "Top"])
def test_unknown_side_raises(side):
    _, z = _zone()
    with pytest.raises(ValueError) as err:
        z.at(side)
    assert str(err.value) == f"unknown zone side {side!r}; use one of top, bottom, left, right"


TIPS = [  # (side, frac, expected tip (x, y)) — on the outline, by hand
    ("top", 0.5, (700, 400)), ("top", 0.8, (880, 400)), ("top", 0.2, (520, 400)),
    ("bottom", 0.5, (700, 700)), ("bottom", 0.1, (460, 700)),
    ("left", 0.5, (400, 550)), ("left", 0.3, (400, 490)), ("left", 0.1, (400, 430)),
    ("right", 0.5, (1000, 550)), ("right", 0.65, (1000, 595)),
]


@pytest.mark.parametrize("route", [None, "ortho"])
@pytest.mark.parametrize("side,frac,tip", TIPS, ids=[f"{s}-{f:g}" for s, f, _ in TIPS])
def test_arrow_tip_on_the_outline(side, frac, tip, route):
    d, z = _zone()
    sx, sy = SOURCE[side]
    d.box("Client", id="c", x=sx, y=sy, w=200, h=100)
    d.edge("c", z.at(side, frac), **({"route": route} if route else {}))
    sc = build_scene(d, THEME)
    c = next(i for i in sc.items if isinstance(i, Connector))
    tx, ty = c.points[-1]
    assert (tx, ty) == pytest.approx(tip, abs=0.5)                       # at that fraction on the outline
    hx, hy, hw, hh = sc.zone_headers["z0"]
    assert not (hx < tx < hx + hw and hy < ty < hy + hh)                 # not inside the header
    assert (c.dst.shape_id, c.dst.side, c.dst.target) == ("z0", side, "zone")

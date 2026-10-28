"""Router and zone headers (HDR-01, HDR-08): headers are obstacles for ortho edges."""
import pytest

from spinagram import Diagram, Theme, build_scene
from spinagram.qa import check
from spinagram.scene import Connector, Shape

THEME = Theme.load("default")
PHASES = ["FASE 1 · CADA NÓ · CLOUD-INIT · USER-DATA", "FASE 2 · CADA NÓ · CLOUD-INIT · CONSUL",
          "FASE 3 · PÓS-APPLY · MANUAL · ACL BOOTSTRAP"]
ZY = [170, 440, 710]          # zone r: x 80, y ZY[r], 1760 x 250
CARD_X = [120, 560, 1000, 1440]  # 320 x 120 cards, top 52.8 below the zone top (header bottom 40.8 + gap 12)


def a04(route=None, header=None):
    """The roadmap's A04 before the hand fix: 3 stacked phase zones, 4 steps per row left to right, chained;
    the row-to-row edges drop from the last step's bottom to the first step's top (centred anchors)."""
    d = Diagram("A04", "Consul bootstrap")
    steps = []
    for r, (zy, label) in enumerate(zip(ZY, PHASES)):
        with d.zone(label, x=80, y=zy, w=1760, h=250, header=header):
            for k, x in enumerate(CARD_X):
                steps.append(d.box(f"Step {4 * r + k + 1}", id=f"s{4 * r + k}", x=x, y=zy + 52.8, w=320, h=120))
    kw = {"route": route} if route else {}
    for i in range(len(steps) - 1):
        a, b = steps[i].id, steps[i + 1].id
        if i % 4 == 3:  # row to row: bottom centre → top centre
            d.edge(f"{a}.bottom", f"{b}.top", **kw)
        else:
            d.edge(a, b, **kw)
    return d


def _kinds(sc, kind):
    return [(i.item, i.detail) for i in check(sc) if i.kind == kind]


HEADER_ROUTE_SCENARIOS = [  # (id, header, route, expected header crossings)
    ("straight-left", None, None, [("e3", "crosses the header of zone 'z1'"), ("e7", "crosses the header of zone 'z2'")]),
    ("straight-right", "right", None, []),
    ("straight-none", "none", None, []),
    ("ortho-left", None, "ortho", []),
    ("ortho-right", "right", "ortho", []),
    ("ortho-none", "none", "ortho", []),
]


@pytest.mark.parametrize("header,route,expected", [s[1:] for s in HEADER_ROUTE_SCENARIOS],
                         ids=[s[0] for s in HEADER_ROUTE_SCENARIOS])
def test_a04_header_crossings(header, route, expected):
    sc = build_scene(a04(route, header), THEME)
    # the straight drop s3 → s4 runs from (1600, 342.8) to (280, 492.8): it is inside z1's header band
    # (y 440 → 480.8) for x 385.6 → 744.6, so a left header wider than 305.6 px is crossed (same for s7 → s8)
    for r in range(3):
        if header is None:
            hx, _, hw, _ = sc.zone_headers[f"z{r}"]
            assert hx == 80 and hx + hw > 386
        elif header == "right":
            hx, _, hw, _ = sc.zone_headers[f"z{r}"]
            assert 1360 < hx and hx + hw == 1840
    assert _kinds(sc, "edge-crosses-zone-header") == expected
    if route == "ortho":
        assert _kinds(sc, "edge-through-box") == []
        conns = {c.id: c for c in sc.items if isinstance(c, Connector)}
        for eid, (a, b) in (("e3", ("s3", "s4")), ("e7", ("s7", "s8"))):  # explicit sides are kept
            c = conns[eid]
            assert (c.src.shape_id, c.src.side, c.dst.shape_id, c.dst.side) == (a, "bottom", b, "top")


@pytest.mark.parametrize("ref,side", [("zone:z0", "top"), ("zone:z0.top", "top")], ids=["auto", "top"])
def test_ortho_into_zone_target_reaches_border(ref, side):
    d = Diagram("Z", "Zone target")
    with d.zone("Availability zone site-a", x=100, y=400, w=600, h=300):
        d.box("In", id="b", x=150, y=520, w=200, h=100)
    d.box("A", id="a", x=150, y=150, w=200, h=100)
    d.edge("a", ref, route="ortho")
    sc = build_scene(d, THEME)
    c = next(i for i in sc.items if isinstance(i, Connector))
    z = next(i for i in sc.items if isinstance(i, Shape) and i.id == "z0")
    end = c.points[-1]
    on = {"top": end[1] == pytest.approx(z.y) and z.x <= end[0] <= z.x + z.w,
          "left": end[0] == pytest.approx(z.x) and z.y <= end[1] <= z.y + z.h}
    assert on[side]                                                  # the arrow tip is on the zone outline
    assert (c.dst.shape_id, c.dst.target) == ("z0", "zone")
    assert _kinds(sc, "edge-crosses-zone-header") == [] and _kinds(sc, "edge-through-box") == []


# A card drawn under its zone's header (HDR-01): the header is still an obstacle. Zone "Availability zone site-a"
# at (100, 200, 600, 300): header x 100 → 354.4 (24 + 24 chars × 9.6), y 200 → 240.8. Target b = (150, 40, 160, 80)
# above the zone (centre y 80, right side x 310); route margin 14.
#   wide-under-header: a = (140, 220, 200, 80) lies wholly under the header band: its top exit at x 240 would cross
#     the header, so it leaves on the right (340, 260), climbs at 354.4 + 14 = 368.4 to y 80 and enters b's right.
#   straddling-header-end: a = (300, 210, 200, 80): its top centre x 400 is past the header end, so it goes up
#     to y 80 and left into b's right.
UNDER_HEADER_SCENARIOS = [  # (id, card a (x, y, w, h), expected points)
    ("wide-under-header", (140, 220, 200, 80), [(340, 260), (368.4, 260), (368.4, 80), (310, 80)]),
    ("straddling-header-end", (300, 210, 200, 80), [(400, 210), (400, 80), (310, 80)]),
]


@pytest.mark.parametrize("card,points", [s[1:] for s in UNDER_HEADER_SCENARIOS],
                         ids=[s[0] for s in UNDER_HEADER_SCENARIOS])
def test_ortho_from_a_card_under_its_zone_header(card, points):
    d = Diagram("Z", "Card under header")
    ax, ay, aw, ah = card
    with d.zone("Availability zone site-a", x=100, y=200, w=600, h=300):
        d.box("A", id="a", x=ax, y=ay, w=aw, h=ah)
    d.box("B", id="b", x=150, y=40, w=160, h=80)
    d.edge("a", "b", route="ortho")
    sc = build_scene(d, THEME)
    assert sc.zone_headers["z0"] == pytest.approx((100, 200, 254.4, 40.8))
    c = next(i for i in sc.items if isinstance(i, Connector))
    assert c.points == [pytest.approx(p) for p in points]
    assert _kinds(sc, "edge-crosses-zone-header") == [] and _kinds(sc, "edge-through-box") == []

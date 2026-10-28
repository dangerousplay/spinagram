"""YAML zone bands and zone rows (BND-08) and the A03-like parity fixture (BND-09)."""
from pathlib import Path

import pytest

from spinagram import Diagram, Theme, build_scene, load
from spinagram.scene import Shape
from spinagram.yaml_io import dump, from_dict

THEME = Theme.load("default")
FIXTURES = Path(__file__).parent / "fixtures" / "consul_diagrams"


def _rects(d):
    return {i.id: (i.x, i.y, i.w, i.h) for i in build_scene(d, THEME).items if isinstance(i, Shape)}


ITEMS = [{"id": f"c{k}", "title": f"C{k}", "w": 200, "h": 80} for k in range(3)]
PARITY = [  # (id, zone YAML extras, row YAML extras, DSL zone kwargs, DSL row kwargs)
    ("band", {"band": [330, 500]}, {}, {"band": (330, 500)}, {}),
    ("align-start", {"band": [330, 500]}, {"align": "start"}, {"band": (330, 500)}, {"align": "start"}),
    ("align-end", {"band": [330, 500]}, {"align": "end"}, {"band": (330, 500)}, {"align": "end"}),
    ("cols", {"band": [330, 500]}, {"cols": 4, "gap": 30}, {"band": (330, 500)}, {"cols": 4, "gap": 30}),
    ("same-text-scale", {"band": [330, 500]}, {"same_text_scale": True}, {"band": (330, 500)},
     {"same_text_scale": True}),
    ("hand-zone", {"x": 100, "y": 100, "w": 900, "h": 300}, {"align": "center"},
     {"x": 100, "y": 100, "w": 900, "h": 300}, {"align": "center"}),
]


@pytest.mark.parametrize("zone_yaml,row_yaml,zone_kw,row_kw", [p[1:] for p in PARITY], ids=[p[0] for p in PARITY])
@pytest.mark.parametrize("axis", ["row", "column"])
def test_yaml_parity(axis, zone_yaml, row_yaml, zone_kw, row_kw):
    y = from_dict({"id": "P", "title": "Parity", "zones": [{"id": "sm", "label": "Secrets", **zone_yaml}],
                   f"{axis}s": [{"zone": "sm", **row_yaml, "nodes": ITEMS}]})
    d = Diagram("P", "Parity")
    with d.zone("Secrets", id="sm", **zone_kw):
        getattr(d, axis)([dict(i) for i in ITEMS], **row_kw)
    assert y.zones[0].band == zone_kw.get("band")                     # band is a tuple, like the DSL's
    yc, dc = y.containers[0], d.containers[0]
    assert (yc.axis, yc.zone, yc.align, yc.cols, yc.same_text_scale, yc.gap, yc.children) == \
        (dc.axis, dc.zone, dc.align, dc.cols, dc.same_text_scale, dc.gap, dc.children)
    assert y.zones[0].children == d.zones[0].children == ["c0", "c1", "c2"]
    assert _rects(y) == _rects(d)


def test_row_with_node_ids_joins_the_zone():
    y = from_dict({"id": "P", "title": "Parity", "zones": [{"id": "sm", "label": "S", "band": [330, 500]}],
                   "nodes": [{"id": "a", "title": "A", "w": 200, "h": 80}], "rows": [{"zone": "sm", "nodes": ["a"]}]})
    assert y.containers[0].children == ["a"] and y.zones[0].children == ["a"]
    assert _rects(y)["a"] == pytest.approx((860, 389.4, 200, 80))     # 104 + (1712 - 200) / 2; centred


def test_row_zone_must_exist():
    with pytest.raises(ValueError) as err:
        from_dict({"id": "P", "title": "Parity", "rows": [{"zone": "nope", "nodes": []}]})
    assert str(err.value) == "P: row zone 'nope' is not a zone id"


def test_row_outside_a_zone_still_needs_xy():
    with pytest.raises(TypeError) as err:
        from_dict({"id": "P", "title": "Parity", "rows": [{"gap": 10, "nodes": []}]})
    assert str(err.value) == "P: row outside a zone needs x and y (missing: x, y)"


def test_unknown_row_key_still_rejected():
    with pytest.raises(ValueError, match=r"row has unknown keys \['colz'\]"):
        from_dict({"id": "P", "title": "Parity", "zones": [{"id": "sm", "band": [0, 100]}],
                   "rows": [{"zone": "sm", "colz": 3, "nodes": []}]})


def test_dump_round_trip():
    d = load(FIXTURES / "a03_bands.yaml")[0]
    back = from_dict(dump(d))
    assert [(z.id, z.band, z.children) for z in back.zones] == [(z.id, z.band, z.children) for z in d.zones]
    fields = lambda c: (c.axis, c.x, c.y, c.gap, c.same_size, c.zone, c.align, c.cols, c.same_text_scale,  # noqa: E731
                        c.children)
    assert [fields(c) for c in back.containers] == [fields(c) for c in d.containers]
    assert _rects(back) == _rects(d)


def test_dump_round_trip_hand_placed_container():
    d = Diagram("P", "Parity")
    with d.row(x=100, y=200, gap=12, same_size=True, max_width=900):
        d.box("A", id="a")
        d.box("B", id="b")
    back = from_dict(dump(d))
    c = back.containers[0]
    assert (c.x, c.y, c.gap, c.same_size, c.max_width, c.zone, c.children) == (100, 200, 12, True, 900, None, ["a", "b"])
    assert _rects(back) == _rects(d)


# The hand-placed twin, every number by hand. Zones: x 80, w 1760 (canvas 1920 - 2 * 80); content x 104 … 1816
# (1712 wide); header without icon → content top = zone y + 52.8; bottom = zone y + h - 24.
#   sm (330, 500): 4 same_size 300 x 80, gap 20 → block 1260, x 104 + 226 = 330; y 382.8 + (93.2 - 80) / 2 = 389.4
#   sg-servers (560, 760): cols 4 → w (1712 - 60) / 4 = 413; 3 cards: block 1279, x 104 + 216.5 = 320.5;
#     y 612.8 + (123.2 - 90) / 2 = 629.4
#   sg-clients (800, 1000): cols 2 → w (1712 - 20) / 2 = 846; x 104, 970; y 852.8 + 16.6 = 869.4
TWIN_ZONES = [("Secrets Manager · <ENV>/consul/*", 330), ("SG consul-servers", 560), ("SG consul-clients", 800)]
TWIN_CARDS = [
    ("ca-cert", 330, 389.4, 300, 80), ("cert", 650, 389.4, 300, 80), ("key", 970, 389.4, 300, 80),
    ("ca-key", 1290, 389.4, 300, 80),
    ("server-1", 320.5, 629.4, 413, 90), ("server-2", 753.5, 629.4, 413, 90), ("server-3", 1186.5, 629.4, 413, 90),
    ("client-a", 104, 869.4, 846, 90), ("client-b", 970, 869.4, 846, 90),
]


def _twin():
    d = Diagram("A03", "Consul certificates")
    for label, zy in TWIN_ZONES:
        d.zone(label, x=80, y=zy, w=1760, h=170 if zy == 330 else 200)
    for cid, x, y, w, h in TWIN_CARDS:
        d.box(cid, id=cid, x=x, y=y, w=w, h=h)
    return d


@pytest.mark.parametrize("item", [c[0] for c in TWIN_CARDS] + ["z0", "z1", "z2"])
def test_a03_parity_with_hand_placed_twin(item):
    got, want = _rects(load(FIXTURES / "a03_bands.yaml")[0]), _rects(_twin())
    assert got[item] == pytest.approx(want[item], abs=2)


def test_a03_fixture_has_no_hand_x():
    text = (FIXTURES / "a03_bands.yaml").read_text()
    assert " x:" not in text and "{x:" not in text

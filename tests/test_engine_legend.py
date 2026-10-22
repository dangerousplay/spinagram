"""Automatic legend (layout-engine LEG-01..05)."""
import pytest

from spinagram import Diagram, Theme, build_scene
from spinagram.engine.legend import collect

THEME = Theme.load("default")


def _diagram(edges=(), zones=()):
    d = Diagram("L", "Legend")
    a = d.box("A", id="a", x=200, y=300, w=200, h=90)
    b = d.box("B", id="b", x=800, y=300, w=200, h=90)
    for kw in edges:
        d.edge(a, b, **kw)
    for k, kw in enumerate(zones):
        d.zone(f"Z{k}", x=150 + 50 * k, y=250, w=900, h=200, **kw)
    return d


def _rows(d):
    return [(r.kind, r.label) for r in collect(d, build_scene(d, THEME))]


ROW_SCENARIOS = [
    ("one-meaning", [{"meaning": "replication", "dashed": True, "color": "gray"}], [], [("edge", "replication")]),
    ("same-style-twice", [{"meaning": "replication", "dashed": True}, {"meaning": "replication", "dashed": True}],
     [], [("edge", "replication")]),
    ("two-styles", [{"meaning": "replication", "dashed": True}, {"meaning": "traffic"}], [],
     [("edge", "replication"), ("edge", "traffic")]),
    ("no-meaning-no-row", [{"dashed": True}], [], []),
    ("zone-meanings", [], [{"meaning": "network", "dash": "dashed", "stroke": "primary"},
                           {"meaning": "availability zone", "dash": "dotted", "stroke": "primary"}],
     [("zone", "network"), ("zone", "availability zone")]),
    ("edges-then-zones", [{"meaning": "logs"}], [{"meaning": "network", "dash": "dashed", "stroke": "primary"}],
     [("edge", "logs"), ("zone", "network")]),
]


@pytest.mark.parametrize("edges,zones,rows", [s[1:] for s in ROW_SCENARIOS], ids=[s[0] for s in ROW_SCENARIOS])
def test_one_row_per_style_with_meaning(edges, zones, rows):  # LEG-01, LEG-02
    assert _rows(_diagram(edges, zones)) == rows


def test_removing_the_last_edge_removes_its_row():  # LEG-03 (roadmap acceptance)
    with_row = _diagram([{"meaning": "traffic"}, {"meaning": "replication", "dashed": True, "color": "gray"}])
    assert ("edge", "replication") in _rows(with_row)
    with_row.edges.pop()
    assert _rows(with_row) == [("edge", "traffic")]


def test_meaning_from_yaml():  # LEG-01 YAML parity
    from spinagram.yaml_io import from_dict
    d = from_dict({"id": "L", "title": "L",
                   "nodes": [{"id": "a", "title": "A", "x": 200, "y": 300, "w": 200, "h": 90},
                             {"id": "b", "title": "B", "x": 800, "y": 300, "w": 200, "h": 90}],
                   "zones": [{"label": "Z", "x": 150, "y": 250, "w": 900, "h": 200, "meaning": "network"}],
                   "edges": [{"from": "a", "to": "b", "meaning": "replication", "dashed": True}]})
    assert _rows(d) == [("edge", "replication"), ("zone", "network")]


# drawing and placement (LEG-04, LEG-05) -----------------------------------------------------------------------
from spinagram.scene import Connector, Shape  # noqa: E402

EDGES = [{"meaning": "replication", "dashed": True, "color": "gray"}, {"meaning": "traffic"}]
ZONES = [{"meaning": "network", "dash": "dashed", "stroke": "primary"},
         {"meaning": "availability zone", "dash": "dotted", "stroke": "primary"}]


def _legend_scene(place="band"):
    d = _diagram(EDGES, ZONES)
    d.add_legend(items="auto", place=place)
    sc = build_scene(d, THEME)
    return d, sc, {getattr(i, "id", None): i for i in sc.items}


@pytest.mark.parametrize("place", ["band", (1300, 200, 400, 400)], ids=["band", "cell"])
def test_rows_draw_their_style(place):  # LEG-04
    _, sc, by = _legend_scene(place)
    labels = [by[f"legend-{j}-label"].block.lines[0] for j in range(4)]
    assert labels == ["replication", "traffic", "network", "availability zone"]
    rep, tra = by["legend-0-sample"], by["legend-1-sample"]
    assert isinstance(rep, Connector) and rep.dashed and rep.color == by["e0"].color
    assert isinstance(tra, Connector) and not tra.dashed
    net, az = by["legend-2-swatch"], by["legend-3-swatch"]
    assert isinstance(net, Shape) and (net.dash, net.cap) == (by["z0"].dash, None)
    assert (az.dash, az.cap) == (by["z1"].dash, "round") and az.stroke == by["z1"].stroke
    assert (net.fill, az.fill) == (by["z0"].fill, by["z1"].fill) and net.fill is not None   # zone fill shown


def test_band_placement_uses_the_annotation_band():  # LEG-05 band
    _, sc, by = _legend_scene("band")
    card = by["legend"]
    assert card.x + card.w <= sc.width - 80 + 0.5 and card.x > sc.width / 2       # right band


@pytest.mark.parametrize("cell,scaled", [((1300, 200, 400, 400), False), ((1300, 200, 400, 150), True)],
                         ids=["roomy-cell", "tight-cell"])
def test_cell_placement_fits_the_cell(cell, scaled):  # LEG-05 cell (card fitted to it)
    d, sc, by = _legend_scene(cell)
    x, y, w, h = cell
    card = by["legend"]
    assert (card.x, card.y, card.w) == (x, y, w) and card.h <= h + 0.5
    size = by["legend-0-label"].block.font.size
    assert (size < 16) == scaled
    from spinagram.annotate import band
    assert band(d, THEME, 1760) is None                                           # no band reserved


def test_auto_legend_from_yaml():  # LEG-05 YAML parity
    from spinagram.yaml_io import from_dict
    d = from_dict({"id": "L", "title": "L",
                   "nodes": [{"id": "a", "title": "A", "x": 200, "y": 300, "w": 200, "h": 90},
                             {"id": "b", "title": "B", "x": 800, "y": 300, "w": 200, "h": 90}],
                   "edges": [{"from": "a", "to": "b", "meaning": "replication", "dashed": True}],
                   "annotations": {"legend": {"items": "auto", "place": [1300, 200, 400, 300]}}})
    by = {getattr(i, "id", None): i for i in build_scene(d, THEME).items}
    assert by["legend"].x == 1300 and by["legend-0-label"].block.lines == ["replication"]


def test_invalid_place_raises():
    with pytest.raises(ValueError, match="legend place"):
        _diagram().add_legend(items="auto", place="corner")

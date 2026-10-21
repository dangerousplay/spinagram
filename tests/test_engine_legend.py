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

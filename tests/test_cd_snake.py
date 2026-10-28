"""Snake model and DSL (SNK-01, SNK-08): one call creates the steps, the row zones and the chain of edges."""
import pytest

from spinagram import Diagram
from spinagram.model import Snake

INPUTS = [  # (id, steps, cols, zones, nodes, rows, zones made, turn edge indexes)
    ("5x2-no-zones", 5, 2, None, 5, 3, 0, [1, 3]),
    ("12x4-3-zones", 12, 4, ["P1", "P2", "P3"], 12, 3, 3, [3, 7]),
    ("3x5-one-row", 3, 5, None, 3, 1, 0, []),
    ("3x5-one-zone", 3, 5, ["Only"], 3, 1, 1, []),
    ("7x3-zone-dicts", 7, 3, [{"label": "A", "id": "pa"}, "B", {"label": "C", "color": "warning"}], 7, 3, 3, [2, 5]),
    ("1x1", 1, 1, None, 1, 1, 0, []),
    ("4x1-column", 4, 1, None, 4, 4, 0, [0, 1, 2]),
]


@pytest.mark.parametrize("n,cols,zones,n_nodes,rows,n_zones,turns", [i[1:] for i in INPUTS],
                         ids=[i[0] for i in INPUTS])
def test_snake_creates_nodes_zones_edges(n, cols, zones, n_nodes, rows, n_zones, turns):
    d = Diagram("S", "Snake")
    nodes = d.snake([f"Step {k + 1}" for k in range(n)], cols, y=200, h=120, zones=zones)
    assert [x.id for x in nodes] == [f"step-{k + 1}" for k in range(n)]           # one node per step, returned
    assert len(d.nodes) == n_nodes and len(d.zones) == n_zones
    assert [(e.src, e.dst) for e in d.edges] == [(f"step-{k + 1}", f"step-{k + 2}") for k in range(n - 1)]  # chain
    assert [k for k, e in enumerate(d.edges) if e.route == "ortho"] == turns      # turn edges r → r + 1: ortho
    s = d.snakes[0]
    assert (s.nodes, s.zones, s.cols, s.y, s.h) == ([x.id for x in nodes], [z.id for z in d.zones], cols, 200, 120)
    for r, z in enumerate(d.zones):                                               # each row's steps in its zone
        assert z.children == [f"step-{k + 1}" for k in range(r * cols, min(n, (r + 1) * cols))]


def test_zone_fields_from_dicts():
    d = Diagram("S", "Snake")
    d.snake(["a", "b", "c", "d"], 2, y=0, h=100, zones=[{"label": "A", "id": "pa", "header": "right"}, "B"])
    assert [(z.id, z.label, z.header, z.fit) for z in d.zones] == [("pa", "A", "right", None), ("z1", "B", None, None)]


def test_step_dicts_and_edge_kwargs():
    d = Diagram("S", "Snake")
    nodes = d.snake([{"title": "Init", "id": "init", "icon": "server"}, "Join", "ACL"], 2, y=0, h=100,
                    color="accent", label="next")
    assert [n.id for n in nodes] == ["init", "join", "acl"] and nodes[0].icon == "server"
    assert [(e.color, e.label, e.route) for e in d.edges] == [("accent", "next", None), ("accent", "next", "ortho")]


def test_defaults():
    d = Diagram("S", "Snake")
    d.snake(["a", "b"], 2, y=10, h=90)
    assert d.snakes == [Snake(nodes=["a", "b"], zones=[], cols=2, y=10, h=90, x=None, w=None, gap=40, row_gap=60,
                              mode="boustrophedon")]


def test_snake_is_not_auto_laid_out():
    d = Diagram("S", "Snake")
    d.snake(["a", "b"], 2, y=10, h=90)
    assert not d.auto


def test_snake_inside_a_zone_nests_its_zones():
    d = Diagram("S", "Snake")
    with d.zone("Account", id="acct"):
        d.snake(["a", "b", "c"], 2, y=10, h=90, zones=["R1", "R2"])
    assert d.zones[0].children == ["z1", "z2"]


ERRORS = [  # (id, args, kwargs, message)
    ("cols-0", (["a"], 0), {}, "S: snake cols 0; use 1 or more"),
    ("empty", ([], 3), {}, "S: snake needs at least one step"),
    ("mode", (["a"], 3), {"mode": "zigzag"}, "S: snake mode 'zigzag'; use boustrophedon or restart"),
    ("zones-few", (["a", "b", "c", "d", "e"], 2), {"zones": ["A", "B"]}, "S: snake has 3 rows but 2 zones; give 3"),
    ("zones-many", (["a", "b"], 2), {"zones": ["A", "B"]}, "S: snake has 1 row but 2 zones; give 1"),
]


@pytest.mark.parametrize("args,kw,msg", [e[1:] for e in ERRORS], ids=[e[0] for e in ERRORS])
def test_errors(args, kw, msg):
    d = Diagram("S", "Snake")
    with pytest.raises(ValueError) as err:
        d.snake(*args, y=0, h=100, **kw)
    assert str(err.value) == msg
    assert (d.nodes, d.zones, d.edges, d.snakes) == ([], [], [], [])               # nothing half-built


@pytest.mark.parametrize("mode", ["boustrophedon", "restart"])
def test_modes_accepted(mode):
    d = Diagram("S", "Snake")
    d.snake(["a", "b", "c"], 2, y=0, h=100, mode=mode)
    assert d.snakes[0].mode == mode

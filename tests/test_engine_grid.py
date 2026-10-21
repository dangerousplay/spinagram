"""Grid, alignment, straight edges and anchor helpers (layout-engine GRD-01..05)."""
import pytest

from spinagram import Diagram, Theme

THEME = Theme.load("default")
COLS, ROWS = [80, 280, 900, 1600], [175, 772]

CELLS = [
    # id, (c, r), gutter, expected (x, y, w, h); last column/row have no size
    ("first", (0, 0), 20, (80, 175, 180, 577)),
    ("inner", (2, 1), 0, (900, 772, 700, None)),
    ("last-col", (3, 0), 20, (1600, 175, None, 577)),
]


@pytest.mark.parametrize("cell,gutter,expected", [c[1:] for c in CELLS], ids=[c[0] for c in CELLS])
def test_grid_cells(cell, gutter, expected):  # GRD-01
    d = Diagram("G", "Grid")
    g = d.grid(cols=COLS, rows=ROWS, gutter=gutter)
    c = g[cell]
    assert (c.x, c.y, c.w, c.h) == expected and tuple(c) == expected[:2]


@pytest.mark.parametrize("what", ["node", "zone"])
@pytest.mark.parametrize("size", [None, (120, 60)], ids=["cell-size", "own-size"])
def test_cell_places_nodes_and_zones(what, size):  # GRD-01
    d = Diagram("G", "Grid")
    g = d.grid(cols=COLS, rows=ROWS, gutter=20)
    kw = {"w": size[0], "h": size[1]} if size else {}
    obj = d.box("N", id="n", cell=g[1, 0], **kw) if what == "node" else d.zone("Z", cell=g[1, 0], **kw)
    assert (obj.x, obj.y) == (280, 175)
    assert (obj.w, obj.h) == (size or (600, 577))


def test_cell_from_yaml():  # GRD-01 YAML parity
    from spinagram.yaml_io import from_dict
    d = from_dict({"id": "G", "title": "G", "grid": {"cols": COLS, "rows": ROWS, "gutter": 20},
                   "zones": [{"label": "Z", "cell": [0, 0]}],
                   "nodes": [{"id": "n", "title": "N", "cell": [2, 0], "h": 90}]})
    assert (d.zones[0].x, d.zones[0].y, d.zones[0].w) == (80, 175, 180)
    assert (d.nodes[0].x, d.nodes[0].y, d.nodes[0].w, d.nodes[0].h) == (900, 175, 680, 90)


@pytest.mark.parametrize("bad", [(9, 0), (0, 5)], ids=["col", "row"])
def test_cell_outside_grid_raises(bad):
    d = Diagram("G", "Grid")
    g = d.grid(cols=COLS, rows=ROWS)
    with pytest.raises(IndexError, match="outside 4 columns x 2 rows"):
        g[bad]


def test_cell_without_grid_raises():
    with pytest.raises(ValueError, match="needs a grid"):
        Diagram("G", "Grid").box("N", cell=(0, 0))

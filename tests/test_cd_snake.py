"""Snake model and DSL (SNK-01, SNK-08): one call creates the steps, the row zones and the chain of edges."""
import pytest

from spinagram import Diagram, Theme, build_scene
from spinagram.engine import model_passes
from spinagram.model import Snake
from spinagram.qa import check
from spinagram.scene import Connector, Shape
from spinagram.yaml_io import from_dict

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


# ---- T14: the snake layout pass (SNK-02, SNK-03, SNK-04, SNK-06) -------------------------------------------------
THEME = Theme.load("default")  # canvas 1920 x 1080, margin 80; zone label 16, no header icon
HEAD = 36 + 16 * 0.3 + 12      # zone top → content top: label header bottom (36 + 0.3 · 16) + gap 12 = 52.8


def _laid(n, cols, **kw):
    d = Diagram("S", "Snake")
    d.snake([f"Step {k + 1}" for k in range(n)], cols, **kw)
    return model_passes.apply(d, THEME)


def _rect(o):
    return tuple(round(v, 3) for v in (o.x, o.y, o.w, o.h))


LAYOUTS = [  # (id, steps, cols, kwargs, expected card (x, y, w, h) per step, expected zone rects)
    # no zones, defaults: row 80 … 1840 (1760), card (1760 - 40) / 2 = 860; rows 200, 380, 560 (120 + 60 apart)
    ("5x2-boustrophedon", 5, 2, {"y": 200, "h": 120},
     [(80, 200, 860, 120), (980, 200, 860, 120), (980, 380, 860, 120), (80, 380, 860, 120), (80, 560, 860, 120)],
     []),
    ("5x2-restart", 5, 2, {"y": 200, "h": 120, "mode": "restart"},
     [(80, 200, 860, 120), (980, 200, 860, 120), (80, 380, 860, 120), (980, 380, 860, 120), (80, 560, 860, 120)],
     []),
    # x/w/gap/row_gap given: card (1000 - 2 * 20) / 3 = 320; rows 50, 180
    ("4x3-xw", 4, 3, {"y": 50, "h": 100, "x": 100, "w": 1000, "gap": 20, "row_gap": 30},
     [(100, 50, 320, 100), (440, 50, 320, 100), (780, 50, 320, 100), (780, 180, 320, 100)], []),
    # fewer steps than cols: one left-aligned row, card (1760 - 4 * 40) / 5 = 320
    ("3x5-one-row", 3, 5, {"y": 300, "h": 90},
     [(80, 300, 320, 90), (440, 300, 320, 90), (800, 300, 320, 90)], []),
    # zones: zone 100 wide 1028; cards inset 24: (1028 - 48 - 2 * 40) / 3 = 300 at x 124, 464, 804.
    # zone 0 at y 100, cards at 100 + 52.8, zone h 52.8 + 100 + 24 = 176.8; next zone 100 + 176.8 + 60 = 336.8 …
    ("7x3-zones", 7, 3, {"y": 100, "h": 100, "x": 100, "w": 1028, "zones": ["A", "B", "C"]},
     [(124, 152.8, 300, 100), (464, 152.8, 300, 100), (804, 152.8, 300, 100),
      (804, 389.6, 300, 100), (464, 389.6, 300, 100), (124, 389.6, 300, 100), (124, 626.4, 300, 100)],
     [(100, 100, 1028, 176.8), (100, 336.8, 1028, 176.8), (100, 573.6, 1028, 176.8)]),
    # zone padding 40: cards (1028 - 80 - 80) / 3 = 289.333 at 140, 469.333, 798.667; zone h 52.8 + 100 + 40;
    # zone 1 at 192.8 + 60 = 252.8, its cards at 252.8 + 52.8 = 305.6
    ("4x3-zones-pad40-restart", 4, 3, {"y": 0, "h": 100, "x": 100, "w": 1028, "mode": "restart",
                                       "zones": [{"label": "A", "padding": 40}, {"label": "B", "padding": 40}]},
     [(140, 52.8, 289.333, 100), (469.333, 52.8, 289.333, 100), (798.667, 52.8, 289.333, 100),
      (140, 305.6, 289.333, 100)],
     [(100, 0, 1028, 192.8), (100, 252.8, 1028, 192.8)]),
]


@pytest.mark.parametrize("n,cols,kw,cards,zones", [t[1:] for t in LAYOUTS], ids=[t[0] for t in LAYOUTS])
def test_layout_by_hand(n, cols, kw, cards, zones):
    d = _laid(n, cols, **kw)
    assert [_rect(c) for c in d.nodes] == [tuple(round(v, 3) for v in r) for r in cards]
    assert [_rect(z) for z in d.zones] == [tuple(round(v, 3) for v in r) for r in zones]


def _expected(n, cols, mode, zoned, y=200, h=120, gap=40, row_gap=60):
    """Card rects by the SNK rules (default x/w: the margins), written out independently of the pass."""
    pad = 24 if zoned else 0
    cw = (1760 - 2 * pad - (cols - 1) * gap) / cols
    out = []
    for k in range(n):
        r, j = divmod(k, cols)
        slot = cols - 1 - j if mode == "boustrophedon" and r % 2 else j
        card_y = y + r * ((HEAD + h + pad + row_gap) if zoned else (h + row_gap)) + (HEAD if zoned else 0)
        out.append((80 + pad + slot * (cw + gap), card_y, cw, h))
    return out


SWEEP = [(n, c, m, z) for n in range(5, 15) for c in range(2, 6) for m in ("boustrophedon", "restart")
         for z in (False, True)]


@pytest.mark.parametrize("n,cols,mode,zoned", SWEEP, ids=[f"{n}x{c}-{m[:4]}-{'zones' if z else 'plain'}"
                                                          for n, c, m, z in SWEEP])
def test_layout_sweep(n, cols, mode, zoned):
    rows = -(-n // cols)
    zones = [f"Phase {r + 1}" for r in range(rows)] if zoned else None
    d = _laid(n, cols, y=200, h=120, mode=mode, zones=zones)
    assert [_rect(c) for c in d.nodes] == [tuple(round(v, 3) for v in r) for r in _expected(n, cols, mode, zoned)]
    for r in range(rows):  # per-row direction: x increases left to right, or decreases on odd boustrophedon rows
        xs = [c.x for c in d.nodes[r * cols:(r + 1) * cols]]
        assert xs == sorted(xs, reverse=mode == "boustrophedon" and r % 2 == 1)
    if zoned:  # zones span the row width and stack row_gap apart
        assert [_rect(z) for z in d.zones] == [
            tuple(round(v, 3) for v in (80, 200 + r * (HEAD + 120 + 24 + 60), 1760, HEAD + 120 + 24))
            for r in range(rows)]


IN_ROW = [  # (id, steps, cols, mode, expected (src, dst) per edge)
    ("5x2-boustrophedon", 5, 2, "boustrophedon",
     [("step-1.right", "step-2.left"), ("step-2", "step-3"), ("step-3.left", "step-4.right"), ("step-4", "step-5")]),
    ("5x2-restart", 5, 2, "restart",
     [("step-1.right", "step-2.left"), ("step-2.bottom", "step-3.left"), ("step-3.right", "step-4.left"),
      ("step-4.bottom", "step-5.left")]),  # restart returns: explicit route (T15)
    ("3x5-one-row", 3, 5, "boustrophedon", [("step-1.right", "step-2.left"), ("step-2.right", "step-3.left")]),
]


@pytest.mark.parametrize("n,cols,mode,ends", [t[1:] for t in IN_ROW], ids=[t[0] for t in IN_ROW])
def test_in_row_edges_anchor_facing_sides(n, cols, mode, ends):
    d = _laid(n, cols, y=200, h=120, mode=mode)
    assert [(e.src, e.dst) for e in d.edges] == ends      # boustrophedon turns keep their ids (ortho routes)


def test_in_row_edges_are_horizontal_in_the_scene():
    d = Diagram("S", "Snake")
    d.snake([f"Step {k + 1}" for k in range(5)], 2, y=200, h=120)
    conns = [i for i in build_scene(d, THEME).items if isinstance(i, Connector)]
    straight = [c.points for k, c in enumerate(conns) if k % 2 == 0]   # edges 0 and 2 are in-row
    assert straight == [[(940, 260), (980, 260)], [(980, 440), (940, 440)]]  # row centres 200 + 60, 380 + 60


def test_pass_leaves_the_source_diagram_alone():
    d = Diagram("S", "Snake")
    d.snake(["a", "b", "c"], 2, y=200, h=120)
    model_passes.apply(d, THEME)
    assert [(n.x, n.y, n.w, n.h) for n in d.nodes] == [(0, 0, 0, 0)] * 3


# ---- T15: snake edges clear and YAML (SNK-05, SNK-07) ----------------------------------------------------------
LONG = "CADA NÓ · CLOUD-INIT · VAULT AGENT · CONSUL CLIENT · FASE {}"
ZONINGS = {  # zone spec for row r (icon: a header icon file), or None
    "plain": None,
    "short": lambda r, icon: f"Phase {r + 1}",
    "long": lambda r, icon: LONG.format(r + 1),
    "long-right": lambda r, icon: {"label": LONG.format(r + 1), "header": "right"},
    "long-icon": lambda r, icon: {"label": LONG.format(r + 1), "icon": icon},
}
CLEAR = [(n, c, m, z) for n in range(5, 15) for c in range(2, 6) for m in ("boustrophedon", "restart")
         for z in ZONINGS]


def _issues(sc):
    return [(i.item, i.kind, i.detail) for i in check(sc) if i.kind in ("edge-crosses-zone-header", "edge-through-box")]


@pytest.fixture(scope="module")
def icon_path(tmp_path_factory):
    p = tmp_path_factory.mktemp("icons") / "icon.svg"
    p.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>')
    return str(p)


@pytest.mark.parametrize("n,cols,mode,zoning", CLEAR, ids=[f"{n}x{c}-{m[:4]}-{z}" for n, c, m, z in CLEAR])
def test_snake_edges_clear(n, cols, mode, zoning, icon_path):
    rows = -(-n // cols)
    zones = [ZONINGS[zoning](r, icon_path) for r in range(rows)] if ZONINGS[zoning] else None
    d = Diagram("S", "Snake")
    d.snake([f"Step {k + 1}" for k in range(n)], cols, y=150, h=110, mode=mode, zones=zones)
    assert _issues(build_scene(d, THEME)) == []


RETURNS = [  # (id, steps, cols, kwargs, expected points of the first restart return edge)
    # 5x2, no zones: step-2 bottom (1410, 320) → row gap middle 320 + 30 → lane 80 - 40 / 2 = 60 → step-3 left
    # (80, 380 + 60)
    ("5x2-plain", 5, 2, {"y": 200, "h": 120},
     [(1410, 320), (1410, 350), (60, 350), (60, 440), (80, 440)]),
    # zones pad 40 (see 4x3-zones-pad40-restart): step-3 bottom (798.667 + 144.667, 152.8) → zone gap middle
    # 192.8 + 30 → lane 100 - 20 → step-4 left (140, 305.6 + 50)
    ("4x3-zones", 4, 3, {"y": 0, "h": 100, "x": 100, "w": 1028,
                         "zones": [{"label": "A", "padding": 40}, {"label": "B", "padding": 40}]},
     [(943.333, 152.8), (943.333, 222.8), (80, 222.8), (80, 355.6), (140, 355.6)]),
]


@pytest.mark.parametrize("n,cols,kw,points", [t[1:] for t in RETURNS], ids=[t[0] for t in RETURNS])
def test_restart_return_runs_through_the_row_gap_and_the_left_lane(n, cols, kw, points):
    d = Diagram("S", "Snake")
    d.snake([f"Step {k + 1}" for k in range(n)], cols, mode="restart", **kw)
    conns = [i for i in build_scene(d, THEME).items if isinstance(i, Connector)]
    assert [tuple(round(v, 3) for v in p) for p in conns[cols - 1].points] == points


def _scene_rects(d):  # shapes by rect, connectors by points
    items = build_scene(d, THEME).items
    return ({i.id: (i.x, i.y, i.w, i.h) for i in items if isinstance(i, Shape)} |
            {i.id: tuple(i.points) for i in items if isinstance(i, Connector)})


STEPS = ["Init", {"title": "Join", "id": "join", "style": "dark"}, "ACL", "Token", "Agent"]
YAML_PARITY = [  # (id, YAML snake row, DSL kwargs)
    ("defaults", {"cols": 2, "y": 200, "h": 120}, {}),
    ("all-keys", {"cols": 3, "y": 100, "h": 100, "x": 100, "w": 1028, "gap": 30, "row_gap": 50, "mode": "restart",
                  "zones": ["A", {"label": "B", "id": "pb", "header": "right"}]},
     {"x": 100, "w": 1028, "gap": 30, "row_gap": 50, "mode": "restart",
      "zones": ["A", {"label": "B", "id": "pb", "header": "right"}]}),
]


@pytest.mark.parametrize("row,kw", [t[1:] for t in YAML_PARITY], ids=[t[0] for t in YAML_PARITY])
def test_yaml_parity(row, kw):
    y = from_dict({"id": "S", "title": "Snake", "snakes": [{"steps": STEPS, **row}]})
    d = Diagram("S", "Snake")
    d.snake([dict(s) if isinstance(s, dict) else s for s in STEPS], row["cols"], y=row["y"], h=row["h"], **kw)
    assert y.snakes == d.snakes
    assert _scene_rects(y) == _scene_rects(d)


YAML_ERRORS = [  # (id, snake row, message)
    ("unknown-key", {"steps": ["a"], "cols": 1, "y": 0, "h": 90, "rows": 2}, "S: snake has unknown keys ['rows']"),
    ("missing", {"steps": ["a"], "y": 0}, "S: snake is missing keys ['cols', 'h']"),
    ("builder-error", {"steps": ["a"], "cols": 1, "y": 0, "h": 90, "mode": "zig"},
     "S: snake mode 'zig'; use boustrophedon or restart"),
]


@pytest.mark.parametrize("row,msg", [t[1:] for t in YAML_ERRORS], ids=[t[0] for t in YAML_ERRORS])
def test_yaml_errors(row, msg):
    with pytest.raises(ValueError) as err:
        from_dict({"id": "S", "title": "Snake", "snakes": [row]})
    assert str(err.value) == msg


A04_PHASES = ["FASE 1 · CADA NÓ · CLOUD-INIT · USER-DATA", "FASE 2 · CADA NÓ · CLOUD-INIT · CONSUL",
              "FASE 3 · PÓS-APPLY · MANUAL · ACL BOOTSTRAP"]


def test_a04_is_one_clean_snake_call():
    d = Diagram("A04", "Consul bootstrap")
    d.snake([f"Step {k + 1}" for k in range(12)], cols=4, y=170, h=120, zones=A04_PHASES)
    assert all(e.via is None and "." not in e.src and "." not in e.dst for e in d.edges)  # no hand anchors or via
    sc = build_scene(d, THEME)
    assert _issues(sc) == []
    assert len([i for i in sc.items if isinstance(i, Connector)]) == 11


# ---- T15b: dump snakes (SNK-07) -----------------------------------------------------------------------------------
def _yaml_snake():
    return from_dict({"id": "S", "title": "Snake", "snakes": [{"steps": STEPS, "cols": 2, "y": 200, "h": 120}]})


def _zoned():
    d = Diagram("S", "Snake")
    d.snake(["Init", "Join", "ACL", "Token"], 3, y=100, h=100, x=100, w=1028, gap=30, row_gap=50, mode="restart",
            zones=["A", {"label": "B", "id": "pb", "header": "right"}])
    return d


def _nested():
    d = Diagram("S", "Snake")
    with d.zone("Account", id="acct", x=60, y=60, w=1800, h=900):
        d.snake(["a", "b", "c"], 2, y=150, h=90, x=100, w=1500, zones=["R1", "R2"])
    return d


def _mixed():
    d = Diagram("S", "Snake")
    d.zone("Secrets", id="sm", band=(800, 960), header="none")
    with d.zone("Tools", id="tools", band=(600, 760), header="right"):
        d.row(["Vault", "Consul"], cols=3, align="start", same_text_scale=True)
    d.box("Ops", id="ops", x=1500, y=400, w=300, h=100)  # YAML order: nodes before snake steps (paint order)
    nodes = d.snake(["a", "b", "c"], 2, y=150, h=90)
    d.edge("ops", nodes[2], "watch")
    return d


def _edge_kwargs():
    d = Diagram("S", "Snake")
    d.snake(["a", "b", "c"], 2, y=150, h=90, dashed=True, label="next")
    return d


def _fixed_edge():
    d = _yaml_snake()
    d.edges[0].src, d.edges[0].dst = "init.bottom@0.65", "join.top@0.65"   # an applied anchor fix
    return d


ROUND_TRIPS = [  # (id, diagram factory, expected dumped snakes, expected dumped node ids, dumped edge count)
    ("yaml-defaults", _yaml_snake,
     [{"steps": [{"id": "init", "title": "Init"}, {"id": "join", "title": "Join", "style": "dark"},
                 {"id": "acl", "title": "ACL"}, {"id": "token", "title": "Token"}, {"id": "agent", "title": "Agent"}],
       "cols": 2, "y": 200, "h": 120}], [], 0),
    ("zoned-all-keys", _zoned,
     [{"steps": [{"id": "init", "title": "Init"}, {"id": "join", "title": "Join"}, {"id": "acl", "title": "ACL"},
                 {"id": "token", "title": "Token"}],
       "cols": 3, "y": 100, "h": 100, "x": 100, "w": 1028, "gap": 30, "row_gap": 50, "mode": "restart",
       "zones": [{"id": "z0", "label": "A"}, {"id": "pb", "label": "B", "header": "right"}]}], [], 0),
    ("nested-in-zone", _nested,
     [{"steps": [{"id": "a", "title": "a"}, {"id": "b", "title": "b"}, {"id": "c", "title": "c"}],
       "cols": 2, "y": 150, "h": 90, "x": 100, "w": 1500,
       "zones": [{"id": "z1", "label": "R1"}, {"id": "z2", "label": "R2"}]}], [], 0),
    ("mixed", _mixed,
     [{"steps": [{"id": "a", "title": "a"}, {"id": "b", "title": "b"}, {"id": "c", "title": "c"}],
       "cols": 2, "y": 150, "h": 90}], ["vault", "consul", "ops"], 1),
    ("edge-kwargs", _edge_kwargs,
     [{"steps": [{"id": "a", "title": "a"}, {"id": "b", "title": "b"}, {"id": "c", "title": "c"}],
       "cols": 2, "y": 150, "h": 90, "chain": False}], [], 2),
    ("fixed-edge", _fixed_edge,
     [{"steps": [{"id": "init", "title": "Init"}, {"id": "join", "title": "Join", "style": "dark"},
                 {"id": "acl", "title": "ACL"}, {"id": "token", "title": "Token"}, {"id": "agent", "title": "Agent"}],
       "cols": 2, "y": 200, "h": 120, "chain": False}], [], 4),
]


def _model(d):
    return (d.nodes, d.zones, d.edges, d.snakes, d.containers)


@pytest.mark.parametrize("make,snakes,node_ids,n_edges", [t[1:] for t in ROUND_TRIPS], ids=[t[0] for t in ROUND_TRIPS])
def test_dump_round_trips_snakes(make, snakes, node_ids, n_edges):
    from spinagram.backends.svg import to_svg
    from spinagram.yaml_io import dump

    d = make()
    out = dump(d)
    assert out["snakes"] == snakes                                                 # snakes: in the YAML shape
    assert [n["id"] for n in out.get("nodes", [])] == node_ids                     # generated nodes omitted
    snake_zones = {z for s in d.snakes for z in s.zones}
    assert not snake_zones & {z["id"] for z in out.get("zones", [])}               # generated zones omitted
    assert len(out.get("edges", [])) == n_edges                                    # chain edges regenerated
    back = from_dict(out)
    assert sorted(_model(back)[0], key=lambda n: n.id) == sorted(d.nodes, key=lambda n: n.id)
    assert sorted(back.zones, key=lambda z: z.id) == sorted(d.zones, key=lambda z: z.id)
    assert (back.edges, back.snakes, back.containers) == (d.edges, d.snakes, d.containers)
    assert to_svg(build_scene(back, THEME)) == to_svg(build_scene(d, THEME))       # identical scene


def test_yaml_step_and_zone_class_keys_are_classes():
    y = from_dict({"id": "S", "title": "Snake", "snakes": [{"steps": [{"title": "a", "class": "hot"}, "b"], "cols": 2,
                                                            "y": 0, "h": 90, "zones": [{"label": "A", "class": "z"}]}]})
    assert (y.nodes[0].cls, y.nodes[0].extra, y.zones[0].cls) == ("hot", {}, "z")


def test_snake_without_chain_draws_no_edges():
    d = Diagram("S", "Snake")
    d.snake(["a", "b", "c"], 2, y=0, h=90, chain=False)
    assert d.edges == [] and len(d.nodes) == 3


SNAKE_FIX_SPEC = """id: F1
title: Fix
snakes:
  - steps: [Init, Join, ACL, Token, Agent]
    cols: 3
    y: 200
    h: 120
    zones: [Phase 1, Phase 2]
nodes:
  - {id: ops, title: Ops, x: 1550, y: 800, w: 300, h: 100}
edges:
  - {from: ops, to: agent}
"""


def test_check_fix_on_a_yaml_snake(tmp_path, monkeypatch, capsys):
    import yaml

    from spinagram import load
    from spinagram.backends.svg import to_svg
    from spinagram.cli import main

    (tmp_path / "s.yaml").write_text(SNAKE_FIX_SPEC)
    monkeypatch.chdir(tmp_path)
    main(["check", "--fix", "s.yaml"])
    assert "s.fixed.yaml: 1 fix(es) applied" in capsys.readouterr().out
    data = yaml.safe_load((tmp_path / "s.fixed.yaml").read_text())
    assert [n["id"] for n in data["nodes"]] == ["ops"] and len(data["snakes"]) == 1
    assert data["nodes"][0]["at"] == [1540, 800, 300, 100]                         # nudged 10 px into the safe area
    want = load(tmp_path / "s.yaml")[0]
    want.node("ops").x = 1540                                                      # the source plus the applied fix
    got = load(tmp_path / "s.fixed.yaml")[0]
    assert to_svg(build_scene(got, THEME)) == to_svg(build_scene(want, THEME))

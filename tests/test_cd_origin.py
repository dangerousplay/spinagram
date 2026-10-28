"""Coordinates relative to the safe area: ``origin="safe"`` (ORG-01..04)."""
from __future__ import annotations

import pytest
import yaml

from spinagram import Diagram, Theme, build_scene
from spinagram.engine import model_passes
from spinagram.qa import check
from spinagram.yaml_io import dump, from_dict

MARGINS = [30, 40, 80]


@pytest.fixture(scope="module")
def themes(tmp_path_factory):
    out = {}
    for m in MARGINS:
        root = tmp_path_factory.mktemp(f"m{m}")
        (root / "theme.yaml").write_text(f"extends: default\ncanvas: {{margin: {m}}}\n")
        out[m] = Theme.load(root)
    return out


def _d():
    return Diagram("O", "Origin", origin="safe")


def _node(d):
    d.box("A", id="a", x=10, y=20, w=300, h=100)


def _pill(d):
    d.pill("P", x=100, y=50)


def _label(d):
    d.label("L", x=100, y=50)


def _zone(d):
    d.zone("Z", x=10, y=20, w=600, h=300)


def _band(d):
    d.zone("Z", band=(100, 300), x=10, w=600)


def _band_full(d):
    d.zone("Z", band=(100, 300))


def _row(d):
    with d.row(x=10, y=20, gap=20):
        d.box("A", id="a", w=200, h=100)
        d.box("B", id="b", w=200, h=100)


def _snake(d):
    d.snake(["a", "b", "c"], 2, y=20, h=100)


def _snake_x(d):
    d.snake(["a", "b", "c"], 2, y=20, h=100, x=10, w=1000)


def _table(d):
    d.table(["a", "b"], [["1", "2"]], x=10, y=20, widths=[100, 100])


def _legend(d):
    d.set_legend([("primary", "x")], x=10, y=20)


def _ends(d):
    d.edge((10, 20), (300, 400))


def _via(d):
    _node(d)
    d.edge("a", (600, 400), via=[(100, 300), (500, 300)])


def _curve(d):
    _node(d)
    d.edge("a", (600, 400), curve=(400, 200))


def _label_at(d):
    _node(d)
    d.edge("a", (600, 400), "go", label_at=(300, 250))


def _place(d):
    _node(d)
    d.add_legend({"style:soft": "s"}, place=(1000, 600, 300, 200))


ELEMENTS = [  # (id, build, read the coordinates from the passed model, safe-area coordinates; +m on x and y)
    ("node", _node, lambda d: (d.nodes[0].x, d.nodes[0].y), (10, 20)),
    ("pill", _pill, lambda d: (d.nodes[0].x, d.nodes[0].y), (100, 50)),
    ("free-label", _label, lambda d: (d.nodes[0].x, d.nodes[0].y), (100, 50)),
    ("zone", _zone, lambda d: (d.zones[0].x, d.zones[0].y), (10, 20)),
    ("zone-band", _band, lambda d: (d.zones[0].x, d.zones[0].y, d.zones[0].y + d.zones[0].h), (10, 100, 300)),
    ("container", _row, lambda d: (d.nodes[0].x, d.nodes[0].y, d.nodes[1].x), (10, 20, 230)),
    ("snake-y", _snake, lambda d: (d.nodes[0].y,), (20,)),
    ("snake-xy", _snake_x, lambda d: (d.nodes[0].x, d.nodes[0].y), (10, 20)),
    ("table", _table, lambda d: (d.tables[0].x, d.tables[0].y), (10, 20)),
    ("fixed-legend", _legend, lambda d: (d.legend.x, d.legend.y), (10, 20)),
    ("edge-points", _ends, lambda d: (*d.edges[0].src, *d.edges[0].dst), (10, 20, 300, 400)),
    ("via", _via, lambda d: tuple(v for p in d.edges[0].via for v in p), (100, 300, 500, 300)),
    ("curve", _curve, lambda d: tuple(d.edges[0].curve), (400, 200)),
    ("label-at", _label_at, lambda d: tuple(d.edges[0].label_at), (300, 250)),
    ("legend-place", _place, lambda d: d.annotations.legend.place[:2], (1000, 600)),
]


@pytest.mark.parametrize("m", MARGINS)
@pytest.mark.parametrize("build,read,at", [e[1:] for e in ELEMENTS], ids=[e[0] for e in ELEMENTS])
def test_safe_origin_offsets_every_coordinate(themes, m, build, read, at):
    d = _d()
    build(d)
    got = model_passes.apply(d, themes[m])
    assert tuple(read(got)) == tuple(v + m for v in at)                     # offset by the margin on both axes
    assert got.origin == "canvas"                                           # the copy is in canvas coordinates
    assert d.origin == "safe"                                               # the spec is not mutated


def test_band_without_x_spans_the_safe_width(themes):
    d = _d()
    _band_full(d)
    z = model_passes.apply(d, themes[40]).zones[0]
    assert (z.x, z.y, z.w, z.h) == (40, 140, 1840, 200)


def test_snake_without_x_starts_at_the_margin(themes):
    d = _d()
    _snake(d)
    n = model_passes.apply(d, themes[30]).nodes[0]
    assert (n.x, n.y) == (30, 50)                                           # x: the margin, not margin twice


def test_snake_via_points_are_not_offset_twice(themes):
    d = _d()
    d.snake(["a", "b", "c", "d"], 2, y=20, h=100, mode="restart")
    plain = Diagram("O", "Origin")
    plain.snake(["a", "b", "c", "d"], 2, y=60, h=100, mode="restart")
    assert model_passes.apply(d, themes[40]).edges[1].via == model_passes.apply(plain, themes[40]).edges[1].via


def _spec(d):  # one of each element, all inside the safe area at every margin (safe area ≥ 1760 x 920)
    d.box("A", id="a", x=0, y=0, w=300, h=100)
    d.zone("Z", x=0, y=150, w=700, h=300)
    d.box("B", id="b", x=40, y=250, w=300, h=100)
    d.pill("pill", x=1000, y=60)
    d.label("free text", x=1000, y=200)
    d.edge("a", "b", "go", label_at=(500, 150))
    d.table(["a", "b"], [["1", "2"]], x=900, y=500, widths=[200, 200])
    d.snake(["s1", "s2", "s3"], 3, y=700, h=100, x=0, w=1700)


@pytest.mark.parametrize("m", MARGINS)
def test_same_spec_fits_every_margin(themes, m):
    d = _d()
    _spec(d)
    sc = build_scene(d, themes[m])
    assert [i for i in check(sc) if i.kind == "outside-safe-area"] == []
    assert (sc.shapes()["a"].x, sc.shapes()["a"].y) == (m, m)


def test_default_origin_is_canvas_and_unchanged(themes):
    from spinagram.backends.svg import to_svg

    a, b = Diagram("O", "Origin"), Diagram("O", "Origin", origin="canvas")
    for d in (a, b):
        _spec(d)
    assert a.origin == "canvas"
    assert model_passes.apply(a, themes[80]).nodes[0].x == 0
    assert to_svg(build_scene(a, themes[80])) == to_svg(build_scene(b, themes[80]))


@pytest.mark.parametrize("bad", ["page", "", None])
def test_invalid_origin(bad):
    with pytest.raises(ValueError) as err:
        Diagram("O", "Origin", origin=bad)
    assert str(err.value) == f"O: origin {bad!r}; use canvas or safe"


def test_yaml_origin_and_dump_round_trip(themes):
    y = from_dict({"id": "O", "title": "Origin", "origin": "safe",
                   "nodes": [{"id": "a", "title": "A", "x": 10, "y": 20, "w": 300, "h": 100}]})
    assert y.origin == "safe"
    assert build_scene(y, themes[40]).shapes()["a"].x == 50
    assert dump(y)["origin"] == "safe" and from_dict(dump(y)).origin == "safe"
    assert "origin" not in dump(Diagram("O", "Origin"))


def test_yaml_invalid_origin():
    with pytest.raises(ValueError, match=r"O: origin 'page'; use canvas or safe"):
        from_dict({"id": "O", "title": "Origin", "origin": "page"})


# ORG-04: a node 10 px past the safe area gets a nudge fix, and check --fix applies it -----------------------------
NUDGE = [  # (id, origin, node x in the spec, x after the fix)
    ("canvas", "canvas", 1550, 1540),      # right edge 1850 > 1840 by 10
    ("safe", "safe", 1470, 1460),          # 1470 + 80 = 1550: the same box in safe coordinates
]


@pytest.mark.parametrize("origin,x,fixed_x", [n[1:] for n in NUDGE], ids=[n[0] for n in NUDGE])
def test_ten_px_overflow_is_nudged_and_fixed(tmp_path, monkeypatch, capsys, origin, x, fixed_x):
    from spinagram import load
    from spinagram.cli import main

    spec = {"id": "N", "title": "Nudge", "origin": origin,
            "nodes": [{"id": "m", "title": "M", "x": x, "y": 400, "w": 300, "h": 100}]}
    (tmp_path / "s.yaml").write_text(yaml.safe_dump(spec))
    theme = Theme.load("default")
    issues = [i for i in check(build_scene(load(tmp_path / "s.yaml")[0], theme)) if i.kind == "outside-safe-area"]
    assert [(i.item, i.detail, i.fix) for i in issues] == [
        ("m", "10px past the right margin (80px)", {"op": "nudge", "node": "m", "dx": -10, "dy": 0})]
    monkeypatch.chdir(tmp_path)
    main(["check", "--fix", "s.yaml"])
    assert "s.fixed.yaml: 1 fix(es) applied" in capsys.readouterr().out
    fixed = load(tmp_path / "s.fixed.yaml")[0]
    assert (fixed.origin, fixed.node("m").x) == (origin, fixed_x)
    assert [i for i in check(build_scene(fixed, theme)) if i.kind == "outside-safe-area"] == []


def test_safe_origin_fix_near_the_left_edge_is_applied():
    """The fix's safe-area test reads canvas coordinates: a safe-origin node at x 10 is inside (90 ≥ 80)."""
    from spinagram.engine.fix import fix_until_clean

    d = _d()
    d.box("M", id="m", x=10, y=880, w=300, h=50)                            # bottom 80 + 930 = 1010 > 1000 by 10
    fixed, applied, left = fix_until_clean(d, Theme.load("default"))
    assert [i.fix for i in applied] == [{"op": "nudge", "node": "m", "dx": 0, "dy": -10}]
    assert (fixed.node("m").x, fixed.node("m").y) == (10, 870)


@pytest.mark.parametrize("origin,label_at", [("canvas", (500, 300)), ("safe", (420, 220))], ids=["canvas", "safe"])
def test_move_label_fix_lands_in_spec_coordinates(origin, label_at):
    from spinagram.engine.fix import apply_to_diagram
    from spinagram.qa import Issue

    d = Diagram("O", "Origin", origin=origin)
    d.box("A", id="a", x=0, y=0, w=200, h=100)
    d.box("B", id="b", x=600, y=0, w=200, h=100)
    d.edge("a", "b", "go")
    fix = {"op": "move-label", "edge": "e0", "to": [500, 300]}           # scene coordinates
    out, applied, _ = apply_to_diagram(d, [Issue("O", "e0", "label-collision", "x", fix=fix)])
    assert len(applied) == 1 and out.edges[0].label_at == label_at

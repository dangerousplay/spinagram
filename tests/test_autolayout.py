"""Auto layout: model/YAML, sizing, and invariants every engine must keep."""
from __future__ import annotations

from pathlib import Path

import pytest

from spinagram.autolayout import apply_layout
from spinagram.autolayout.engines import EngineUnavailable, available, get_engine
from spinagram.autolayout.graph import LGraph, LResult
from spinagram.model import Diagram
from spinagram.theme import Theme
from spinagram.yaml_io import from_dict, load

EXAMPLE = Path(__file__).parent.parent / "examples" / "aws_layout.yaml"
ENGINES = ["flex", "layered", "dot", "elk", "d2"]


def _theme() -> Theme:
    return Theme.load(None)


def _engine_ok(name: str) -> bool:
    try:
        get_engine(name)
        return True
    except (EngineUnavailable, ModuleNotFoundError, ImportError):
        return False


def _inside(inner, outer, tol=0.5) -> bool:
    ix, iy, iw, ih = inner
    ox, oy, ow, oh = outer
    return ix >= ox - tol and iy >= oy - tol and ix + iw <= ox + ow + tol and iy + ih <= oy + oh + tol


def _overlap(a, b) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw - 0.5 and bx < ax + aw - 0.5 and ay < by + bh - 0.5 and by < ay + ah - 0.5


def _check_invariants(src: Diagram, out: Diagram) -> None:
    zones = {g.id: z for g, z in zip(src.groups, out.zones)}
    boxes = {n.id: (n.x, n.y, n.w, n.h) for n in out.nodes}
    boxes.update({gid: (z.x, z.y, z.w, z.h) for gid, z in zones.items()})
    for g in src.groups:
        for c in g.children:
            assert _inside(boxes[c], boxes[g.id]), f"{c} not inside {g.id}"
        # label band free: children start below the group's top + band
        top = min(boxes[c][1] for c in g.children)
        assert top - boxes[g.id][1] >= 30, f"{g.id}: children cover the label band"
    siblings = [g.children for g in src.groups]
    child_of = {c for g in src.groups for c in g.children}
    siblings.append([n.id for n in src.nodes if n.id not in child_of] +
                    [g.id for g in src.groups if g.id not in child_of])
    for sib in siblings:
        for i, a in enumerate(sib):
            for b in sib[i + 1:]:
                assert not _overlap(boxes[a], boxes[b]), f"{a} overlaps {b}"
    for n in out.nodes:
        assert n.w > 0 and n.h > 0


# model ------------------------------------------------------------------------------------------
def test_yaml_and_dsl_build_same_groups():
    y = from_dict({"id": "x", "title": "t", "layout": "flex",
                   "groups": [{"id": "r", "label": "R", "children": [{"id": "a", "children": ["n1"]}, "n2"]}],
                   "nodes": [{"id": "n1", "title": "A"}, {"id": "n2", "title": "B"}, {"id": "n3", "title": "C", "in": "a"}]})
    d = Diagram("x", "t", layout={"engine": "flex"})
    with d.group("R", id="r"):
        with d.group(id="a"):
            d.box("A", id="n1")
        d.box("B", id="n2")
    with d.group(id="a2"):
        pass
    d.groups[1].children.append("n3")
    d.box("C", id="n3")
    d.groups.pop()  # same tree as the YAML (n3 added to "a")
    assert [(g.id, g.children) for g in y.groups] == [("r", ["a", "n2"]), ("a", ["n1", "n3"])]
    assert [(g.id, g.children) for g in d.groups] == [("r", ["a", "n2"]), ("a", ["n1", "n3"])]


@pytest.mark.parametrize("groups,err", [
    ([{"id": "g", "children": ["nope"]}], "unknown child"),
    ([{"id": "g", "children": ["n1"]}, {"id": "h", "children": ["n1"]}], "two groups"),
])
def test_group_validation(groups, err):
    with pytest.raises(ValueError, match=err):
        from_dict({"id": "x", "title": "t", "groups": groups, "nodes": [{"id": "n1", "title": "A"}]})


def test_no_layout_is_untouched():
    d = from_dict({"id": "x", "title": "t", "nodes": [{"id": "a", "title": "A", "at": [10, 20, 100, 50]}]})
    assert apply_layout(d, _theme()) is d


def test_auto_size_wraps_long_titles():
    d = from_dict({"id": "x", "title": "t", "layout": "flex",
                   "nodes": [{"id": "a", "title": "A very long title that must wrap inside the maximum width"},
                             {"id": "b", "title": "B"}]})
    out = apply_layout(d, _theme())
    a, b = out.node("a"), out.node("b")
    auto = _theme().defaults("node").get("auto") or {}
    assert a.w <= auto.get("max_w", 360) and a.h > b.h
    assert b.w >= auto.get("min_w", 220)


def test_free_positioned_nodes_stay_put():
    d = from_dict({"id": "x", "title": "t", "layout": "flex",
                   "nodes": [{"id": "a", "title": "A"}, {"id": "fixed", "title": "F", "at": [50, 900, 200, 80]}]})
    out = apply_layout(d, _theme())
    assert (out.node("fixed").x, out.node("fixed").y) == (50, 900)


def test_toy_engine_protocol(monkeypatch):
    class Toy:
        name = "toy"

        def available(self):
            return None

        def run(self, g: LGraph) -> LResult:
            return LResult({nid: (i * 300.0, 0.0, 200.0, 80.0) for i, nid in enumerate(g.node_ids())})

    import spinagram.autolayout.engines as eng
    monkeypatch.setattr(eng, "get_engine", lambda name: Toy())
    import spinagram.autolayout as al
    monkeypatch.setattr(al, "get_engine", lambda name: Toy())
    d = from_dict({"id": "x", "title": "t", "layout": "toy", "nodes": [{"id": "a", "title": "A"}, {"id": "b", "title": "B"}]})
    out = apply_layout(d, _theme())
    assert out.node("b").x - out.node("a").x == 300


def test_unknown_engine():
    with pytest.raises(KeyError, match="unknown layout engine"):
        get_engine("nope")
    assert set(ENGINES) <= set(available())


def test_overflow_is_a_qa_issue():
    from spinagram.api import scenes
    from spinagram.qa import check

    nodes = [{"id": f"n{i}", "title": f"Node {i}"} for i in range(12)]
    d = from_dict({"id": "x", "title": "t", "layout": {"engine": "flex", "direction": "right"}, "nodes": nodes})
    issues = check(scenes([d], _theme())[0])
    assert any(i.kind == "overflow" and i.item == "layout" for i in issues)


# engines ----------------------------------------------------------------------------------------
@pytest.mark.parametrize("engine", ENGINES)
def test_engine_invariants(engine):
    if not _engine_ok(engine):
        pytest.skip(f"{engine} runtime not installed")
    [d] = load(EXAMPLE)
    out = apply_layout(d, _theme(), engine)
    _check_invariants(d, out)
    assert out.meta["layout_engine"] == engine


@pytest.mark.parametrize("engine", ["dot", "elk", "d2"])
def test_graph_engines_route_edges(engine):
    if not _engine_ok(engine):
        pytest.skip(f"{engine} runtime not installed")
    [d] = load(EXAMPLE)
    out = apply_layout(d, _theme(), engine)
    assert any(e.via for e in out.edges), "no edge got a route"
    for e in out.edges:
        assert "." in str(e.src) and "." in str(e.dst)


def test_flex_is_deterministic():
    [d] = load(EXAMPLE)
    a = apply_layout(d, _theme(), "flex")
    b = apply_layout(d, _theme(), "flex")
    assert [(n.x, n.y, n.w, n.h) for n in a.nodes] == [(n.x, n.y, n.w, n.h) for n in b.nodes]


def test_missing_binary_message(monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    for name in ("dot", "d2", "elk"):
        with pytest.raises(EngineUnavailable, match=name):
            get_engine(name)


def test_flex_ortho_elbows():
    d = from_dict({"id": "x", "title": "t", "layout": {"engine": "flex", "route": "ortho"},
                   "groups": [{"id": "g", "direction": "column", "children": ["b", "c"]}],
                   "nodes": [{"id": "a", "title": "A"}, {"id": "b", "title": "B"}, {"id": "c", "title": "C"}],
                   "edges": ["a -> b", "a -> c"]})
    out = apply_layout(d, _theme(), "flex")
    for e in out.edges:
        assert e.src.startswith("a.right") and e.dst.endswith(".left")
        for (x1, y1), (x2, y2) in zip(e.via or [], (e.via or [])[1:]):
            assert x1 == x2 or y1 == y2  # no diagonal segment


def test_frozen_layout_renders_identically(tmp_path):
    import yaml

    from spinagram.api import scenes
    from spinagram.backends.svg import to_svg
    from spinagram.yaml_io import dump

    [d] = load(EXAMPLE)
    th = _theme()
    frozen = from_dict(yaml.safe_load(yaml.safe_dump(dump(apply_layout(d, th, "flex")))), base_dir=EXAMPLE.parent)
    a, b = scenes([d], th)[0], scenes([frozen], th)[0]
    assert to_svg(a) == to_svg(b)


def test_routed_edge_label_sits_on_longest_segment():
    from spinagram.autolayout import _label_point
    from spinagram.model import Edge

    boxes = {"a": (0, 0, 100, 50), "b": (400, 300, 100, 50)}
    # a.right (100,25) → (150,25) → (150,325) → b.left (400,325): the vertical leg (300 px) is the longest
    e = Edge(src="a.right", dst="b.left", label="x", via=[(150, 25), (150, 325)])
    assert _label_point(boxes, e) == (150, 179.5)  # centred on the vertical leg, clear of both ends
    # make the last horizontal leg the longest
    boxes["b"] = (900, 300, 100, 50)
    assert _label_point(boxes, e) == (525, 317)


# regressions found while building the docs showcase ------------------------------------------------
def test_node_and_group_ids_never_collide():
    import pytest
    from spinagram import Diagram

    d = Diagram("X", "Ids")
    with d.group("namespace: shop", id="shop"):
        shop = d.box("Shop")  # the auto id steps around the group id
    assert shop.id == "shop-2"
    with pytest.raises(ValueError, match="already a group id"):
        d.box("Other", id="shop")
    with pytest.raises(ValueError, match="already a node id"):
        with d.group("G", id="shop-2"):
            pass


def test_yaml_node_and_group_with_one_id_is_a_clear_error():
    import pytest
    from spinagram.yaml_io import from_dict

    with pytest.raises(ValueError, match="already a group id"):  # not a RecursionError in the CSS tree
        from_dict({"id": "Y", "title": "Y", "layout": "flex",
                   "groups": [{"id": "shop", "label": "Shop", "children": ["api"]}],
                   "nodes": [{"id": "shop", "title": "Shop"}, {"id": "api", "title": "API"}]})


def test_route_prefers_a_side_no_other_edge_uses():
    from spinagram.autolayout.route import route

    src, dst = (0, 0, 100, 60), (300, 0, 100, 60)
    assert route(src, dst, [src, dst])[-1] == (300, 30)  # face to face: straight into the left side
    busy = route(src, dst, [src, dst], busy={dst: {"left"}})
    assert busy[-1] in ((350, 0), (350, 60))  # another edge already ends on the left: top or bottom wins


def test_route_keeps_clear_of_boxes_it_passes():
    from spinagram.autolayout.route import route

    # the straight line from src to dst would graze the bottom of ``mid`` by 4 px
    src, mid, dst = (0, 100, 100, 60), (200, 66, 100, 60), (400, 100, 100, 60)
    pts = route(src, dst, [src, mid, dst], sides=("right", "left"))
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if y1 == y2 and min(x1, x2) < 300 and max(x1, x2) > 200:  # a horizontal leg under ``mid``
            assert y1 >= 66 + 60 + 14 or y1 <= 66 - 14


def test_short_edge_label_leaves_the_arrowhead_visible():
    from spinagram import Diagram

    th = _theme()
    d = Diagram("S", "Short", layout={"engine": "flex", "direction": "right", "gap": 60, "route": "ortho"})
    a, b = d.box("NLB"), d.box("Route 53")
    b.to(a, "alias")
    out = apply_layout(d, th)
    e = out.edges[0]
    n = {k.id: (k.x, k.y, k.w, k.h) for k in out.nodes}
    tip = (n["nlb"][0] + n["nlb"][2], n["nlb"][1] + n["nlb"][3] / 2)  # NLB's right side, where the head is
    size = th.defaults("edge").get("label_size", 17)
    from spinagram.text import measure
    pw, ph = measure("alias", th.font("body", 700, size)) + 24, size + 14
    lx, ly = e.label_at
    pill = (lx - pw / 2, ly - size - 3, pw, ph)
    assert not (pill[0] < tip[0] + 15 and tip[0] - 15 < pill[0] + pill[2]
                and pill[1] < tip[1] + 15 and tip[1] - 15 < pill[1] + pill[3])


def test_check_reports_a_label_over_an_arrowhead():
    from spinagram.api import scenes
    from spinagram.qa import check

    d = Diagram("H", "Hidden head")
    a = d.box("A", x=100, y=300, w=300, h=120)
    b = d.box("B", x=480, y=300, w=300, h=120)  # 80 px gap: no room for the pill beside the head
    d.edge(a.right, b.left, "a long label")
    issues = [i for i in check(scenes([d], _theme())[0]) if i.kind == "label"]
    assert issues and "hides its own arrowhead" in issues[0].detail


def test_unconnected_items_follow_the_flow():
    d = Diagram("U", "Unconnected", layout={"engine": "flex", "direction": "right"})
    users, api = d.box("Users"), d.box("API")
    users.to(api, "HTTPS")
    d.note("Why", text="Explain the choice")  # created last, linked to nothing
    out = apply_layout(d, _theme())
    x = {n.id: n.x for n in out.nodes}
    assert x["users"] < x["api"] < x["why"]  # never between Users and API, where the edge runs


def test_flex_widens_only_gaps_that_carry_a_label():
    d = Diagram("G", "Gaps", layout={"engine": "flex", "direction": "right"})
    with d.group("Row", id="row", direction="right"):
        a, b, c = d.box("A"), d.box("B"), d.box("C")
    a.to(b, "a fairly long label")
    b >> c
    out = apply_layout(d, _theme())
    n = {k.id: (k.x, k.w) for k in out.nodes}
    ab = n["b"][0] - (n["a"][0] + n["a"][1])
    bc = n["c"][0] - (n["b"][0] + n["b"][1])
    assert ab > bc and ab >= 150  # room for the pill and the arrowhead; the unlabelled gap stays default


def test_flex_keeps_an_explicit_gap():
    d = Diagram("E", "Explicit", layout={"engine": "flex", "direction": "right"})
    with d.group("Row", id="row", direction="right", gap=12):
        a, b = d.box("A"), d.box("B")
    a.to(b, "a fairly long label")
    out = apply_layout(d, _theme())
    n = {k.id: (k.x, k.w) for k in out.nodes}
    assert round(n["b"][0] - (n["a"][0] + n["a"][1])) == 12


def test_check_reports_an_edge_through_a_box():
    from spinagram.api import scenes
    from spinagram.qa import check

    d = Diagram("T", "Through")
    a = d.box("A", x=100, y=300, w=200, h=100)
    d.box("Mid", x=500, y=300, w=200, h=100)
    b = d.box("B", x=900, y=300, w=200, h=100)
    d.edge(a.right, b.left)  # straight over Mid
    issues = [i for i in check(scenes([d], _theme())[0]) if i.kind == "edge"]
    assert issues and "mid" in issues[0].detail

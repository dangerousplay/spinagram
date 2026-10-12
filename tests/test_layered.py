"""Layered layout engine (spec: .specs/features/layered-layout/spec.md)."""
from __future__ import annotations

from spinagram.autolayout import build_graph
from spinagram.model import Diagram
from spinagram.theme import Theme


def _theme() -> Theme:
    return Theme.load(None)


# T1: layout graph -------------------------------------------------------------------------------
def test_self_edges_go_to_loops_not_edges():  # LAY-09 input
    d = Diagram("x", "t", layout={"engine": "layered"})
    a, b = d.box("a"), d.box("b")
    a >> b
    d.edge(b, b, "retry")
    g, _ = build_graph(d, _theme())
    assert [(e.src, e.dst) for e in g.edges] == [("a", "b")]
    assert [(e.id, e.src, e.dst) for e in g.loops] == [("e1", "b", "b")]


def test_group_hints_carry_lanes_engine_direction():  # LAY-16 input, regions
    d = Diagram("x", "t", layout={"engine": "flex"})
    with d.group("Flow", id="flow", engine="layered", direction="down", lanes=True):
        d.box("a")
    g, _ = build_graph(d, _theme())
    grp = g.root.children[0]
    assert grp.hints["engine"] == "layered"
    assert grp.hints["direction"] == "down"
    assert grp.hints["lanes"] is True


# T2: layered engine -----------------------------------------------------------------------------
import warnings  # noqa: E402

import pytest  # noqa: E402

from spinagram.autolayout.engines import get_engine  # noqa: E402
from spinagram.autolayout.graph import LEdge, LGraph, LGroup, LNode  # noqa: E402


def _graph(nodes, edges, direction="down", kinds=None, loops=()):
    kinds = kinds or {}
    root = LGroup("__root__", [LNode(n, 160, 80, kinds.get(n, "box")) for n in nodes])
    return LGraph(root, [LEdge(f"e{i}", a, b) for i, (a, b) in enumerate(edges)], direction,
                  {"gap": 40, "node_gap": 48, "rank_gap": 80},
                  loops=[LEdge(f"l{i}", a, a) for i, a in enumerate(loops)])


def _run(g):
    return get_engine("layered").run(g)


def _overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw - 0.5 and bx < ax + aw - 0.5 and ay < by + bh - 0.5 and by < ay + ah - 0.5


def _seg_hits_box(p, q, box, pad=0.5):
    """Axis-aligned segment p-q passes through the interior of box."""
    x, y, w, h = box
    (x1, y1), (x2, y2) = p, q
    if abs(x1 - x2) < 1e-6:  # vertical
        return x + pad < x1 < x + w - pad and max(min(y1, y2), y + pad) < min(max(y1, y2), y + h - pad)
    if abs(y1 - y2) < 1e-6:
        return y + pad < y1 < y + h - pad and max(min(x1, x2), x + pad) < min(max(x1, x2), x + w - pad)
    return True  # diagonal segments are a failure in their own right


ORDER = ["start", "receive", "stock", "ship", "backorder", "done"]
ORDER_EDGES = [("start", "receive"), ("receive", "stock"), ("stock", "ship"), ("stock", "backorder"),
               ("ship", "done"), ("backorder", "done")]


def _rank_axis(res, n, direction):
    x, y, w, h = res.boxes[n]
    return (y, y + h) if direction == "down" else (x, x + w)


@pytest.mark.parametrize("direction", ["down", "right"])
def test_targets_rank_after_sources(direction):  # LAY-01, LAY-02
    res = _run(_graph(ORDER, ORDER_EDGES, direction))
    for a, b in ORDER_EDGES:
        assert _rank_axis(res, b, direction)[0] >= _rank_axis(res, a, direction)[1] + 80 - 0.5, (a, b)


def test_gaps_and_no_overlaps():  # LAY-03, LAY-04
    res = _run(_graph(ORDER, ORDER_EDGES))
    boxes = [res.boxes[n] for n in ORDER]
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            assert not _overlap(a, b)
    ship, back = res.boxes["ship"], res.boxes["backorder"]  # same rank: at least node_gap apart
    left, right = sorted([ship, back])
    assert right[0] - (left[0] + left[2]) >= 48 - 0.5


def test_deterministic():  # LAY-05
    a, b = _run(_graph(ORDER, ORDER_EDGES)), _run(_graph(ORDER, ORDER_EDGES))
    assert a.boxes == b.boxes and a.routes == b.routes


def test_no_edges_is_one_rank_in_declaration_order():  # LAY-06
    res = _run(_graph(["a", "b", "c"], []))
    ys = {res.boxes[n][1] for n in "abc"}
    assert len(ys) == 1
    assert res.boxes["a"][0] < res.boxes["b"][0] < res.boxes["c"][0]


def test_cycle_edge_drawn_in_original_direction():  # LAY-07
    edges = ORDER_EDGES + [("backorder", "receive")]
    res = _run(_graph(ORDER, edges))
    pts = res.routes["e6"]
    bx, by, bw, bh = res.boxes["backorder"]
    rx, ry, rw, rh = res.boxes["receive"]
    assert abs(pts[0][1] - by) < 0.6 and bx - 0.5 <= pts[0][0] <= bx + bw + 0.5  # leaves backorder (top)
    assert abs(pts[-1][1] - (ry + rh)) < 0.6 and rx - 0.5 <= pts[-1][0] <= rx + rw + 0.5  # enters receive (bottom)


def test_routes_are_orthogonal_and_avoid_boxes():  # LAY-08, LAY-11
    edges = ORDER_EDGES + [("backorder", "receive"), ("start", "done")]
    res = _run(_graph(ORDER, edges))
    for eid, pts in res.routes.items():
        for p, q in zip(pts, pts[1:]):
            assert abs(p[0] - q[0]) < 1e-6 or abs(p[1] - q[1]) < 1e-6, (eid, p, q)
            for n in ORDER:
                assert not _seg_hits_box(p, q, res.boxes[n]), (eid, n, p, q)


def test_long_back_edge_goes_round_the_outer_side():  # LAY-08
    edges = ORDER_EDGES + [("done", "receive")]
    res = _run(_graph(ORDER, edges))
    right = max(res.boxes[n][0] + res.boxes[n][2] for n in ORDER)
    assert max(x for x, _ in res.routes["e6"]) > right


def test_parallel_edges_get_separate_routes():  # LAY-10
    res = _run(_graph(["a", "b"], [("a", "b"), ("a", "b")]))
    assert res.routes["e0"] != res.routes["e1"]
    assert res.routes["e0"][0] != res.routes["e1"][0]


def test_decision_edges_leave_distinct_ports():  # LAY-13
    res = _run(_graph(ORDER, ORDER_EDGES, kinds={"stock": "decision"}))
    assert res.routes["e2"][0] != res.routes["e3"][0]


def test_components_side_by_side_in_declaration_order():  # LAY-21
    res = _run(_graph(["a", "b", "c", "d"], [("a", "b"), ("c", "d")]))
    assert res.boxes["a"][0] + res.boxes["a"][2] <= res.boxes["c"][0]
    assert res.boxes["b"][0] + res.boxes["b"][2] <= res.boxes["d"][0]


def test_large_graph_warns_but_completes():  # LAY-22
    names = [f"n{i}" for i in range(301)]
    g = _graph(names, [(names[i], names[i + 1]) for i in range(0, 300, 2)])
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        res = _run(g)
    assert any("300" in str(x.message) for x in w)
    assert len([k for k in res.boxes if k.startswith("n")]) == 301


# T3: obstacle router ----------------------------------------------------------------------------
from spinagram.autolayout.route import loop, route  # noqa: E402


def _on_border(pt, box, tol=0.6):
    x, y, w, h = box
    px, py = pt
    on_v = (abs(px - x) < tol or abs(px - x - w) < tol) and y - tol <= py <= y + h + tol
    on_h = (abs(py - y) < tol or abs(py - y - h) < tol) and x - tol <= px <= x + w + tol
    return on_v or on_h


def test_router_avoids_obstacles_and_is_orthogonal():  # LAY-17
    src, dst = (0, 0, 100, 60), (400, 300, 100, 60)
    walls = [(150, -100, 60, 400), (250, 200, 300, 40)]
    pts = route(src, dst, walls + [src, dst])
    assert _on_border(pts[0], src) and _on_border(pts[-1], dst)
    for p, q in zip(pts, pts[1:]):
        assert abs(p[0] - q[0]) < 1e-6 or abs(p[1] - q[1]) < 1e-6
        for b in walls + [src, dst]:
            assert not _seg_hits_box(p, q, b), (p, q, b)


def test_router_straight_when_unobstructed():  # LAY-11 (no needless bends)
    pts = route((0, 0, 100, 60), (0, 200, 100, 60), [])
    assert len(pts) == 2 and pts[0][0] == pts[1][0]


def test_self_loop_leaves_and_reenters_one_side():  # LAY-09
    box = (100, 100, 160, 80)
    pts = loop(box, "right")
    assert pts[0][0] == pts[-1][0] == 260
    assert pts[0][1] != pts[-1][1]
    assert max(x for x, _ in pts) > 260
    for p, q in zip(pts, pts[1:]):
        assert not _seg_hits_box(p, q, box)


# T4: groups, lanes, loops, cross-block edges ----------------------------------------------------
def _inside(inner, outer, tol=0.5):
    ix, iy, iw, ih = inner
    ox, oy, ow, oh = outer
    return ix >= ox - tol and iy >= oy - tol and ix + iw <= ox + ow + tol and iy + ih <= oy + oh + tol


def _grouped():
    """a → [b → c] (group g) → d, plus an edge from outside into the group's second node."""
    g = LGroup("g", [LNode("b", 160, 80), LNode("c", 160, 80)], pad=(50, 20, 20, 20))
    root = LGroup("__root__", [LNode("a", 160, 80), g, LNode("d", 160, 80)])
    edges = [LEdge("e0", "a", "b"), LEdge("e1", "b", "c"), LEdge("e2", "c", "d"), LEdge("e3", "a", "c")]
    return LGraph(root, edges, "down", {"gap": 40, "node_gap": 48, "rank_gap": 80})


def test_group_members_inside_and_others_outside():  # LAY-15
    res = _run(_grouped())
    g = res.boxes["g"]
    assert _inside(res.boxes["b"], g) and _inside(res.boxes["c"], g)
    assert min(res.boxes["b"][1], res.boxes["c"][1]) - g[1] >= 50 - 0.5  # label band kept free
    for n in ("a", "d"):
        assert not _overlap(res.boxes[n], g)


def test_cross_group_edges_routed_without_crossing_nodes():  # LAY-17
    res = _run(_grouped())
    for eid in ("e0", "e2", "e3"):
        pts = res.routes[eid]
        for p, q in zip(pts, pts[1:]):
            assert abs(p[0] - q[0]) < 1e-6 or abs(p[1] - q[1]) < 1e-6
            for n in "abcd":
                assert not _seg_hits_box(p, q, res.boxes[n]), (eid, n)
    assert _on_border(res.routes["e3"][0], res.boxes["a"]) and _on_border(res.routes["e3"][-1], res.boxes["c"])


def _lanes(direction="down", empty=False):
    lanes = [LGroup("L1", [LNode("a", 160, 80), LNode("c", 160, 80)], pad=(50, 16, 16, 16)),
             LGroup("L2", [LNode("b", 160, 80)], pad=(50, 16, 16, 16))]
    if empty:
        lanes.append(LGroup("L3", [], pad=(50, 16, 16, 16)))
    act = LGroup("act", lanes, pad=(20, 20, 20, 20), hints={"lanes": True})
    edges = [LEdge("e0", "a", "b"), LEdge("e1", "b", "c")]
    return LGraph(LGroup("__root__", [act]), edges, direction, {"gap": 40, "node_gap": 48, "rank_gap": 80})


@pytest.mark.parametrize("direction", ["down", "right"])
def test_lanes_are_disjoint_full_span_bands(direction):  # LAY-16
    res = _run(_lanes(direction))
    l1, l2 = res.boxes["L1"], res.boxes["L2"]
    assert _inside(res.boxes["a"], l1) and _inside(res.boxes["c"], l1) and _inside(res.boxes["b"], l2)
    assert not _overlap(l1, l2)
    if direction == "down":  # vertical bands side by side, same top and height
        assert l1[0] + l1[2] <= l2[0] + 0.5 and l1[1] == l2[1] and l1[3] == l2[3]
    else:  # horizontal bands stacked
        assert l1[1] + l1[3] <= l2[1] + 0.5 and l1[0] == l2[0] and l1[2] == l2[2]
    # ranks are shared across lanes: b sits between a and c along the flow
    ax = 1 if direction == "down" else 0
    assert res.boxes["a"][ax] < res.boxes["b"][ax] < res.boxes["c"][ax]


def test_empty_lane_still_drawn_200px():  # BHV-34 (layout side)
    res = _run(_lanes(empty=True))
    assert res.boxes["L3"][2] >= 200


def test_self_loop_routed_beside_its_node():  # LAY-09
    g = _graph(["a", "b"], [("a", "b")], loops=["b"])
    res = _run(g)
    pts = res.routes["l0"]
    bx, by, bw, bh = res.boxes["b"]
    assert pts[0][0] == pts[-1][0] == bx + bw
    for p, q in zip(pts, pts[1:]):
        for n in "ab":
            assert not _seg_hits_box(p, q, res.boxes[n])


# T5: per-group engines in apply_layout ----------------------------------------------------------
from spinagram.autolayout import apply_layout  # noqa: E402


def _region_diagram():
    d = Diagram("r", "Regions", layout={"engine": "flex", "direction": "right"})
    x = d.box("Client")
    with d.group("Flow", id="flow", engine="layered", direction="down"):
        a, b, c = d.box("A"), d.box("B"), d.box("C")
    a >> b >> c
    d.edge(x, b, "calls")
    d.edge(x.bottom, c.top)  # anchored by the author
    return d


def test_region_laid_out_by_its_own_engine():  # BHV-24 / LAY-17 (layout side)
    out = apply_layout(_region_diagram(), _theme())
    n = {k.id: k for k in out.nodes}
    assert n["a"].y + n["a"].h < n["b"].y and n["b"].y + n["b"].h < n["c"].y  # ranked down
    zone = next(z for z in out.zones if z.label == "Flow")
    for k in "abc":
        assert _inside((n[k].x, n[k].y, n[k].w, n[k].h), (zone.x, zone.y, zone.w, zone.h))
    assert n["client"].x + n["client"].w <= zone.x  # flex parent places the region as one box


def test_crossing_edge_rerouted_and_anchored_edge_kept():  # LAY-14, LAY-17
    out = apply_layout(_region_diagram(), _theme())
    crossing = out.edges[2]
    assert crossing.src.startswith("client.") and crossing.dst.startswith("b.")
    anchored = out.edges[3]
    assert anchored.src == "client.bottom" and anchored.dst == "c.top" and not anchored.via


def test_self_loop_bound_as_via():  # LAY-09 (binding)
    d = Diagram("s", "Loop", layout={"engine": "layered", "direction": "down"})
    a, b = d.box("A"), d.box("B")
    a >> b
    d.edge(b, b, "retry")
    out = apply_layout(d, _theme())
    e = out.edges[1]
    assert e.src.startswith("b.right") and e.dst.startswith("b.right") and e.via and len(e.via) == 2

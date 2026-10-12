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


# T6: labels -------------------------------------------------------------------------------------
from spinagram.text import measure  # noqa: E402


def _order_flow(direction="down"):
    d = Diagram("f", "Order flow", layout={"engine": "layered", "direction": direction})
    s, a, ok = d.box("Start"), d.box("Receive order"), d.diamond("In stock?")
    ship, bo, done = d.box("Ship"), d.box("Backorder"), d.box("Done")
    s >> a >> ok
    ok.to(ship, "yes")
    ok.to(bo, "no")
    [ship, bo] >> done
    bo.to(a, "retry with supplier")
    d.edge(bo, bo, "wait a day")
    return d


def _pill_box(e, th):
    size = e.label_size or th.defaults("edge").get("label_size", 17)
    w = measure(e.label, th.font("body", 700, size)) + 24
    lx, ly = e.label_at
    return (lx - w / 2, ly - size - 3, w, size + 14)


def test_label_pills_avoid_node_boxes():  # LAY-12
    th = _theme()
    out = apply_layout(_order_flow(), th)
    boxes = [(n.x, n.y, n.w, n.h) for n in out.nodes]
    pills = [_pill_box(e, th) for e in out.edges if e.label]
    assert len(pills) == 4
    for p in pills:
        for b in boxes:
            assert not _overlap(p, b), (p, b)
    for i, p in enumerate(pills):
        for q in pills[i + 1:]:
            assert not _overlap(p, q)
    for e in out.edges:
        if e.label:
            assert _gap_to_route(_pill_box(e, th), _route_pts(out, e)) <= 6.5, e.label


def test_rank_gap_grows_with_label_width_only_across_the_flow():  # LAY-03 with labels
    long = Diagram("g", "t", layout={"engine": "layered", "direction": "down"})
    a, b = long.box("a"), long.box("b")
    long.edge(a, b, "a very long label that is wider than eighty pixels")
    g, _ = build_graph(long, _theme())
    assert g.spacing["rank_gap"] == 80
    long.layout["direction"] = "right"
    g, _ = build_graph(long, _theme())
    assert g.spacing["rank_gap"] > 80


def test_overflow_still_reported():  # LAY-20
    from spinagram.api import scenes
    from spinagram.qa import check
    d = Diagram("big", "Too tall", layout={"engine": "layered", "direction": "down"})
    prev = d.box("n0")
    for i in range(1, 12):
        cur = d.box(f"n{i}")
        prev >> cur
        prev = cur
    assert any(i.kind == "overflow" for i in check(scenes([d])[0]))


# verifier gaps (validation.md, iteration 1) -----------------------------------------------------
import json  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402


def test_adjacent_back_edge_stays_in_the_gap():  # LAY-08 (adjacent ranks)
    res = _run(_graph(["a", "b"], [("a", "b"), ("b", "a")]))
    a, b = res.boxes["a"], res.boxes["b"]
    pts = res.routes["e1"]
    assert abs(pts[0][1] - b[1]) < 0.6 and abs(pts[-1][1] - (a[1] + a[3])) < 0.6  # b top → a bottom
    for x, y in pts[1:-1]:
        assert a[1] + a[3] - 0.5 <= y <= b[1] + 0.5  # every bend inside the gap
    lo = min(a[0], b[0])
    hi = max(a[0] + a[2], b[0] + b[2])
    assert all(lo - 0.5 <= x <= hi + 0.5 for x, _ in pts)  # not sent round the outside


_SEED_SCRIPT = """
import json, sys
sys.path.insert(0, {tests!r})
from test_layered import _graph, _run, ORDER, ORDER_EDGES
g = _graph(ORDER + ["x", "y"], ORDER_EDGES + [("backorder", "receive"), ("x", "y"), ("y", "x")])
r = _run(g)
print(json.dumps([sorted(r.boxes.items()), sorted(r.routes.items())]))
"""


def test_deterministic_across_hash_seeds():  # LAY-05 (across runs, not only within one process)
    outs = []
    for seed in ("1", "2", "3"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        script = _SEED_SCRIPT.format(tests=os.path.dirname(__file__))
        outs.append(subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True,
                                   check=True).stdout)
    assert outs[0] == outs[1] == outs[2]
    assert json.loads(outs[0])


@pytest.mark.parametrize("direction", ["down", "right"])
def test_routes_inside_lanes_are_orthogonal_and_avoid_nodes(direction):  # LAY-16, LAY-17
    g = _lanes(direction)
    g.edges.append(LEdge("e2", "a", "c"))  # same lane, skips a rank
    res = _run(g)
    for eid in ("e0", "e1", "e2"):
        pts = res.routes[eid]
        for p, q in zip(pts, pts[1:]):
            assert abs(p[0] - q[0]) < 1e-6 or abs(p[1] - q[1]) < 1e-6, eid
            for n in "abc":
                assert not _seg_hits_box(p, q, res.boxes[n]), (eid, n)
    for eid, a, b in (("e0", "a", "b"), ("e1", "b", "c"), ("e2", "a", "c")):
        assert _on_border(res.routes[eid][0], res.boxes[a]), (direction, eid)
        assert _on_border(res.routes[eid][-1], res.boxes[b]), (direction, eid)


def test_self_loop_clears_same_rank_neighbour_and_its_label_sits_beside_it():  # LAY-09
    d = Diagram("s", "Loop", layout={"engine": "layered", "direction": "down"})
    a, b, c = d.box("A"), d.box("B"), d.box("C")
    a >> b
    a >> c
    d.edge(b, b, "retry later")
    th = _theme()
    out = apply_layout(d, th)
    n = {k.id: (k.x, k.y, k.w, k.h) for k in out.nodes}
    loop_e = out.edges[2]
    xs = [x for x, _ in loop_e.via]
    for (x1, y1), (x2, y2) in zip(loop_e.via, loop_e.via[1:]):
        assert not _seg_hits_box((x1, y1), (x2, y2), n["c"]) and not _seg_hits_box((x1, y1), (x2, y2), n["b"])
    pill = _pill_box(loop_e, th)
    for box in n.values():
        assert not _overlap(pill, box)
    assert pill[0] >= min(xs) - 0.5  # beside the loop, on its outer side (never over the node)
    assert abs(pill[1] + pill[3] / 2 - (loop_e.via[0][1] + loop_e.via[1][1]) / 2) < pill[3]  # level with the loop
    assert _gap_to_route(pill, _route_pts(out, loop_e)) <= 6.5


def test_parallel_edges_get_separate_non_overlapping_labels():  # LAY-10, LAY-12
    th = _theme()
    d = Diagram("p", "Parallel", layout={"engine": "layered", "direction": "down"})
    a, b = d.box("A"), d.box("B")
    d.edge(a, b, "request")
    d.edge(a, b, "retry")
    out = apply_layout(d, th)
    p1, p2 = _pill_box(out.edges[0], th), _pill_box(out.edges[1], th)
    assert out.edges[0].label_at != out.edges[1].label_at
    assert not _overlap(p1, p2)
    assert _gap_to_route(p1, _route_pts(out, out.edges[0])) <= 6.5
    assert _gap_to_route(p2, _route_pts(out, out.edges[1])) <= 6.5


def test_overflow_reports_the_excess_in_px():  # LAY-20
    from spinagram.api import scenes
    from spinagram.qa import check
    d = Diagram("big", "Too tall", layout={"engine": "layered", "direction": "down"})
    prev = d.box("n0")
    for i in range(1, 12):
        cur = d.box(f"n{i}")
        prev >> cur
        prev = cur
    sc = scenes([d])[0]
    over = sc.layout_overflow
    assert over and over[1] > 0
    issue = next(i for i in check(sc) if i.kind == "overflow")
    assert f"{over[1]}px tall" in issue.detail


def _route_pts(out, e):
    """Polyline of a laid-out edge: anchor points from node sides plus its via."""
    boxes = {n.id: (n.x, n.y, n.w, n.h) for n in out.nodes}

    def anchor(ref):
        nid, _, side = ref.partition(".")
        side, _, frac = side.partition("@")
        x, y, w, h = boxes[nid]
        f = float(frac) if frac else 0.5
        return {"left": (x, y + h * f), "right": (x + w, y + h * f), "top": (x + w * f, y),
                "bottom": (x + w * f, y + h)}.get(side, (x + w / 2, y + h / 2))

    return [anchor(e.src), *(e.via or []), anchor(e.dst)]


def _gap_to_route(box, pts):
    """Smallest distance between a box and any segment of the route (0 when they touch)."""
    x, y, w, h = box
    best = float("inf")
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        sx0, sx1, sy0, sy1 = min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2)
        dx = max(0.0, x - sx1, sx0 - (x + w))
        dy = max(0.0, y - sy1, sy0 - (y + h))
        best = min(best, (dx * dx + dy * dy) ** 0.5)
    return best


GOLDEN = "8fb4d9b2873e6bb703027e991f826d526f5f186b78ab0d7bf3e49cc777309288"


def test_layout_matches_frozen_golden():  # LAY-05 (identical on every run, seed and Python version)
    import hashlib
    g = _graph(ORDER + ["x", "y"], ORDER_EDGES + [("backorder", "receive"), ("x", "y"), ("y", "x")],
               kinds={"stock": "decision"}, loops=["ship"])
    r = _run(g)
    blob = json.dumps([sorted(r.boxes.items()), sorted(r.routes.items())])
    assert hashlib.sha256(blob.encode()).hexdigest() == GOLDEN

"""Behavior diagrams: symbols, builders, regions (spec: .specs/features/behavior-diagrams/spec.md)."""
from __future__ import annotations

import pytest

from spinagram import shapes

KINDS = ["terminator", "process", "decision", "io", "document", "predefined", "data", "connector", "initial",
         "final", "flow_final", "fork", "join", "merge", "choice", "history", "deep_history", "state", "action",
         "object", "signal_send", "signal_receive"]  # BHV-01 (note keeps its existing renderer)
PSEUDO = ["initial", "final", "flow_final", "fork", "join", "choice", "history"]


def _coords(d: str):
    nums = [float(t) for t in d.replace(",", " ").split() if t not in "MLCZ" and t.strip()]
    return list(zip(nums[0::2], nums[1::2]))


# T1: geometry library ---------------------------------------------------------------------------
@pytest.mark.parametrize("kind", KINDS)
def test_every_kind_has_geometry_inside_its_box(kind):  # BHV-01, BHV-02
    x, y, w, h = 100.0, 50.0, 200.0, 120.0
    parts = shapes.parts(kind, x, y, w, h)
    assert parts and all(p.paint in ("shape", "solid", "stroke") for p in parts)
    for p in parts:
        for px, py in _coords(p.d):
            assert x - 0.5 <= px <= x + w + 0.5 and y - 0.5 <= py <= y + h + 0.5, (kind, px, py)
    tx, ty, tw, th = shapes.text_box(kind, x, y, w, h)
    assert x - 0.5 <= tx and y - 0.5 <= ty and tx + tw <= x + w + 0.5 and ty + th <= y + h + 0.5
    assert kind in shapes.KINDS


def test_symbol_paints():  # BHV-02 (shape table)
    assert [p.paint for p in shapes.parts("initial", 0, 0, 24, 24)] == ["solid"]
    assert [p.paint for p in shapes.parts("final", 0, 0, 32, 32)] == ["stroke", "solid"]
    assert [p.paint for p in shapes.parts("fork", 0, 0, 140, 8)] == ["solid"]
    assert [p.paint for p in shapes.parts("flow_final", 0, 0, 28, 28)] == ["shape", "stroke"]


@pytest.mark.parametrize("kind", PSEUDO)
def test_pseudostates_have_fixed_sizes(kind):  # BHV-05
    assert shapes.fixed_size(kind) is not None


def test_fixed_size_values():  # BHV-02 sizes from the shape table
    assert shapes.fixed_size("initial") == (24, 24)
    assert shapes.fixed_size("final") == (32, 32)
    assert shapes.fixed_size("fork") == (140, 8)
    assert shapes.fixed_size("fork", vertical=True) == (8, 140)
    assert shapes.fixed_size("state") is None


@pytest.mark.parametrize("kind", KINDS)
def test_every_kind_has_a_pptx_plan(kind):  # BHV-03 plan
    plan = shapes.pptx_plan(kind)
    assert plan in ("freeform", "group") or plan.isupper()


def test_path_parser_round_trip():
    subs = shapes.parse("M 0 0 L 10 0 C 10 5 5 10 0 10 Z M 1 1 L 2 2")
    assert subs[0].closed and not subs[1].closed
    assert subs[0].start == (0, 0)
    assert subs[0].segments[1] == ("C", [(10, 5), (5, 10), (0, 10)])


# T2: sizing -------------------------------------------------------------------------------------
from spinagram.autolayout.sizing import auto_size  # noqa: E402
from spinagram.model import Node  # noqa: E402
from spinagram.text import measure, wrap_paragraphs  # noqa: E402
from spinagram.theme import Theme  # noqa: E402


def _th():
    return Theme.load(None)


@pytest.mark.parametrize("kind", PSEUDO)
def test_untitled_pseudostates_use_symbol_sizes(kind):  # BHV-05
    assert auto_size(Node(id="p", kind=kind), _th()) == shapes.fixed_size(kind)


def test_vertical_fork_for_horizontal_flows():  # BHV-05
    assert auto_size(Node(id="f", kind="fork", extra={"orient": "v"}), _th()) == (8, 140)


@pytest.mark.parametrize("kind", ["terminator", "process", "io", "document", "data", "state", "action",
                                  "object", "signal_send", "signal_receive", "predefined", "decision"])
def test_titled_symbols_fit_their_text_box(kind):  # BHV-02 text inside shape
    th = _th()
    n = Node(id="s", kind=kind, title="Validate payment details", text="Checks card, address and fraud score")
    w, h = auto_size(n, th)
    tx, ty, tw, tht = shapes.text_box(kind, 0, 0, w, h)
    nd = th.defaults("node")
    tf = th.font("heading", 700, nd.get("title_size", 24))
    bf = th.font("body", 400, nd.get("body_size", 18))
    avail = tw - 2 * 12
    lines_t = wrap_paragraphs([n.title], tf, avail)
    lines_b = wrap_paragraphs([n.text], bf, avail)
    assert all(measure(t, tf) <= avail + 1 for t in lines_t)
    total = len(lines_t) * tf.size * nd.get("title_leading", 1.15) + len(lines_b) * bf.size * nd.get(
        "body_leading", 1.32) + nd.get("title_body_gap", 10)
    assert total <= tht - 2 * 12 + 1


# T3: scene --------------------------------------------------------------------------------------
from spinagram import Diagram  # noqa: E402
from spinagram.api import scenes  # noqa: E402
from spinagram.qa import check  # noqa: E402
from spinagram.scene import Shape  # noqa: E402

TITLED = {"terminator", "process", "decision", "io", "document", "predefined", "data", "state", "action",
          "object", "signal_send", "signal_receive"}


def _all_kinds_diagram():
    d = Diagram("k", "Kinds", layout={"engine": "layered", "direction": "right"})
    for k in KINDS:
        title = k.replace("_", " ").title() if k in TITLED else ("H" if k == "history" else
                                                              "H*" if k == "deep_history" else None)
        d.add(k, title, id=k)
    return d


def test_scene_symbols_carry_parts_and_text_inside():  # BHV-02
    sc = scenes([_all_kinds_diagram()])[0]
    shapes_by_id = {s.id: s for s in sc.items if isinstance(s, Shape)}
    for k in KINDS:
        s = shapes_by_id[k]
        assert s.kind == k
        assert [p.d for p in s.parts] == [p.d for p in shapes.parts(k, s.x, s.y, s.w, s.h)]
        if s.label:
            tx, ty, tw, th = shapes.text_box(k, s.x, s.y, s.w, s.h)
            lx, ly, lw, lh = s.label.box
            assert lx >= tx - 0.5 and ly >= ty - 0.5 and lx + lw <= tx + tw + 0.5 and ly + lh <= ty + th + 0.5


def test_default_sized_symbols_have_no_overflow():  # BHV-02 / BHV-05
    sc = scenes([_all_kinds_diagram()])[0]
    assert [i for i in check(sc) if i.kind.startswith("overflow-")] == []


def test_round_symbols_anchor_on_their_outline():
    sc = scenes([_all_kinds_diagram()])[0]
    s = next(i for i in sc.items if isinstance(i, Shape) and i.id == "initial")
    assert s.anchor("left", 0.2) == (s.x, s.y + s.h / 2)


# T4: SVG ----------------------------------------------------------------------------------------
import re  # noqa: E402

from spinagram.backends.svg import to_svg  # noqa: E402


def _paths(svg: str) -> dict[str, str]:
    """path d → the full element."""
    return {m.group(1): m.group(0) for m in re.finditer(r'<path d="([^"]+)"[^>]*/?>', svg)}


def test_svg_draws_every_part_with_its_paint():  # BHV-02
    sc = scenes([_all_kinds_diagram()])[0]
    svg = to_svg(sc)
    paths = _paths(svg)
    for s in (i for i in sc.items if isinstance(i, Shape) and i.parts):
        for p in s.parts:
            el = paths[p.d]
            if p.paint == "solid":
                assert f'fill="{s.stroke}"' in el
            elif p.paint == "stroke":
                assert 'fill="none"' in el and f'stroke="{s.stroke}"' in el
            else:
                assert f'fill="{s.fill}"' in el and f'stroke="{s.stroke}"' in el


# T5: PowerPoint ---------------------------------------------------------------------------------
PRST = {"terminator": "flowChartTerminator", "process": "rect", "decision": "diamond", "io": "flowChartInputOutput",
        "document": "flowChartDocument", "predefined": "flowChartPredefinedProcess", "data": "can",
        "connector": "ellipse", "initial": "ellipse", "flow_final": "flowChartSummingJunction", "fork": "rect",
        "join": "rect", "merge": "diamond", "choice": "diamond", "history": "ellipse", "deep_history": "ellipse",
        "state": "roundRect", "action": "roundRect", "object": "rect", "signal_send": "homePlate"}


def _pptx_shapes(tmp_path):
    pptx = pytest.importorskip("pptx")
    from spinagram import render
    render([_all_kinds_diagram()], tmp_path, formats=["pptx"])
    slide = pptx.Presentation(str(tmp_path / "diagrams.pptx")).slides[0]
    return {sh.name: sh for sh in slide.shapes}


def test_pptx_uses_preset_geometry_per_kind(tmp_path):  # BHV-03
    by_name = _pptx_shapes(tmp_path)
    for kind, prst in PRST.items():
        geom = by_name[kind]._element.spPr.find(
            "{http://schemas.openxmlformats.org/drawingml/2006/main}prstGeom")
        assert geom is not None and geom.get("prst") == prst, kind


def test_pptx_final_is_a_group_of_two_ovals(tmp_path):  # BHV-03
    grp = _pptx_shapes(tmp_path)["final (group)"]
    prsts = [s._element.spPr.prstGeom.get("prst") for s in grp.shapes]
    assert prsts == ["ellipse", "ellipse"]


def test_pptx_signal_receive_is_a_freeform_with_text(tmp_path):  # BHV-03
    sh = _pptx_shapes(tmp_path)["signal_receive"]
    assert sh._element.spPr.find("{http://schemas.openxmlformats.org/drawingml/2006/main}custGeom") is not None
    assert sh.text_frame.text == "Signal Receive"


def test_pptx_text_inside_titled_symbols(tmp_path):  # BHV-03
    by_name = _pptx_shapes(tmp_path)
    assert by_name["state"].text_frame.text == "State"
    assert by_name["history"].text_frame.text == "H"


# T6: Figma --------------------------------------------------------------------------------------
import json as _json  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
from pathlib import Path  # noqa: E402

from spinagram.backends.figma import FigmaBackend  # noqa: E402

MOCK = Path(__file__).parent / "js" / "figma_mock.mjs"


def _vec_calls(js: str) -> dict[str, list[dict]]:
    """name → vector networks passed to vec(name, x, y, net, o)."""
    out: dict[str, list[dict]] = {}
    for m in re.finditer(r'await vec\("([^"]+)", [-\d.]+, [-\d.]+, (\{.*?\}), (\{.*?\})\);', js):
        out.setdefault(m.group(1), []).append({"net": _json.loads(m.group(2)), "o": _json.loads(m.group(3))})
    return out


def test_figma_draws_every_part_as_a_vector(tmp_path):  # BHV-04
    sc = scenes([_all_kinds_diagram()])[0]
    files = FigmaBackend().render([sc], tmp_path)
    js = "\n".join(p.read_text() for p in files if p.suffix == ".js")
    calls = _vec_calls(js)
    for s in (i for i in sc.items if isinstance(i, Shape) and i.parts):
        got = calls[s.id]
        assert len(got) == len(s.parts), s.id
        for part, call in zip(s.parts, got):
            closed = any(sub.closed for sub in shapes.parse(part.d))
            if part.paint == "stroke":
                assert "fill" not in call["o"] and call["o"]["stroke"] == s.stroke
            else:
                assert call["o"]["fill"] == (s.stroke if part.paint == "solid" else s.fill)
                assert ("regions" in call["net"]) == closed
    curved = calls["initial"][0]["net"]["segments"]
    assert any("tangentStart" in seg for seg in curved)  # circles keep their curves


def test_figma_symbol_script_runs_on_mock(tmp_path):  # BHV-04
    node = shutil.which("node") or shutil.which("bun")
    if not node:
        pytest.skip("node/bun not installed")
    sc = scenes([_all_kinds_diagram()])[0]
    files = [p for p in FigmaBackend().render([sc], tmp_path) if p.suffix == ".js"]
    for f in files:
        r = subprocess.run([node, str(MOCK), str(f)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr


# T7: Flowchart ----------------------------------------------------------------------------------
from spinagram.autolayout import apply_layout  # noqa: E402
from spinagram.behavior import Activity, Flowchart, StateMachine  # noqa: E402,F401


def test_flowchart_verbs_create_kinds():  # BHV-06
    fc = Flowchart("F1", "Checkout")
    nodes = [fc.start(), fc.process("Pay"), fc.decision("OK?"), fc.io("Read card"), fc.document("Receipt"),
             fc.end()]
    assert [n.kind for n in nodes] == ["terminator", "process", "decision", "io", "document", "terminator"]
    assert nodes[0].title == "Start" and nodes[-1].title == "End"


def test_decision_yes_no_labels_and_distinct_sides():  # BHV-07
    fc = Flowchart("F1", "Checkout")
    ok = fc.decision("OK?")
    a, b = fc.process("Ship"), fc.process("Refund")
    ok.yes(a)
    ok.no(b)
    ok.to(fc.end(), "Maybe")
    assert [e.label for e in fc.edges] == ["Yes", "No", "Maybe"]
    out = apply_layout(fc, _th())
    starts = {e.src for e in out.edges}
    assert len(starts) == 3  # three distinct ports on the decision


def test_flowchart_defaults_to_layered_down():  # BHV-08
    fc = Flowchart("F1", "Checkout")
    assert fc.layout == {"engine": "layered", "direction": "down"}
    assert Flowchart("F2", "x", direction="right").layout["direction"] == "right"


def test_edges_out_of_finals_rejected():  # BHV-31
    sm = StateMachine("S1", "x")
    s = sm.state("Done")
    with pytest.raises(ValueError, match="final node final cannot have outgoing edges"):
        sm.final >> s


def test_edges_into_initials_rejected():  # BHV-32
    sm = StateMachine("S1", "x")
    s = sm.state("Idle")
    with pytest.raises(ValueError, match="initial node initial cannot have incoming edges"):
        s >> sm.initial


def test_on_composes_transition_labels():  # BHV-11 helper
    sm = StateMachine("S1", "x")
    a, b = sm.state("Idle"), sm.state("Busy")
    a.on("click", b, guard="enabled", action="beep")
    a.on("tick", b)
    b.on("done", a, action="log")
    assert [e.label for e in sm.edges] == ["click [enabled] / beep", "tick", "done / log"]


# T8: StateMachine -------------------------------------------------------------------------------
def _lifecycle():
    sm = StateMachine("S1", "Order lifecycle")
    created = sm.state("Created", entry="reserve stock")
    paid = sm.state("Paid", do="notify warehouse", exit="log")
    cancelled = sm.state("Cancelled")
    sm.initial >> created
    created.on("pay", paid, guard="amount ok", action="capture")
    created.on("cancel", cancelled)
    paid.on("cancel", cancelled, action="refund")
    paid.on("retry", paid)
    with sm.composite("Fulfilment") as f:
        with f.region() as picking:
            pick = picking.state("Picking")
            picking.initial >> pick
        with f.region() as billing:
            bill = billing.state("Invoicing")
            billing.initial >> bill
        hist = f.history()
    paid.on("ship", pick)
    choice = sm.choice()
    bill >> choice
    choice.to(sm.final, "[delivered]")
    cancelled >> sm.final
    return sm, dict(created=created, paid=paid, cancelled=cancelled, pick=pick, bill=bill, hist=hist,
                    choice=choice)


def test_state_entry_do_exit_lines():  # BHV-10
    _, n = _lifecycle()
    assert n["created"].kind == "state" and n["created"].lines == ["entry / reserve stock"]
    assert n["paid"].lines == ["do / notify warehouse", "exit / log"]


def test_transition_labels():  # BHV-11
    sm, _ = _lifecycle()
    labels = [e.label for e in sm.edges]
    assert "pay [amount ok] / capture" in labels and "cancel / refund" in labels and "cancel" in labels


def test_initial_and_final_one_per_region():  # BHV-12
    sm, n = _lifecycle()
    kinds = [x.kind for x in sm.nodes]
    assert kinds.count("final") == 1
    assert kinds.count("initial") == 3  # machine + two orthogonal regions
    assert sm.edges[0].src == "initial" and sm.edges[0].dst == "created"


def test_composite_contains_substates_and_has_state_style():  # BHV-13
    sm, n = _lifecycle()
    comp = next(g for g in sm.groups if g.label == "Fulfilment")
    assert comp.style == "state"
    regions = [g for g in sm.groups if g.id in comp.children]
    assert [g.style for g in regions] == ["region", "region"]  # BHV-14 (dashed boxes, see design deviation)
    assert "picking" in regions[0].children and "invoicing" in regions[1].children
    assert n["hist"].id in comp.children


def test_choice_and_history_kinds():  # BHV-15
    _, n = _lifecycle()
    assert n["choice"].kind == "choice"
    assert n["hist"].kind == "history" and n["hist"].title == "H"
    sm = StateMachine("S2", "x")
    with sm.composite("C") as c:
        deep = c.history(deep=True)
    assert deep.kind == "deep_history" and deep.title == "H*"


def test_lifecycle_lays_out_and_renders_with_containment():  # BHV-13, BHV-17
    sm, n = _lifecycle()
    out = apply_layout(sm, _th())
    zone = next(z for z in out.zones if z.label == "Fulfilment")
    pick = out.node("picking")
    assert zone.x <= pick.x and pick.x + pick.w <= zone.x + zone.w
    retry = next(e for e in out.edges if e.label == "retry")
    assert retry.src.startswith("paid.") and retry.dst.startswith("paid.") and retry.via  # self-transition loop
    sc = scenes([sm])[0]
    assert sc.items


def test_edge_labels_keep_group_labels_clear():  # LAY-12 with zones (found rendering BHV-13)
    from spinagram.text import measure as _m
    sm, _ = _lifecycle()
    th = _th()
    out = apply_layout(sm, th)
    zone = next(z for z in out.zones if z.label == "Fulfilment")
    lf = th.font("body", 700, th.defaults("zone").get("label_size", 16))
    band = (zone.x, zone.y, _m("Fulfilment", lf) + 48, 36)
    size = th.defaults("edge").get("label_size", 17)
    for e in out.edges:
        if e.label and e.label_at:
            w = _m(e.label, th.font("body", 700, size)) + 24
            lx, ly = e.label_at
            pill = (lx - w / 2, ly - size - 3, w, size + 14)
            px, py, pw, ph = pill
            bx, by, bw, bh = band
            assert not (px < bx + bw and bx < px + pw and py < by + bh and by < py + ph), e.label


# T9: Activity -----------------------------------------------------------------------------------
def _fulfilment(direction="down"):
    act = Activity("A1", "Order fulfilment", direction=direction)
    with act.sequence():
        with act.lane("Customer"):
            start = act.start()
            order = act.action("Place order")
        with act.lane("Shop"):
            check = act.action("Check stock")
            with act.parallel() as par:
                with par.branch():
                    pick = act.action("Pick items")
                    pack = act.action("Pack")
                with par.branch():
                    bill = act.action("Send invoice")
        with act.lane("Warehouse"):
            ship = act.send("Ship parcel")
            end = act.end()
    act.lane("Audit")  # declared, never used
    slip = act.object("Packing slip")
    pack >> slip
    return act, dict(start=start, order=order, check=check, pick=pick, pack=pack, bill=bill, ship=ship, end=end,
                     par=par, slip=slip)


def test_activity_verbs_create_kinds():  # BHV-18, BHV-21
    act = Activity("A", "x")
    kinds = [act.action("a").kind, act.decision("d?").kind, act.merge().kind, act.start().kind, act.end().kind,
             act.flow_end().kind, act.send("s").kind, act.receive("r").kind, act.object("o").kind]
    assert kinds == ["action", "decision", "merge", "initial", "final", "flow_final", "signal_send",
                     "signal_receive", "object"]


def test_parallel_creates_fork_and_join_around_branches():  # BHV-19
    act, n = _fulfilment()
    fork, join = n["par"].fork, n["par"].join
    assert fork.kind == "fork" and join.kind == "join"
    pairs = {(e.src, e.dst) for e in act.edges}
    assert (fork.id, n["pick"].id) in pairs and (fork.id, n["bill"].id) in pairs
    assert (n["pick"].id, n["pack"].id) in pairs
    assert (n["pack"].id, join.id) in pairs and (n["bill"].id, join.id) in pairs


def test_sequence_connects_units_in_creation_order():  # BHV-22
    act, n = _fulfilment()
    pairs = {(e.src, e.dst) for e in act.edges}
    for a, b in [("start", "order"), ("order", "check"), ("ship", "end")]:
        assert (n[a].id, n[b].id) in pairs
    assert (n["check"].id, n["par"].fork.id) in pairs and (n["par"].join.id, n["ship"].id) in pairs


def test_lanes_hold_their_nodes_and_lay_out_as_bands():  # BHV-20
    act, n = _fulfilment()
    lanes = {g.label: g for g in act.groups if g.style == "lane"}
    assert list(lanes) == ["Customer", "Shop", "Warehouse", "Audit"]
    assert n["order"].id in lanes["Customer"].children and n["ship"].id in lanes["Warehouse"].children
    out = apply_layout(act, _th())
    zones = {z.label: z for z in out.zones}
    c, s = zones["Customer"], zones["Shop"]
    assert c.x + c.w <= s.x + 0.5 and c.y == s.y  # vertical bands side by side for direction down
    xs = [zones[k].x for k in ("Customer", "Shop", "Warehouse", "Audit")]
    assert xs == sorted(xs)  # bands in declaration order
    o = out.node(n["order"].id)
    assert c.x <= o.x and o.x + o.w <= c.x + c.w


def test_horizontal_lanes_for_direction_right():  # BHV-20
    act, n = _fulfilment("right")
    out = apply_layout(act, _th())
    zones = {z.label: z for z in out.zones}
    c, s = zones["Customer"], zones["Shop"]
    assert c.y + c.h <= s.y + 0.5 and c.x == s.x
    assert out.node(n["par"].fork.id).w < out.node(n["par"].fork.id).h  # bars turn vertical


def test_object_flows_are_dashed():  # BHV-21
    act, n = _fulfilment()
    flow = next(e for e in act.edges if e.dst == n["slip"].id)
    assert flow.dashed


def test_empty_lane_drawn_with_minimum_width():  # BHV-34
    act, _ = _fulfilment()
    out = apply_layout(act, _th())
    audit = next(z for z in out.zones if z.label == "Audit")
    assert audit.w >= 200


# T10: typed regions -----------------------------------------------------------------------------
def _mixed():
    d = Diagram("M1", "Checkout service and its order lifecycle")
    with d.group("Platform", id="platform", style="soft"):
        web = d.box("Web shop", icon="terrastruct:react")
        api = d.box("Orders API", icon="terrastruct:python")
    web >> api
    with d.state_machine("Order lifecycle", id="lifecycle") as sm:
        created = sm.state("Created")
        paid = sm.state("Paid")
        sm.initial >> created
        created.on("pay", paid)
        paid >> sm.final
    api.to(created, "creates")
    return d, sm, dict(web=web, api=api, created=created, paid=paid)


def test_region_builders_expose_typed_verbs():  # BHV-23
    d = Diagram("R", "Regions")
    with d.flowchart("Flow") as fc:
        assert fc.decision("ok?").kind == "decision"
    with d.state_machine("States") as sm:
        assert sm.state("Idle").kind == "state"
    with d.activity("Steps") as act:
        assert act.action("Do").kind == "action"
    regions = {g.region: g for g in d.groups if g.region}
    assert set(regions) == {"flowchart", "state_machine", "activity"}
    assert all(g.engine == "layered" for g in regions.values())


def test_region_laid_out_by_own_layout_as_one_box():  # BHV-24
    d, sm, n = _mixed()
    out = apply_layout(d, _th())
    zone = next(z for z in out.zones if z.label == "Order lifecycle")
    c, p = out.node("created"), out.node("paid")
    assert c.y + c.h < p.y  # layered, down, inside the region
    for k in ("created", "paid"):
        b = out.node(k)
        assert zone.x <= b.x and b.x + b.w <= zone.x + zone.w and zone.y <= b.y and b.y + b.h <= zone.y + zone.h
    platform = next(z for z in out.zones if z.label == "Platform")
    assert platform.x + platform.w <= zone.x or zone.x + zone.w <= platform.x  # parent places regions apart


def test_edge_into_region_crosses_its_border():  # BHV-25
    d, sm, n = _mixed()
    out = apply_layout(d, _th())
    e = next(e for e in out.edges if e.label == "creates")
    assert e.src.startswith("orders-api.") and e.dst.startswith("created.") and e.via


def test_standalone_equals_embedded_contents():  # BHV-26
    alone = StateMachine("S", "Lifecycle")
    a1, b1 = alone.state("Created"), alone.state("Paid")
    alone.initial >> a1
    a1.on("pay", b1)
    host = Diagram("H", "Host")
    with host.state_machine("Lifecycle") as sm:
        a2, b2 = sm.state("Created"), sm.state("Paid")
        sm.initial >> a2
        a2.on("pay", b2)
    o1, o2 = apply_layout(alone, _th()), apply_layout(host, _th())

    def rel(out, ids):
        boxes = [out.node(i) for i in ids]
        x0, y0 = boxes[0].x, boxes[0].y
        return [(round(b.x - x0, 1), round(b.y - y0, 1), b.w, b.h) for b in boxes]

    init2 = next(x.id for x in host.nodes if x.kind == "initial")
    assert rel(o1, ["initial", "created", "paid"]) == rel(o2, [init2, "created", "paid"])


def test_duplicate_region_ids_rejected():  # BHV-35
    d = Diagram("D", "x")
    with d.flowchart("Flow", id="f"):
        pass
    with pytest.raises(ValueError, match="duplicate group id 'f'"):
        with d.activity("Other", id="f"):
            pass


def test_builders_exported():
    import spinagram
    assert spinagram.Flowchart is Flowchart and spinagram.StateMachine is StateMachine
    assert spinagram.Activity is Activity

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

"""CSS-like styling (spec: .specs/features/css-styling/spec.md)."""
from __future__ import annotations

import re

import pytest

from spinagram import css


# T2: parser and selectors -----------------------------------------------------------------------
def _tree():
    """diagram > group#vpc.zone(region) > [node#api.critical.svc (state), node#db[icon]] ; edge#e0 from api to db"""
    root = css.El("diagram", id="d")
    vpc = css.El("group", id="vpc", classes=["zone"], parent=root)
    api = css.El("node", kinds=["state"], id="api", classes=["critical", "svc"], parent=vpc,
                 attrs={"kind": "state", "label": "API"})
    db = css.El("node", kinds=["data"], id="db", parent=vpc, attrs={"kind": "data", "icon": "aws:rds"})
    edge = css.El("edge", id="e0", parent=root, attrs={"from": "api", "to": "db", "label": "yes"})
    return root, vpc, api, db, edge


def _m(selector, el):
    rules, errors = css.parse(f"{selector} {{ fill: red }}")
    assert not errors, errors
    return any(css.matches(s, el) for s in rules[0].selectors)


@pytest.mark.parametrize("sel,target,expected", [
    ("node", "api", True), ("state", "api", True), ("state", "db", False), ("*", "db", True),     # type, kind, universal
    (".critical", "api", True), (".critical", "db", False), (".critical.svc", "api", True),       # class
    ("#db", "db", True), ("#db", "api", False),                                                  # id
    ("[icon]", "db", True), ("[icon]", "api", False), ("[kind=state]", "api", True),              # attribute
    ('[label="yes"]', "edge", True), ("edge[from=api]", "edge", True), ("edge[to=api]", "edge", False),
    ("group.zone node", "api", True), ("diagram node", "db", True), ("edge node", "api", False),  # descendant
    ("group > node", "api", True), ("diagram > node", "api", False),                             # child
    ("node:first-child", "api", True), ("node:first-child", "db", False), ("node:last-child", "db", True),
    ("node:not(.critical)", "db", True), ("node:not(.critical)", "api", False),
    ("#nope, .svc", "api", True),                                                                # list
])
def test_selector_forms(sel, target, expected):  # CSS-02
    root, vpc, api, db, edge = _tree()
    el = {"api": api, "db": db, "edge": edge}[target]
    assert _m(sel, el) is expected


def test_specificity():  # CSS-03 input
    rules, _ = css.parse("#a .b node { fill: red } node.c[d] { fill: red } * { fill: red } :not(#x) { fill: red }")
    assert [r.selectors[0].specificity for r in rules] == [(1, 1, 1), (0, 2, 1), (0, 0, 0), (1, 0, 0)]


def test_pseudo_elements_parsed():  # CSS-09 input
    rules, _ = css.parse("node::title { color: red } edge::label { color: blue }")
    assert [r.selectors[0].pseudo_element for r in rules] == ["title", "label"]


def test_declarations_and_importance():
    rules, _ = css.parse("node { fill: #fff; stroke-width: 4px !important }")
    d = rules[0].decls
    assert [(x.name, x.value, x.important) for x in d] == [("fill", "#fff", False), ("stroke-width", "4px", True)]


def test_syntax_error_reported_and_rest_applied():  # CSS-21
    text = "node { fill: red }\nnode..bad { fill: blue }\nedge { stroke: green }\n"
    rules, errors = css.parse(text, origin="brand.css")
    assert [r.selectors[0].text for r in rules] == ["node", "edge"]
    assert len(errors) == 1
    e = errors[0]
    assert e.origin == "brand.css" and e.line == 2 and e.column >= 1 and "node..bad" in e.message


# T3: cascade ------------------------------------------------------------------------------------
from spinagram.theme import Theme  # noqa: E402


def _compute(sheet, root, theme=None, origin="t.css"):
    rules, errors = css.parse(sheet, origin)
    assert not errors
    return css.compute(root, rules, theme or Theme.load(None))


def test_cascade_order_importance_specificity_inline():  # CSS-01, CSS-03, CSS-04, CSS-05
    root, vpc, api, db, edge = _tree()
    api.inline = "stroke-width: 9; stroke: #000000"
    sheet = """
      node { fill: #111111; stroke: #222222; stroke-width: 2; opacity: 0.5 }
      .critical { fill: #333333 }
      #api { fill: #444444 }
      node { fill: #555555 }
      state { stroke-width: 7 !important }
      #db { opacity: 1 } node { opacity: 0.25 }
    """
    out = _compute(sheet, root)
    assert out[api][""]["fill"] == "#444444"            # id beats class and later type rules (CSS-03)
    assert out[db][""]["fill"] == "#555555"             # same specificity: later wins (CSS-03)
    assert out[api][""]["stroke-width"] == 7.0          # !important beats inline normal (CSS-04)
    assert out[api][""]["stroke"] == "#000000"          # inline beats every normal declaration (CSS-05)
    assert out[db][""]["opacity"] == 1.0                # #db beats a later type rule
    assert out[edge][""].get("fill") is None            # unmatched element keeps no value (CSS-01)


def test_inherited_font_and_colour_from_groups():  # CSS-07
    root, vpc, api, db, edge = _tree()
    out = _compute("group { color: #123456; font-size: 30px; font-weight: bold; stroke: #ff0000 } "
                   "#db { font-size: 12 }", root)
    assert out[api][""]["color"] == "#123456" and out[api][""]["font-size"] == 30.0
    assert out[api][""]["font-weight"] == 700
    assert out[db][""]["font-size"] == 12.0
    assert "stroke" not in out[api][""]                 # stroke is not inherited
    assert out[api]["title"]["color"] == "#123456"      # pseudo-elements inherit from their element


def test_pseudo_element_rules():  # CSS-09
    root, vpc, api, db, edge = _tree()
    out = _compute("node::title { font-size: 28; font-style: italic } edge::label { color: red }", root)
    assert out[api]["title"]["font-size"] == 28.0 and out[api]["title"]["font-style"] == "italic"
    assert out[edge]["label"]["color"] == "#FF0000"
    assert "font-size" not in out[api][""]


def test_var_and_theme_tokens():  # CSS-14, CSS-15
    root, vpc, api, db, edge = _tree()
    th = Theme.load(None)
    out = _compute(":root { --brand: #0F766E } diagram { --accent: primary } "
                   "#api { fill: var(--brand); stroke: var(--accent) } #db { fill: primary-soft; stroke: var(--warning) }",
                   root, th)
    assert out[api][""]["fill"] == "#0F766E"
    assert out[api][""]["stroke"] == th.color("primary")
    assert out[db][""]["fill"] == th.color("primary-soft")
    assert out[db][""]["stroke"] == th.color("warning")  # var() falls back to the theme token


def test_unresolvable_colour_raises_with_location():  # CSS-16
    root, *_ = _tree()
    with pytest.raises(ValueError, match=r"brand\.css:1: #api: cannot resolve colour 'not-a-token'"):
        _compute("#api { fill: not-a-token }", root, origin="brand.css")


def test_values_parsed():  # CSS-08, CSS-10 value forms
    root, vpc, api, db, edge = _tree()
    out = _compute("#api { stroke-dasharray: 6 4; box-shadow: 2px 4px 8px rgba(0,0,0,0.3); border-radius: 0; "
                   "fill: rgb(255, 0, 128); fill-opacity: 50% } "
                   "edge { marker-end: diamond; marker-start: none; stroke-dasharray: none; color: navy }", root)
    a, e = out[api][""], out[edge][""]
    assert a["stroke-dasharray"] == [6.0, 4.0] and a["box-shadow"] == (2.0, 4.0, 8.0, "#000000", 0.3)
    assert a["border-radius"] == 0.0 and a["fill"] == "#FF0080" and a["fill-opacity"] == 0.5
    assert e["marker-end"] == "diamond" and e["marker-start"] == "none" and e["stroke-dasharray"] == []
    assert e["color"] == "#000080"


def test_unknown_property_and_negative_values_warn():  # CSS-22, CSS-30
    root, vpc, api, db, edge = _tree()
    rules, _ = css.parse("#api { fil: red; stroke-width: -3; font-size: -1px; fill: #abcdef }", "b.css")
    warnings = []
    out = css.compute(root, rules, Theme.load(None), warnings)
    assert "b.css:1: unknown property 'fil' (did you mean 'fill'?)" in warnings
    assert any("stroke-width" in w and "negative" in w for w in warnings)
    assert any("font-size" in w and "negative" in w for w in warnings)
    assert "stroke-width" not in out[api][""] and out[api][""]["fill"] == "#ABCDEF"
    assert "font-size" not in out[api][""]


# T4: classes and stylesheets from Python ---------------------------------------------------------
from spinagram import Diagram  # noqa: E402


def test_classes_inline_and_sheets_reach_the_cascade(tmp_path):  # CSS-17, CSS-18
    sheet = tmp_path / "brand.css"
    sheet.write_text(".critical { stroke: #DC2626 } edge.async { stroke-dasharray: 6 4 } group.edge-zone { fill: #FFFFFF }")
    d = Diagram("D", "Styled", css="node { fill: #EEEEEE }")
    d.stylesheet(str(sheet))
    d.stylesheet("#db { fill: #111111 }")
    with d.group("Zone", id="zone", class_="edge-zone"):
        api = d.box("API", class_="critical", css="stroke-width: 6")
        db = d.box("DB", id="db")
    api.to(db, "write", class_="async")
    styles, warnings = css.styles(d, Theme.load(None))
    assert warnings == []
    assert styles["node:api"][""] == {"fill": "#EEEEEE", "stroke": "#DC2626", "stroke-width": 6.0}
    assert styles["node:db"][""]["fill"] == "#111111"
    assert styles["edge:0"][""]["stroke-dasharray"] == [6.0, 4.0]
    assert styles["group:zone"][""]["fill"] == "#FFFFFF"


def test_named_style_also_matches_as_class():  # CSS-20
    d = Diagram("D", "x", css=".dark { stroke-width: 5 }")
    d.box("A", style="dark")
    styles, _ = css.styles(d, Theme.load(None))
    assert styles["node:a"][""]["stroke-width"] == 5.0


def test_no_css_means_no_styles():  # CSS-27 precondition
    d = Diagram("D", "x")
    d.box("A", style="dark")
    assert css.styles(d, Theme.load(None)) == ({}, [])


def test_tree_types_and_attributes():  # CSS-02 on real diagrams
    d = Diagram("D", "x", css="region > state { fill: #010101 } lane node { fill: #020202 } "
                             "edge[from=a] { stroke: #030303 } [kind=decision] { fill: #040404 }")
    a = d.box("A")
    with d.state_machine("SM", id="sm") as sm:
        s = sm.state("Idle")
    with d.activity("Act") as act:
        with act.lane("Ops"):
            x = act.action("Do")
    q = d.add("decision", "Q?", id="q")
    a >> s
    styles, _ = css.styles(d, Theme.load(None))
    assert styles[f"node:{s.id}"][""]["fill"] == "#010101"
    assert styles[f"node:{x.id}"][""]["fill"] == "#020202"
    assert styles["edge:0"][""]["stroke"] == "#030303"
    assert styles[f"node:{q.id}"][""]["fill"] == "#040404"


# T5: YAML, folder defaults and theme sheets -----------------------------------------------------
from spinagram.yaml_io import from_dict, load  # noqa: E402


def test_yaml_and_python_resolve_identical_styles(tmp_path):  # CSS-19
    (tmp_path / "brand.css").write_text(".critical { stroke: #DC2626 } edge.async { stroke-dasharray: 6 4 }")
    spec = {"id": "D", "title": "Styled", "css": "node { fill: #EEEEEE }", "stylesheets": ["brand.css"],
            "groups": [{"id": "zone", "label": "Zone", "class": "edge-zone", "css": "fill: #FFFFFF",
                        "children": ["api", "db"]}],
            "nodes": [{"id": "api", "title": "API", "class": "critical", "css": "stroke-width: 6"},
                      {"id": "db", "title": "DB"}],
            "edges": [{"from": "api", "to": "db", "label": "write", "class": "async"}]}
    y = from_dict(spec, base_dir=tmp_path)
    p = Diagram("D", "Styled", css="node { fill: #EEEEEE }", base_dir=tmp_path)
    p.stylesheet("brand.css")
    with p.group("Zone", id="zone", class_="edge-zone", css="fill: #FFFFFF"):
        api = p.box("API", id="api", class_="critical", css="stroke-width: 6")
        db = p.box("DB", id="db")
    api.to(db, "write", class_="async")
    th = Theme.load(None)
    assert css.styles(y, th) == css.styles(p, th)
    assert css.styles(y, th)[0]["node:api"][""]["stroke"] == "#DC2626"


def test_folder_defaults_stylesheets(tmp_path):  # CSS-19
    (tmp_path / "_defaults.yaml").write_text("stylesheets: [team.css]\n")
    (tmp_path / "team.css").write_text("node { fill: #ABCDEF }")
    (tmp_path / "a.yaml").write_text("id: A\ntitle: A\nnodes: [{id: n, title: N}]\n")
    (d,) = load(tmp_path / "a.yaml")
    assert css.styles(d, Theme.load(None))[0]["node:n"][""]["fill"] == "#ABCDEF"


def test_theme_css_comes_first_and_inherits(tmp_path):  # cascade order: theme < diagram
    base = tmp_path / "base"
    base.mkdir()
    (base / "theme.yaml").write_text("extends: default\nname: base\n")
    (base / "theme.css").write_text("node { fill: #111111; stroke: #222222 }")
    child = tmp_path / "child"
    child.mkdir()
    (child / "theme.yaml").write_text("extends: ../base\nname: child\n")
    (child / "theme.css").write_text("node { stroke: #333333 }")
    th = Theme.load(child)
    assert [p.name for p in th.stylesheets()] == ["theme.css", "theme.css"]
    d = Diagram("D", "x", css="#n { fill: #444444 }")
    d.box("N", id="n")
    d.box("M", id="m")
    s, _ = css.styles(d, th)
    assert s["node:n"][""]["fill"] == "#444444" and s["node:n"][""]["stroke"] == "#333333"
    assert s["node:m"][""]["fill"] == "#111111"


# T6: computed styles in the scene ---------------------------------------------------------------
from pathlib import Path  # noqa: E402

from spinagram.api import scenes  # noqa: E402
from spinagram.scene import Connector, Shape  # noqa: E402

BRAND = """
node.critical { fill: #FEE2E2; stroke: #DC2626; stroke-width: 5; border-radius: 4; box-shadow: 2px 4px 8px rgba(0,0,0,.3) }
node.critical::title { color: #7F1D1D; font-size: 30; font-style: italic }
node::body { color: #374151; font-weight: bold }
edge.async { stroke: #F59E0B; stroke-width: 2; stroke-dasharray: 6 4; marker-end: diamond; marker-start: circle }
edge.async::label { color: #92400E; font-size: 14 }
group.trusted { fill: #ECFDF5; stroke: #059669; stroke-dasharray: 2 2; opacity: 1 }
#db { opacity: 0.5 }
"""


def _styled():
    d = Diagram("S", "Styled", css=BRAND, layout={"engine": "layered", "direction": "right"})
    with d.group("Trusted", id="trusted", class_="trusted"):
        api = d.box("API", text="Python", class_="critical")
        db = d.box("DB", id="db")
    api.to(db, "write", class_="async")
    return d


def test_scene_applies_computed_styles():  # CSS-08, CSS-09, CSS-10
    sc = scenes([_styled()])[0]
    shapes = {s.id: s for s in sc.items if isinstance(s, Shape)}
    api = shapes["api"]
    assert (api.fill, api.stroke, api.stroke_width, api.radius) == ("#FEE2E2", "#DC2626", 5.0, 4.0)
    assert api.shadow == (2.0, 4.0, 8.0, "#000000", 0.3)
    title, body = api.label.blocks
    assert title.color == "#7F1D1D" and title.font.size == 30 and title.font.italic
    assert body.color == "#374151" and body.font.weight == 700
    assert shapes["db"].opacity == 0.5
    conn = next(c for c in sc.items if isinstance(c, Connector))
    assert (conn.color, conn.width, conn.dash, conn.marker_end, conn.marker_start) == (
        "#F59E0B", 2.0, [6.0, 4.0], "diamond", "circle")
    assert conn.arrow_end and conn.arrow_start and conn.dashed
    lab = conn.label.label.blocks[0]
    assert lab.color == "#92400E" and lab.font.size == 14
    zone = next(s for s in sc.items if isinstance(s, Shape) and s.role == "zone")
    assert (zone.fill, zone.stroke, zone.dash, zone.opacity) == ("#ECFDF5", "#059669", [2.0, 2.0], 1.0)
    assert zone.stroke_width == 2.0  # a CSS stroke on an outline-less zone draws a 2 px outline


def test_font_size_from_css_drives_auto_size():  # CSS-09 before layout (no overflow)
    from spinagram.qa import check
    d = Diagram("S", "x", css="node::title { font-size: 40 }", layout={"engine": "layered"})
    d.box("A much longer title than usual")
    sc = scenes([d])[0]
    assert [i for i in check(sc) if i.kind.startswith("overflow-")] == []
    node = next(s for s in sc.items if isinstance(s, Shape) and s.role == "node")
    assert node.label.blocks[0].font.size == 40


def test_marker_none_removes_arrow():  # CSS-10
    d = Diagram("S", "x", css="edge { marker-end: none }", layout={"engine": "layered"})
    d.box("A") >> d.box("B")
    conn = next(c for c in scenes([d])[0].items if isinstance(c, Connector))
    assert not conn.arrow_end and conn.marker_end == "none"


def test_unknown_font_family_falls_back_and_warns():  # CSS-29
    from spinagram.qa import check
    d = Diagram("S", "x", css="node { font-family: 'Comic Sans' }", layout={"engine": "layered"})
    d.box("A")
    sc = scenes([d])[0]
    node = next(s for s in sc.items if isinstance(s, Shape) and s.role == "node")
    assert node.label.blocks[0].font.family != "Comic Sans"
    msgs = [i.detail for i in check(sc) if i.kind == "style"]
    assert msgs == ["font-family 'Comic Sans' is not embedded in the theme; using the theme font"]


def test_unknown_property_reported_by_check():  # CSS-22 through check
    from spinagram.qa import check
    d = Diagram("S", "x", css="node { fil: red }")
    d.box("A", x=100, y=200, w=200, h=100)
    msgs = [i.detail for i in check(scenes([d])[0]) if i.kind == "style"]
    assert msgs == ["S css:1: unknown property 'fil' (did you mean 'fill'?)"]


def test_examples_untouched_without_css():  # CSS-27
    from spinagram import css as css_mod
    from spinagram.theme import Theme
    from spinagram.yaml_io import load as load_specs
    th = Theme.load(None)
    examples = Path(__file__).parent.parent / "examples"
    for d in load_specs(examples):
        assert css_mod.prepare(d, th) is d and "css" not in d.meta


# T7: SVG ----------------------------------------------------------------------------------------
from spinagram.backends.svg import to_svg  # noqa: E402


def test_svg_renders_style_properties():  # CSS-12 (SVG)
    sc = scenes([_styled()])[0]
    svg = to_svg(sc)
    api = re.search(r'<rect [^>]*fill="#FEE2E2"[^>]*/?>', svg).group(0)
    assert 'stroke="#DC2626"' in api and 'stroke-width="5"' in api and 'rx="4"' in api
    fid = re.search(r'filter="url\(#([^)]+)\)"', api).group(1)
    assert re.search(rf'<filter id="{fid}"[^>]*><feDropShadow dx="2" dy="4" stdDeviation="4" '
                     r'flood-color="#000000" flood-opacity="0.3"/></filter>', svg)
    path = re.search(r'<path d="M[^"]*" fill="none" stroke="#F59E0B"[^>]*>', svg).group(0)
    assert 'stroke-width="2"' in path and 'stroke-dasharray="6 4"' in path
    end = re.search(r'marker-end="url\(#([^)]+)\)"', path).group(1)
    start = re.search(r'marker-start="url\(#([^)]+)\)"', path).group(1)
    assert re.search(rf'<marker id="{end}"[^>]*>.*?M0,5 L5,0 L10,5 L5,10 z', svg)        # diamond
    assert re.search(rf'<marker id="{start}"[^>]*><circle ', svg)                       # circle
    assert re.search(r'<rect [^>]*fill="#ECFDF5"[^>]*stroke-dasharray="2 2"', svg)       # zone dash
    assert 'font-style="italic"' in svg and 'fill="#7F1D1D"' in svg                     # title text
    assert re.search(r'<rect [^>]*opacity="0.5"', svg)                                   # #db opacity



# T8: PowerPoint ---------------------------------------------------------------------------------
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def _slide(tmp_path, d):
    pptx = pytest.importorskip("pptx")
    from spinagram import render
    render([d], tmp_path, formats=["pptx"])
    return pptx.Presentation(str(tmp_path / "diagrams.pptx")).slides[0]


def _all_shapes(shapes):
    for sh in shapes:
        yield sh
        if sh.shape_type == 6:  # group
            yield from _all_shapes(sh.shapes)


def test_pptx_renders_style_properties(tmp_path):  # CSS-12 (PowerPoint)
    slide = _slide(tmp_path, _styled())
    by = {sh.name: sh for sh in _all_shapes(slide.shapes)}
    api = by["api"]._element.spPr
    ln = api.find(f"{A}ln")
    from spinagram.backends.pptx import _e
    assert int(ln.get("w")) == _e(5)
    shdw = api.find(f"{A}effectLst/{A}outerShdw")
    assert shdw is not None and shdw.find(f"{A}srgbClr").get("val") == "000000"
    assert shdw.find(f"{A}srgbClr/{A}alpha").get("val") == "30000"
    edge = by["e0"]._element.spPr.find(f"{A}ln")
    ds = edge.find(f"{A}custDash/{A}ds")
    assert ds.get("d") == "300000" and ds.get("sp") == "200000"       # 6 4 at width 2 → 300 % / 200 %
    assert edge.find(f"{A}tailEnd").get("type") == "diamond" and edge.find(f"{A}headEnd").get("type") == "oval"
    zone = next(sh for sh in by.values() if sh.name.startswith("z") and sh._element.spPr.find(f"{A}ln/{A}custDash")
                is not None)
    assert zone._element.spPr.find(f"{A}ln/{A}custDash/{A}ds") is not None
    runs = [r for sh in slide.shapes if sh.has_text_frame for p in sh.text_frame.paragraphs for r in p.runs]
    title = next(r for r in runs if r.text == "API")
    assert title.font.italic and str(title.font.color.rgb) == "7F1D1D"


def test_pptx_warns_for_markers_it_cannot_draw(tmp_path):  # CSS-13
    d = Diagram("S", "x", css="edge { marker-end: open-diamond; marker-start: bar }", layout={"engine": "layered"})
    d.box("A") >> d.box("B")
    with pytest.warns(UserWarning) as rec:
        _slide(tmp_path, d)
    msgs = [str(r.message) for r in rec]
    assert any("pptx" in m and "marker-end" in m and "open-diamond" in m for m in msgs)
    assert any("pptx" in m and "marker-start" in m and "bar" in m for m in msgs)


# T9: Figma --------------------------------------------------------------------------------------
import json as _json  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402

from spinagram.backends.figma import FigmaBackend  # noqa: E402


def test_figma_renders_style_properties(tmp_path):  # CSS-12 (Figma)
    sc = scenes([_styled()])[0]
    files = [p for p in FigmaBackend().render([sc], tmp_path) if p.suffix == ".js"]
    js = "\n".join(p.read_text() for p in files)
    m = re.search(r'rect\("api", [-\d.]+, [-\d.]+, [-\d.]+, [-\d.]+, (\{.*?\})\);', js)
    o = _json.loads(m.group(1))
    assert o["fill"] == "#FEE2E2" and o["stroke"] == "#DC2626" and o["sw"] == 5 and o["radius"] == 4
    assert o["shadow"] == {"x": 2, "y": 4, "blur": 8, "color": "#000000", "a": 0.3}
    edge = re.search(r'await vec\("e0", [-\d.]+, [-\d.]+, (\{.*?\}), (\{.*?\})\);', js)
    net, eo = _json.loads(edge.group(1)), _json.loads(edge.group(2))
    assert eo["dashes"] == [6, 4] and eo["stroke"] == "#F59E0B" and eo["sw"] == 2
    assert net["vertices"][-1]["strokeCap"] == "DIAMOND_FILLED" and net["vertices"][0]["strokeCap"] == "CIRCLE_FILLED"
    node = shutil.which("node") or shutil.which("bun")
    if node:
        mock = Path(__file__).parent / "js" / "figma_mock.mjs"
        for f in files:
            r = subprocess.run([node, str(mock), str(f)], capture_output=True, text=True)
            assert r.returncode == 0, r.stderr


# verifier gaps (css validation.md, iteration 1) -------------------------------------------------
import hashlib  # noqa: E402
import warnings as _warnings  # noqa: E402


def _golden_diagram():
    d = Diagram("G", "Unstyled golden", subtitle="no stylesheet anywhere",
                layout={"engine": "layered", "direction": "down"})
    with d.group("Zone", id="zone"):
        a = d.box("Gateway", text="NGINX")
        q = d.diamond("Valid?")
    s = d.add("state", "Paid", id="paid")
    t = d.add("terminator", "Done", id="done")
    a >> q
    q.to(s, "yes")
    q.to(t, "no", dashed=True)
    d.edge(s, t, arrow="both")
    return d


def _placed_diagram():
    d = Diagram("P", "Placed by hand")
    a = d.box("A", x=100, y=250, w=300, h=140, style="dark")
    b = d.box("B", x=700, y=250, w=300, h=140)
    d.zone("Zone", x=60, y=200, w=1000, h=260)
    d.edge(a.right, b.left, "go", dashed=True)
    return d


# SVG of the two diagrams above rendered at 46d7696, before any CSS code existed (scene, markers, dashes).
# Updated once by layout-engine T19 (EDG-01): the only change is P:e0's label, now centred on its edge midpoint
# instead of 12.5 px above it (pinned by tests/test_engine_labels.py::test_golden_label_change_is_the_centring).
UNSTYLED_GOLDEN = "019deb5210fc199084ac3c7cf9ce1592c1283ef872cc357cb0c909a9507a5926"


def test_unstyled_svg_matches_pre_css_golden():  # CSS-27
    svgs = [to_svg(sc) for sc in scenes([_golden_diagram(), _placed_diagram()])]
    assert hashlib.sha256("".join(svgs).encode()).hexdigest() == UNSTYLED_GOLDEN


def test_folder_and_spec_stylesheets_both_apply(tmp_path):  # CSS-19
    (tmp_path / "_defaults.yaml").write_text("stylesheets: [team.css]\n")
    (tmp_path / "team.css").write_text("node { fill: #ABCDEF; stroke: #111111 }")
    (tmp_path / "own.css").write_text("node { stroke: #222222 }")
    (tmp_path / "a.yaml").write_text("id: A\ntitle: A\nstylesheets: [own.css]\nnodes: [{id: n, title: N}]\n")
    (tmp_path / "b.py").write_text("from spinagram import Diagram\nd = Diagram('B', 'B')\nd.box('M', id='m')\n"
                                   "diagram = d\n")
    th = Theme.load(None)
    (a,) = load(tmp_path / "a.yaml")
    st = css.styles(a, th)[0]["node:n"][""]
    assert st["fill"] == "#ABCDEF" and st["stroke"] == "#222222"  # folder first, spec's own later
    (b,) = load(tmp_path / "b.py")
    assert css.styles(b, th)[0]["node:m"][""]["fill"] == "#ABCDEF"  # Python specs get folder sheets too


def test_pptx_fill_radius_and_shadow_geometry(tmp_path):  # CSS-12 (PowerPoint)
    import math
    from spinagram.backends.pptx import _e
    slide = _slide(tmp_path, _styled())
    api = next(sh for sh in _all_shapes(slide.shapes) if sh.name == "api")
    assert str(api.fill.fore_color.rgb) == "FEE2E2"
    from spinagram.backends.pptx import EMU
    w_px, h_px = api.width / EMU, api.height / EMU
    assert abs(api.adjustments[0] - 4 / min(w_px, h_px)) < 1e-3  # border-radius: 4 → roundRect adjustment
    shdw = api._element.spPr.find(f"{A}effectLst/{A}outerShdw")
    assert int(shdw.get("blurRad")) == _e(8)
    assert int(shdw.get("dist")) == _e(math.hypot(2, 4))
    assert int(shdw.get("dir")) == round(math.degrees(math.atan2(4, 2)) * 60000)


def test_figma_italic_title_font(tmp_path):  # CSS-12 (Figma fonts)
    sc = scenes([_styled()])[0]
    js = "\n".join(p.read_text() for p in FigmaBackend().render([sc], tmp_path) if p.suffix == ".js")
    m = re.search(r'text\("[^"]*", "API", [-\d.]+, [-\d.]+, (\{.*?\})\);', js)
    o = _json.loads(m.group(1))
    assert o["style"] == "Bold Italic" and o["color"] == "#7F1D1D"


def test_edge_opacity_reaches_every_backend(tmp_path):  # CSS-10 opacity
    d = Diagram("O", "x", css="edge { opacity: 0.4 }", layout={"engine": "layered"})
    d.box("A") >> d.box("B")
    sc = scenes([d])[0]
    conn = next(c for c in sc.items if isinstance(c, Connector))
    assert conn.opacity == 0.4
    assert re.search(r'<path d="M[^"]*" fill="none"[^>]*opacity="0.4"', to_svg(sc))
    slide = _slide(tmp_path, d)
    ln = next(sh for sh in slide.shapes if sh.name == "e0")._element.spPr.find(f"{A}ln")
    assert ln.find(f"{A}solidFill/{A}srgbClr/{A}alpha").get("val") == "40000"
    js = "\n".join(p.read_text() for p in FigmaBackend().render([sc], tmp_path / "f") if p.suffix == ".js")
    assert '"lineOpacity":0.4' in js


def test_unresolvable_shadow_colour_raises():  # CSS-16
    root, *_ = _tree()
    with pytest.raises(ValueError, match=r"cannot resolve colour"):
        _compute("#api { box-shadow: 1px 1px 2px not-a-token }", root)


def test_var_fallback_may_contain_a_function():  # CSS-14
    root, vpc, api, db, edge = _tree()
    out = _compute("#api { fill: var(--missing, rgb(1, 2, 3)) }", root)
    assert out[api][""]["fill"] == "#010203"
    out = _compute(":root { --x: #FFFFFF; --b: #0000FF } #api { fill: var(--x, rgb(1, 2, 3)) } "
                   "#db { fill: var(--a, var(--b)) }", root)
    assert out[api][""]["fill"] == "#FFFFFF"   # defined: the fallback (with its parentheses) is skipped whole
    assert out[db][""]["fill"] == "#0000FF"    # nested var() fallback


def test_one_warning_per_backend_property_and_value(tmp_path):  # CSS-13 ("one warning")
    from spinagram.backends import figma as fig_mod
    from spinagram.backends import pptx as pptx_mod
    pptx_mod._warned.clear()
    fig_mod._WARNED.clear()
    d = Diagram("W", "x", css="edge { marker-end: open-diamond }", layout={"engine": "layered"})
    a, b, c = d.box("A"), d.box("B"), d.box("C")
    a >> b
    a >> c
    with _warnings.catch_warnings(record=True) as rec:
        _warnings.simplefilter("always")
        _slide(tmp_path, d)
        FigmaBackend().render(scenes([d]), tmp_path / "f")
    msgs = [str(r.message) for r in rec if "open-diamond" in str(r.message)]
    assert sorted(m.split(":")[0] for m in msgs) == ["figma", "pptx"]


def test_edge_to_selector_on_a_real_diagram():  # CSS-06
    d = Diagram("D", "x", css="edge[to=db] { stroke: #00FF00 } edge[from=db] { stroke: #FF0000 }")
    api, db, web = d.box("API"), d.box("DB", id="db"), d.box("Web")
    api >> db
    web >> api
    st, _ = css.styles(d, Theme.load(None))
    assert st["edge:0"][""]["stroke"] == "#00FF00" and "stroke" not in st["edge:1"][""]


def test_unknown_font_family_warned_once_for_many_nodes():  # CSS-29 ("once per family")
    from spinagram.qa import check
    d = Diagram("S", "x", css="node { font-family: 'Comic Sans' }", layout={"engine": "layered"})
    d.box("A") >> d.box("B")
    msgs = [i.detail for i in check(scenes([d])[0]) if i.kind == "style"]
    assert msgs == ["font-family 'Comic Sans' is not embedded in the theme; using the theme font"]


def test_group_label_styling_in_scene():  # CSS-09 (group ::label)
    d = Diagram("G", "x", css="group::label { color: #065F46; font-size: 22 }", layout={"engine": "layered"})
    with d.group("Trusted", id="t"):
        d.box("A")
    lab = next(i for i in scenes([d])[0].items if getattr(i, "id", "") == "z0-label")
    assert lab.block.color == "#065F46" and lab.block.font.size == 22


def test_figma_deco_sets_shadow_effects_and_dashes():  # CSS-12 (Figma JS behaviour)
    node = shutil.which("node") or shutil.which("bun")
    if not node:
        pytest.skip("node/bun not installed")
    from spinagram.backends import figma as fig_mod
    src = next(v for v in vars(fig_mod).values() if isinstance(v, str) and "function deco(" in v)
    rgb = re.search(r"const rgb = .*?;\n", src).group(0)
    deco = re.search(r"function deco\(n, o\) \{.*?\n\}\n", src, re.S).group(0)
    script = rgb + deco + ("const n = {}; deco(n, {dashes: [6, 4], lineOpacity: 0.5, shadow: {x: 2, y: 4, blur: 8, "
                           "color: '#000000', a: 0.3}}); console.log(JSON.stringify(n));")
    out = _json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)
    assert out["dashPattern"] == [6, 4] and out["opacity"] == 0.5
    eff = out["effects"][0]
    assert eff["type"] == "DROP_SHADOW" and eff["offset"] == {"x": 2, "y": 4} and eff["radius"] == 8
    assert eff["color"] == {"r": 0, "g": 0, "b": 0, "a": 0.3}


@pytest.mark.parametrize("bad", ["#GGGGGG", "#12", "#1234567890", "#FFFFFF)"])
def test_malformed_hex_colours_raise(bad):  # CSS-16 (iteration-3 finding: hex was not validated)
    root, *_ = _tree()
    with pytest.raises(ValueError, match="cannot resolve colour"):
        _compute(f"#api {{ fill: {bad} }}", root)


def test_defined_var_with_function_fallback_resolves_cleanly():  # CSS-14 (kills the unbalanced-scan mutant)
    root, vpc, api, db, edge = _tree()
    out = _compute(":root { --x: white } #api { fill: var(--x, rgb(1, 2, 3)) }", root)
    assert out[api][""]["fill"] == "#FFFFFF"


def test_not_with_nested_selector_list():  # CSS-02 (bracket counting in :not)
    root, vpc, api, db, edge = _tree()
    assert _m("node:not(:not(.critical))", api) is True and _m("node:not(:not(.critical))", db) is False

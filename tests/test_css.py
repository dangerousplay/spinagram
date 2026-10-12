"""CSS-like styling (spec: .specs/features/css-styling/spec.md)."""
from __future__ import annotations

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

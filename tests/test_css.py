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

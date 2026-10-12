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

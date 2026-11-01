"""CSS matching and cascade in the Rust core against Python (CSS-02, CSS-03, CSS-01, CSS-06, CSS-07, CSS-08, CSS-09)."""
import json

import pytest

from spinagram import css
from spinagram.css import El, matches, parse_selectors

# (parent index, type, kinds, id, classes, attrs) in pre-order
NODES = [
    (None, "diagram", [], "d", [], {}),
    (0, "group", ["group"], "g1", ["a"], {"label": "Net"}),
    (1, "node", ["box"], "n1", ["hot", "a"], {"kind": "box", "label": "a b", "icon": "x"}),
    (1, "node", ["decision"], "n2", [], {"kind": "decision"}),
    (1, "region", ["group", "aws"], "r1", [], {}),
    (4, "node", ["state"], "n3", ["hot"], {"kind": "state"}),
    (1, "node", ["text", "label"], None, [], {"label": "x y"}),
    (0, "node", ["box", "chip"], "n5", ["b"], {"kind": "box"}),
    (0, "edge", [], None, [], {"from": "n1", "to": "n2"}),
    (0, "edge", [], None, ["hot"], {"label": "a b"}),
]

SELECTORS = [
    "node", "state", "chip", "group", "*", ".hot", ".a.b", "#n1", "node#n1.hot", "[icon]", "[kind=box]", '[label="a b"]',
    "[label='x y']", "[kind=nope]", "[ kind = decision ]", "group node", "diagram node", "group > node", "group>node",
    "diagram > node", "diagram group > node.hot", "edge, .a", "node:first-child", "node:last-child", ":root",
    "diagram:root", "node:root", "node:not(.hot)", "node:not(.a, #n5)", "node:not(:not(.hot))", "node:not(group node)",
    "node:not(:first-child)", "node::title", "::label", "group > node[kind=box]:first-child:not(#n9)", "* > *",
    "group:last-child", "group group node", "edge[from=n1]",
]


def python_tree(spec=NODES):
    els = []
    for par, typ, kinds, id_, cls, attrs in spec:
        els.append(El(typ, list(kinds), id_, list(cls), dict(attrs), els[par] if par is not None else None))
    return els


def tree_json(els):
    index = {id(e): i for i, e in enumerate(els)}
    return json.dumps({"nodes": [{"parent": index[id(e.parent)] if e.parent is not None else None, "type": e.type,
                                  "kinds": e.kinds, "id": e.id, "classes": e.classes, "attrs": e.attrs, "inline": []}
                                 for e in els]})


@pytest.fixture(scope="module")
def core():
    return pytest.importorskip("spinagram_core")


@pytest.mark.parametrize("text", SELECTORS)
def test_binding_match_sets_equal_python(core, text):  # CSS-03
    els = python_tree()
    sels = parse_selectors(text)
    expected = [i for i, el in enumerate(els) if any(matches(s, el) for s in sels)]
    [got] = json.loads(core.css_select(tree_json(els), [text]))
    assert got == expected


def test_lone_root_is_its_own_only_child(core):  # CSS-03 edge case (no parent)
    els = python_tree(NODES[:1])
    texts = ["diagram:first-child", "diagram:last-child", ":root", ":not(:root)"]
    expected = [[i for i, el in enumerate(els) if any(matches(s, el) for s in parse_selectors(t))] for t in texts]
    assert json.loads(core.css_select(tree_json(els), texts)) == expected


def test_one_result_list_per_selector_text(core):  # the binding returns the texts' results in order
    got = json.loads(core.css_select(tree_json(python_tree()), ["edge", "#n1", "diagram"]))
    assert got == [[8, 9], [2], [0]]


def test_selector_the_crate_cannot_parse_raises_valueerror(core):  # fallback precondition (SPEC_DEVIATION)
    for text in ("node >", "> node", "[w=100px]"):
        parse_selectors(text)  # Python accepts them
        with pytest.raises(ValueError):
            core.css_select(tree_json(python_tree()), [text])


# compute() and styles() (CSS-01, CSS-08, CSS-09) -----------------------------------------------------------------
from unittest import mock  # noqa: E402

from example_scenes import example_diagrams  # noqa: E402

from spinagram.theme import Theme  # noqa: E402

THEME = Theme.load("default")

# (css, inline css per element index): every cascade level, pseudo-element and var() form
SHEETS = [
    ("node { stroke: #111 } node { fill: #222 !important } node { stroke-width: 1 }",
     {2: "stroke: #c00; opacity: 0.5 !important; font-size: 20"}),
    ("node { fill: #111; fill: #112 } .hot { fill: #222 } #n1 { fill: #333 } node.hot { fill: #444 } node { fill: #555 }", {}),
    ("node, node { fill: #111; stroke: #222 } box { fill: #333 } [kind] { fill: #444 }", {}),
    ("node::title { color: #111 } node { color: #222 } ::label { color: #333 } group::body { color: #444 }", {}),
    ("diagram { --a: var(--b); --b: Inter; --p: Parent } node { font-family: var(--a) } group { font-family: var(--p) }", {}),
    ("node { font-family: var(--missing, rgb(1, 2, 3)) } group { font-family: var( --x , fallback ) } edge { font-family: var(--n,) }", {}),
    ("node { --c: Own } node::title { --d: PseudoOnly; font-family: var(--c) } node::body { font-family: var(--d) }", {}),
    ("node { --k: First } .hot { --k: Hot } node { font-family: var(--k) }", {2: "--k: Inline"}),
    ("node { --v0: var(--v1); --v1: var(--v2); --v2: var(--v3); --v3: var(--v4); --v4: var(--v5); --v5: var(--v6); "
     "--v6: var(--v7); --v7: var(--v8); --v8: var(--v9); --v9: End; font-family: var(--v0) }", {}),
    ("node { frobnicate: 1; font-size: -3; stroke-width: abc; fill: }  group { opacity: 0.4; font-weight: bold }", {}),
    ("node:not(.hot):first-child { fill: #123456 } group > node:last-child { stroke: red }", {}),
    ("node > { fill: #111 } node { stroke: #222 }", {}),  # a rule the CSS parser skips with an error
    ("> node { fill: #111 } [w=100px] { stroke: #222 } node { color: #333 }", {}),  # selectors the crate cannot parse
]


def python_tree_with_inline(inline):
    els = []
    for i, (par, typ, kinds, id_, cls, attrs) in enumerate(NODES):
        els.append(El(typ, list(kinds), id_, list(cls), dict(attrs), els[par] if par is not None else None, inline.get(i)))
    return els


def run(root, rules, core_module):
    css._CORE = core_module
    warnings, trace = [], {}
    values = css.compute(root, rules, THEME, warnings, trace)
    els = list(css._walk(root))
    return [values[e] for e in els], warnings, [trace[e] for e in els]


@pytest.mark.parametrize("sheet,inline", SHEETS, ids=[f"sheet{i}" for i in range(len(SHEETS))])
def test_compute_equal_across_modes(core, monkeypatch, sheet, inline):  # CSS-01
    monkeypatch.setattr(css, "_CORE", None)
    root = python_tree_with_inline(inline)[0]
    rules, _ = css.parse(sheet)
    assert run(root, rules, core) == run(root, rules, None)


def test_compute_values_come_from_the_core_when_active(core, monkeypatch):  # CSS-01 (dispatch)
    monkeypatch.setattr(css, "_CORE", core)
    root = python_tree_with_inline({})[0]
    rules, _ = css.parse("node { font-family: var(--x, Inter) }")
    with mock.patch.object(core, "css_cascade", wraps=core.css_cascade) as spy:
        values = css.compute(root, rules, THEME)
    assert spy.call_count == 1 and values[root.children[0].children[0]][""]["font-family"] == "Inter"


@pytest.mark.parametrize("fn", ["styles", "inspect"])
def test_every_example_diagram_equal_across_modes(core, monkeypatch, fn):  # CSS-01, CSS-07
    monkeypatch.setattr(css, "_CORE", None)
    for d in example_diagrams():
        css._CORE = None
        expected = getattr(css, fn)(d, THEME)
        css._CORE = core
        assert getattr(css, fn)(d, THEME) == expected, d.id


def test_core_inactive_never_calls_the_core(monkeypatch):  # CSS-08
    spy = mock.Mock()
    monkeypatch.setattr(css, "_CORE", None)
    root = python_tree_with_inline({})[0]
    rules, _ = css.parse("node { fill: #111 }")
    css.compute(root, rules, THEME)
    assert spy.mock_calls == [] and css._CORE is None


def test_unstyled_diagram_does_not_call_the_core(core, monkeypatch):  # CSS-08 edge case
    from spinagram import Diagram

    d = Diagram("D", "t")
    d.box("a", id="a", x=0, y=0, w=10, h=10)
    spy = mock.Mock(wraps=core)
    monkeypatch.setattr(css, "_CORE", spy)
    assert css.styles(d, THEME) == ({}, [])
    assert spy.mock_calls == []


def test_unresolvable_colour_raises_the_same_message(core, monkeypatch):  # CSS-09
    root = python_tree_with_inline({})[0]
    rules, _ = css.parse("node { fill: var(--nowhere) }")
    messages = []
    for module in (None, core):
        monkeypatch.setattr(css, "_CORE", module)
        with pytest.raises(css.CssValueError) as err:
            css.compute(root, rules, THEME)
        messages.append(str(err.value))
    assert messages[0] == messages[1] == "<css>:1: node: cannot resolve colour 'nowhere'"


# select() and inspect() (CSS-06, CSS-07) ---------------------------------------------------------------------------
def selectable_diagram():
    from spinagram import Diagram

    d = Diagram("D", "t")
    d.group("Net", id="g1", children=[])
    d.box("A", id="a", x=0, y=0, w=100, h=50, cls="hot")
    d.box("B", id="b", x=200, y=0, w=100, h=50)
    d.edge("a", "b")
    d.edge("b", "a", cls="hot")
    return d


@pytest.mark.parametrize("text", ["node", "edge", ".hot", "#a", "node, edge", "node:first-child", "node:last-child",
                                  ":root", "diagram > node", "diagram node:not(.hot)", "[from=a]", "[from]", "group",
                                  "node::title", "edge.hot, #b", "*", "nothing", "> node", "[w=100px]"])
def test_select_keys_and_order_equal_across_modes(core, monkeypatch, text):  # CSS-06
    monkeypatch.setattr(css, "_CORE", None)
    d = selectable_diagram()
    expected = css.select(d, text)
    css._CORE = core
    assert css.select(d, text) == expected


def test_select_asks_the_core_when_active(core, monkeypatch):  # CSS-06 (dispatch)
    monkeypatch.setattr(css, "_CORE", core)
    with mock.patch.object(core, "css_select", wraps=core.css_select) as spy:
        keys = css.select(selectable_diagram(), "edge")
    assert spy.call_count == 1 and keys == ["edge:0", "edge:1"]


def test_select_does_not_ask_the_core_when_inactive(monkeypatch):  # CSS-08
    monkeypatch.setattr(css, "_CORE", None)
    assert css.select(selectable_diagram(), "edge") == ["edge:0", "edge:1"]


def test_inspect_reports_unused_selectors_equal_across_modes(core, monkeypatch):  # CSS-07
    monkeypatch.setattr(css, "_CORE", None)
    d = selectable_diagram()
    d.css = "node { fill: #112233 } .nothing { fill: red } edge.hot, group::title { stroke: #445566 } [nope] { opacity: 1 }"
    css._CORE = None
    expected = css.inspect(d, THEME)
    css._CORE = core
    got = css.inspect(d, THEME)
    assert got == expected
    assert [u["selector"] for u in got["unused"]] == [".nothing", "group::title", "[nope]"]

"""CSS matching and cascade in the Rust core against Python (CSS-02, CSS-03, CSS-01, CSS-06, CSS-07, CSS-08, CSS-09)."""
import json

import pytest

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

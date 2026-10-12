"""CSS inspector, live reload of stylesheets and fill-opacity (spec: .specs/features/css-inspector/spec.md)."""
from __future__ import annotations

from spinagram import css
from spinagram.theme import Theme


def _tree():
    root = css.El("diagram", id="d", key="diagram")
    vpc = css.El("group", id="vpc", classes=["zone"], parent=root, key="group:vpc")
    api = css.El("node", kinds=["state"], id="api", classes=["critical"], parent=vpc, key="node:api")
    db = css.El("node", kinds=["data"], id="db", parent=vpc, key="node:db")
    return root, vpc, api, db


SHEET = """
:root { --brand: #0F766E }
node { fill: #111111; stroke: #222222 }
.critical { fill: var(--brand); strok: red; stroke-width: -3 }
#api { stroke: #333333 }
group { color: #123456; font-size: 30 }
"""


def _traced(sheet=SHEET, inline=None):
    root, vpc, api, db = _tree()
    api.inline = inline
    rules, errors = css.parse(sheet, "brand.css")
    assert not errors
    trace: dict = {}
    out = css.compute(root, rules, Theme.load(None), [], trace)
    return out, trace, (root, vpc, api, db)


def _by(entries, prop):
    return [e for e in entries if e["property"] == prop]


def test_trace_statuses_origin_and_specificity():  # INS-01
    _, trace, (_, _, api, _) = _traced()
    decls = trace[api][""]["decls"]
    fill = _by(decls, "fill")
    assert [(e["selector"], e["status"]) for e in fill] == [("node", "overridden"), (".critical", "applied")]
    assert fill[1]["value"] == "var(--brand)" and fill[1]["resolved"] == "#0F766E"
    assert fill[1]["origin"] == "brand.css" and fill[1]["line"] == 4 and fill[1]["specificity"] == [0, 1, 0]
    assert [(e["selector"], e["status"]) for e in _by(decls, "stroke")] == [("node", "overridden"), ("#api", "applied")]
    assert _by(decls, "strok")[0]["status"] == "unknown" and "stroke" in _by(decls, "strok")[0]["message"]
    assert _by(decls, "stroke-width")[0]["status"] == "invalid"


def test_trace_marks_inline_and_important():  # INS-01
    _, trace, (_, _, api, _) = _traced(SHEET + "node { stroke: #444444 !important }", inline="stroke: #555555")
    st = _by(trace[api][""]["decls"], "stroke")
    assert [(e["origin"], e["status"], e["important"]) for e in st][-2:] == [
        ("inline", "overridden", False), ("brand.css", "applied", True)]
    assert st[-2]["selector"] is None and st[-2]["specificity"] is None


def test_trace_lists_inherited_values_with_their_source():  # INS-02
    _, trace, (_, vpc, api, _) = _traced()
    inh = {e["property"]: e for e in trace[api][""]["inherited"]}
    assert inh["color"]["value"] == "#123456" and inh["color"]["from"] == "group:vpc"
    assert inh["font-size"]["value"] == 30.0
    assert "fill" not in inh                                      # not inherited
    assert trace[vpc][""]["inherited"] == []                      # nothing above the group sets them
    title = {e["property"]: e for e in trace[api]["title"]["inherited"]}
    assert title["color"]["from"] == "group:vpc"                  # pseudo-elements inherit through the node


def test_trace_does_not_change_computed_styles():  # INS-03
    root, *_ = _tree()
    rules, _ = css.parse(SHEET, "brand.css")
    plain = css.compute(root, rules, Theme.load(None), [])
    traced = css.compute(root, rules, Theme.load(None), [], {})
    assert {k.key: v for k, v in plain.items()} == {k.key: v for k, v in traced.items()}

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


# T2: inspect report --------------------------------------------------------------------------------
import json  # noqa: E402

import pytest  # noqa: E402

from spinagram import Diagram  # noqa: E402


def _diagram(tmp_path=None):
    d = Diagram("D", "Styled", css="node { fill: #EEEEEE } .ghost { fill: #000000 } #db::title { color: red }")
    with d.group("Zone", id="zone", class_="trusted"):
        api = d.box("API", class_="critical", css="stroke-width: 6")
        db = d.box("DB", id="db")
    api.to(db, "write", class_="async")
    return d


def test_inspect_report_fields():  # INS-12
    r = css.inspect(_diagram(), Theme.load(None))
    assert r["styled"] and r["diagram"] == "D"
    assert [e["key"] for e in r["elements"]] == ["diagram", "group:zone", "node:api", "node:db", "edge:0"]
    api = next(e for e in r["elements"] if e["key"] == "node:api")
    assert api["type"] == "node" and api["classes"] == ["critical"] and api["parent"] == "group:zone"
    assert api["attrs"]["label"] == "API"
    assert api["styles"][""] == {"fill": "#EEEEEE", "stroke-width": 6.0}
    assert [d["origin"] for d in api["trace"][""]["decls"]] == ["D css", "inline"]
    db = next(e for e in r["elements"] if e["key"] == "node:db")
    assert db["styles"]["title"] == {"color": "#FF0000"} and "body" not in db["styles"]
    assert r["sheets"] == [{"origin": "D css", "theme": False, "rules": 3}]
    json.dumps(r)                                                   # JSON-ready for the UI and --json


def test_unused_selectors_only_from_own_sheets(tmp_path):  # INS-08
    th_dir = tmp_path / "th"
    th_dir.mkdir()
    (th_dir / "theme.yaml").write_text("extends: default\nname: th\n")
    (th_dir / "theme.css").write_text("decision { fill: #111111 }")      # unused here, but a theme sheet
    r = css.inspect(_diagram(), Theme.load(th_dir))
    assert r["unused"] == [{"origin": "D css", "line": 1, "selector": ".ghost"}]
    assert r["sheets"][0]["theme"] is True


def test_select_filters_by_selector():  # INS-05
    d = _diagram()
    assert css.select(d, "group .critical, edge.async") == ["node:api", "edge:0"]
    assert css.select(d, "#db::title") == ["node:db"]
    with pytest.raises(ValueError, match="invalid selector"):
        css.select(d, "node[")


def test_unstyled_diagram_reports_nothing():  # INS-16
    d = Diagram("P", "Plain")
    d.box("A")
    r = css.inspect(d, Theme.load(None))
    assert r["styled"] is False and r["elements"] == [] and r["unused"] == []


def test_syntax_error_keeps_the_valid_trace():  # INS-17
    d = Diagram("E", "Broken", css="node { fill: #EEEEEE } node { fill: ; stroke: #111111 } @media x { }")
    d.box("A")
    r = css.inspect(d, Theme.load(None))
    a = next(e for e in r["elements"] if e["key"] == "node:a")
    assert a["styles"][""]["fill"] == "#EEEEEE" and a["styles"][""]["stroke"] == "#111111"
    assert any("at-rule" in w for w in r["warnings"])


def test_empty_value_is_invalid_not_black():  # INS-17 (found while testing: `fill: ;` became #000000)
    d = Diagram("E", "Empty", css="node { fill: }")
    d.box("A")
    styles, warnings = css.styles(d, Theme.load(None))
    assert "fill" not in styles["node:a"][""] and any("empty value" in w for w in warnings)


# T3: check --styles -------------------------------------------------------------------------------
from spinagram.cli import main  # noqa: E402

SPEC = """\
id: S01
title: Styled
stylesheets: [brand.css]
css: "#db { opacity: 0.5 }"
nodes:
  - {id: api, title: API, class: critical, x: 100, y: 100, w: 300, h: 140}
  - {id: db, title: DB, x: 600, y: 100, w: 300, h: 140}
edges:
  - {from: api, to: db, label: write}
"""
BRAND = """\
:root { --danger: #DC2626 }
node { fill: #FFFFFF; stroke: #333333 }
.critical { stroke: var(--danger); strok: red }
.nothing { fill: #000000 }
group { color: #111111 }
"""


@pytest.fixture
def spec(tmp_path, monkeypatch):
    (tmp_path / "s.yaml").write_text(SPEC)
    (tmp_path / "brand.css").write_text(BRAND)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NO_COLOR", raising=False)
    return tmp_path


def test_check_styles_plain_output(spec, capsys):  # INS-04, INS-07 (pipe → plain)
    assert main(["check", "--styles", "s.yaml"]) == 1        # the unknown property is an issue
    out = capsys.readouterr().out
    assert "\x1b[" not in out
    assert "S01 · Styled  cascade: brand.css, S01 css" in out
    api = out[out.index("node#api.critical"):out.index("node#db")]
    assert api.index(".critical  brand.css:3 (0,1,0)") < api.index("node  brand.css:2 (0,0,1)")  # winner first
    assert "stroke: var(--danger) → #DC2626" in api
    assert "stroke: #333333  (overridden)" in api
    assert "strok: red  ⚠ unknown property (did you mean 'stroke'?)" in api
    assert "edge api → db  'write'" not in out              # edge has no declarations ...
    assert "1 element(s) without declarations: edge api → db" in out  # ... so it is summarised
    assert "info: unused selector .nothing brand.css:4" in out
    assert "#db  S01 css:1 (1,0,0)" in out and "opacity: 0.5" in out


def test_check_styles_colour_output(spec, capsys):  # INS-07
    main(["check", "--styles", "--color", "always", "s.yaml"])
    out = capsys.readouterr().out
    assert "\x1b[9;2mstroke: #333333\x1b[0m" in out                  # struck through
    assert "\x1b[48;2;220;38;38m  \x1b[0m #DC2626" in out            # swatch before the colour
    assert "(overridden)" not in out


def test_check_styles_select_and_bad_selector(spec, capsys):  # INS-05
    main(["check", "--styles", "--select", "#db", "s.yaml"])
    out = capsys.readouterr().out
    assert "node#db" in out and "node#api" not in out
    assert main(["check", "--styles", "--select", "node[", "s.yaml"]) == 2
    assert "invalid selector" in capsys.readouterr().err


def test_check_json(spec, capsys):  # INS-06
    assert main(["check", "--json", "--select", ".critical", "s.yaml"]) == 0
    r = json.loads(capsys.readouterr().out)
    assert r["diagram"] == "S01" and [e["key"] for e in r["elements"]] == ["node:api"]
    assert r["elements"][0]["styles"][""]["stroke"] == "#DC2626"


def test_plain_check_lists_unused_selectors_as_info(spec, capsys):  # INS-08
    rc = main(["check", "s.yaml"])
    out = capsys.readouterr().out
    assert "info: unused selector .nothing (brand.css:4)" in out
    assert "group" in out.split("info: unused selector")[2]           # `group` matches nothing either
    assert out.rstrip().endswith("1 diagram(s), 1 issue(s)") and rc == 1  # only the unknown property counts


def test_check_styles_unstyled(tmp_path, monkeypatch, capsys):  # INS-16
    (tmp_path / "p.yaml").write_text("id: P\ntitle: Plain\nnodes:\n  - {id: a, title: A, x: 0, y: 0, w: 200, h: 100}\n")
    monkeypatch.chdir(tmp_path)
    main(["check", "--styles", "p.yaml"])
    assert "P · Plain\n  no stylesheet or inline css" in capsys.readouterr().out


def test_unused_needs_every_diagram_to_miss_it():  # INS-08 across diagrams
    from spinagram import inspect_fmt
    a = {"sheets": [{"origin": "x.css"}], "unused": [{"origin": "x.css", "line": 1, "selector": ".a"}]}
    b = {"sheets": [{"origin": "x.css"}], "unused": []}
    assert inspect_fmt.unused([a, b]) == [] and inspect_fmt.unused([a, a]) == a["unused"]

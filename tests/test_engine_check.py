"""check diagnostics, fixes and --fix (layout-engine CHK-01..08)."""
import json

import pytest

from spinagram.cli import main
from spinagram.qa import Issue

SEVERITY_SCENARIOS = [
    ("overflow-x", "P0"), ("overflow-y", "P0"), ("label-collision", "P0"), ("icon-touches-border", "P0"),
    ("header-overlap", "P0"), ("icon-overflows-box", "P0"), ("outside-safe-area", "P0"), ("zone-clips-child", "P0"),
    ("glyph-missing", "P1"), ("low-contrast", "P1"), ("zone-underused", "P2"), ("edge-crossings", "P2"),
    ("unlisted-kind", "P1"),
]


@pytest.mark.parametrize("kind,severity", SEVERITY_SCENARIOS, ids=[k for k, _ in SEVERITY_SCENARIOS])
def test_issue_severity_by_kind(kind, severity):
    assert Issue("D", "n", kind, "x").severity == severity


FIX_SCENARIOS = [
    ("no-fix", None),
    ("move-label", {"op": "move-label", "edge": "e3", "to": [100, 200]}),
    ("resize", {"op": "resize", "node": "pool", "w": 240}),
]


@pytest.mark.parametrize("fix", [f for _, f in FIX_SCENARIOS], ids=[i for i, _ in FIX_SCENARIOS])
def test_issue_dict_carries_fix_and_keeps_text(fix):
    i = Issue("D", "pool", "overflow-x", "too wide", fix=fix)
    assert i.to_dict() == {"scene": "D", "item": "pool", "kind": "overflow-x", "detail": "too wide", "fix": fix,
                           "severity": "P0"}
    assert str(i) == "D:pool: overflow-x — too wide"


JSON_SPECS = [
    ("clean", "nodes:\n  - {id: a, title: Ok, x: 100, y: 200, w: 300, h: 120}\n", []),
    ("overflow", "nodes:\n  - {id: a, title: averyveryverylongunbreakabletokenname, x: 100, y: 200, w: 90, h: 60}\n", ["overflow-x"]),
]


@pytest.mark.parametrize("body,kinds", [s[1:] for s in JSON_SPECS], ids=[s[0] for s in JSON_SPECS])
def test_check_json_lists_issues_with_fix_key(tmp_path, monkeypatch, capsys, body, kinds):
    (tmp_path / "s.yaml").write_text("id: J1\ntitle: Json\n" + body)
    monkeypatch.chdir(tmp_path)
    main(["check", "--json", "s.yaml"])
    r = json.loads(capsys.readouterr().out)
    assert sorted({i["kind"] for i in r["issues"]}) == kinds
    assert all({"fix", "severity", "item", "detail"} <= set(i) for i in r["issues"])


# icon and header diagnostics (CHK-01) --------------------------------------------------------------------------
from spinagram import Diagram, Theme, build_scene  # noqa: E402
from spinagram.qa import check  # noqa: E402

THEME = Theme.load("default")


@pytest.fixture
def icon(tmp_path):
    p = tmp_path / "i.svg"
    p.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>')
    return str(p)


def _kinds(build, icon):
    d = Diagram("C", "Check")
    build(d, icon)
    return sorted({(i.kind, i.item) for i in check(build_scene(d, THEME))
                   if i.kind in ("icon-touches-border", "icon-overflows-box", "header-overlap")})


ICON_HEADER_SCENARIOS = [
    ("clean", lambda d, i: (d.zone("Net", x=100, y=100, w=800, h=400, icon=i),
                            d.box("A", id="a", x=200, y=250, w=200, h=100, icon=i)), []),
    ("node-icon-on-zone-border", lambda d, i: (d.zone("Net", id="net", x=100, y=100, w=800, h=400),
                                               d.box(None, id="chip", x=80, y=200, w=60, h=60, icon=i, icon_size=30)),
     [("icon-touches-border", "chip")]),
    ("override-padding-touches", lambda d, i: d.zone("Net", x=100, y=100, w=800, h=400, icon=i,
                                                       header={"padding": 1}),
     [("icon-touches-border", "z0-icon")]),
    ("flush-aws-style-is-fine", lambda d, i: d.zone("Net", x=100, y=100, w=800, h=400, icon=i,
                                                     header={"inset": False}), []),
    ("icon-bigger-than-box", lambda d, i: d.box(None, id="tiny", x=300, y=300, w=40, h=40, icon=i, icon_size=60),
     [("icon-overflows-box", "tiny")]),
    ("node-over-header", lambda d, i: (d.zone("Net", x=100, y=100, w=800, h=400, icon=i),
                                       d.box("A", id="a", x=110, y=110, w=200, h=60)),
     [("header-overlap", "z0")]),
    ("free-label-on-header-baseline", lambda d, i: (d.zone("Net", x=100, y=100, w=800, h=400, icon=i),
                                                    d.label("NETWORK", x=170, y=135)),
     [("header-overlap", "z0")]),
]


@pytest.mark.parametrize("build,expected", [s[1:] for s in ICON_HEADER_SCENARIOS],
                         ids=[s[0] for s in ICON_HEADER_SCENARIOS])
def test_icon_and_header_diagnostics(icon, build, expected):
    assert _kinds(build, icon) == expected

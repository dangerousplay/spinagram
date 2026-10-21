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

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


# safe area and contrast (CHK-01) ------------------------------------------------------------------------------
from spinagram.qa import contrast  # noqa: E402

SAFE_SCENARIOS = [
    # id, box (x, y, w, h), expected detail or None (canvas 1920x1080, margin 80)
    ("inside", (80, 80, 300, 100), None),
    ("right-13px", (1553, 300, 300, 100), "13px past the right margin (80px)"),
    ("left", (60, 300, 300, 100), "20px past the left margin (80px)"),
    ("top", (300, 50, 300, 100), "30px past the top margin (80px)"),
    ("bottom", (300, 950, 300, 100), "50px past the bottom margin (80px)"),
]


@pytest.mark.parametrize("box,detail", [s[1:] for s in SAFE_SCENARIOS], ids=[s[0] for s in SAFE_SCENARIOS])
def test_outside_safe_area(box, detail):
    d = Diagram("C", "Check")
    x, y, w, h = box
    d.box("A", id="a", x=x, y=y, w=w, h=h)
    got = [i.detail for i in check(build_scene(d, THEME)) if i.kind == "outside-safe-area"]
    assert got == ([detail] if detail else [])


def test_safe_area_uses_theme_margin(tmp_path):
    (tmp_path / "theme.yaml").write_text("extends: default\ncanvas: {margin: 40}\n")
    d = Diagram("C", "Check")
    d.box("A", id="a", x=60, y=300, w=300, h=100)
    assert [i for i in check(build_scene(d, Theme.load(tmp_path))) if i.kind == "outside-safe-area"] == []


CONTRAST_PAIRS = [
    # id, text colour, fill, flagged at the default 2.0:1
    ("dark-on-white-21", "#000000", "#FFFFFF", False),
    ("white-on-white-1", "#FFFFFF", "#FFFFFF", True),
    ("grey-1.92", "#BBBBBB", "#FFFFFF", True),
    ("grey-2.32", "#AAAAAA", "#FFFFFF", False),
    ("green-on-dark-green-1.91", "#388E3C", "#1B5E20", True),
    ("slate-on-white", "#64748B", "#FFFFFF", False),
]


@pytest.mark.parametrize("fg,fill,flagged", [s[1:] for s in CONTRAST_PAIRS], ids=[s[0] for s in CONTRAST_PAIRS])
def test_low_contrast_text(tmp_path, fg, fill, flagged):
    (tmp_path / "theme.yaml").write_text(
        "extends: default\nstyles: {node: {t: {fill: '%s', stroke: '%s', title: '%s', body: '%s'}}}\n" % (fill, fill, fg, fg))
    d = Diagram("C", "Check")
    d.box("Title", id="a", x=200, y=200, w=300, h=150, text="body text", style="t")
    got = sorted(i.detail.split(" ")[0] for i in check(build_scene(d, Theme.load(tmp_path))) if i.kind == "low-contrast")
    assert got == (["body", "title"] if flagged else [])


@pytest.mark.parametrize("a,b,ratio", [("#000000", "#FFFFFF", 21.0), ("#FFFFFF", "#FFFFFF", 1.0),
                                       ("#767676", "#FFFFFF", 4.54)], ids=["max", "min", "aa-grey"])
def test_contrast_ratio_matches_wcag(a, b, ratio):
    assert contrast(a, b) == pytest.approx(ratio, abs=0.01)


def test_theme_raises_contrast_to_wcag(tmp_path):
    (tmp_path / "theme.yaml").write_text(
        "extends: default\ndefaults: {check: {contrast: {title: 3, body: 4.5, icon: 3}}}\n"
        "styles: {node: {t: {fill: '#FFFFFF', stroke: '#000000', title: '#94A3B8', body: '#94A3B8'}}}\n")
    d = Diagram("C", "Check")
    d.box("Title", id="a", x=200, y=200, w=300, h=150, text="body", style="t")
    got = sorted(i.detail.split(" ")[0] for i in check(build_scene(d, Theme.load(tmp_path))) if i.kind == "low-contrast")
    assert got == ["body", "title"]


@pytest.mark.parametrize("colours,flagged", [(["#205F24"], True), (["#2E7D32", "#FFFFFF"], False),
                                             (["#000000"], False)], ids=["mono-green", "two-colour", "mono-black"])
def test_low_contrast_single_colour_icon(tmp_path, colours, flagged):
    p = tmp_path / "i.svg"
    p.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">' +
                 "".join(f'<rect width="5" height="5" fill="{c}"/>' for c in colours) + "</svg>")
    (tmp_path / "theme.yaml").write_text(
        "extends: default\nstyles: {node: {t: {fill: '#1B5E20', stroke: '#1B5E20', title: '#FFFFFF', body: '#FFFFFF'}}}\n")
    d = Diagram("C", "Check")
    d.box("T", id="a", x=200, y=200, w=300, h=150, icon=str(p), style="t")
    got = [i for i in check(build_scene(d, Theme.load(tmp_path))) if i.kind == "low-contrast"]
    assert bool(got) == flagged


# fixes attached to issues (CHK-02) ---------------------------------------------------------------------------
LONG = "averyveryverylongunbreakabletoken"


def _issue(d, kind, item=None):
    sc = build_scene(d, THEME)
    return next(i for i in check(sc) if i.kind == kind and (item is None or i.item == item)), sc


def _kinds_after(d, kind):
    return [i for i in check(build_scene(d, THEME)) if i.kind == kind]


def test_fix_resize_width_clears_overflow_x():
    d = Diagram("F", "Fix")
    n = d.box(LONG, id="n", x=200, y=200, w=230, h=120, fit="none")
    i, _ = _issue(d, "overflow-x")
    assert i.fix["op"] == "resize" and i.fix["node"] == "n" and i.fix["w"] > 230
    n.w = i.fix["w"]
    assert _kinds_after(d, "overflow-x") == []


def test_fix_resize_height_clears_overflow_y():
    d = Diagram("F", "Fix")
    n = d.box("Managers", id="n", x=200, y=200, w=300, h=50, fit="none",
              text="three managers spread across two availability zones in one region")
    i, _ = _issue(d, "overflow-y")
    assert i.fix["op"] == "resize" and i.fix["h"] > 50
    n.h = i.fix["h"]
    assert _kinds_after(d, "overflow-y") == []


def test_fix_shrinks_font_when_resize_would_leave_the_safe_area():
    d = Diagram("F", "Fix")
    d.box(LONG, id="n", x=1600, y=200, w=230, h=120, fit="none")
    i, _ = _issue(d, "overflow-x")
    assert i.fix == {"op": "shrink-font", "node": "n", "title_size": 19}


@pytest.mark.parametrize("box,dx,dy", [((1553, 300), -13, 0), ((60, 300), 20, 0), ((300, 950), 0, -50)],
                         ids=["right", "left", "bottom"])
def test_fix_nudge_clears_outside_safe_area(box, dx, dy):
    d = Diagram("F", "Fix")
    n = d.box("A", id="n", x=box[0], y=box[1], w=300, h=100)
    i, _ = _issue(d, "outside-safe-area")
    assert i.fix == {"op": "nudge", "node": "n", "dx": dx, "dy": dy}
    n.x, n.y = n.x + dx, n.y + dy
    assert _kinds_after(d, "outside-safe-area") == []


def test_fix_nudge_clears_header_overlap(icon):
    d = Diagram("F", "Fix")
    d.zone("Net", x=100, y=100, w=800, h=400, icon=icon)
    n = d.box("A", id="a", x=110, y=110, w=200, h=60)
    i, _ = _issue(d, "header-overlap")
    assert i.fix["op"] == "nudge" and i.fix["node"] == "a" and i.fix["dx"] == 0
    n.y += i.fix["dy"]
    assert _kinds_after(d, "header-overlap") == []


def test_fix_move_label_finds_a_free_spot():
    from spinagram.engine.labels import overlap
    from spinagram.scene import Shape
    d = Diagram("F", "Fix")
    a = d.box("A", id="a", x=200, y=400, w=200, h=100)
    b = d.box("B", id="b", x=460, y=400, w=200, h=100)
    e = d.edge(a, b, "replication")
    i, _ = _issue(d, "label-collision")
    assert i.fix["op"] == "move-label" and i.fix["edge"] == "e0"
    e.label_at = tuple(i.fix["to"])
    sc = build_scene(d, THEME)
    lab = next(c for c in sc.items if getattr(c, "id", "") == "e0").label
    nodes = [s for s in sc.items if isinstance(s, Shape) and s.role == "node"]
    assert all(overlap((lab.x, lab.y, lab.w, lab.h), (s.x, s.y, s.w, s.h)) < 0.5 for s in nodes)


def test_fix_resize_clears_icon_overflow(icon):
    d = Diagram("F", "Fix")
    n = d.box(None, id="tiny", x=300, y=300, w=40, h=40, icon=icon, icon_size=60)
    i, _ = _issue(d, "icon-overflows-box")
    assert i.fix["op"] == "resize"
    n.w, n.h = i.fix["w"], i.fix["h"]
    assert _kinds_after(d, "icon-overflows-box") == []

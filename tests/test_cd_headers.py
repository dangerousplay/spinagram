"""Zone headers: align right/none (HDR-06, HDR-07)."""
import pytest

from spinagram import Diagram, Theme, build_scene
from spinagram.engine.zones import header_options
from spinagram.model import Zone
from spinagram.scene import Shape, Text
from spinagram.text import measure
from spinagram.yaml_io import from_dict

THEME = Theme.load("default")
FONT = THEME.font("body", 700, 16)  # zone label: body, bold, label_size 16, upper (no tracking by default)
X, Y, W, H = 100, 200, 600, 300     # zone under test


@pytest.fixture
def icon_path(tmp_path):
    p = tmp_path / "icon.svg"
    p.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>')
    return str(p)


def _scene(header, icons, label, icon_path):
    d = Diagram("Z", "Zones")
    icon = [icon_path] * icons if icons else None
    d.zone(label, x=X, y=Y, w=W, h=H, icon=icon, header=header)
    sc = build_scene(d, THEME)
    return {i.id: i for i in sc.items if isinstance(i, (Shape, Text))}, sc


# expected geometry, by hand. Inset header: padding 14, icon 28, chip_gap 8, label_gap 10.
# One-line label (size 16, leading 20.8) centred on the icon slot centre y = 200 + 14 + 14 = 228:
#   baseline = 228 - 10.4 + 2.4 + 12.8 = 232.8; header bottom = 200 + 14 + 28 = 242.
# No icons: label at baseline 236 (200 + 36), header bottom 200 + 36 + 16 * 0.3 = 240.8.
GEOMETRY = {  # (align, icons) → (icon xs, label x, label anchor, baseline, header bottom)
    ("left", 0): ([], 124, "start", 236, 240.8),
    ("left", 1): ([114], 114 + 28 + 10, "start", 232.8, 242),
    ("left", 2): ([114, 150], 150 + 28 + 10, "start", 232.8, 242),
    ("right", 0): ([], 700 - 24, "end", 236, 240.8),
    ("right", 1): ([700 - 14 - 28], 658 - 10, "end", 232.8, 242),
    ("right", 2): ([622, 658], 622 - 10, "end", 232.8, 242),
}
LABELS = {"short": "AZ", "long": "Availability zone site-a · RHEL 9"}
ALIGN_SCENARIOS = [pytest.param(align, icons, lab, id=f"{align}-{icons}icons-{lab}")
                   for (align, icons) in GEOMETRY for lab in LABELS]


@pytest.mark.parametrize("align,icons,lab", ALIGN_SCENARIOS)
@pytest.mark.parametrize("form", ["str", "dict"])
def test_header_align_geometry(icon_path, align, icons, lab, form):
    header = align if form == "str" else {"align": align}
    by, sc = _scene(header, icons, LABELS[lab], icon_path)
    xs, lx, anchor, baseline, bottom = GEOMETRY[(align, icons)]
    chips = [by["z0-icon"]] + [by[f"z0-icon{k}"] for k in range(1, icons)] if icons else []
    assert [c.icon.x for c in chips] == pytest.approx(xs)                     # icons from the chosen side
    assert all(c.icon.size == 28 and c.icon.y == 214 for c in chips)
    label = by["z0-label"]
    assert (label.x, label.anchor) == (pytest.approx(lx), anchor)              # label ends label_gap before icons
    assert label.y == pytest.approx(baseline)
    width = measure(LABELS[lab].upper(), FONT)
    left = lx if align == "left" else lx - width
    right = lx + width if align == "left" else X + W
    if align == "left":
        left, right = X, max(X + 24, right, *(x + 28 for x in xs))
    else:
        left = min(X + W - 24, left, *xs)
    assert sc.zone_headers["z0"] == pytest.approx((left, Y, right - left, bottom - Y))  # exactly those items
    assert sc.zone_content_tops["z0"] == pytest.approx(bottom + 12)


@pytest.mark.parametrize("icons", [0, 1, 2], ids=lambda n: f"{n}icons")
@pytest.mark.parametrize("header", ["none", {"align": "none"}], ids=["str", "dict"])
def test_header_none_draws_nothing(icon_path, icons, header):
    by, sc = _scene(header, icons, "Site A", icon_path)
    assert not [k for k in by if k.startswith("z0-icon") or k == "z0-label"]   # neither icon nor label
    assert "z0" not in sc.zone_headers                                         # no header rect
    assert sc.zone_content_tops["z0"] == Y + 24                                # content starts at the padding


def test_header_none_zone_still_checked(icon_path):  # zone-clips-child keeps working without a header rect
    from spinagram.qa import check
    d = Diagram("Z", "Zones")
    with d.zone("Site A", x=X, y=Y, w=W, h=H, header="none"):
        d.box("A", id="a", x=600, y=300, w=200, h=100)
    kinds = {(i.item, i.kind) for i in check(build_scene(d, THEME))}
    assert ("z0", "zone-clips-child") in kinds


@pytest.mark.parametrize("header,expected", [
    (None, "left"), ("left", "left"), ("right", "right"), ("none", "none"), ({"align": "right"}, "right"),
    ({"padding": 20}, "left"), ({"align": "none", "padding": 20}, "none")],
    ids=["unset", "left", "right", "none", "dict-right", "dict-no-align", "dict-none"])
def test_header_options_normalise_align(header, expected):
    assert header_options(Zone(x=0, y=0, w=10, h=10, header=header), None, None)["align"] == expected


@pytest.mark.parametrize("header", ["center", {"align": "middle"}, "RIGHT"], ids=["str", "dict", "case"])
def test_unknown_header_align_raises(header):
    d = Diagram("Z", "Zones")
    d.zone("Site A", x=X, y=Y, w=W, h=H, header=header)
    with pytest.raises(ValueError, match=r"zone header align .*; use left, right or none"):
        build_scene(d, THEME)


@pytest.mark.parametrize("header", ["right", "none", {"align": "right", "padding": 20}],
                         ids=["right", "none", "dict"])
def test_yaml_header_align_parity(header):
    d = Diagram("Z", "Zones")
    z = d.zone("Net", x=X, y=Y, w=W, h=H, header=header)
    y = from_dict({"id": "Z", "title": "Zones", "zones": [{"label": "Net", "x": X, "y": Y, "w": W, "h": H,
                                                          "header": header}]})
    assert y.zones[0] == z
    a, b = build_scene(d, THEME), build_scene(y, THEME)
    assert a.zone_headers == b.zone_headers and a.zone_content_tops == b.zone_content_tops


# edge-crosses-zone-header (HDR-02, HDR-03) -------------------------------------------------------------------
from spinagram.qa import check  # noqa: E402

LONG = "Availability zone site-a"   # header rect: x 100 → 124 + label width (> 300), y 200 → 240.8


def _crossing_scene(edge):
    """Zone z0 (100, 200, 600, 300) with a long header label; a above it, b inside it below the header,
    c far right of the header, inside the zone."""
    d = Diagram("Z", "Zones")
    with d.zone(LONG, x=X, y=Y, w=W, h=H):
        d.box("B", id="b", x=100, y=400, w=80, h=60)
        d.box("C", id="c", x=600, y=400, w=80, h=60)
    d.box("A", id="a", x=100, y=80, w=80, h=60)
    d.box("D", id="d", x=600, y=80, w=80, h=60)
    src, dst, kw = edge
    d.edge(src, dst, **kw)
    sc = build_scene(d, THEME)
    hx, hy, hw, hh = sc.zone_headers["z0"]
    assert (hx, hy) == (100, 200) and hx + hw > 300 and hx + hw < 590 and hh == pytest.approx(40.8)
    return sc


CROSSING_SCENARIOS = [  # (id, (src, dst, edge kwargs), reported)
    ("straight-through", ("a", "b", {}), True),               # (140,140) → (140,400) through the header
    ("straight-near", ("d", "c", {}), False),                 # x = 640, right of the header
    ("poly-through", ("d", "b", {"via": [(640, 220), (140, 220)]}), True),  # runs inside the header
    ("poly-near", ("d", "b", {"via": [(640, 300), (140, 300)]}), False),    # below the header
    ("poly-inset-clear", ("d", "b", {"via": [(640, 240.3), (140, 240.3)]}), False),  # 0.5 px inside: in the 1 px inset
    ("poly-inset-hit", ("d", "b", {"via": [(640, 239.3), (140, 239.3)]}), True),     # 1.5 px inside: past the inset
    ("curve-through", ("a", "b", {"curve": (300, 270)}), True),            # bulges into the header
    ("curve-near", ("d", "c", {"curve": (560, 270)}), False),
    ("own-zone-target", ("b", "zone:z0.top@0.0666667", {}), False),        # final segment to its zone border
    ("own-zone-source", ("zone:z0.top@0.0666667", "b", {}), False),        # first segment from its border
    ("own-zone-earlier-segment", ("a", "zone:z0.left@0.333333", {"via": [(140, 300)]}), True),
]


@pytest.mark.parametrize("edge,reported", [s[1:] for s in CROSSING_SCENARIOS], ids=[s[0] for s in CROSSING_SCENARIOS])
def test_edge_crosses_zone_header(edge, reported):
    sc = _crossing_scene(edge)
    got = [i for i in check(sc) if i.kind == "edge-crosses-zone-header"]
    if not reported:
        assert got == []
        return
    assert len(got) == 1                                                   # one issue per (edge, zone)
    i = got[0]
    assert i.item == "e0"
    assert i.detail == "crosses the header of zone 'z0'"
    assert i.severity == "P0"


def test_header_crossing_one_issue_per_zone_and_edge():
    d = Diagram("Z", "Zones")
    d.zone(LONG, x=X, y=Y, w=W, h=H)
    d.zone(LONG, x=X, y=600, w=W, h=300)
    d.box("A", id="a", x=100, y=80, w=80, h=60)
    d.box("B", id="b", x=100, y=950, w=80, h=60)
    d.edge("a", "b", via=[(140, 220), (200, 220), (140, 620)])    # z0 header twice, z1 header once
    got = [(i.item, i.detail) for i in check(build_scene(d, THEME)) if i.kind == "edge-crosses-zone-header"]
    assert got == [("e0", "crosses the header of zone 'z0'"), ("e0", "crosses the header of zone 'z1'")]


def test_header_crossing_hand_placed_only():
    sc = _crossing_scene(("a", "b", {}))
    sc.laid_out = True
    assert not [i for i in check(sc) if i.kind == "edge-crosses-zone-header"]


# anchor and reroute fixes (HDR-04, HDR-05) --------------------------------------------------------------------
# The measured font is 9.6 px per character at 16 px: LONG's header ends at 124 + 24 × 9.6 = 354.4, so its
# interior (shrunk by 1 px) is x 101 → 353.4, y 201 → 239.8. a = (100, 80, 400, 60), b = (100, 400, 400, 60):
# an anchor at fraction f sits at x = 100 + 400 f. A segment from (px, 140) to (qx, 400) is inside the header band
# for t = (y - 140) / 260 in 0.2346 → 0.3838.
#   fs 0.5  (px 300): x at the band top ≤ 300 + 140 × 0.2346 = 332.8 for every fd → all hit.
#   fs 0.65 (px 360): fd 0.5 (qx 300) → x at the band bottom 360 - 60 × 0.3838 = 337 → hit;
#                     fd 0.65 (qx 360) → vertical at 360 → clear: the first pair.
#   with a blocker c = (340, 300, 40, 40): (0.65, 0.65) hits c; fd 0.35 (qx 240) → 313.9 in the band → hit;
#                     fd 0.8 (qx 420) → x ≥ 360 in the band and 396.9 → 406 at y 300 → 340 (c is x 341 → 379): clear.
#   WIDE header (label 50 chars → ends at 124 + 480 = 604): every anchor x (160 → 440) is under it → reroute.
# Fraction order (two candidates clear, the order picks): zone "AZ1" at x 320 → header 320 → 372.8 (interior
# x 321 → 371.8); a = (100, 80, 500, 60), b = (100, 400, 500, 60): an anchor at fraction f sits at x = 100 + 500 f.
#   zone y 200 (band t 0.2346 → 0.3838), the destination decides. fs 0.5 (px 350):
#     fd 0.5 (qx 350) → vertical at 350 → hit; fd 0.65 (qx 425) → x 367.6 at the band top → hit;
#     fd 0.35 (qx 275) → 332.4 → 321.2 → hit; fd 0.8 (qx 500) → 385.2 → 407.6 → clear: (0.5, 0.8).
#     fd 0.2 (qx 200) → 314.8 → 292.4 would also clear: 0.2 before 0.8 gives (0.5, 0.2).
#   zone y 150 (header 150 → 190.8, interior y 151 → 189.8, band t 0.0423 → 0.1915), the source decides.
#     fs 0.5 (px 350): every qx (175 → 525) keeps x within 350 ± 7.4 at the band top → all hit.
#     fs 0.65 (px 425), fd 0.5 (qx 350) → 421.8 → 410.6 → clear: (0.65, 0.5).
#     fs 0.35 (px 275), fd 0.5 → 278.2 → 289.4 would also clear: 0.35 before 0.65 gives (0.35, 0.5).
WIDE = "Availability zone site-a · primary · consul server"   # 50 characters


def _fix_scene(label=LONG, blocker=False, edge=("a.bottom", "b.top", {}), zx=X, zy=Y, bw=400):
    d = Diagram("Z", "Zones")
    with d.zone(label, x=zx, y=zy, w=W, h=H):
        d.box("B", id="b", x=100, y=400, w=bw, h=60)
        if blocker:
            d.box("C", id="c", x=340, y=300, w=40, h=60)
    d.box("A", id="a", x=100, y=80, w=bw, h=60)
    src, dst, kw = edge
    d.edge(src, dst, **kw)
    return d


FIX_SCENARIOS = [  # (id, scene kwargs, expected fix)
    ("anchor-first-pair", {}, {"op": "anchor", "edge": "e0", "src": "a.bottom@0.65", "dst": "b.top@0.65"}),
    ("anchor-skips-node", {"blocker": True}, {"op": "anchor", "edge": "e0", "src": "a.bottom@0.65",
                                              "dst": "b.top@0.8"}),
    ("anchor-auto-sides", {"edge": ("a", "b", {})},
     {"op": "anchor", "edge": "e0", "src": "a.bottom@0.65", "dst": "b.top@0.65"}),
    ("reroute", {"label": WIDE}, {"op": "reroute", "edge": "e0", "route": "ortho"}),
    ("fraction-order-destination", {"label": "AZ1", "zx": 320, "bw": 500},
     {"op": "anchor", "edge": "e0", "src": "a.bottom@0.5", "dst": "b.top@0.8"}),
    ("fraction-order-source", {"label": "AZ1", "zx": 320, "zy": 150, "bw": 500},
     {"op": "anchor", "edge": "e0", "src": "a.bottom@0.65", "dst": "b.top@0.5"}),
    ("zone-end-no-fix", {"edge": ("a", "zone:z0.left@0.333333", {"via": [(140, 300)]})}, None),
    ("via-no-fix", {"edge": ("a", "b", {"via": [(300, 220), (300, 400)]})}, None),
    ("curve-no-fix", {"edge": ("a", "b", {"curve": (300, 270)})}, None),
]


@pytest.mark.parametrize("kw,fix", [s[1:] for s in FIX_SCENARIOS], ids=[s[0] for s in FIX_SCENARIOS])
def test_header_crossing_fix(kw, fix):
    sc = build_scene(_fix_scene(**kw), THEME)
    label = kw.get("label", LONG)    # header w = 24 + 9.6 per character: LONG 254.4, WIDE 504, AZ1 52.8
    zx, zy = kw.get("zx", X), kw.get("zy", Y)
    assert sc.zone_headers["z0"] == pytest.approx((zx, zy, 24 + 9.6 * len(label), 40.8))
    got = [i for i in check(sc) if i.kind == "edge-crosses-zone-header"]
    assert len(got) == 1 and got[0].fix == fix


APPLY = [("anchor", {}, {"src": "a.bottom@0.65", "dst": "b.top@0.65", "route": None}),
         ("reroute", {"label": WIDE}, {"src": "a.bottom", "dst": "b.top", "route": "ortho"})]


@pytest.mark.parametrize("kw,edge", [s[1:] for s in APPLY], ids=[s[0] for s in APPLY])
def test_apply_anchor_and_reroute(kw, edge):
    from spinagram.engine.fix import apply_to_diagram
    d = _fix_scene(**kw)
    issues = [i for i in check(build_scene(d, THEME)) if i.kind == "edge-crosses-zone-header"]
    fixed, applied, skipped = apply_to_diagram(d, issues)
    assert len(applied) == 1 and skipped == []
    e = fixed.edges[0]
    assert {"src": e.src, "dst": e.dst, "route": e.route} == edge
    assert (d.edges[0].src, d.edges[0].dst, d.edges[0].route) == ("a.bottom", "b.top", None)  # source untouched
    after = check(build_scene(fixed, THEME))
    assert [i for i in after if i.kind in ("edge-crosses-zone-header", "edge-through-box")] == []


def _yaml_spec(label):
    return (f"id: F1\ntitle: Fix\nzones:\n  - {{label: '{label}', x: 100, y: 200, w: 600, h: 300}}\n"
            "nodes:\n  - {id: a, title: A, x: 100, y: 80, w: 400, h: 60}\n"
            "  - {id: b, title: B, x: 100, y: 400, w: 400, h: 60}\n"
            "edges:\n  - {from: a.bottom, to: b.top}\n")


@pytest.mark.parametrize("label,edge", [(LONG, {"from": "a.bottom@0.65", "to": "b.top@0.65"}),
                                        (WIDE, {"from": "a.bottom", "to": "b.top", "route": "ortho"})],
                         ids=["anchor", "reroute"])
def test_check_fix_yaml_applies_header_fixes(tmp_path, monkeypatch, capsys, label, edge):
    import yaml
    from spinagram import load
    from spinagram.cli import main
    (tmp_path / "s.yaml").write_text(_yaml_spec(label))
    monkeypatch.chdir(tmp_path)
    main(["check", "--fix", "s.yaml"])
    assert "s.fixed.yaml" in capsys.readouterr().out
    data = yaml.safe_load((tmp_path / "s.fixed.yaml").read_text())
    assert data["edges"][0] == edge
    d = load(tmp_path / "s.fixed.yaml")[0]
    assert [i for i in check(build_scene(d, THEME)) if i.kind == "edge-crosses-zone-header"] == []


@pytest.mark.parametrize("label,line", [(LONG, 'e0: src="a.bottom@0.65", dst="b.top@0.65"'),
                                        (WIDE, 'e0: route="ortho"')], ids=["anchor", "reroute"])
def test_check_fix_python_suggests_header_fixes(tmp_path, monkeypatch, capsys, label, line):
    from spinagram.cli import main
    src = ("from spinagram import Diagram\nd = Diagram('P1', 'Py')\n"
           f"with d.zone({label!r}, x=100, y=200, w=600, h=300):\n"
           "    d.box('B', id='b', x=100, y=400, w=400, h=60)\n"
           "d.box('A', id='a', x=100, y=80, w=400, h=60)\nd.edge('a.bottom', 'b.top')\ndiagram = d\n")
    (tmp_path / "s.py").write_text(src)
    monkeypatch.chdir(tmp_path)
    main(["check", "--fix", "s.py"])
    out = capsys.readouterr().out.splitlines()
    assert any(row.endswith(f"s.py: {line}") for row in out)

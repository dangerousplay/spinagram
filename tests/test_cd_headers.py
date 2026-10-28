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

"""Zone rows placed in the zone content area (BND-02, BND-03, BND-06, BND-07)."""
import pytest

from spinagram import Diagram, Theme, build_scene
from spinagram.scene import Shape
from spinagram.text import measure

THEME = Theme.load("default")


@pytest.fixture
def icon_path(tmp_path):
    p = tmp_path / "icon.svg"
    p.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>')
    return str(p)


def _rects(d, ids):
    by = {i.id: i for i in build_scene(d, THEME).items if isinstance(i, Shape)}
    return [(by[k].x, by[k].y, by[k].w, by[k].h) for k in ids]


# Content area, by hand. Band (330, 500) → zone 80, 330, 1760 x 170. Pad 24 → x 104 … 1816 (1712 wide), bottom 476.
# Header without icon: bottom 330 + 36 + 16 * 0.3 = 370.8, content top + 12 = 382.8 (93.2 tall).
# One header icon: bottom 330 + 14 + 28 = 372, content top 384 (92 tall). Pad 40: x 120 … 1800 (1680), bottom 460.
# Band (100, 500): content top 152.8, bottom 476 (323.2 tall).
PLACE_SCENARIOS = [  # (id, axis, band, sizes (w, h), row kwargs, zone kwargs, icon, expected (x, y, w, h) per card)
    ("4-center", "row", (330, 500), [(200, 80)] * 4, {}, {}, False,
     # block 4 * 200 + 3 * 20 = 860 → x 104 + (1712 - 860) / 2 = 530; y 382.8 + (93.2 - 80) / 2 = 389.4
     [(530, 389.4, 200, 80), (750, 389.4, 200, 80), (970, 389.4, 200, 80), (1190, 389.4, 200, 80)]),
    ("4-start", "row", (330, 500), [(200, 80)] * 4, {"align": "start"}, {}, False,
     [(104, 382.8, 200, 80), (324, 382.8, 200, 80), (544, 382.8, 200, 80), (764, 382.8, 200, 80)]),
    ("4-end", "row", (330, 500), [(200, 80)] * 4, {"align": "end"}, {}, False,
     # x 1816 - 860 = 956, vertically centred
     [(956, 389.4, 200, 80), (1176, 389.4, 200, 80), (1396, 389.4, 200, 80), (1616, 389.4, 200, 80)]),
    ("3-same-size-center", "row", (330, 500), [(200, 80), (260, 80), (140, 80)], {"same_size": True}, {}, False,
     # all 260 wide: block 820 → x 104 + 446 = 550
     [(550, 389.4, 260, 80), (830, 389.4, 260, 80), (1110, 389.4, 260, 80)]),
    ("cols4-3-center", "row", (330, 500), [(200, 80)] * 3, {"cols": 4}, {}, False,
     # w (1712 - 3 * 20) / 4 = 413; block 3 * 413 + 40 = 1279 → x 104 + 216.5 = 320.5
     [(320.5, 389.4, 413, 80), (753.5, 389.4, 413, 80), (1186.5, 389.4, 413, 80)]),
    ("cols4-4-center", "row", (330, 500), [(200, 80)] * 4, {"cols": 4}, {}, False,
     [(104, 389.4, 413, 80), (537, 389.4, 413, 80), (970, 389.4, 413, 80), (1403, 389.4, 413, 80)]),
    ("cols2-gap40-start", "row", (330, 500), [(200, 80)] * 2, {"cols": 2, "gap": 40, "align": "start"}, {}, False,
     # w (1712 - 40) / 2 = 836
     [(104, 382.8, 836, 80), (980, 382.8, 836, 80)]),
    ("pad40-center", "row", (330, 500), [(200, 60)] * 4, {}, {"padding": 40}, False,
     # x 120 + (1680 - 860) / 2 = 530; y 382.8 + (460 - 382.8 - 60) / 2 = 391.4
     [(530, 391.4, 200, 60), (750, 391.4, 200, 60), (970, 391.4, 200, 60), (1190, 391.4, 200, 60)]),
    ("icon-center", "row", (330, 500), [(200, 80)] * 4, {}, {}, True,
     # y 384 + (92 - 80) / 2 = 390
     [(530, 390, 200, 80), (750, 390, 200, 80), (970, 390, 200, 80), (1190, 390, 200, 80)]),
    ("icon-cols2-start", "row", (330, 500), [(200, 80)] * 2, {"cols": 2, "align": "start"}, {}, True,
     # w (1712 - 20) / 2 = 846
     [(104, 384, 846, 80), (970, 384, 846, 80)]),
    ("column-3-center", "column", (100, 500), [(200, 80)] * 3, {}, {}, False,
     # block 200 x 280 → x 104 + (1712 - 200) / 2 = 860; y 152.8 + (323.2 - 280) / 2 = 174.4
     [(860, 174.4, 200, 80), (860, 274.4, 200, 80), (860, 374.4, 200, 80)]),
    ("column-3-end", "column", (100, 500), [(200, 80)] * 3, {"align": "end"}, {}, False,
     [(1616, 174.4, 200, 80), (1616, 274.4, 200, 80), (1616, 374.4, 200, 80)]),
    ("column-3-start", "column", (100, 500), [(200, 80)] * 3, {"align": "start"}, {}, False,
     [(104, 152.8, 200, 80), (104, 252.8, 200, 80), (104, 352.8, 200, 80)]),
]


@pytest.mark.parametrize("axis,band,sizes,row_kw,zone_kw,icon,expected", [s[1:] for s in PLACE_SCENARIOS],
                         ids=[s[0] for s in PLACE_SCENARIOS])
def test_zone_container_placement(icon_path, axis, band, sizes, row_kw, zone_kw, icon, expected):
    d = Diagram("B", "Bands")
    with d.zone("Secrets Manager", id="sm", band=band, icon=icon_path if icon else None, **zone_kw):
        nodes = getattr(d, axis)([{"title": f"C{k}", "w": w, "h": h} for k, (w, h) in enumerate(sizes)], **row_kw)
    assert _rects(d, [n.id for n in nodes]) == [pytest.approx(r) for r in expected]


def test_default_max_width_is_content_width():
    # zone 100, 330, 600 x 170 → content 124 … 676 (552); 3 same_size 300-wide cards: room (552 - 40) / 3
    d = Diagram("B", "Bands")
    with d.zone("SG", id="sg", band=(330, 500), x=100, w=600):
        nodes = d.row([{"title": t, "w": 300, "h": 80} for t in "ABC"], same_size=True)
    w = 512 / 3
    assert _rects(d, [n.id for n in nodes]) == [pytest.approx((124 + k * (w + 20), 389.4, w, 80)) for k in range(3)]


def test_explicit_max_width_wins():
    d = Diagram("B", "Bands")
    with d.zone("SG", id="sg", band=(330, 500), x=100, w=600):
        nodes = d.row([{"title": t, "w": 300, "h": 80} for t in "AB"], same_size=True, max_width=320)
    # width min(300, (320 - 20) / 2) = 150; block 320 → x 124 + (552 - 320) / 2 = 240
    assert _rects(d, [n.id for n in nodes]) == [pytest.approx((240, 389.4, 150, 80)), pytest.approx((410, 389.4, 150, 80))]


def test_row_too_wide_for_the_zone_cannot_fit():
    # content 252 wide; 4 same_size cards: (252 - 60) / 4 = 48 px; "IAM" at min scale needs its width + 2 * 22
    d = Diagram("B", "Bands")
    with d.zone("SG", id="sg", band=(330, 500), x=100, w=300):
        d.row([{"title": "IAM", "id": f"iam{k}", "w": 200, "h": 80} for k in range(4)], same_size=True)
    needs = measure("IAM", THEME.font("heading", 700, 24 * 0.85)) + 44
    with pytest.raises(ValueError) as err:
        build_scene(d, THEME)
    assert str(err.value) == (f"B: row cannot fit 'iam0' in 48px (needs {needs:.0f}px); "
                              "raise max_width or shorten the text")


def test_more_members_than_cols():
    d = Diagram("B", "Bands")
    with d.zone("SG", id="sg", band=(330, 500)):
        d.row([{"title": f"C{k}", "w": 200, "h": 80} for k in range(5)], cols=4)
    with pytest.raises(ValueError) as err:
        build_scene(d, THEME)
    assert str(err.value) == "B: row in zone 'sg' has 5 members, more than cols=4"


def test_zone_row_follows_a_hand_placed_zone():  # no band: the zone's own rect
    d = Diagram("B", "Bands")
    with d.zone("SG", id="sg", x=200, y=100, w=1000, h=200):
        nodes = d.row([{"title": "A", "w": 200, "h": 80}], align="start")
    assert _rects(d, [nodes[0].id]) == [pytest.approx((224, 152.8, 200, 80))]


def test_empty_zone_row_is_ignored():
    d = Diagram("B", "Bands")
    with d.zone("SG", id="sg", band=(330, 500)), d.row():
        pass
    assert _rects(d, ["z0"]) == [(80, 330, 1760, 170)]                 # builds; the zone keeps its band


# Zone rows of items without w/h are sized from their content (BND-04), like any node without a size. Default
# theme: title 24 px bold at 0.6 em = 14.4 px per character, padding 22, auto min_w 220 / max_w 360 / min_h 96.
#   "Short": 5 × 14.4 = 72 + 2 × 22 + 4 = 120 → min_w 220; one line 24 × 1.15 = 27.6 + 44 = 71.6 → min_h 96.
#   "A much longer card title": 24 × 14.4 = 345.6 + 48 = 393.6 → max_w 360; text width 360 − 44 = 316 holds
#   "A much longer card" (259.2) but not the whole title (345.6) → 2 lines: 2 × 27.6 + 44 = 99.2.
# Band (300, 600) → zone 80, 300, 1760 x 300: content x 104 … 1816 (1712), top 300 + 40.8 + 12 = 352.8, bottom 576
# (223.2 tall). The block (row gap 20) is centred; its height is the tallest card's, cards share its top.
CONTENT_SIZE_SCENARIOS = [  # (id, titles, expected (x, y, w, h) per card)
    # block 220 + 20 + 360 = 600 → x 104 + 556 = 660; y 352.8 + (223.2 − 99.2) / 2 = 414.8
    ("short-and-long", ["Short", "A much longer card title"], [(660, 414.8, 220, 96), (900, 414.8, 360, 99.2)]),
    # x 104 + (1712 − 220) / 2 = 850; y 352.8 + (223.2 − 96) / 2 = 416.4
    ("one-short", ["Short"], [(850, 416.4, 220, 96)]),
]


@pytest.mark.parametrize("titles,expected", [s[1:] for s in CONTENT_SIZE_SCENARIOS],
                         ids=[s[0] for s in CONTENT_SIZE_SCENARIOS])
def test_zone_row_without_sizes_gets_content_sizes(titles, expected):
    d = Diagram("B", "Bands")
    with d.zone("Secrets Manager", id="sm", band=(300, 600)):
        nodes = d.row(titles)
    assert [(n.w, n.h) for n in nodes] == [(0, 0)] * len(titles)          # sized at layout, not at build time
    assert _rects(d, [n.id for n in nodes]) == [pytest.approx(r) for r in expected]
    plain = Diagram("P", "Plain")                                              # the same titles, placed by hand
    loose = [plain.box(t, x=100 + 400 * k, y=200) for k, t in enumerate(titles)]
    assert [r[2:] for r in _rects(plain, [n.id for n in loose])] == [pytest.approx(r[2:]) for r in expected]


def test_headerless_zone_row_starts_at_the_zone_padding():  # BND-02: no header, so the content top is y + padding
    d = Diagram("B", "Bands")
    with d.zone("SG", id="sg", header="none", padding=40, band=(300, 600)):
        nodes = d.row(["One", "Two"], align="start")
    assert [r[1] for r in _rects(d, [n.id for n in nodes])] == [pytest.approx(340)] * 2

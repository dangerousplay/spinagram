"""Centred icons and text (ICO-01..03, ICO-07): the icon reserves its height, shrinks before the text does."""
import pytest

from spinagram import Diagram, Theme, build_scene
from spinagram.scene import Shape

THEME = Theme.load("default")
X0, Y0 = 200, 200
BODY = "two lines of text here maybe"   # 2 lines at 196 px (240 - 2 × 22 padding), 18 px × 1.32 = 23.76 each


@pytest.fixture
def icon(tmp_path):
    p = tmp_path / "i.svg"
    p.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>')
    return str(p)


def _card(icon, w, h, title, body=None, theme=THEME, **kw):
    d = Diagram("I", "Icons")
    d.box(title, id="n", x=X0, y=Y0, w=w, h=h, icon=icon, align="center", text=body, **kw)
    sc = build_scene(d, theme)
    return next(s for s in sc.items if isinstance(s, Shape) and s.id == "n")


# Expected icon sizes by hand. Default theme: icon_size_center 40, icon_scale 0.26, icon at y + 16, gap 8, floor 24.
# Text heights: title 24 × 1.15 = 27.6 per line, body 23.76 per line, 10 between blocks.
#   api:       240 × 200, "API"                     → isz max(40, 52) = 52; needs 27.6 ≤ 200 - 76 → keeps 52
#   gateway:   240 × 140, "Gateway" + BODY           → isz 40; needs 27.6 + 10 + 47.52 = 85.12 ≤ 140 - 24 - s + 0.5
#                                                      → s ≤ 31.38: 40 → 31 in 1 px steps, first fit 31
#   floor:     240 × 160, "Service mesh gateway" + BODY → isz 41.6; needs 55.2 + 10 + 47.52 = 112.72 → s ≤ 24.28 - 0.5
#                                                      … 24.6 fails, the floor 24 fails (112 + 0.5 < 112.72): keeps 24,
#                                                      the normal fit shrinks the text
#   explicit-big:   icon_size 80 on api             → 200 - 104 = 96 ≥ 27.6 → keeps 80
#   explicit-small: icon_size 20 on floor           → 160 - 44 = 116 ≥ 112.72 → keeps 20 (never enlarged)
CENTRED = [  # (id, w, h, title, body, kwargs, expected icon size)
    ("api", 240, 200, "API", None, {}, 52),
    ("gateway", 240, 140, "Gateway", BODY, {}, 31),
    ("floor", 240, 160, "Service mesh gateway", BODY, {}, 24),
    ("explicit-big", 240, 200, "API", None, {"icon_size": 80}, 80),
    ("explicit-small", 240, 160, "Service mesh gateway", BODY, {"icon_size": 20}, 20),
]


@pytest.mark.parametrize("w,h,title,body,kw,size", [s[1:] for s in CENTRED], ids=[s[0] for s in CENTRED])
def test_centred_icon_reserves_its_height(icon, w, h, title, body, kw, size):
    s = _card(icon, w, h, title, body, **kw)
    ic = s.icon
    assert ic.size == pytest.approx(size)                                  # ICO-02: shrunk in 1 px steps
    assert (ic.x, ic.y) == (pytest.approx(X0 + w / 2 - size / 2), Y0 + 16)  # centred, 16 px from the top
    bottom = Y0 + 16 + size
    assert s.label.box[1] == pytest.approx(bottom + 8)                     # ICO-01: label box at icon bottom + gap
    _, _, top = s.label.place()[0]
    assert top >= bottom + 8 - 0.5                                         # first text line clear of the icon
    assert ic.size >= min(24, kw.get("icon_size", 24))                     # never under icon_min (unless explicit)


def test_floor_card_falls_back_to_the_normal_fit(icon):  # ICO-03: text shrinks once the icon is at icon_min
    s = _card(icon, 240, 160, "Service mesh gateway", BODY)
    assert s.label.blocks[0].font.size < 24
    total = sum(b.height for b in s.label.blocks) + s.label.gap * (len(s.label.blocks) - 1)
    assert total <= 160 - (16 + 24 + 8) + 0.5


def test_explicit_small_icon_never_enlarged_and_overflow_reported(icon):  # ICO-02/03
    from spinagram.qa import check
    d = Diagram("I", "Icons")  # 240 × 120: 120 - 44 = 76 px for 112.72 px of text, shrinking to 0.85 is not enough
    d.box("Service mesh gateway", id="n", x=X0, y=Y0, w=240, h=120, icon=icon, align="center", text=BODY,
          icon_size=20)
    sc = build_scene(d, THEME)
    s = next(i for i in sc.items if isinstance(i, Shape) and i.id == "n")
    assert s.icon.size == 20 and s.label.box[1] == Y0 + 16 + 20 + 8
    assert [i.item for i in check(sc) if i.kind == "overflow-y"] == ["n"]


@pytest.mark.parametrize("w,h", [(120, 60), (80, 80)], ids=["chip", "square"])
def test_icon_only_centred_box_unchanged(icon, w, h):
    s = _card(icon, w, h, None)
    isz = max(40, h * 0.26)
    assert (s.icon.x, s.icon.y, s.icon.size) == (X0 + (w - isz) / 2, Y0 + (h - isz) / 2, isz)
    assert s.label is None


def _theme(tmp_path, **node):
    import yaml
    (tmp_path / "theme.yaml").write_text("extends: default\n" + yaml.safe_dump({"defaults": {"node": node}}))
    return Theme.load(tmp_path)


# theme keys (ICO-07): gap 16 and floor 32.
#   gateway: needs 85.12 ≤ 140 - 32 - s + 0.5 → s ≤ 23.38 < 32: floor 32, label box at 16 + 32 + 16 = 64
#   api:     52 kept (27.6 ≤ 200 - 84), label box at 16 + 52 + 16 = 84
THEME_KEYS = [("gateway", 240, 140, "Gateway", BODY, 32, 64), ("api", 240, 200, "API", None, 52, 84)]


@pytest.mark.parametrize("w,h,title,body,size,box_top", [s[1:] for s in THEME_KEYS], ids=[s[0] for s in THEME_KEYS])
def test_theme_keys_override_gap_and_floor(tmp_path, icon, w, h, title, body, size, box_top):
    s = _card(icon, w, h, title, body, theme=_theme(tmp_path, icon_text_gap=16, icon_min=32))
    assert s.icon.size == pytest.approx(size)
    assert s.label.box[1] == pytest.approx(Y0 + box_top)


def test_centred_card_text_moved_below_the_icon(icon):
    """Intent pin for the behaviour change: a centred card's text box used to start 12 px above the icon bottom
    (16 + isz - 12); it now starts icon_text_gap below it."""
    s = _card(icon, 240, 200, "API")
    assert s.label.box[1] - (s.icon.y + s.icon.size) == pytest.approx(8)    # was -12 in 0.4

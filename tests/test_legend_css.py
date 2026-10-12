"""Legend placement and styling from CSS (spec: .specs/features/legend-css/spec.md)."""
from __future__ import annotations

import pytest

from spinagram import Diagram
from spinagram.theme import Theme


def _diagram(css: str = "", **legend):
    d = Diagram("LC1", "Legend CSS", layout={"engine": "flex", "direction": "right"})
    a = d.box("A", class_="web")
    b = d.box("B", class_="db")
    d.edge(a, b, class_="async")
    d.add_legend(**legend)
    d.css = css
    return d


# T1 · properties --------------------------------------------------------------------------------------
def test_legend_properties_are_computed():  # LCSS-07..11, LCSS-13
    from spinagram import css

    d = _diagram("legend { placement: left; width: 300px; columns: 3; gap: 20; padding: 30; swatch-width: 60;"
                 " swatch-height: 20; display: none }")
    comp, warnings = css.styles(d, Theme.load("default"))
    assert not warnings
    assert comp["legend"][""] == {"placement": "left", "width": 300, "columns": 3, "gap": 20, "padding": 30,
                                  "swatch-width": 60, "swatch-height": 20, "display": "none"}


@pytest.mark.parametrize("decl, words", [
    ("placement: middle", ["placement", "bottom", "left", "right", "top"]),      # LCSS-05
    ("columns: 0", ["columns", "positive integer"]),                             # edge case
    ("columns: 2.5", ["columns", "positive integer"]),
    ("display: flex", ["display", "block", "none"]),
])
def test_invalid_legend_values_warn(decl, words):
    from spinagram import css

    comp, warnings = css.styles(_diagram(f"legend {{ {decl} }}"), Theme.load("default"))
    assert decl.split(":")[0] not in comp["legend"].get("", {})
    assert len(warnings) == 1 and all(w in warnings[0] for w in words), warnings


# T2 · explicit position stays optional ----------------------------------------------------------------------
def test_position_defaults_to_none_and_explicit_values_are_kept(tmp_path):  # LCSS-04
    from spinagram.yaml_io import dump, from_dict

    assert _diagram().annotations.legend.position is None
    for side in ("right", "left", "top", "bottom"):
        assert _diagram(position=side).annotations.legend.position == side
    with pytest.raises(ValueError, match="right, bottom, left, top"):
        _diagram(position="middle")
    out = dump(_diagram())
    assert "position" not in out["annotations"]["legend"]
    assert from_dict(dump(_diagram(position="top"))).annotations.legend.position == "top"


# T3 · the annotator reads the legend style ---------------------------------------------------------------
def _scene(d):
    from spinagram.layout import build_scene

    sc = build_scene(d, Theme.load("default"))
    return {getattr(i, "id", None): i for i in sc.items}


def _area(d):
    from spinagram.autolayout import _area as area

    return area(d, Theme.load("default"), reserve=False)


def _four():
    d = Diagram("LC2", "Four entries", layout={"engine": "flex", "direction": "right"})
    for c in ("web", "db", "cache", "queue"):
        d.box(c.title(), class_=c)
    d.add_legend()
    return d


def test_placement_left_starts_the_card_at_the_area_left():  # LCSS-01
    d = _diagram("legend { placement: left }")
    ax, ay, aw, ah = _area(d)
    card = _scene(d)["legend"]
    assert (card.x, card.y, card.w) == (ax, ay, 360)


def test_placement_top_starts_the_card_at_the_area_top():  # LCSS-02
    d = _diagram("legend { placement: top }")
    ax, ay, aw, ah = _area(d)
    card = _scene(d)["legend"]
    assert (card.x, card.y, card.w) == (ax, ay, aw)


@pytest.mark.parametrize("side", ["right", "bottom"])
def test_css_placement_matches_the_position_argument(side):  # LCSS-03
    by_css, by_arg = _scene(_diagram(f"legend {{ placement: {side} }}"))["legend"], _scene(_diagram(position=side))["legend"]
    assert (by_css.x, by_css.y, by_css.w, by_css.h) == (by_arg.x, by_arg.y, by_arg.w, by_arg.h)


def test_explicit_position_beats_css():  # LCSS-04
    d = _diagram("legend { placement: left }", position="right")
    ax, ay, aw, ah = _area(d)
    assert _scene(d)["legend"].x == ax + aw - 360


def test_width_sets_the_side_band():  # LCSS-07
    from spinagram.annotate import band
    from spinagram.css import prepare

    d = _diagram("legend { width: 300 }")
    ax, ay, aw, ah = _area(d)
    card = _scene(d)["legend"]
    assert (card.x, card.w) == (ax + aw - 300, 300)
    assert band(prepare(d, Theme.load("default")), Theme.load("default"), aw) == ("right", 332)


def test_columns_lay_entries_out_per_row():  # LCSS-08
    d = _four()
    d.css = "legend { columns: 3 }"
    items = _scene(d)
    ys = [items[f"legend-{j}-swatch"].y for j in range(4)]
    assert ys[0] == ys[1] == ys[2] < ys[3]
    xs = [items[f"legend-{j}-swatch"].x for j in range(3)]
    assert xs[0] < xs[1] < xs[2]


def test_gap_spaces_the_rows():  # LCSS-09
    d = _four()
    d.css = "legend { gap: 20; swatch-height: 30 }"
    items = _scene(d)
    assert items["legend-1-swatch"].y - items["legend-0-swatch"].y == 30 + 20


def test_padding_insets_title_and_swatches():  # LCSS-10
    d = _four()
    d.css = "legend { padding: 30 }"
    items = _scene(d)
    card = items["legend"]
    assert items["legend-title"].x == card.x + 30 and items["legend-0-swatch"].x == card.x + 30


def test_swatch_size():  # LCSS-11
    d = _four()
    d.css = "legend { swatch-width: 60; swatch-height: 20 }"
    sw = _scene(d)["legend-0-swatch"]
    assert (sw.w, sw.h) == (60, 20)


def test_body_font_size_sets_label_text():  # LCSS-12
    d = _four()
    d.css = "legend::body { font-size: 20 }"
    assert _scene(d)["legend-0-label"].block.font.size == 20


def test_display_none_hides_the_legend_and_its_band():  # LCSS-13
    from spinagram.annotate import band
    from spinagram.css import prepare

    t = Theme.load("default")
    d = _four()
    d.css = "legend { display: none }"
    assert "legend" not in _scene(d)
    assert band(prepare(d, t), t, 1760) is None
    d.step("go", on="web")
    items = _scene(d)
    ax, ay, aw, ah = _area(d)
    assert "legend" not in items and (items["steps"].x, items["steps"].y) == (ax + aw - 360, ay)


# T4 · layout area after a left or top band --------------------------------------------------------------
@pytest.mark.parametrize("side", ["left", "top"])
def test_content_starts_after_a_left_or_top_band(side):  # LCSS-06
    from spinagram.annotate import band
    from spinagram.autolayout import _area as area
    from spinagram.autolayout import apply_layout
    from spinagram.css import prepare

    t = Theme.load("default")
    d = _diagram(f"legend {{ placement: {side} }}")
    ax, ay, aw, ah = area(d, t, reserve=False)
    thick = band(prepare(d, t), t, aw)[1]
    expected = (ax + thick, ay, aw - thick, ah) if side == "left" else (ax, ay + thick, aw, ah - thick)
    assert area(prepare(d, t), t) == expected
    laid = apply_layout(d, t)
    card = _scene(d)["legend"]
    if side == "left":
        assert min(n.x for n in laid.nodes) >= card.x + card.w
    else:
        assert min(n.y for n in laid.nodes) >= card.y + card.h


# T7 · verifier gaps -----------------------------------------------------------------------------------------
@pytest.mark.parametrize("side", ["top", "bottom"])
def test_columns_on_a_top_or_bottom_band(side):  # LCSS-08 on every band side
    d = _four()
    d.css = f"legend {{ placement: {side}; columns: 3 }}"
    items = _scene(d)
    card = items["legend"]
    sw = [items[f"legend-{j}-swatch"] for j in range(4)]
    assert sw[0].y == sw[1].y == sw[2].y < sw[3].y
    step = (card.w - 2 * 22) / 3
    assert sw[1].x - sw[0].x == pytest.approx(step) and sw[2].x - sw[1].x == pytest.approx(step)


@pytest.mark.parametrize("side", ["top", "bottom"])
def test_columns_on_a_top_or_bottom_band_reserve_their_rows(side):  # LCSS-08: reserved size matches drawn rows
    from spinagram.annotate import band
    from spinagram.autolayout import apply_layout
    from spinagram.css import prepare

    t = Theme.load("default")
    d = _four()
    d.css = f"legend {{ placement: {side}; columns: 3 }}"
    ax, ay, aw, ah = _area(d)
    # theme defaults: head 22 + 20 × 1.3 + 10 = 58, two rows 2 × 28 + 12 = 68, padding 22, gap 32
    assert band(prepare(d, t), t, aw) == (side, 58 + 68 + 22 + 32)
    card = _scene(d)["legend"]
    assert card.h == 58 + 68 + 22
    laid = apply_layout(d, t)
    if side == "top":
        assert min(n.y for n in laid.nodes) >= card.y + card.h
    else:
        assert card.y + card.h <= ay + ah and max(n.y + n.h for n in laid.nodes) <= card.y


def test_explicit_columns_beat_the_automatic_two_columns():  # LCSS-08 "forces"
    d = Diagram("LC3", "Tall legend", layout={"engine": "flex", "direction": "right"})
    for k in range(30):
        d.box(f"N{k}", class_=f"c{k}")
    d.add_legend()
    auto = _scene(d)
    assert len({round(auto[f"legend-{j}-swatch"].x) for j in range(30)}) == 2  # tall: two columns by default
    d.css = "legend { columns: 1 }"
    forced = _scene(d)
    assert len({round(forced[f"legend-{j}-swatch"].x) for j in range(30)}) == 1


def test_yaml_legend_without_position_follows_the_stylesheet():  # LCSS-04 (YAML path)
    from spinagram.yaml_io import from_dict

    d = from_dict({"id": "Y1", "title": "YAML", "layout": {"engine": "flex"},
                   "nodes": [{"id": "a", "title": "A", "class": "web"}],
                   "annotations": {"legend": {"title": "Key"}}, "css": "legend { placement: left }"})
    assert d.annotations.legend.position is None
    ax, ay, aw, ah = _area(d)
    assert _scene(d)["legend"].x == ax


@pytest.mark.parametrize("side, covered", [("left", "left-box"), ("top", "top-box")])
def test_manual_layout_overlap_on_left_and_top_bands(side, covered):  # ANN-12 with the new sides
    from spinagram.layout import build_scene
    from spinagram.qa import check

    d = Diagram("M2", "Manual")
    d.box("Left box", x=100, y=500, w=200, h=100)
    d.box("Top box", x=900, y=200, w=200, h=80)
    d.box("Clear", x=900, y=600, w=200, h=100)
    d.add_legend()
    d.css = f"legend {{ placement: {side} }}"
    issues = [str(i) for i in check(build_scene(d, Theme.load("default"))) if "overlap" in str(i)]
    assert issues == [f"M2:annotations: overlap — the band covers {covered!r}"]


def test_invalid_placement_keeps_the_default_side():  # LCSS-05 clause 2
    d = _diagram("legend { placement: middle }")
    ax, ay, aw, ah = _area(d)
    assert _scene(d)["legend"].x == ax + aw - 360

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

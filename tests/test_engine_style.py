"""CSS element model: label and chip (layout-engine STY-02, STY-03; zone and none are in test_engine_zones)."""
import pytest

from spinagram import Diagram, Theme, build_scene
from spinagram.scene import Shape, Text

THEME = Theme.load("default")


@pytest.fixture
def icon(tmp_path):
    p = tmp_path / "i.svg"
    p.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>')
    return str(p)


def _scene(icon, css):
    d = Diagram("C", "Css", css=css)
    d.box(None, id="chip", x=100, y=100, w=60, h=60, icon=icon, align="center")
    d.box("Card", id="card", x=300, y=100, w=300, h=120, icon=icon)
    d.label("NETWORK", id="hdr", x=100, y=400)
    d.zone("Net", id="net", x=700, y=100, w=400, h=300)
    sc = build_scene(d, THEME)
    return {i.id: i for i in sc.items if isinstance(i, (Shape, Text))}


SELECTORS = [
    # id, rule, element that must change, attribute, value, elements that must not change
    ("chip", "chip { fill: #112233 }", "chip", "fill", "#112233", ["card"]),
    ("label-colour", "label { color: #AA0000 }", "hdr", "color", "#AA0000", []),
    ("label-by-id", "label#hdr { color: #00AA00 }", "hdr", "color", "#00AA00", []),
    ("zone", "zone { stroke: #445566 }", "z0", "stroke", "#445566", ["card", "chip"]),
    ("node-covers-chip", "node { stroke: #778899; stroke-width: 2 }", "chip", "stroke", "#778899", []),
]


@pytest.mark.parametrize("rule,target,attr,value,others", [s[1:] for s in SELECTORS], ids=[s[0] for s in SELECTORS])
def test_element_types_in_selectors(icon, rule, target, attr, value, others):  # STY-02
    plain, styled = _scene(icon, ""), _scene(icon, rule)
    got = styled[target].block.color if attr == "color" else getattr(styled[target], attr)
    assert got == value
    for o in others:
        assert getattr(styled[o], attr) == getattr(plain[o], attr)


def test_icon_only_box_has_no_outline_or_shadow_by_default(icon):  # STY-03
    by = _scene(icon, "")
    assert (by["chip"].stroke, by["chip"].stroke_width, by["chip"].shadow) == (None, 0, None)
    assert by["card"].stroke is not None and by["card"].stroke_width > 0        # boxes with text keep theirs


def test_icon_only_box_can_be_styled_back(icon):  # STY-03: "unless styled"
    by = _scene(icon, "chip { stroke: #000000; stroke-width: 1.5; box-shadow: 0 2px 6px #000000 }")
    assert (by["chip"].stroke, by["chip"].stroke_width) == ("#000000", 1.5) and by["chip"].shadow is not None

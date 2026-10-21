"""Sizing: content-sized boxes, row/column containers, uniform icons, zones fitted to children
(layout-engine BOX-01..06, ZON-14..18)."""
import pytest

from spinagram import Diagram, Theme, build_scene
from spinagram.autolayout.sizing import auto_size
from spinagram.engine import model_passes
from spinagram.qa import check
from spinagram.scene import Shape

THEME = Theme.load("default")


@pytest.fixture
def icon(tmp_path):
    p = tmp_path / "i.svg"
    p.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>')
    return str(p)


CONTENT = [
    pytest.param(i, t, b, id=f"{'icon' if i else 'noicon'}-{tid}-{bid}")
    for i in (False, True)
    for tid, t in (("short", "API"), ("long", "lb-pool-https-8081 managers"))
    for bid, b in (("nobody", None), ("body", "8 members · nginx :8081 behind one virtual server"))
]


@pytest.mark.parametrize("with_icon,title,body", CONTENT)
def test_box_without_size_fits_its_content(icon, with_icon, title, body):  # BOX-01
    d = Diagram("S", "Size")
    n = d.box(title, id="n", x=200, y=200, text=body, icon=icon if with_icon else None)
    s = next(i for i in build_scene(d, THEME).items if isinstance(i, Shape) and i.id == "n")
    assert (s.w, s.h) == pytest.approx(auto_size(n, THEME))
    assert s.w > 0 and s.h > 0
    assert [i for i in check(build_scene(d, THEME)) if i.item == "n" and i.kind.startswith("overflow")] == []


def test_explicit_size_is_kept():
    d = Diagram("S", "Size")
    d.box("API", id="n", x=200, y=200, w=500, h=300)
    s = next(i for i in build_scene(d, THEME).items if isinstance(i, Shape) and i.id == "n")
    assert (s.w, s.h) == (500, 300)


def test_auto_layout_diagrams_are_left_to_the_engine():  # model passes skip engine-laid-out diagrams
    d = Diagram("S", "Size")
    d.box("A")
    d.box("B")
    assert d.auto and model_passes.apply(d, THEME) is d

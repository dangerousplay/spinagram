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


# row / column containers (BOX-02..05) -------------------------------------------------------------------------
TITLES = ["node-a", "node-b-with-a-longer-name", "c"]


def _container_scene(axis, same_size=True, max_width=None, gap=12, titles=TITLES, texts=None):
    d = Diagram("S", "Size")
    with getattr(d, axis)(x=200, y=200, gap=gap, same_size=same_size, max_width=max_width):
        for k, t in enumerate(titles):
            d.box(t, id=f"n{k}", text=(texts or [None] * len(titles))[k])
    sc = build_scene(d, THEME)
    return sc, [next(i for i in sc.items if isinstance(i, Shape) and i.id == f"n{k}") for k in range(len(titles))]


@pytest.mark.parametrize("axis", ["row", "column"])
@pytest.mark.parametrize("max_width", [None, 612], ids=["no-cap", "cap-612"])
def test_same_size_container(axis, max_width):  # BOX-02, BOX-03 (roadmap acceptance)
    sc, shapes = _container_scene(axis, max_width=max_width, texts=["gitlab", "gitlab 17 · gitaly", None])
    assert len({(s.w, s.h) for s in shapes}) == 1                                   # equal sizes
    if axis == "row":
        assert [s.x for s in shapes] == pytest.approx([200, 200 + shapes[0].w + 12, 200 + 2 * (shapes[0].w + 12)])
        assert {s.y for s in shapes} == {200}
        if max_width:
            assert shapes[-1].x + shapes[-1].w <= 200 + max_width + 0.5             # within max_width
    else:
        assert [s.y for s in shapes] == pytest.approx([200, 200 + shapes[0].h + 12, 200 + 2 * (shapes[0].h + 12)])
        assert {s.x for s in shapes} == {200}
    assert [i for i in check(sc) if i.kind.startswith("overflow")] == []           # no overflow


def test_container_without_same_size_keeps_content_sizes():
    _, shapes = _container_scene("row", same_size=False)
    assert len({s.w for s in shapes}) > 1


@pytest.mark.parametrize("max_width", [120, 200], ids=["120", "200"])
def test_impossible_max_width_raises_naming_widest(max_width):  # BOX-04
    with pytest.raises(ValueError, match="row cannot fit 'n1'"):
        _container_scene("row", max_width=max_width, titles=["a", "supercalifragilistic-expialidocious", "b"])


def test_legacy_function_forms_unchanged():  # BOX-05
    d = Diagram("S", "Size")
    a = d.row(["A", "B"], x=100, y=100, w=200, h=80)
    c = d.column(["C", "D"], x=100, y=400, w=200, h=80)
    assert [(n.x, n.y, n.w, n.h) for n in a] == [(100, 100, 200, 80), (360, 100, 200, 80)]
    assert [(n.x, n.y, n.w, n.h) for n in c] == [(100, 400, 200, 80), (100, 520, 200, 80)]
    with pytest.raises(TypeError, match="needs w and h"):
        d.row(["E"], x=0, y=0)


def test_container_yaml_parity():  # BOX-02 YAML
    from spinagram.yaml_io import from_dict
    y = from_dict({"id": "S", "title": "Size", "rows": [{"x": 200, "y": 200, "gap": 12, "same_size": True,
                                                         "nodes": [{"id": f"n{k}", "title": t}
                                                                   for k, t in enumerate(TITLES)]}]})
    ys = [next(i for i in build_scene(y, THEME).items if isinstance(i, Shape) and i.id == f"n{k}") for k in range(3)]
    _, ps = _container_scene("row", texts=None)
    assert [(s.x, s.y, s.w, s.h) for s in ys] == [(s.x, s.y, s.w, s.h) for s in ps]


def test_container_yaml_unknown_key_raises():
    from spinagram.yaml_io import from_dict
    with pytest.raises(ValueError, match="row has unknown keys"):
        from_dict({"id": "S", "title": "S", "rows": [{"x": 0, "y": 0, "spacing": 3, "nodes": []}]})

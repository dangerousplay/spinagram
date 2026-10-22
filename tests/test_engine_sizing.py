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


# uniform icon size (BOX-06) -----------------------------------------------------------------------------------
@pytest.mark.parametrize("same_icon_size,heights", [(True, (90, 140, 220)), (False, (90, 140, 220)),
                                                    (False, (90, 90, 90))],
                         ids=["uniform", "mismatch", "same-heights"])
def test_same_icon_size_in_a_row(icon, same_icon_size, heights):
    d = Diagram("S", "Size")
    with d.row(x=200, y=200, gap=12, same_icon_size=same_icon_size):
        for k, h in enumerate(heights):
            d.box(f"N{k}", id=f"n{k}", w=260, h=h, icon=icon)
    sc = build_scene(d, THEME)
    sizes = [next(i for i in sc.items if isinstance(i, Shape) and i.id == f"n{k}").icon.size for k in range(3)]
    mism = [i for i in check(sc) if i.kind == "icon-size-mismatch"]
    if same_icon_size:
        assert len(set(sizes)) == 1 and sizes[0] == min(min(88, max(44, h * 0.26)) for h in heights)
        assert mism == []
    elif len(set(heights)) > 1:
        assert len(set(sizes)) > 1 and len(mism) == 1 and mism[0].item == "row0" and mism[0].severity == "P2"
    else:
        assert mism == []


# zones as containers (ZON-18) ---------------------------------------------------------------------------------
@pytest.mark.parametrize("depth", [1, 2, 3, 4], ids=lambda n: f"depth{n}")
def test_zone_context_collects_children(depth):
    from contextlib import ExitStack
    d = Diagram("S", "Size")
    with ExitStack() as stack:
        for k in range(depth):
            stack.enter_context(d.zone(f"Z{k}", id=f"z{k}"))
            d.box(f"N{k}", id=f"n{k}", x=0, y=0, w=10, h=10)
    d.box("outside", id="out", x=0, y=0, w=10, h=10)
    for k in range(depth):  # creation order: the zone's own node, then the zone nested in it
        assert d.zones[k].children == [f"n{k}"] + ([f"z{k + 1}"] if k < depth - 1 else [])
    assert d.nodes[-1].id == "out" and all("out" not in z.children for z in d.zones)


def test_zone_children_from_yaml():
    from spinagram.yaml_io import from_dict
    d = from_dict({"id": "S", "title": "S", "zones": [{"id": "net", "x": 0, "y": 0, "w": 10, "h": 10,
                                                       "children": ["a", "b"]}],
                   "nodes": [{"id": "a", "title": "A"}, {"id": "b", "title": "B"}]})
    assert d.zones[0].children == ["a", "b"]


# zones fitted to their children (ZON-14..16) ----------------------------------------------------------------
NO_ICON_HEAD = 36 + 16 * 0.3 + 12      # label-only header + gap
ICON_HEAD = 14 + 28 + 12               # inset icon header + gap


@pytest.mark.parametrize("padding,expect_pad", [(None, 24), (40, 40)], ids=["default-pad", "pad-40"])
@pytest.mark.parametrize("with_icon,head", [(False, NO_ICON_HEAD), (True, ICON_HEAD)], ids=["label", "icon"])
def test_zone_fits_its_children(icon, padding, expect_pad, with_icon, head):  # ZON-14
    d = Diagram("S", "Size")
    kw = {"padding": padding} if padding is not None else {}
    with d.zone("Net", id="net", fit="children", icon=icon if with_icon else None, **kw):
        d.box("A", id="a", x=300, y=300, w=200, h=100)
        d.box("B", id="b", x=600, y=420, w=200, h=100)
    z = next(i for i in build_scene(d, THEME).items if isinstance(i, Shape) and i.id == "z0")
    assert (z.x, z.y, z.w, z.h) == pytest.approx((300 - expect_pad, 300 - head, 500 + 2 * expect_pad,
                                                   220 + head + expect_pad))


@pytest.mark.parametrize("depth", [2, 3], ids=["2-levels", "3-levels"])
def test_nested_fit_resolves_innermost_first(depth):  # ZON-15
    from contextlib import ExitStack
    d = Diagram("S", "Size")
    with ExitStack() as st:
        for k in range(depth):
            st.enter_context(d.zone(f"Z{k}", id=f"z{k}", fit="children"))
        d.box("Leaf", id="leaf", x=500, y=500, w=200, h=100)
    sc = build_scene(d, THEME)
    rects = [next(i for i in sc.items if isinstance(i, Shape) and i.id == f"z{k}") for k in range(depth)]
    for outer, inner in zip(rects, rects[1:]):  # each zone contains the next one with its own padding/header
        assert outer.x == pytest.approx(inner.x - 24) and outer.y == pytest.approx(inner.y - NO_ICON_HEAD)
        assert outer.x + outer.w == pytest.approx(inner.x + inner.w + 24)
    assert [i for i in check(sc) if i.kind == "zone-clips-child"] == []


@pytest.mark.parametrize("equalize", [True, False], ids=["equalize", "independent"])
def test_equalize_siblings(equalize):  # ZON-16 (opt-in: blank space never a default)
    d = Diagram("S", "Size")
    kw = {"equalize": "siblings"} if equalize else {}
    with d.zone("Project A", id="pa", fit="children", **kw):
        d.box("A1", id="a1", x=200, y=300, w=200, h=100)
        d.box("A2", id="a2", x=200, y=450, w=200, h=100)
    with d.zone("Project B", id="pb", fit="children", **kw):
        d.box("B1", id="b1", x=600, y=300, w=200, h=100)
    sc = build_scene(d, THEME)
    a, b = (next(i for i in sc.items if isinstance(i, Shape) and i.id == z) for z in ("z0", "z1"))
    assert (a.h == b.h) == equalize and max(a.h, b.h) == pytest.approx(250 + NO_ICON_HEAD + 24)


# zone diagnostics (ZON-17) ------------------------------------------------------------------------------------
CLIP = [
    # id, declared child?, node rect, expected detail or None   (zone z0 at 200,200 600x400)
    ("declared-right", True, (700, 300, 130, 100), "'n' extends 30px past the right side"),
    ("declared-inside", True, (300, 300, 200, 100), None),
    ("geometric-bottom", False, (300, 520, 200, 100), "'n' extends 20px past the bottom side"),
    ("geometric-mostly-outside", False, (750, 300, 200, 100), None),
]


@pytest.mark.parametrize("declared,rect,detail", [c[1:] for c in CLIP], ids=[c[0] for c in CLIP])
def test_zone_clips_child(declared, rect, detail):
    d = Diagram("S", "Size")
    z = d.zone("Net", x=200, y=200, w=600, h=400)
    x, y, w, h = rect
    d.box("N", id="n", x=x, y=y, w=w, h=h)
    if declared:
        z.children.append("n")
    got = [i.detail for i in check(build_scene(d, THEME)) if i.kind == "zone-clips-child"]
    assert got == ([detail] if detail else [])


@pytest.mark.parametrize("equalize,threshold,flagged", [(True, None, True), (False, None, False),
                                                        (True, 0.2, False)],
                         ids=["blank-sibling", "tight", "theme-threshold-0.2"])
def test_zone_underused(tmp_path, equalize, threshold, flagged):  # roadmap D1: the single-AZ blank sibling
    th = THEME
    if threshold is not None:
        (tmp_path / "theme.yaml").write_text(f"extends: default\ndefaults: {{check: {{underused: {threshold}}}}}\n")
        th = Theme.load(tmp_path)
    d = Diagram("S", "Size")
    kw = {"equalize": "siblings"} if equalize else {}
    with d.zone("Project A", id="pa", fit="children", **kw):
        d.box("A1", id="a1", x=200, y=300, w=200, h=100)
        d.box("A2", id="a2", x=200, y=450, w=200, h=100)
    with d.zone("Project B", id="pb", fit="children", **kw):
        d.box("B1", id="b1", x=600, y=300, w=200, h=100)
    got = [i for i in check(build_scene(d, th)) if i.kind == "zone-underused"]
    assert [i.item for i in got] == (["z1"] if flagged else [])
    if flagged:
        assert got[0].severity == "P2" and got[0].detail.startswith("content fills 28%")


@pytest.mark.parametrize("axis", ["row", "column"])
def test_same_size_is_the_largest_member(axis):  # BOX-03: the largest member wins (fix after verification)
    texts = ["gitlab", "gitlab 17 · gitaly with a longer body text", None]
    _, shapes = _container_scene(axis, texts=texts)
    d = Diagram("S", "Size")
    natural = [auto_size(d.box(t, text=b), THEME) for t, b in zip(TITLES, texts)]
    assert shapes[0].w == pytest.approx(max(w for w, _ in natural))
    assert shapes[0].h >= max(h for _, h in natural) - 0.5

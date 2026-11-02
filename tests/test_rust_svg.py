"""SVG drawn by the Rust core vs the Python writer (SVG-01, SVG-07, SVG-08)."""
from pathlib import Path
from unittest import mock

import pytest
from example_scenes import example_scenes

from spinagram.backends import svg
from spinagram.scene import (Cell, Connector, Icon, Image, Label, Line, Run, Scene, Shape, TableGrid, Text,
                             TextBlock)
from spinagram.shapes import Part
from spinagram.text import bundled_fonts

ROOT = Path(__file__).resolve().parents[1]
ICON = ROOT / "examples" / "icons" / "acme.svg"
PIXEL = ROOT / "rust" / "spinagram-core" / "tests" / "data" / "pixel.png"

MATH, SYMBOLS = (f for f in bundled_fonts(14))  # two real font files that ship with spinagram
BOLD = MATH.with_size(13.5)


@pytest.fixture
def core():
    return pytest.importorskip("spinagram._core")


@pytest.fixture
def python_writer(monkeypatch):
    monkeypatch.setattr(svg, "_CORE", None)


@pytest.fixture
def rust_writer(core, monkeypatch):
    monkeypatch.setattr(svg, "_CORE", core)


def font_scene(path=None) -> Scene:
    """Every item type, fallback runs, empty lines, tooltips, sources, shadows and markers, with real font files."""
    runs = [[Run("ab", MATH), Run("∑", SYMBOLS), Run("c", MATH)], [], [Run("", MATH)]]
    fallback = TextBlock(["ab∑c", "", ""], ["ab∑c", "", ""], MATH, "#102030", 20, runs)
    plain = TextBlock(["Title ✓", "", "line & <two>"], ["x"], BOLD, "#222", 19.6)
    label = Label([plain, fallback], (20, 30, 160, 90), "center", 8)
    shape = Shape("a", "rect", 10, 20.25, 200, 110, "#fafafa", "#111", 2, 8, False, 1.0, label, Icon(ICON, 16, 28, 24),
                  "node", None, None, (2, 4, 10, "#00000033", 0.25))
    parts = Shape("p", "rect", 0, 0, 50, 50, "#abc", "#123456", 2, 0, False, 1.0, None, None, "node",
                  [Part("M 0 0 L 10 10 Z", "shape"), Part("M 1 1 Z", "solid"), Part("M 3 3 Z", "stroke")])
    diamond = Shape("d", "diamond", 300, 20, 90, 60, None, "#000", 1, 0)
    conns = [Connector(f"c{i}", [(0, 100 + i * 10), (50, 100 + i * 10), (80, 90)], "poly", "#aa00ff", 1.5, dashed=i % 2 == 0,
                       arrow_start=True, marker_start="open-diamond" if i % 2 else "circle", marker_end=k)
             for i, k in enumerate(["arrow", "open-arrow", "diamond", "open-diamond", "circle", "bar"])]
    curve = Connector("cv", [(0, 0), (50.55, 80.05), (100, 0)], "curve", "#334455", 2, True, True, True, None, None,
                      Shape("cl", "pill", 40, 40, 60, 20, "#fff", None, 0, 10, False, 1.0,
                            Label([TextBlock(["lbl"], ["lbl"], MATH, "#000", 16)], (40, 40, 60, 20), "center"),
                            role="pill"))
    cell = lambda t, fill: Cell(TextBlock([t], [t], BOLD, "#222", 18), fill, Icon(ICON, 0, 0, 16), 12, True)  # noqa: E731
    table = TableGrid("tb", 10, 300, [100, 90.5], [30, 28],
                      [[cell("H1", "#e0e0e0"), cell("H2", "#e0e0e0")], [cell("a", "#fff"), cell("", "#f6f6f6")]],
                      "#ccc", 6)
    items = [shape, parts, diamond, *conns, curve, Text("zt", 5, 6, plain, "start", 0.5), Text("t2", 5, 6, fallback, "end", 1),
             Line("l", 1, 2.55, 30, 40.25, "#0a0a0a", 2), Image("i", PIXEL, 1, 2, 30, 40.5), table]
    return Scene("S", "Title & more", "s", 640, 480, "#fafafa", items, item_facts={"a": ["f1"], "tb": ["f1"], "zt": ["f1"]},
                 sources=[{"id": "f1", "display": "é"}], meta_tooltips={"f1": "from <the> wiki"})


def render(scene: Scene, fonts: str) -> str:
    return svg.to_svg(scene, fonts)


@pytest.mark.parametrize("fonts", svg.FONT_MODES)
def test_example_scenes_are_byte_identical(fonts, core, monkeypatch):  # SVG-01
    for sc in example_scenes():
        monkeypatch.setattr(svg, "_CORE", None)
        expected = render(sc, fonts)
        monkeypatch.setattr(svg, "_CORE", core)
        assert render(sc, fonts) == expected, sc.slug


@pytest.mark.parametrize("fonts", svg.FONT_MODES)
def test_scene_with_font_files_is_byte_identical(fonts, core, monkeypatch):  # SVG-01 (subset, embed, link with files)
    sc = font_scene()
    monkeypatch.setattr(svg, "_CORE", None)
    expected = render(sc, fonts)
    monkeypatch.setattr(svg, "_CORE", core)
    assert render(sc, fonts) == expected
    assert "@font-face" in expected or fonts == "link"


def test_core_inactive_uses_the_python_path(python_writer):  # SVG-07
    with mock.patch.object(svg._Svg, "_draw", autospec=True, side_effect=svg._Svg._draw) as spy:
        svg.to_svg(font_scene())
    assert spy.call_count == 1


def test_core_active_draws_in_rust(rust_writer):  # SVG-01 dispatch
    with mock.patch.object(svg._Svg, "_draw", autospec=True) as spy:
        out = svg.to_svg(font_scene())
    assert spy.call_count == 0 and out.startswith("<svg")


def test_chars_per_face_equal_python(rust_writer):  # SVG-08
    sc = font_scene()
    python = svg._Svg(sc)
    python._draw()
    rust_chars = svg._Svg(sc)._draw_rust()[4]
    assert rust_chars == python.chars
    assert (MATH.family, MATH.weight, MATH.italic) in rust_chars and " " in rust_chars[(MATH.family, 400, False)]


def test_missing_image_raises_filenotfound_naming_the_path(rust_writer):  # edge case (SVG-04)
    sc = Scene("S", "T", "s", 10, 10, "#fff", [Image("i", Path("/no/such/file.png"), 0, 0, 1, 1)])
    with pytest.raises(FileNotFoundError, match="/no/such/file.png"):
        svg.to_svg(sc)


def test_compensated_sum_flag_matches_the_interpreter():  # SVG-01 (sum() differs between 3.11 and 3.12+)
    import sys
    assert svg.COMPENSATED_SUM == (sys.version_info >= (3, 12))
    assert (sum([0.1] * 10) == 1.0) == svg.COMPENSATED_SUM  # the behaviour the flag stands for


def test_writer_sends_the_flag_to_the_core(core, monkeypatch):  # SVG-01
    spy = mock.Mock(wraps=core)
    monkeypatch.setattr(svg, "_CORE", spy)
    svg.to_svg(font_scene())
    assert spy.svg_draw.call_args.args[1] is svg.COMPENSATED_SUM


def _decision_scene() -> Scene:
    from spinagram import api, cli
    from spinagram.theme import Theme
    return api.scenes(cli._collect([str(ROOT / "examples" / "decision.yaml")], None), Theme.load(None))[0]


def _item_ids(scene: Scene) -> set[str]:
    ids = set()
    for it in scene.items:
        ids.add(it.id)
        if isinstance(it, Connector) and it.label:
            ids.add(it.label.id)
    return ids


@pytest.mark.parametrize("writer", ["python_writer", "rust_writer"])
def test_every_item_group_carries_its_scene_id(writer, request):  # CTR-01
    import re
    request.getfixturevalue(writer)
    scene = _decision_scene()
    svg_text = svg.to_svg(scene, "link")
    data_ids = re.findall(r'<g data-id="([^"]*)"', svg_text)
    assert len(data_ids) == len(set(data_ids)), "a data-id repeats"
    ids = _item_ids(scene)
    assert any(isinstance(i, Connector) for i in scene.items) and any(isinstance(i, Shape) for i in scene.items)
    for item_id in ids:
        assert item_id in data_ids, f"{item_id} has no group"
    assert set(data_ids) - ids == {f"{i}@{layer}" for i in ids for layer in ("mid", "front")} & set(data_ids)


@pytest.mark.parametrize("writer", ["python_writer", "rust_writer"])
def test_node_group_holds_its_shape_icon_and_title(writer, request):  # CTR-01
    request.getfixturevalue(writer)
    scene = _decision_scene()
    svg_text = svg.to_svg(scene, "link")
    node = next(i for i in scene.items if isinstance(i, Shape) and i.role == "node" and i.label)
    start = svg_text.index(f'<g data-id="{node.id}">')
    assert svg_text.index("<rect", start) < svg_text.index("</g>", start)
    front = svg_text.index(f'<g data-id="{node.id}@front">')
    assert node.label.blocks[0].lines[0] in svg_text[front:svg_text.index("</g>", front)]

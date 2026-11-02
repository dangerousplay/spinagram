"""Colours and file paths in a scene cannot break out of the SVG (SEC-01, SEC-02) in either engine."""
import re
from pathlib import Path

import pytest
from test_rust_svg import BOLD, MATH, PIXEL

from spinagram import scene_json
from spinagram.backends import svg
from spinagram.scene import Connector, Image, Label, Line, Scene, Shape, TableGrid, Text, TextBlock
from spinagram.scene import Cell
from spinagram.shapes import Part

EVIL = 'x" onload="y'


@pytest.fixture
def core():
    return pytest.importorskip("spinagram._core")


def evil_scene() -> Scene:
    block = TextBlock(["t"], ["t"], BOLD, EVIL, 18)
    shape = Shape("s", "rect", 0, 0, 50, 50, EVIL, EVIL, 1, 0, False, 1.0, Label([block], (0, 0, 50, 50), "left"), None,
                  "node", [Part('M 0 0" x="1', "solid")], None, (1, 1, 2, EVIL, 0.5))
    conn = [Connector(f"c{i}", [(0, 10 * i), (30, 10 * i)], "straight", c, 1, False, True, True, None, None, None, None,
                      "circle" if i % 2 else "arrow", "arrow") for i, c in enumerate([EVIL, "rgb(1,2,3)", "#FF00AA", "red"])]
    table = TableGrid("tb", 0, 100, [40], [20, 20], [[Cell(block, EVIL)], [Cell(block, EVIL)]], EVIL)
    return Scene("S", "T", "s", 100, 200, EVIL, [shape, *conn, Line("l", 0, 0, 5, 5, EVIL, 1), Text("t", 1, 2, block, "start"), table])


def ids_and_refs(text: str) -> list[str]:
    return re.findall(r'\bid="([^"]*)"', text) + re.findall(r"url\(#([^)]*)\)", text)


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_colours_are_escaped_and_marker_ids_are_valid_names(engine, core, monkeypatch):
    monkeypatch.setattr(svg, "_CORE", core if engine == "rust" else None)
    out = svg.to_svg(evil_scene())
    assert 'onload="y' not in out
    assert "x&quot; onload=&quot;y" in out
    assert ' x="1"' not in out
    for ident in ids_and_refs(out):
        if ident.startswith("m"):
            assert re.fullmatch(r"[A-Za-z0-9_-]+", ident), ident
    assert "marker-end=\"url(#mFF00AA)\"" in out and "url(#mred)" in out  # plain colours keep their ids


def test_both_engines_write_the_same_bytes_for_hostile_colours(core, monkeypatch):
    monkeypatch.setattr(svg, "_CORE", None)
    python = svg.to_svg(evil_scene())
    monkeypatch.setattr(svg, "_CORE", core)
    assert svg.to_svg(evil_scene()) == python


def test_the_marker_id_of_a_composite_colour_is_a_hash_both_engines_share():
    assert svg._marker_key("rgb(1,2,3)") == "xb114c0dd91cdd7d7"
    assert svg._marker_key("#FF00AA") == "FF00AA"
    assert svg._marker_key("red") == "red"


def test_the_core_reads_only_the_files_the_host_lists(core):
    sc = Scene("S", "T", "s", 10, 10, "#fff", [Image("i", PIXEL, 0, 0, 1, 1)])
    dumped = scene_json.dumps(sc)
    assert "<image" in "".join(core.svg_draw(dumped, True, scene_json.file_paths(sc))[1:4])
    assert "<image" not in "".join(core.svg_draw(dumped, True)[1:4]), "no list: nothing is read"
    assert "<image" not in "".join(core.svg_draw(dumped, True, [str(Path("/elsewhere/other.png"))])[1:4])


def test_file_paths_lists_icons_images_and_cell_icons():
    from spinagram.scene import Icon
    icon = Icon(PIXEL, 0, 0, 4)
    shape = Shape("a", "rect", 0, 0, 5, 5, "#fff", icon=icon)
    pill = Shape("p", "pill", 0, 0, 5, 5, "#fff", icon=Icon(PIXEL.with_name("pixel.jpeg"), 0, 0, 4))
    conn = Connector("c", [(0, 0), (1, 1)], "straight", "#000", 1, label=pill)
    table = TableGrid("t", 0, 0, [10], [10], [[Cell(TextBlock(["x"], ["x"], MATH, "#000", 10), "#fff", icon)]], "#ccc")
    sc = Scene("S", "T", "s", 10, 10, "#fff", [shape, conn, Image("i", PIXEL, 0, 0, 1, 1), table])
    assert scene_json.file_paths(sc) == [str(PIXEL), str(PIXEL.with_name("pixel.jpeg"))]

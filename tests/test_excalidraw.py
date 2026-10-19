"""Excalidraw backend (spec: .specs/features/excalidraw-backend/spec.md)."""
from __future__ import annotations

import json

from spinagram.backends.excalidraw import ExcalidrawBackend, to_excalidraw
from spinagram.scene import Scene, Shape


def scene(*items, bg="#FAFAFA") -> Scene:
    return Scene("D1", "Title", "d1", 1920, 1080, bg, list(items))


def els(doc, type=None):
    return [e for e in doc["elements"] if type is None or e["type"] == type]


def by_id(doc, id):
    return next(e for e in doc["elements"] if e["id"] == id)


def box(id="a", **kw):
    kw = {"kind": "rect", "x": 100, "y": 200, "w": 300, "h": 120, "fill": "#112233", **kw}
    return Shape(id, **kw)


# T1 -------------------------------------------------------------------------------------------------
def test_document_top_level_keys():  # EXC-02
    doc = to_excalidraw(scene())
    assert list(doc) == ["type", "version", "source", "elements", "appState", "files"]
    assert doc["type"] == "excalidraw" and doc["version"] == 2
    assert doc["source"] == "https://github.com/dangerousplay/spinagram"
    assert doc["files"] == {}


def test_backend_writes_slug_file_as_utf8_json(tmp_path):  # EXC-02
    paths = ExcalidrawBackend().render([scene(box())], tmp_path)
    assert paths == [tmp_path / "d1.excalidraw"]
    assert json.loads(paths[0].read_text(encoding="utf-8"))["type"] == "excalidraw"


def test_frame_first_holds_everything():  # EXC-14, EXC-17
    doc = to_excalidraw(scene(box("a"), box("b", x=500), bg="#101010"))
    frame, *rest = doc["elements"]
    assert frame["type"] == "frame" and frame["name"] == "spinagram:D1"
    assert (frame["x"], frame["y"], frame["width"], frame["height"]) == (0, 0, 1920, 1080)
    assert rest and all(e["frameId"] == frame["id"] for e in rest)
    assert frame["frameId"] is None
    assert doc["appState"]["viewBackgroundColor"] == "#101010"


def test_empty_scene_only_frame():  # edge case
    assert [e["type"] for e in to_excalidraw(scene())["elements"]] == ["frame"]


def test_clean_style():  # EXC-03
    doc = to_excalidraw(scene(box("a"), box("b", kind="diamond")))
    assert all(e["roughness"] == 0 for e in doc["elements"])
    assert all(e["fillStyle"] == "solid" for e in els(doc) if e["type"] != "frame")


def test_rectangle_geometry_and_paint():  # EXC-04
    doc = to_excalidraw(scene(box("a", stroke="#FF0000", stroke_width=2.5)))
    r = by_id(doc, "a")
    assert r["type"] == "rectangle"
    assert (r["x"], r["y"], r["width"], r["height"]) == (100, 200, 300, 120)
    assert (r["backgroundColor"], r["strokeColor"], r["strokeWidth"]) == ("#112233", "#FF0000", 2.5)
    assert r["roundness"] is None


def test_kinds_and_roundness():  # EXC-04, Kinds row
    doc = to_excalidraw(scene(box("r", radius=12), box("p", kind="pill", h=40), box("d", kind="diamond")))
    assert by_id(doc, "r")["roundness"] == {"type": 3, "value": 12}
    assert by_id(doc, "p")["type"] == "rectangle" and by_id(doc, "p")["roundness"] == {"type": 3, "value": 20}
    assert by_id(doc, "d")["type"] == "diamond"


def test_transparent_paints():  # edge case: no fill, no stroke
    r = by_id(to_excalidraw(scene(box("a", fill=None))), "a")
    assert (r["backgroundColor"], r["strokeColor"], r["strokeWidth"]) == ("transparent", "transparent", 1)


def test_dashes():  # Dashes row
    doc = to_excalidraw(scene(box("s"), box("d", dashed=True), box("p", dash=[8, 4]), box("o", dash=[2, 3])))
    assert [by_id(doc, i)["strokeStyle"] for i in "sdpo"] == ["solid", "dashed", "dashed", "dotted"]


def test_opacity():  # Opacity row
    doc = to_excalidraw(scene(box("a", opacity=0.5), box("b", opacity=0.5, fill_opacity=0.5), box("c")))
    assert [by_id(doc, i)["opacity"] for i in "abc"] == [50, 25, 100]


def test_unique_ids_and_deterministic(tmp_path):  # EXC-16
    sc = scene(box("a"), box("a", x=600), box("b"))
    ids = [e["id"] for e in to_excalidraw(sc)["elements"]]
    assert len(ids) == len(set(ids))
    one = ExcalidrawBackend().render([sc], tmp_path / "1")[0].read_bytes()
    two = ExcalidrawBackend().render([sc], tmp_path / "2")[0].read_bytes()
    assert one == two


def test_layer_order():  # EXC-17
    doc = to_excalidraw(scene(box("n"), box("pill", role="pill"), box("z", role="zone"), box("c", role="chrome")))
    assert [e["id"] for e in doc["elements"][1:]] == ["z", "c", "n", "pill"]


# T2 -------------------------------------------------------------------------------------------------
def _flat(d: str) -> list[tuple[float, float]]:
    """Points along the path: line ends and 8 samples per cubic."""
    from spinagram.shapes import parse

    out = []
    for sp in parse(d):
        cur = sp.start
        out.append(cur)
        for cmd, pts in sp.segments:
            if cmd == "L":
                cur = pts[0]
                out.append(cur)
            else:
                (x1, y1), (x2, y2), (x3, y3) = pts
                for i in range(1, 9):
                    t = i / 8
                    a, b, c, e = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
                    out.append((a * cur[0] + b * x1 + c * x2 + e * x3, a * cur[1] + b * y1 + c * y2 + e * y3))
                cur = (x3, y3)
    return out


def test_symbol_parts_become_grouped_polygons():  # EXC-05
    from spinagram import shapes

    s = box("db", kind="data", parts=shapes.parts("data", 100, 200, 300, 120), stroke="#333333", stroke_width=2)
    doc = to_excalidraw(scene(s))
    lines = els(doc, "line")
    assert len(lines) == 2                                         # body (closed) + lip (open)
    assert [ln["polygon"] for ln in lines] == [True, False]
    assert lines[0]["id"] == "db"                                   # the shape's id stays on its first element
    group = lines[0]["groupIds"]
    assert group and all(ln["groupIds"] == group for ln in lines)
    expected = [_flat(p.d) for p in s.parts]
    for ln, want in zip(lines, expected):
        got = [(ln["x"] + px, ln["y"] + py) for px, py in ln["points"]]
        if ln["polygon"]:                                           # Excalidraw closes a polygon on its first point
            assert got[-1] == got[0]
            got = got[:-1] if want[-1] != want[0] else got
        assert len(got) == len(want)
        assert all(abs(gx - wx) <= 1 and abs(gy - wy) <= 1 for (gx, gy), (wx, wy) in zip(got, want))


def test_part_paints():  # Kinds row: solid fills with the stroke colour, stroke has no fill
    from spinagram import shapes

    s = box("f", kind="final", parts=shapes.parts("final", 0, 0, 40, 40), fill="#FFFFFF", stroke="#222222",
            stroke_width=2)
    ring, dot = els(to_excalidraw(scene(s)), "line")
    assert (ring["backgroundColor"], ring["strokeColor"]) == ("transparent", "#222222")
    assert (dot["backgroundColor"], dot["strokeColor"]) == ("#222222", "transparent")
    assert by_id(to_excalidraw(scene(box("p", parts=[shapes.Part("M 0 0 L 10 0 L 10 10 Z")]))), "p")[
        "backgroundColor"] == "#112233"                              # paint "shape": the shape's fill

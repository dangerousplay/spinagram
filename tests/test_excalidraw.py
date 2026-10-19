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


# T3 -------------------------------------------------------------------------------------------------
def block(lines, size=20, color="#202020", family="Arial", fallback="sans-serif", leading=26):
    from spinagram.scene import TextBlock
    from spinagram.theme import FontRef

    return TextBlock(list(lines), [" ".join(lines)], FontRef(family, size=size, fallback=fallback), color, leading)


def test_one_block_label_binds_into_the_shape():  # EXC-06
    from spinagram.scene import Label

    s = box("a", label=Label([block(["Load", "balancer"])], (110, 210, 280, 100), align="center"))
    doc = to_excalidraw(scene(s))
    (t,) = els(doc, "text")
    assert t["containerId"] == "a"
    assert by_id(doc, "a")["boundElements"] == [{"type": "text", "id": t["id"]}]
    assert (t["text"], t["originalText"]) == ("Load\nbalancer", "Load\nbalancer")
    assert (t["textAlign"], t["verticalAlign"]) == ("center", "middle")
    top = 210 + (100 - 52) / 2
    assert (t["x"], t["y"], t["width"], t["height"]) == (110, top, 280, 52)


def test_label_alignment_follows_the_label():  # EXC-06
    from spinagram.scene import Label

    s = box("a", label=Label([block(["x"])], (110, 210, 280, 100), align="left", valign="top"))
    (t,) = els(to_excalidraw(scene(s)), "text")
    assert (t["textAlign"], t["verticalAlign"]) == ("left", "top")


def test_multi_block_label_is_grouped_free_text():  # EXC-07
    from spinagram.scene import Label

    lab = Label([block(["Title"], size=24, color="#000000"), block(["body", "text"], size=16, color="#555555")],
                (110, 210, 280, 100), align="left")
    doc = to_excalidraw(scene(box("a", label=lab)))
    texts = els(doc, "text")
    assert len(texts) == 2 and all(t["containerId"] is None for t in texts)
    assert by_id(doc, "a")["boundElements"] is None
    for t, (b, x, top) in zip(texts, lab.place()):
        assert (t["x"], t["y"], t["fontSize"], t["strokeColor"]) == (x, top, b.font.size, b.color)
        assert t["text"] == "\n".join(b.lines)
    group = by_id(doc, "a")["groupIds"]
    assert group and all(t["groupIds"] == group for t in texts)


def test_free_text_anchor_alignment():  # EXC-13 (Text)
    from spinagram.scene import Text

    b = block(["Header"])
    doc = to_excalidraw(scene(Text("s", 100, 50, b, "start", width=200), Text("m", 100, 50, b, "middle", width=200),
                              Text("e", 100, 50, b, "end", width=200)))
    s, m, e = (by_id(doc, i) for i in "sme")
    assert [s["textAlign"], m["textAlign"], e["textAlign"]] == ["left", "center", "right"]
    assert [s["x"], m["x"], e["x"]] == [100, 0, -100]
    assert s["y"] == round(50 - b.baseline_offset(), 2) and s["width"] == 200


def test_fonts():  # EXC-15
    from spinagram.scene import Text

    doc = to_excalidraw(scene(Text("sans", 0, 30, block(["a"], size=18)),
                              Text("mono", 0, 90, block(["b"], family="JetBrains Mono", fallback="monospace"))))
    sans, mono = by_id(doc, "sans"), by_id(doc, "mono")
    assert (sans["fontFamily"], sans["fontSize"]) == (2, 18)
    assert mono["fontFamily"] == 3
    assert sans["lineHeight"] == round(26 / 18, 2) and sans["autoResize"] is False


# T4 -------------------------------------------------------------------------------------------------
def conn(id="e", points=((400, 260), (500, 260), (500, 400)), **kw):
    from spinagram.scene import Connector

    return Connector(id, [tuple(p) for p in points], kw.pop("route", "poly"), kw.pop("color", "#444444"),
                     kw.pop("width", 2), **kw)


def test_arrow_points_and_paint():  # EXC-08
    doc = to_excalidraw(scene(conn(dashed=True, opacity=0.5)))
    a = by_id(doc, "e")
    assert a["type"] == "arrow" and a["elbowed"] is False and a["roundness"] is None
    assert [(a["x"] + px, a["y"] + py) for px, py in a["points"]] == [(400, 260), (500, 260), (500, 400)]
    assert (a["strokeColor"], a["strokeWidth"], a["strokeStyle"], a["opacity"]) == ("#444444", 2, "dashed", 50)
    assert (a["width"], a["height"]) == (100, 140)


def test_curve_keeps_three_points_and_rounds():  # EXC-08 (curve)
    a = by_id(to_excalidraw(scene(conn(points=((0, 0), (50, -40), (100, 0)), route="curve"))), "e")
    assert [(a["x"] + px, a["y"] + py) for px, py in a["points"]] == [(0, 0), (50, -40), (100, 0)]
    assert a["roundness"] == {"type": 2}


def test_arrowheads():  # Arrowheads row
    pairs = {"arrow": "triangle", "open-arrow": "arrow", "diamond": "diamond", "open-diamond": "diamond_outline",
             "circle": "circle", "bar": "bar"}
    for ours, theirs in pairs.items():
        a = by_id(to_excalidraw(scene(conn(arrow_start=True, marker_start=ours, marker_end=ours))), "e")
        assert (a["startArrowhead"], a["endArrowhead"]) == (theirs, theirs)
    a = by_id(to_excalidraw(scene(conn(arrow_end=False))), "e")
    assert (a["startArrowhead"], a["endArrowhead"]) == (None, None)
    a = by_id(to_excalidraw(scene(conn(arrow_start=True, marker_start="none"))), "e")
    assert a["startArrowhead"] is None


def test_bindings():  # EXC-09
    from spinagram.scene import Binding

    a, b = box("a", x=100, y=200, w=300, h=120), box("b", x=600, y=200, w=200, h=100)
    e = conn(points=((400, 260), (600, 225)), src=Binding("a", "right"), dst=Binding("b", "left", 0.25))
    doc = to_excalidraw(scene(e, a, b))                                # connector listed before its shapes
    arrow = by_id(doc, "e")
    assert arrow["startBinding"]["elementId"] == "a" and arrow["endBinding"]["elementId"] == "b"
    assert arrow["startBinding"]["fixedPoint"] == [1, 0.5]
    assert arrow["endBinding"]["fixedPoint"] == [0, 0.25]
    assert by_id(doc, "a")["boundElements"] == [{"type": "arrow", "id": "e"}]
    assert by_id(doc, "b")["boundElements"] == [{"type": "arrow", "id": "e"}]


def test_unbound_end_is_null():  # edge case
    from spinagram.scene import Binding

    doc = to_excalidraw(scene(box("a"), conn(src=Binding("a", "right"))))
    assert by_id(doc, "e")["endBinding"] is None and by_id(doc, "e")["startBinding"] is not None


def test_edge_label_grouped_with_arrow():  # EXC-10
    from spinagram.scene import Label

    pill = box("e:label", kind="pill", x=430, y=245, w=60, h=30, role="pill",
               label=Label([block(["go"], size=14)], (430, 245, 60, 30), align="center"))
    doc = to_excalidraw(scene(conn(label=pill)))
    arrow, rect, text = by_id(doc, "e"), by_id(doc, "e:label"), els(doc, "text")[0]
    assert (rect["x"], rect["y"], rect["width"], rect["height"]) == (430, 245, 60, 30)
    assert text["text"] == "go"
    shared = set(arrow["groupIds"]) & set(rect["groupIds"]) & set(text["groupIds"])
    assert shared


# T5 -------------------------------------------------------------------------------------------------
SVG_DOT = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8"><circle r="4"/></svg>'


def test_icon_and_image_become_image_elements(tmp_path):  # EXC-11
    import base64

    from spinagram.scene import Icon, Image

    (tmp_path / "dot.svg").write_bytes(SVG_DOT)
    (tmp_path / "pic.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    doc = to_excalidraw(scene(box("a", icon=Icon(tmp_path / "dot.svg", 120, 220, 48)),
                              Image("img", tmp_path / "pic.png", 10, 20, 64, 32)))
    icon, img = els(doc, "image")
    assert (icon["x"], icon["y"], icon["width"], icon["height"]) == (120, 220, 48, 48)
    assert (img["x"], img["y"], img["width"], img["height"]) == (10, 20, 64, 32)
    for el, raw, mime in ((icon, SVG_DOT, "image/svg+xml"), (img, b"\x89PNG\r\n\x1a\nfake", "image/png")):
        f = doc["files"][el["fileId"]]
        assert f["id"] == el["fileId"] and f["mimeType"] == mime
        head, data = f["dataURL"].split(",", 1)
        assert head == f"data:{mime};base64" and base64.b64decode(data) == raw
    assert icon["groupIds"] == by_id(doc, "a")["groupIds"] != []     # the icon moves with its box


def test_same_bytes_stored_once(tmp_path):  # EXC-12
    from spinagram.scene import Icon

    (tmp_path / "one.svg").write_bytes(SVG_DOT)
    (tmp_path / "two.svg").write_bytes(SVG_DOT)
    doc = to_excalidraw(scene(box("a", icon=Icon(tmp_path / "one.svg", 0, 0, 10)),
                              box("b", icon=Icon(tmp_path / "two.svg", 50, 0, 10))))
    assert len(els(doc, "image")) == 2 and len(doc["files"]) == 1


def test_missing_icon_raises_like_svg(tmp_path):  # edge case
    import pytest

    from spinagram.backends.svg import to_svg
    from spinagram.scene import Icon

    sc = scene(box("a", icon=Icon(tmp_path / "gone.svg", 0, 0, 10)))
    with pytest.raises(FileNotFoundError):
        to_svg(sc)
    with pytest.raises(FileNotFoundError):
        to_excalidraw(sc)


# T6 -------------------------------------------------------------------------------------------------
def test_line_item():  # EXC-13 (Line)
    from spinagram.scene import Line

    ln = by_id(to_excalidraw(scene(Line("rule", 80, 1000, 1840, 1000, "#CCCCCC", 2))), "rule")
    assert ln["type"] == "line" and ln["polygon"] is False
    assert [(ln["x"] + px, ln["y"] + py) for px, py in ln["points"]] == [(80, 1000), (1840, 1000)]
    assert (ln["strokeColor"], ln["strokeWidth"]) == ("#CCCCCC", 2)


def test_table_cells_grouped():  # EXC-13 (TableGrid)
    from spinagram.scene import Cell, TableGrid

    head, body = "#003366", "#FFFFFF"
    cells = [[Cell(block(["Col A"]), head), Cell(block(["Col B"]), head)],
             [Cell(block(["1"]), body), Cell(block(["2"]), body)]]
    doc = to_excalidraw(scene(TableGrid("t", 100, 300, [200, 150], [40, 50], cells, "#DDDDDD")))
    rects = els(doc, "rectangle")
    boxes = [(r["x"], r["y"], r["width"], r["height"], r["backgroundColor"]) for r in rects]
    assert boxes == [(100, 300, 200, 40, head), (300, 300, 150, 40, head),
                     (100, 340, 200, 50, body), (300, 340, 150, 50, body)]
    texts = els(doc, "text")
    assert [t["text"] for t in texts] == ["Col A", "Col B", "1", "2"]
    assert texts[0]["x"] == 100 + 16 and texts[0]["y"] == 300 + (40 - 26) / 2
    table = [e for e in doc["elements"] if e["type"] != "frame"]
    assert {tuple(e["groupIds"]) for e in table} == {("g:t",)}


# T7 -------------------------------------------------------------------------------------------------
def test_registered():  # EXC-01
    from spinagram.backends import available, get_backend

    assert available()["excalidraw"] == "spinagram.backends.excalidraw:ExcalidrawBackend"
    assert isinstance(get_backend("excalidraw"), ExcalidrawBackend)


def test_render_examples_with_the_cli(tmp_path, capsys):  # EXC-01, EXC-02 over every example
    from pathlib import Path

    from spinagram.cli import main
    from spinagram.yaml_io import load

    root = Path(__file__).resolve().parents[1] / "examples"
    specs = sorted(p for p in root.glob("*.yaml"))
    assert main(["render", *map(str, specs), "-f", "excalidraw", "-o", str(tmp_path), "--no-gallery"]) == 0
    written = sorted(tmp_path.glob("*.excalidraw"))
    assert len(written) == sum(len(load(str(p))) for p in specs)
    for p in written:
        doc = json.loads(p.read_text(encoding="utf-8"))
        assert doc["type"] == "excalidraw" and doc["elements"][0]["type"] == "frame"
    assert "excalidraw" in capsys.readouterr().out


# T9 (validation.md, iteration 1) ---------------------------------------------------------------------
def _outline(doc, s):
    """Absolute points of each line element drawn for ``s``, in order."""
    return [[(ln["x"] + px, ln["y"] + py) for px, py in ln["points"]] for ln in els(doc, "line")
            if "g:" + s.id in ln["groupIds"]]


def test_every_subpath_of_a_part_is_drawn():  # EXC-05: one line per subpath
    from spinagram import shapes

    for kind in ("predefined", "flow_final"):                       # body + two open strokes in one part
        s = box(kind, kind=kind, parts=shapes.parts(kind, 100, 200, 300, 120), stroke="#333333", stroke_width=2)
        lines = _outline(to_excalidraw(scene(s)), s)
        subs = [sp for p in s.parts for sp in shapes.parse(p.d)]
        assert len(lines) == len(subs) == 3
        for got, sp in zip(lines, subs):
            assert abs(got[0][0] - sp.start[0]) <= 1 and abs(got[0][1] - sp.start[1]) <= 1


def test_closed_subpath_ends_on_its_start():  # EXC-05: polygon closes on its first point
    from spinagram import shapes

    for kind in ("document", "decision"):                           # the path data does not repeat its start
        s = box(kind, kind=kind, parts=shapes.parts(kind, 100, 200, 300, 120))
        sp = shapes.parse(s.parts[0].d)[0]
        assert sp.closed and (sp.segments[-1][1][-1] != sp.start)
        (pts,) = _outline(to_excalidraw(scene(s)), s)
        assert pts[-1] == pts[0]

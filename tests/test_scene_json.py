"""Scene JSON: version, item tags and every field the SVG writer reads (SCN-01)."""
import json
from pathlib import Path

import pytest

from spinagram import scene_json
from spinagram.scene import (Binding, Cell, Connector, Icon, Image, Label, Line, Run, Scene, Shape, TableGrid, Text,
                             TextBlock)
from spinagram.shapes import Part
from spinagram.theme import FontRef

FONT = FontRef("Inter", 700, True, 14, Path("/fonts/inter.ttf"), "sans-serif", "Bold Italic")
FALLBACK = FontRef("Noto Sans", 400, False, 14, None)


def block(runs=True):
    return TextBlock(["one", ""], ["one"], FONT, "#112233", 18.0,
                     [[Run("o", FONT), Run("ne", FALLBACK)], []] if runs else None)


def full_scene() -> Scene:
    icon = Icon(Path("icons/a.svg"), 1, 2, 24, 30)
    label = Label([block()], (10, 20, 100, 50), "center", 8, "top")
    shape = Shape("s1", "rect", 10, 20, 100, 50, "#fff", "#000", 2, 6, True, 0.5, label, icon, "node",
                  [Part("M 0 0 L 1 1 Z", "solid"), Part("M 1 1 Z", "stroke")], [4, 2], (1, 2, 6, "#000000", 0.25),
                  0.75, "round")
    conn = Connector("c1", [(0, 0), (5, 5), (9, 0)], "curve", "#abcdef", 1.5, True, True, False,
                     Binding("s1", "right", 0.25, "zone"), None, Shape("lab", "pill", 0, 0, 10, 10, None), [3.0],
                     "open-diamond", "bar", 0.5)
    text = Text("t1", 5, 6, block(), "middle", 0.5, 120)
    cell = Cell(block(runs=False), "#eee", icon, 20, True)
    table = TableGrid("tb", 1, 2, [50, 60], [20, 30], [[cell, cell], [cell, cell]], "#ccc", 4)
    return Scene("S1", "Title & more", "s1-title", 640, 480, "#fafafa",
                 [shape, conn, text, Line("l1", 0, 1, 2, 3, "#000", 2), Image("i1", Path("/img/x.png"), 1, 2, 3, 4),
                  table], item_facts={"s1": ["f1"]}, sources=[{"id": "f1", "display": "é"}],
                 meta_tooltips={"f1": "from the wiki"})


@pytest.fixture(scope="module")
def doc():
    return json.loads(scene_json.dumps(full_scene()))


def test_version_is_1(doc):  # SCN-01
    assert doc["version"] == 1


@pytest.mark.parametrize("i,tag", enumerate(["shape", "connector", "text", "line", "image", "table"]))
def test_item_type_tags(doc, i, tag):  # SCN-01 (all six item types, L-020)
    assert doc["items"][i]["type"] == tag


def test_shape_fields(doc):  # SCN-01
    s = doc["items"][0]
    assert (s["id"], s["kind"], s["role"], s["radius"], s["dashed"], s["opacity"], s["fill_opacity"], s["cap"]) == (
        "s1", "rect", "node", 6, True, 0.5, 0.75, "round")
    assert s["dash"] == [4, 2] and s["shadow"] == [1, 2, 6, "#000000", 0.25]
    assert s["parts"] == [{"d": "M 0 0 L 1 1 Z", "paint": "solid"}, {"d": "M 1 1 Z", "paint": "stroke"}]
    assert s["label"]["box"] == [10, 20, 100, 50] and s["label"]["align"] == "center"
    assert s["icon"] == {"path": str(Path("icons/a.svg").absolute()), "x": 1, "y": 2, "size": 24, "w": 30}


def test_text_block_font_and_runs(doc):  # SCN-01
    b = doc["items"][0]["label"]["blocks"][0]
    assert b["lines"] == ["one", ""] and b["paragraphs"] == ["one"] and b["color"] == "#112233"
    assert b["font"] == {"family": "Inter", "weight": 700, "italic": True, "size": 14, "file": "/fonts/inter.ttf",
                         "fallback": "sans-serif", "figma_style": "Bold Italic"}
    assert [[r["text"] for r in line] for line in b["runs"]] == [["o", "ne"], []]
    assert [[r["base"] for r in line] for line in b["runs"]] == [[True, False], []]
    assert b["runs"][0][1]["font"]["file"] is None


def test_connector_fields(doc):  # SCN-01
    c = doc["items"][1]
    assert c["points"] == [[0, 0], [5, 5], [9, 0]] and c["route"] == "curve"
    assert (c["arrow_start"], c["arrow_end"], c["marker_start"], c["marker_end"]) == (True, False, "open-diamond",
                                                                                      "bar")
    assert c["src"] == {"shape_id": "s1", "side": "right", "frac": 0.25, "target": "zone"} and c["dst"] is None
    assert c["label"]["type"] == "shape" and c["label"]["id"] == "lab"


def test_text_line_image_table_fields(doc):  # SCN-01
    assert doc["items"][2]["anchor"] == "middle" and doc["items"][2]["letter_spacing"] == 0.5
    assert doc["items"][3]["x2"] == 2 and doc["items"][3]["width"] == 2
    assert doc["items"][4]["path"] == "/img/x.png"
    t = doc["items"][5]
    assert t["col_widths"] == [50, 60] and t["row_heights"] == [20, 30] and t["header_radius"] == 4
    assert t["cells"][0][0]["pad_left"] == 20 and t["cells"][0][0]["bold"] is True
    assert t["cells"][0][0]["block"]["runs"] is None and t["cells"][0][0]["icon"]["size"] == 24


def test_scene_width(doc):  # SCN-01
    assert doc["width"] == 640


def test_scene_height(doc):  # SCN-01
    assert doc["height"] == 480


def test_scene_background(doc):  # SCN-01
    assert doc["background"] == "#fafafa"


def test_scene_title(doc):  # SCN-01
    assert doc["title"] == "Title & more"


def test_scene_sources(doc):  # SCN-01
    assert doc["sources"] == [{"id": "f1", "display": "é"}]


def test_scene_item_facts(doc):  # SCN-01
    assert doc["item_facts"] == {"s1": ["f1"]}


def test_scene_meta_tooltips(doc):  # SCN-01
    assert doc["meta_tooltips"] == {"f1": "from the wiki"}



# the Rust core: round trip, schema, version (SCN-02, SCN-04, SCN-05) ---------------------------------------------
from example_scenes import example_scenes  # noqa: E402

SCHEMA = Path(__file__).resolve().parents[1] / "rust" / "schema" / "scene.schema.json"


@pytest.fixture(scope="module")
def core():
    return pytest.importorskip("spinagram._core")


def test_example_scenes_are_all_covered():
    assert len(example_scenes()) > 40


def test_every_example_scene_round_trips_equal(core):  # SCN-02
    for sc in example_scenes():
        text = scene_json.dumps(sc)
        assert json.loads(core.scene_roundtrip(text)) == json.loads(text), sc.slug


def test_every_example_scene_validates_against_the_schema():  # SCN-04
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(schema)
    for sc in example_scenes():
        errors = list(validator.iter_errors(scene_json.to_dict(sc)))
        assert not errors, (sc.slug, errors[0].message)


def test_full_scene_validates_against_the_schema():  # SCN-04 (every item type and optional field)
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.validate(scene_json.to_dict(full_scene()), json.loads(SCHEMA.read_text()))


def test_wrong_version_raises_valueerror_with_the_rust_message(core):  # SCN-05
    doc = scene_json.to_dict(full_scene())
    doc["version"] = 2
    with pytest.raises(ValueError, match=r"scene version 2 is not supported \(expected 1\)"):
        core.scene_roundtrip(json.dumps(doc))


# zones and containers for the canvas (T11) ---------------------------------------------------------------------
def _container_scene() -> Scene:
    a = Shape("a", "rect", 10, 20, 100, 50, None, role="node")
    b = Shape("b", "rect", 150, 40, 80, 60, None, role="node")
    z = Shape("z0", "rect", 0, 0, 400, 300, None, role="zone")
    sc = Scene("S2", "t", "s2", 640, 480, "#fff", [z, a, b])
    sc.rows = [("row0", ["a", "b"], False), ("column1", ["b"], False)]
    sc.zone_ids = {"z0": "outer"}
    sc.zone_children = {"z0": ["a"]}
    return sc


def test_scene_lists_containers_with_axis_members_and_enclosing_box():
    doc = scene_json.to_dict(_container_scene())
    assert doc["containers"] == [
        {"id": "row0", "axis": "row", "members": ["a", "b"], "box": [10, 20, 220, 80]},
        {"id": "column1", "axis": "column", "members": ["b"], "box": [150, 40, 80, 60]}]


def test_scene_lists_zones_with_declared_id_shape_id_and_children():
    doc = scene_json.to_dict(_container_scene())
    assert doc["zones"] == [{"id": "outer", "shape_id": "z0", "children": ["a"]}]


def test_scene_without_zones_or_containers_omits_the_keys():
    doc = scene_json.to_dict(full_scene())
    assert "zones" not in doc and "containers" not in doc


def test_container_scene_validates_and_round_trips(core):
    jsonschema = pytest.importorskip("jsonschema")
    doc = scene_json.to_dict(_container_scene())
    jsonschema.validate(doc, json.loads(SCHEMA.read_text()))
    assert json.loads(core.scene_roundtrip(json.dumps(doc))) == doc

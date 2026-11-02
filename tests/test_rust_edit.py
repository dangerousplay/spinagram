"""Rust edit operations through ``spinagram.edit``: the patched YAML loads through ``yaml_io`` and renders."""
from __future__ import annotations

from pathlib import Path

import pytest

from spinagram import edit
from spinagram.edit import EditError
from spinagram.yaml_io import load_yaml

ROOT = Path(__file__).resolve().parents[1]


def _load(tmp_path: Path, text: str):
    f = tmp_path / "d.yaml"
    f.write_text(text, encoding="utf-8")
    return load_yaml(f)[0]


def _boxes(d):
    return {n.id: (n.x, n.y, n.w, n.h) for n in d.nodes}


def _hand_placed(name: str) -> str:
    return (ROOT / "examples" / name).read_text(encoding="utf-8")


def test_move_sets_the_node_position_and_leaves_the_others(tmp_path):
    text = _hand_placed("software_architecture.yaml")
    before = _load(tmp_path, text)
    target = before.nodes[0]
    out = edit.apply_ops(text, [{"op": "move", "id": target.id, "x": 777, "y": 333}])
    after = _load(tmp_path, out)
    got, was = _boxes(after), _boxes(before)
    assert (got[target.id][0], got[target.id][1]) == (777, 333)
    assert got[target.id][2:] == was[target.id][2:]
    assert {k: v for k, v in got.items() if k != target.id} == {k: v for k, v in was.items() if k != target.id}
    assert len(after.edges) == len(before.edges)


def test_move_on_aws_layout_gives_the_node_the_new_coordinates(tmp_path):
    text = _hand_placed("aws_layout.yaml")
    before = _load(tmp_path, text)
    out = edit.apply_ops(text, [{"op": "move", "id": "alb", "x": 120, "y": 340}])
    after = _load(tmp_path, out)
    alb = next(n for n in after.nodes if n.id == "alb")
    assert (alb.x, alb.y) == (120, 340)
    assert {n.id: (n.x, n.y, n.w, n.h) for n in after.nodes if n.id != "alb"} == \
        {n.id: (n.x, n.y, n.w, n.h) for n in before.nodes if n.id != "alb"}


def test_move_changes_only_that_entry_bytes():
    text = _hand_placed("software_architecture.yaml")
    ids = edit.srcmap(text)
    first = next(i for i in ids if not i.startswith("e"))
    out = edit.apply_ops(text, [{"op": "move", "id": first, "x": 1, "y": 2}])
    a, b = ids[first]
    raw = text.encode()
    assert out.encode().startswith(raw[:a]) and out.encode().endswith(raw[b:])


def test_delete_removes_the_node_and_its_edges_and_the_diagram_renders(tmp_path):
    from spinagram.autolayout import apply_layout
    from spinagram.backends.svg import to_svg
    from spinagram.layout import build_scene
    from spinagram.theme import Theme

    text = _hand_placed("software_architecture.yaml")
    before = _load(tmp_path, text)
    victim = next(n.id for n in before.nodes if any(n.id in (str(e.src).partition(".")[0], str(e.dst).partition(".")[0])
                                                     for e in before.edges))
    out = edit.apply_ops(text, [{"op": "delete", "id": victim}])
    after = _load(tmp_path, out)
    assert victim not in {n.id for n in after.nodes}
    assert {n.id for n in after.nodes} == {n.id for n in before.nodes} - {victim}
    ends = {str(x).partition(".")[0] for e in after.edges for x in (e.src, e.dst)}
    assert victim not in ends
    assert len(after.edges) < len(before.edges)
    theme = Theme.load(None)
    assert to_svg(build_scene(apply_layout(after, theme, None), theme)).startswith("<svg")


def test_aws_layout_example_loads_after_a_delete(tmp_path):
    """The engine-laid-out example: groups and `children` lists lose the node too."""
    from spinagram.autolayout import apply_layout
    from spinagram.backends.svg import to_svg
    from spinagram.layout import build_scene
    from spinagram.theme import Theme

    text = _hand_placed("aws_layout.yaml")
    out = edit.apply_ops(text, [{"op": "delete", "id": "s3"}])
    d = _load(tmp_path, out)
    assert "s3" not in {n.id for n in d.nodes}
    assert all("s3" not in g.children for g in d.groups)
    assert not any("s3" in (str(e.src), str(e.dst)) for e in d.edges)
    theme = Theme.load(None)
    assert to_svg(build_scene(apply_layout(d, theme, None), theme)).startswith("<svg")


def test_connect_rename_add_and_disconnect_round_trip(tmp_path):
    text = _hand_placed("software_architecture.yaml")
    d0 = _load(tmp_path, text)
    a, b = d0.nodes[0].id, d0.nodes[1].id
    out = edit.apply_ops(text, [
        {"op": "add_node", "id": "fresh", "title": "Fresh node", "x": 10, "y": 10, "w": 120, "h": 60},
        {"op": "connect", "from": a, "to": "fresh", "label": "new"},
        {"op": "rename", "id": b, "title": "Renamed: B"},
    ])
    d1 = _load(tmp_path, out)
    assert next(n for n in d1.nodes if n.id == "fresh").title == "Fresh node"
    assert next(n for n in d1.nodes if n.id == b).title == "Renamed: B"
    assert any(e.src == a and e.dst == "fresh" and e.label == "new" for e in d1.edges)
    back = edit.apply_ops(out, [{"op": "disconnect", "from": a, "to": "fresh"}, {"op": "delete", "id": "fresh"}])
    assert len(_load(tmp_path, back).edges) == len(d0.edges)


def test_invalid_op_raises_edit_error_with_the_rust_reason():
    text = _hand_placed("software_architecture.yaml")
    with pytest.raises(EditError, match="unknown id `nope`"):
        edit.apply_ops(text, [{"op": "move", "id": "nope", "x": 1, "y": 1}])
    with pytest.raises(EditError, match="operation 1: .*duplicate id"):
        first = next(i for i in edit.srcmap(text) if not i.startswith("e"))
        edit.apply_ops(text, [{"op": "move", "id": first, "x": 1, "y": 1}, {"op": "add_node", "id": first}])
    with pytest.raises(EditError, match="invalid operations"):
        edit.apply_ops(text, [{"op": "frobnicate"}])
    with pytest.raises(EditError, match="invalid YAML"):
        edit.srcmap("a: [1")


def _is_container(key: str) -> bool:
    import re

    return re.fullmatch(r"(row|column)\d+", key) is not None


@pytest.mark.parametrize("name", sorted(str(p.relative_to(ROOT / "examples")) for p in (ROOT / "examples").rglob("*.yaml")))
def test_srcmap_slices_parse_back_for_every_example(name):
    import yaml

    text = _hand_placed(name)
    try:
        m = edit.srcmap(text)
    except EditError:
        pytest.skip("not a single-document mapping")
    raw = text.encode()
    for key, (a, b) in m.items():
        piece = raw[a:b].decode()
        value = yaml.safe_load(piece)
        assert value is not None, (key, piece)
        if _is_container(key):  # row0, column1: the entry of a `rows`/`columns` list, no id of its own
            assert isinstance(value, dict) and "nodes" in value
        elif not key.startswith("e"):
            assert isinstance(value, dict) and str(value["id"]) == key


@pytest.mark.parametrize("name", sorted(str(p.relative_to(ROOT / "examples")) for p in (ROOT / "examples").rglob("*.yaml")))
def test_every_element_of_every_example_survives_edits(name, tmp_path):
    """Move, resize and rename each node and zone of each example: the result still loads in ``yaml_io``."""
    text = _hand_placed(name)
    try:
        ids = [i for i in edit.srcmap(text) if not (i[0] == "e" and i[1:].isdigit()) and not _is_container(i)]
    except EditError:
        pytest.skip("not a single-document mapping")
    for i in ids:
        out = edit.apply_ops(text, [{"op": "move", "id": i, "x": 11, "y": 22}, {"op": "resize", "id": i, "w": 33, "h": 44},
                                    {"op": "rename", "id": i, "title": "T: x # y"}])
        d = _load(tmp_path, out)
        hit = next((n for n in d.nodes if n.id == i), None)
        if hit is not None:
            assert hit.title == "T: x # y"


# --- zone and container operations (T10): every patched fixture loads and has the expected structure ----------

EDIT_DATA = ROOT / "rust" / "spinagram-core" / "tests" / "data" / "edit"


def _fixture(name: str) -> str:
    return (EDIT_DATA / f"{name}.yaml").read_text(encoding="utf-8")


def _zone_children(d):
    return {z.id: list(z.children) for z in d.zones}


def _containers(d):
    return [(c.axis, list(c.children), c.gap, c.x, c.y) for c in d.containers]


def test_reparent_changes_zone_children_after_loading(tmp_path):
    text = _fixture("zones_block")
    assert _zone_children(_load(tmp_path, text)) == {"outer": ["inner", "n1"], "inner": ["n2"], "empty": []}
    out = edit.apply_ops(text, [{"op": "reparent", "id": "n2", "parent": "empty"},
                                {"op": "reparent", "id": "n1", "parent": None},
                                {"op": "reparent", "id": "n3", "parent": "outer"}])
    assert _zone_children(_load(tmp_path, out)) == {"outer": ["inner", "n3"], "inner": [], "empty": ["n2"]}
    flow = edit.apply_ops(_fixture("zones_flow"), [{"op": "reparent", "id": "m2", "parent": "zb"}])
    assert _zone_children(_load(tmp_path, flow)) == {"za": ["zb", "m1"], "zb": ["m2"]}


def test_zone_into_its_descendant_is_rejected_with_the_spec_message():
    with pytest.raises(EditError, match="A zone cannot contain itself"):
        edit.apply_ops(_fixture("zones_block"), [{"op": "reparent", "id": "outer", "parent": "inner"}])


def test_move_zone_moves_the_zone_and_its_children_after_loading(tmp_path):
    text = _fixture("zones_block")
    before = _load(tmp_path, text)
    out = edit.apply_ops(text, [{"op": "move_zone", "id": "outer", "x": 30, "y": 40}])
    after = _load(tmp_path, out)
    zones = {z.id: (z.x, z.y) for z in after.zones}
    assert zones == {"outer": (30, 40), "inner": (70, 100), "empty": (900, 20)}
    boxes, was = _boxes(after), _boxes(before)
    assert (boxes["n1"][0], boxes["n1"][1]) == (410, 120)
    assert (boxes["n2"][0], boxes["n2"][1]) == (90, 140)
    assert boxes["n3"] == was["n3"]
    assert [b[2:] for b in boxes.values()] == [b[2:] for b in was.values()]


def test_add_zone_loads_as_a_zone(tmp_path):
    out = edit.apply_ops(_fixture("zones_flow"), [{"op": "add_zone", "id": "zc", "label": "C", "x": 1, "y": 2, "w": 300, "h": 200}])
    zc = next(z for z in _load(tmp_path, out).zones if z.id == "zc")
    assert (zc.label, zc.x, zc.y, zc.w, zc.h) == ("C", 1, 2, 300, 200)


def test_add_zone_style_and_set_zone_style_load_as_the_zone_color(tmp_path):
    out = edit.apply_ops(_fixture("zones_flow"), [
        {"op": "add_zone", "id": "zc", "label": "C", "style": "aws-vpc", "x": 1, "y": 2, "w": 300, "h": 200},
        {"op": "set_zone_style", "id": "zb", "style": "azure-vnet"},
    ])
    zones = {z.id: z for z in _load(tmp_path, out).zones}
    assert (zones["zc"].color, zones["zb"].color) == ("aws-vpc", "azure-vnet")
    assert zones["za"].color == "soft"  # untouched zones keep the default
    with pytest.raises(EditError, match="not a zone"):
        edit.apply_ops(_fixture("zones_flow"), [{"op": "set_zone_style", "id": "m1", "style": "aws-vpc"}])
    # the Python and the Rust results agree with the Rust unit tests on the bytes
    assert edit.apply_ops(_fixture("zones_flow"), [{"op": "set_zone_style", "id": "zb", "style": "k8s-namespace"}]) == \
        _fixture("zones_flow").replace("h: 200}]", "h: 200, color: k8s-namespace}]")


def test_group_add_remove_and_ungroup_after_loading(tmp_path):
    text = _fixture("groups_block")
    assert _containers(_load(tmp_path, text)) == [("row", ["e", "f", "g"], 30, 40, 500), ("column", ["h", "i"], 20, 800, 100)]
    grouped = edit.apply_ops(text, [{"op": "group", "axis": "row", "ids": ["a", "b", "c"]}])
    assert _containers(_load(tmp_path, grouped))[1] == ("row", ["b", "a", "c"], 20, 40, 60)
    added = edit.apply_ops(text, [{"op": "add_to_container", "id": "row0", "node": "a", "index": 1}])
    assert _containers(_load(tmp_path, added))[0][1] == ["e", "a", "f", "g"]
    removed = _load(tmp_path, edit.apply_ops(text, [{"op": "remove_from_container", "id": "row0", "node": "f",
                                                      "boxes": {"f": [10, 20, 100, 60]}}]))
    assert _containers(removed)[0][1] == ["e", "g"]
    assert _boxes(removed)["f"] == (10, 20, 100, 60)
    dissolved = _load(tmp_path, edit.apply_ops(text, [{"op": "remove_from_container", "id": "column1", "node": "h",
                                                        "boxes": {"h": [1, 2, 30, 40], "i": [5, 6, 70, 80]}}]))
    assert _containers(dissolved) == [("row", ["e", "f", "g"], 30, 40, 500)]
    assert (_boxes(dissolved)["h"], _boxes(dissolved)["i"]) == ((1, 2, 30, 40), (5, 6, 70, 80))
    ungrouped = _load(tmp_path, edit.apply_ops(text, [{"op": "ungroup", "id": "row0", "boxes": {
        "e": [40, 500, 100, 60], "f": [170, 500, 100, 60], "g": [300, 500, 100, 60]}}]))
    assert [c[0] for c in _containers(ungrouped)] == ["column"]
    assert _boxes(ungrouped)["g"] == (300, 500, 100, 60)


def test_set_container_changes_gap_and_align(tmp_path):
    out = edit.apply_ops(_fixture("groups_block"), [{"op": "set_container", "id": "row0", "gap": 44}])
    assert _load(tmp_path, out).containers[0].gap == 44
    zoned = ("id: t\ntitle: T\nzones: [{id: z, x: 0, y: 0, w: 600, h: 300}]\nnodes: [{id: a}, {id: b}]\n"
             "rows:\n  - {zone: z, nodes: [a, b]}\n")
    c = _load(tmp_path, edit.apply_ops(zoned, [{"op": "set_container", "id": "row0", "gap": 8, "align": "start"}])).containers[0]
    assert (c.gap, c.align) == (8, "start")
    with pytest.raises(EditError, match="placed in a zone"):
        edit.apply_ops(_fixture("groups_block"), [{"op": "set_container", "id": "row0", "align": "start"}])


def test_inline_container_members_become_nodes_on_ungroup(tmp_path):
    text = "id: t\ntitle: T\nrows:\n  - x: 0\n    y: 0\n    nodes:\n      - {id: p, title: P}\n      - {id: q, title: Q}\n"
    out = edit.apply_ops(text, [{"op": "ungroup", "id": "row0", "boxes": {"p": [10, 20, 100, 50], "q": [150, 20, 100, 50]}}])
    d = _load(tmp_path, out)
    assert d.containers == [] and _boxes(d) == {"p": (10, 20, 100, 50), "q": (150, 20, 100, 50)}


def test_add_to_the_same_container_reorders_its_members(tmp_path):
    text = _fixture("groups_block")
    out = edit.apply_ops(text, [{"op": "add_to_container", "id": "row0", "node": "e", "index": 1}])
    assert _containers(_load(tmp_path, out))[0][1] == ["f", "e", "g"]
    out = edit.apply_ops(text, [{"op": "add_to_container", "id": "column1", "node": "i", "index": 0}])
    assert _containers(_load(tmp_path, out))[1][1] == ["i", "h"]


def test_add_node_with_an_icon_ref_loads_with_that_icon(tmp_path):
    out = edit.apply_ops(_fixture("zones_flow"), [{"op": "add_node", "id": "pg", "title": "Postgres", "icon": "aws:rds-postgresql",
                                                    "x": 10, "y": 20, "w": 220, "h": 96}])
    node = next(n for n in _load(tmp_path, out).nodes if n.id == "pg")
    assert (node.icon, node.title, node.w, node.h) == ("aws:rds-postgresql", "Postgres", 220, 96)


# ---- properties, duplicate, reconnect, reverse (wasm-editor T38) ----

def _edge(d, i):
    e = d.edges[i]
    return (e.src, e.dst, e.label, e.arrow, e.route, e.dashed, e.color, e.width)


@pytest.mark.parametrize("name", ["props_block", "props_flow"])
def test_every_property_fixture_loads_before_any_edit(tmp_path, name):
    assert _load(tmp_path, _fixture(name)).nodes


def test_set_props_changes_the_model_values_of_a_node_zone_and_edges(tmp_path):
    text = _fixture("props_block")
    out = edit.apply_ops(text, [
        {"op": "set_props", "id": "api", "props": {"title": "Orders API", "class": None, "dashed": True}},
        {"op": "set_props", "id": "vpc", "props": {"label": "Prod VPC", "color": "aws-region"}},
        {"op": "set_props", "id": "e0", "props": {"route": "ortho"}},            # string edge becomes a mapping
        {"op": "set_props", "id": "e1", "props": {"label": "warm"}},             # string edge stays a string
        {"op": "set_props", "id": "e3", "props": {"dashed": None, "width": 2}},
    ])
    d = _load(tmp_path, out)
    api = next(n for n in d.nodes if n.id == "api")
    assert (api.title, api.cls, api.dashed) == ("Orders API", None, True)
    vpc = d.zones[0]
    assert (vpc.label, vpc.color) == ("Prod VPC", "aws-region")
    assert _edge(d, 0)[:5] == ("api", "db", "reads", "end", "ortho")
    assert _edge(d, 1)[:3] == ("api", "cache", "warm")
    assert (_edge(d, 3)[5], _edge(d, 3)[7]) == (False, 2)
    assert "  - api -> cache: warm" not in out and '"api -> cache: warm"' in out      # a labelled string edge is quoted
    # nothing else moved: the untouched node and the two other edges are as before
    before = _load(tmp_path, text)
    assert _edge(d, 2) == _edge(before, 2) and _edge(d, 4) == _edge(before, 4)
    assert _boxes(d)["db"] == _boxes(before)["db"]


def test_set_props_rejects_what_the_loader_would_refuse(tmp_path):
    text = _fixture("props_block")
    for props, reason in [({"bogus": 1}, "not a property of a node"), ({"x": 5}, "move, resize"), ({"dashed": "yes"}, "wrong type")]:
        with pytest.raises(EditError, match=reason):
            edit.apply_ops(text, [{"op": "set_props", "id": "api", "props": props}])
    with pytest.raises(EditError, match="one of ortho, elbow"):
        edit.apply_ops(text, [{"op": "set_props", "id": "e1", "props": {"route": "weird"}}])


def test_duplicate_adds_a_node_in_the_same_zone_and_container(tmp_path):
    text = _fixture("props_block")
    d = _load(tmp_path, edit.apply_ops(text, [{"op": "duplicate", "id": "api", "dx": 30, "dy": 40},
                                              {"op": "duplicate", "id": "cache", "dx": 10, "dy": 10}]))
    boxes = _boxes(d)
    assert boxes["api-2"][:2] == (130, 140) and boxes["api-2"][2:] == boxes["api"][2:]
    assert next(n for n in d.nodes if n.id == "api-2").title == "API"
    assert d.zones[0].children == ["api", "api-2", "db"]
    assert _containers(d)[0][1] == ["cache", "cache-2", "inline"]
    z = _load(tmp_path, edit.apply_ops(text, [{"op": "duplicate", "id": "vpc", "dx": 50, "dy": 50}]))
    assert [(zz.x, zz.y, zz.children) for zz in z.zones] == [(20, 20, ["api", "db"]), (70, 70, [])]


def test_reconnect_and_reverse_change_the_ends_in_the_model(tmp_path):
    text = _fixture("props_block")
    d = _load(tmp_path, edit.apply_ops(text, [
        {"op": "reconnect", "id": "e0", "to": "cache"},
        {"op": "reconnect", "id": "e4", "to": "cache"},
        {"op": "reverse", "id": "e1"},
        {"op": "reverse", "id": "e2"},
    ]))
    assert _edge(d, 0)[:3] == ("api", "cache", "reads")
    assert _edge(d, 4)[:2] == ("db.left", "cache")          # `<-`: the end that was api.right@0.3 changed
    assert _edge(d, 1)[:2] == ("cache", "api")
    assert (_edge(d, 2)[:2], d.edges[2].via) == (("cache", "db"), [(30.0, 40.0), (10.0, 20.0)])
    with pytest.raises(EditError, match="unknown id `ghost`"):
        edit.apply_ops(text, [{"op": "reconnect", "id": "e0", "to": "ghost"}])


def test_delete_by_edge_id_removes_that_edge(tmp_path):
    d = _load(tmp_path, edit.apply_ops(_fixture("props_block"), [{"op": "delete", "id": "e1"}]))
    assert [(e.src, e.dst) for e in d.edges] == [("api", "db"), ("db", "cache"), ("cache", "api"), ("db.left", "api.right@0.3"), ("cache", "db")]


def test_set_props_accepts_exactly_the_keys_the_loader_accepts():
    """Removing (null) a key is valid only for a key the loader reads: the Rust allow-lists track yaml_io and the model."""
    import dataclasses

    from spinagram import model, yaml_io

    text = _fixture("props_block")
    geometry = {"id", "x", "y", "w", "h"}

    def accepted(target: str, key: str) -> bool:
        try:
            edit.apply_ops(text, [{"op": "set_props", "id": target, "props": {key: None}}])
            return True
        except EditError as exc:
            assert "not a property" in str(exc), exc
            return False

    node_keys = (yaml_io._NODE_KEYS | yaml_io._NODE_EXTRA) - geometry
    assert all(accepted("api", k) for k in node_keys)
    assert not accepted("api", "no_such_key") and not accepted("api", "at") and accepted("api", "x-owner")

    fields = lambda cls: {("class" if f.name == "cls" else f.name) for f in dataclasses.fields(cls)}  # noqa: E731
    zone_keys = fields(model.Zone) - geometry - {"children", "gid"}
    assert all(accepted("vpc", k) for k in zone_keys)
    assert not accepted("vpc", "children") and not accepted("vpc", "icon_size")

    edge_keys = fields(model.Edge) - {"src", "dst"}
    assert all(accepted("e0", k) for k in edge_keys)
    assert not accepted("e0", "from") and not accepted("e0", "src")

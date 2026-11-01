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
        if not key.startswith("e"):
            assert isinstance(value, dict) and str(value["id"]) == key


@pytest.mark.parametrize("name", sorted(str(p.relative_to(ROOT / "examples")) for p in (ROOT / "examples").rglob("*.yaml")))
def test_every_element_of_every_example_survives_edits(name, tmp_path):
    """Move, resize and rename each node and zone of each example: the result still loads in ``yaml_io``."""
    text = _hand_placed(name)
    try:
        ids = [i for i in edit.srcmap(text) if not (i[0] == "e" and i[1:].isdigit())]
    except EditError:
        pytest.skip("not a single-document mapping")
    for i in ids:
        out = edit.apply_ops(text, [{"op": "move", "id": i, "x": 11, "y": 22}, {"op": "resize", "id": i, "w": 33, "h": 44},
                                    {"op": "rename", "id": i, "title": "T: x # y"}])
        d = _load(tmp_path, out)
        hit = next((n for n in d.nodes if n.id == i), None)
        if hit is not None:
            assert hit.title == "T: x # y"

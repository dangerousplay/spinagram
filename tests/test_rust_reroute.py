"""``_core.reroute`` on a Python-rendered scene equals a full Python render of the YAML after the Move edit."""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest

from spinagram import edit, rust, scene_json
from spinagram.autolayout import apply_layout
from spinagram.layout import build_scene
from spinagram.theme import Theme
from spinagram.yaml_io import load_yaml

ROOT = Path(__file__).resolve().parents[1]
DECISION = (ROOT / "examples" / "decision.yaml").read_text(encoding="utf-8")


def _scene(tmp_path: Path, text: str) -> dict:
    f = tmp_path / "d.yaml"
    f.write_text(text, encoding="utf-8")
    theme = Theme.load(None)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return scene_json.to_dict(build_scene(apply_layout(load_yaml(f)[0], theme, None), theme))


def _connectors(scene: dict) -> dict[str, dict]:
    return {i["id"]: i for i in scene["items"] if i["type"] == "connector"}


def test_the_server_scene_carries_the_explicit_flag(tmp_path):
    cs = _connectors(_scene(tmp_path, DECISION))
    assert "explicit" not in cs["e0"]["src"]  # start -> known: the side is chosen by the router
    assert cs["e1"]["src"]["explicit"] is True and cs["e1"]["dst"]["explicit"] is True  # known.right -> std.left


@pytest.mark.parametrize("node,dx,dy", [("std", 60, 40), ("known", 0, 30), ("tg", -40, 25)])
def test_reroute_equals_a_full_render_of_the_moved_yaml(tmp_path, node, dx, dy):
    core = rust._load()
    before = _scene(tmp_path, DECISION)
    box = next(i for i in before["items"] if i["type"] == "shape" and i["id"] == node)
    moved_yaml = edit.apply_ops(DECISION, [{"op": "move", "id": node, "x": box["x"] + dx, "y": box["y"] + dy}])
    want = _connectors(_scene(tmp_path, moved_yaml))
    got = _connectors(json.loads(core.reroute(json.dumps(before), json.dumps({node: [dx, dy]}))))
    assert got.keys() == want.keys()
    for cid in want:
        a, b = got[cid]["points"], want[cid]["points"]
        assert len(a) == len(b), cid
        assert all(abs(p[0] - q[0]) < 1e-9 and abs(p[1] - q[1]) < 1e-9 for p, q in zip(a, b)), (cid, a, b)


def test_reroute_leaves_untouched_connectors_alone(tmp_path):
    core = rust._load()
    before = _scene(tmp_path, DECISION)
    got = _connectors(json.loads(core.reroute(json.dumps(before), json.dumps({"std": [60, 40]}))))
    old = _connectors(before)
    for cid in ("e0", "e2", "e3"):  # none of them touches `std`
        assert got[cid]["points"] == old[cid]["points"]
    assert got["e1"]["points"] != old["e1"]["points"]


def test_reroute_rejects_an_unknown_shape(tmp_path):
    core = rust._load()
    with pytest.raises(ValueError, match="unknown shape"):
        core.reroute(json.dumps(_scene(tmp_path, DECISION)), json.dumps({"nope": [1, 1]}))

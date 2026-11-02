"""Regenerate rust/spinagram-wasm/tests/golden/: scenes, drawn bodies, op batches and their results.

The drawn body comes from the pure-Python writer (the parity oracle), the patched YAML and source map from the
Rust core through PyO3. Run from the repo root:

    SPINAGRAM_RUST=0 uv run --all-extras python rust/spinagram-wasm/tests/gen_golden.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import warnings
from pathlib import Path

assert os.environ.get("SPINAGRAM_RUST") == "0", "run with SPINAGRAM_RUST=0 so the body is drawn by the Python writer"

from spinagram import edit, rust, scene_json  # noqa: E402
from spinagram.autolayout import apply_layout  # noqa: E402
from spinagram.backends import svg as svg_backend  # noqa: E402
from spinagram.layout import build_scene  # noqa: E402
from spinagram.theme import Theme  # noqa: E402
from spinagram.yaml_io import load  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "golden"
assert svg_backend.COMPENSATED_SUM, "the wasm build assumes the compensated sum of Python 3.12+"

MOVES = {"decision": {"std": [60, 40]}, "software_architecture": {"api": [50, 60]}}
FONT = ROOT / "src/spinagram/fonts/NotoSansMath-Regular.ttf"

CASES = {
    "decision": (ROOT / "examples/decision.yaml", [
        {"op": "move", "id": "std", "x": 1000, "y": 260},
        {"op": "rename", "id": "known", "title": "Seen before?"},
        {"op": "add_node", "id": "extra", "title": "Extra", "x": 100, "y": 600, "w": 200, "h": 100},
        {"op": "connect", "from": "start", "to": "extra", "label": "new"},
        {"op": "disconnect", "from": "tg", "to": "cab"},
        {"op": "delete", "id": "cab"},
    ]),
    "ortho": (ROOT / "rust/spinagram-core/tests/data/reroute/ortho.yaml", [
        {"op": "move", "id": "a", "x": 100, "y": 300},
        {"op": "resize", "id": "o", "w": 140, "h": 90},
        {"op": "delete", "id": "b"},
    ]),
    "software_architecture": (ROOT / "examples/software_architecture.yaml", [
        {"op": "move", "id": "api", "x": 400, "y": 300},
        {"op": "delete", "id": "mongo"},
    ]),
}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    theme = Theme.load(None)
    for name, (src, ops) in CASES.items():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            scene = build_scene(apply_layout(load(src)[0], theme, None), theme)
        writer = svg_backend._Svg(scene)
        writer._draw()
        body = "".join(writer.back) + "".join(writer.mid) + "".join(writer.front)
        # icons are copied next to the golden files and named @GOLDEN@/icons/<file>: the test registers their bytes
        # under that name, so the scene does not depend on this machine's icon cache
        data = scene_json.dumps(scene)
        for path in sorted(set(re.findall(r'"path": "([^"]+)"', data))):
            (OUT / "icons").mkdir(exist_ok=True)
            shutil.copy(path, OUT / "icons" / Path(path).name)
            data = data.replace(f'"path": "{path}"', f'"path": "@GOLDEN@/icons/{Path(path).name}"')
        body_icons = body.count("data:image")
        (OUT / f"{name}.scene.json").write_text(data + "\n", encoding="utf-8")
        (OUT / f"{name}.body.svg").write_text(body, encoding="utf-8")
        print(name, len(data), "bytes of scene,", body_icons, "embedded images", file=sys.stderr)
        if name in MOVES:  # the PyO3 binding's answer; the wasm build must give the same bytes
            out = rust._load().reroute(data, json.dumps(MOVES[name]))
            (OUT / f"{name}.rerouted.scene.json").write_text(out + "\n", encoding="utf-8")
            (OUT / f"{name}.moves.json").write_text(json.dumps(MOVES[name]) + "\n", encoding="utf-8")
        if ops is not None:
            text = src.read_text(encoding="utf-8")
            (OUT / f"{name}.yaml").write_text(text, encoding="utf-8")
            (OUT / f"{name}.ops.json").write_text(json.dumps(ops) + "\n", encoding="utf-8")
            (OUT / f"{name}.patched.yaml").write_text(edit.apply_ops(text, ops), encoding="utf-8")
            (OUT / f"{name}.srcmap.json").write_text(json.dumps(edit.srcmap(text), sort_keys=True) + "\n", encoding="utf-8")
    text = "\u2211 x\u00b2 + \u222b f dx"
    width = rust._load().measure(text, (str(FONT), 18.0, 400), [])
    (OUT / "measure.json").write_text(json.dumps({"text": text, "size": 18.0, "weight": 400, "width": width}) + "\n",
                                      encoding="utf-8")


if __name__ == "__main__":
    main()

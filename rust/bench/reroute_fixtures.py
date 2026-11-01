"""Regenerate rust/spinagram-core/tests/data/reroute/*.scene.json: scenes rendered by the Python engine, before
and after moving a node in the YAML. The Rust `reroute` tests compare their result with these full renders.

    uv run --all-extras python rust/bench/reroute_fixtures.py
"""
from __future__ import annotations

import warnings
from pathlib import Path

from spinagram import scene_json
from spinagram.autolayout import apply_layout
from spinagram.layout import build_scene
from spinagram.theme import Theme
from spinagram.yaml_io import load_yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "rust/spinagram-core/tests/data/reroute"

CASES = {  # name: (source yaml, [(old text, new text)])
    "decision": (ROOT / "examples/decision.yaml", []),
    "decision_std": (ROOT / "examples/decision.yaml", [("at: [900, 220, 360, 130]", "at: [960, 260, 360, 130]")]),
    "decision_known": (ROOT / "examples/decision.yaml", [("at: [520, 260, 300, 220]", "at: [520, 290, 300, 220]")]),
    "ortho": (OUT / "ortho.yaml", []),
    "ortho_b": (OUT / "ortho.yaml", [("at: [500, 100, 120, 60]", "at: [500, 300, 120, 60]")]),
    "ortho_a": (OUT / "ortho.yaml", [("at: [100, 100, 120, 60]", "at: [100, 300, 120, 60]")]),
}


def main() -> None:
    theme = Theme.load(None)
    tmp = OUT / "_tmp.yaml"
    for name, (src, edits) in CASES.items():
        text = src.read_text(encoding="utf-8")
        for old, new in edits:
            assert text.count(old) == 1, (name, old)
            text = text.replace(old, new)
        tmp.write_text(text, encoding="utf-8")
        d = load_yaml(tmp)[0]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            scene = build_scene(apply_layout(d, theme, None), theme)
        (OUT / f"{name}.scene.json").write_text(scene_json.dumps(scene).replace(str(ROOT), "@ROOT@") + "\n", encoding="utf-8")
    tmp.unlink()


if __name__ == "__main__":
    main()

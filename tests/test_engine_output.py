"""Output naming, version pinning and the SVG content hash (layout-engine OUT-01..04)."""
import pytest

from spinagram import Diagram, render
from spinagram.cli import main

TWO = ("- id: R01\n  title: Runners network\n  nodes: [{id: a, title: A, x: 100, y: 100, w: 200, h: 90}]\n"
       "- id: R02\n  title: Egress path\n  output: egress\n  nodes: [{id: a, title: A, x: 100, y: 100, w: 200, h: 90}]\n")
ONE = "id: G01\ntitle: Git service\nnodes: [{id: a, title: A, x: 100, y: 100, w: 200, h: 90}]\n"

NAMES = [
    # id, spec text, --name-from, expected svg names
    ("slug-default", TWO, None, {"R01-runners-network.svg", "egress.svg"}),
    ("from-id", TWO, "id", {"R01.svg", "egress.svg"}),
    ("from-file-two-diagrams", TWO, "file", {"runners-R01.svg", "egress.svg"}),
    ("from-file-one-diagram", ONE, "file", {"runners.svg"}),
]


@pytest.mark.parametrize("text,name_from,names", [n[1:] for n in NAMES], ids=[n[0] for n in NAMES])
def test_render_names(tmp_path, monkeypatch, capsys, text, name_from, names):  # OUT-01, OUT-02
    (tmp_path / "runners.yaml").write_text(text)
    monkeypatch.chdir(tmp_path)
    args = ["render", "-f", "svg", "--no-gallery", "-o", "out", "runners.yaml"]
    if name_from:
        args[1:1] = ["--name-from", name_from]
    assert main(args) == 0
    capsys.readouterr()
    assert {p.name for p in (tmp_path / "out").glob("*.svg")} == names


@pytest.mark.parametrize("fmt", ["svg", "png"])
def test_python_output_name(tmp_path, fmt):  # OUT-01 for each format
    if fmt == "png":
        pytest.importorskip("playwright")
    d = Diagram("R01", "Runners network", output="runners-network")
    d.box("A", x=100, y=100, w=200, h=90)
    assert [p.name for p in render([d], tmp_path, formats=[fmt])] == [f"runners-network.{fmt}"]


def test_unknown_name_from_raises():
    from spinagram.api import scenes
    with pytest.raises(ValueError, match="name_from 'title'"):
        scenes([Diagram("A", "B")], name_from="title")

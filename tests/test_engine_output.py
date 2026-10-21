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


# requires (OUT-03) ------------------------------------------------------------------------------------------
from spinagram.engine.version import satisfies  # noqa: E402

SPECS = [
    ("0.4.2", ">=0.4,<0.5", True), ("0.5.0", ">=0.4,<0.5", False), ("0.3.9", ">=0.4", False),
    ("0.4.0", "==0.4.*", True), ("0.5.1", "==0.4.*", False), ("0.4.7", "~=0.4.1", True),
    ("0.5.0", "~=0.4.1", False), ("1.0.0", "!=1.0.0", False), ("0.1.0", "<=0.1", True),
]


@pytest.mark.parametrize("version,spec,ok", SPECS, ids=[f"{v}-{s}" for v, s, _ in SPECS])
def test_version_specifiers(version, spec, ok):
    assert satisfies(version, spec) is ok


def test_bad_clause_raises():
    with pytest.raises(ValueError, match="clause '0.4'"):
        satisfies("0.4.0", "0.4")


@pytest.mark.parametrize("front", ["python", "yaml"])
@pytest.mark.parametrize("requires,flagged", [(">=0.0.1", False), (">=99", True)], ids=["met", "unmet"])
def test_requires_warns_and_reports(front, requires, flagged):
    import warnings

    from spinagram import Theme, build_scene
    from spinagram.engine.version import installed
    from spinagram.qa import check
    from spinagram.yaml_io import from_dict
    if front == "python":
        d = Diagram("V", "Version", requires=requires)
    else:
        d = from_dict({"id": "V", "title": "Version", "requires": requires})
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        sc = build_scene(d, Theme.load("default"))
    issues = [i for i in check(sc) if i.kind == "version-mismatch"]
    if flagged:
        assert any(f"written for spinagram {requires}" in str(x.message) for x in w)
        assert [i.detail for i in issues] == [f"spec requires spinagram {requires}; installed {installed()}"]
    else:
        assert issues == [] and not w

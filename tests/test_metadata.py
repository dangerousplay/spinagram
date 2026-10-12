"""Diagram catalog metadata (spec: .specs/features/diagram-catalog/spec.md)."""
from __future__ import annotations

import pytest

from spinagram import Diagram


# META-01, META-07: declared category and normalised tags --------------------------------------
def test_python_metadata_is_normalised():
    d = Diagram("N1", "Hub", category="Networking", tags=["aws", " Hub ", "AWS", ""])
    assert d.category == "Networking"
    assert d.tags == ["aws", "hub"]


def test_tags_are_sorted_and_deduplicated():
    assert Diagram("N2", "t", tags=["zeta", "Alpha", "alpha "]).tags == ["alpha", "zeta"]


def test_metadata_defaults_are_empty():
    d = Diagram("N3", "t")
    assert d.category is None
    assert d.tags == []


# META-04: a single string is one tag -----------------------------------------------------------
def test_single_string_tag():
    assert Diagram("N4", "t", tags=" Kubernetes ").tags == ["kubernetes"]


# META-03: wrong types fail with the diagram id and the key --------------------------------------
@pytest.mark.parametrize("tags", [5, ["ok", 3], {"a": 1}])
def test_invalid_tags_name_id_and_key(tags):
    with pytest.raises(ValueError, match=r"N5: tags must be a list of strings"):
        Diagram("N5", "t", tags=tags)


@pytest.mark.parametrize("category", [["x"], 3])
def test_invalid_category_names_id_and_key(category):
    with pytest.raises(ValueError, match=r"N6: category must be a string"):
        Diagram("N6", "t", category=category)


# META-02, META-03: YAML keys ---------------------------------------------------------------------
YAML = "id: Y1\ntitle: Hub\n{meta}nodes:\n  - {{id: a, title: A}}\n"


def _yaml(tmp_path, meta: str, name="spec.yaml"):
    from spinagram.yaml_io import load

    (tmp_path / name).write_text(YAML.format(meta=meta))
    return load(tmp_path / name)[0]


def test_yaml_metadata_matches_python(tmp_path):
    d = _yaml(tmp_path, "category: Networking\ntags: [aws, ' Hub ', AWS]\n")
    assert d.category == "Networking"
    assert d.tags == ["aws", "hub"]


def test_yaml_single_string_tag(tmp_path):
    assert _yaml(tmp_path, "tags: Kubernetes\n").tags == ["kubernetes"]


@pytest.mark.parametrize("meta, key", [("tags: 5\n", "tags"), ("tags: [ok, 3]\n", "tags"),
                                       ("category: [x]\n", "category")])
def test_yaml_invalid_metadata_names_id_and_key(tmp_path, meta, key):
    with pytest.raises(ValueError, match=rf"Y1: {key} must be a"):
        _yaml(tmp_path, meta)


def test_frozen_layout_keeps_metadata(tmp_path):
    from spinagram.yaml_io import dump

    out = dump(_yaml(tmp_path, "category: Networking\ntags: [aws]\n"))
    assert (out["category"], out["tags"]) == ("Networking", ["aws"])


# META-05, META-06: folder defaults ---------------------------------------------------------------
PY = ("from spinagram import Diagram\n"
      "diagram = Diagram('P1', 'Py', {args})\n"
      "diagram.box('A')\n")


def _folder(tmp_path, defaults: str):
    (tmp_path / "_defaults.yaml").write_text(defaults)


def test_folder_category_fills_unset_yaml_and_python(tmp_path):
    from spinagram.yaml_io import load

    _folder(tmp_path, "category: Platform\n")
    (tmp_path / "a.yaml").write_text(YAML.format(meta=""))
    (tmp_path / "b.py").write_text(PY.format(args=""))
    assert [d.category for d in load(tmp_path)] == ["Platform", "Platform"]


def test_spec_category_beats_folder_category(tmp_path):
    from spinagram.yaml_io import load

    _folder(tmp_path, "category: Platform\n")
    (tmp_path / "a.yaml").write_text(YAML.format(meta="category: Networking\n"))
    (tmp_path / "b.py").write_text(PY.format(args="category='Data'"))
    assert [d.category for d in load(tmp_path)] == ["Networking", "Data"]


def test_folder_tags_union_with_spec_tags(tmp_path):
    from spinagram.yaml_io import load

    _folder(tmp_path, "tags: [Team-A, shared]\n")
    (tmp_path / "a.yaml").write_text(YAML.format(meta="tags: [aws, shared]\n"))
    (tmp_path / "b.py").write_text(PY.format(args="tags=['gcp']"))
    (tmp_path / "c.yaml").write_text(YAML.format(meta="").replace("Y1", "Y2"))
    assert [d.tags for d in load(tmp_path)] == [["aws", "shared", "team-a"], ["gcp", "shared", "team-a"],
                                                ["shared", "team-a"]]

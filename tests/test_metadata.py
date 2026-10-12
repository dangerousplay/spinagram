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
                                       ("tags: 0\n", "tags"), ("tags: false\n", "tags"), ("tags: {}\n", "tags"),
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


@pytest.mark.parametrize("bad", ["0", "false", "{}"])
def test_invalid_folder_tags_fail_for_yaml_and_python(tmp_path, bad):
    from spinagram.yaml_io import load

    _folder(tmp_path, f"tags: {bad}\n")
    (tmp_path / "a.yaml").write_text(YAML.format(meta="tags: [aws]\n"))
    with pytest.raises(ValueError, match="Y1: tags must be a list of strings"):
        load(tmp_path / "a.yaml")
    (tmp_path / "a.yaml").unlink()
    (tmp_path / "b.py").write_text(PY.format(args=""))
    with pytest.raises(ValueError, match="P1: tags must be a list of strings"):
        load(tmp_path / "b.py")


def test_folder_tags_union_with_spec_tags(tmp_path):
    from spinagram.yaml_io import load

    _folder(tmp_path, "tags: [Team-A, shared]\n")
    (tmp_path / "a.yaml").write_text(YAML.format(meta="tags: [aws, shared]\n"))
    (tmp_path / "b.py").write_text(PY.format(args="tags=['gcp']"))
    (tmp_path / "c.yaml").write_text(YAML.format(meta="").replace("Y1", "Y2"))
    assert [d.tags for d in load(tmp_path)] == [["aws", "shared", "team-a"], ["gcp", "shared", "team-a"],
                                                ["shared", "team-a"]]


# META-08..12: effective tags and category ---------------------------------------------------------
def test_provider_tags_from_node_group_and_zone_icons():
    from spinagram.metadata import effective_tags

    d = Diagram("I1", "t", tags=["team"])
    d.box("A", icon="gcp:gke")
    d.box("B", icon="k8s:pod")
    with d.group("G", icon="azure:aks"):
        d.box("C", icon="terrastruct:python")
    d.zone("Z", x=0, y=0, w=10, h=10, icon="oci:vm")
    d.box("D", icon="openstack:nova")
    d.box("E", icon="aws:s3")
    d.box("F", icon="icons/local.svg")
    assert effective_tags(d) == ["aws", "azure", "gcp", "kubernetes", "oci", "openstack", "team"]


def test_aws_group_and_zone_styles_count_as_aws():
    from spinagram.metadata import effective_tags

    d = Diagram("I2", "t")
    with d.group("VPC", style="aws-vpc"):
        d.box("A")
    assert effective_tags(d) == ["aws"]
    z = Diagram("I3", "t")
    z.zone("AZ", x=0, y=0, w=10, h=10, color="aws-az")
    assert effective_tags(z) == ["aws"]


def test_dominant_provider_is_the_category():
    from spinagram.metadata import effective_category

    d = Diagram("I4", "t")
    d.box("User", icon="k8s:user")
    for name in ("gke", "cloud-sql", "pubsub"):
        d.box(name, icon=f"gcp:{name}")
    assert effective_category(d) == "Google Cloud"


def test_category_tie_goes_to_the_alphabetically_first_tag():
    from spinagram.metadata import effective_category

    d = Diagram("I5", "t")
    d.box("A", icon="k8s:pod")
    d.box("B", icon="gcp:gke")
    assert effective_category(d) == "Google Cloud"  # "gcp" < "kubernetes"


def test_declared_category_wins_over_icons():
    from spinagram.metadata import effective_category

    d = Diagram("I6", "t", category="Networking")
    d.box("A", icon="aws:s3")
    assert effective_category(d) == "Networking"


def test_no_category_and_no_provider_icons_is_empty():
    from spinagram.metadata import effective_category, effective_tags

    d = Diagram("I7", "t")
    d.box("A", icon="terrastruct:python")
    assert effective_category(d) == ""
    assert effective_tags(d) == []


def test_showcase_groups_by_provider_without_metadata():
    from pathlib import Path

    from spinagram.metadata import effective_category
    from spinagram.yaml_io import load

    showcase = Path(__file__).resolve().parents[1] / "examples" / "showcase"
    got = {d.id: effective_category(d) for d in load(showcase)}
    assert got == {"AWS01": "AWS", "AWS02": "AWS", "GCP01": "Google Cloud",
                   "K8S01": "Kubernetes", "K8S02": "Kubernetes", "NOTE01": "Decisions",  # NOTE01 declares one
                   "HOME01": "Self-hosted", "NET01": "Network", "NET02": "Network"}


# META-28..31: CLI filters -------------------------------------------------------------------------
SHOWCASE = str(__import__("pathlib").Path(__file__).resolve().parents[1] / "examples" / "showcase")


def _checked(capsys, *flags) -> str:
    from spinagram import cli

    assert cli.main(["check", SHOWCASE, *flags]) == 0
    return capsys.readouterr().out.strip().splitlines()[-1]


def test_cli_tag_filter(capsys):
    # K8S01, K8S02 and GCP01 (which uses k8s:user) all carry the inferred kubernetes tag (META-08)
    assert _checked(capsys, "--tag", "kubernetes").startswith("3 diagram(s)")


def test_cli_repeated_tags_must_all_match(capsys):
    from spinagram import cli

    assert _checked(capsys, "--tag", "KUBERNETES", "--tag", "gcp").startswith("1 diagram(s)")  # GCP01 uses k8s:user
    with pytest.raises(SystemExit, match="no diagrams found"):
        cli.main(["check", SHOWCASE, "--tag", "kubernetes", "--tag", "azure"])


def test_cli_category_filter(capsys):
    assert _checked(capsys, "--category", "aws").startswith("2 diagram(s)")
    assert _checked(capsys, "--category", "google cloud").startswith("1 diagram(s)")


def test_cli_filters_combine_with_only(capsys):
    assert _checked(capsys, "--only", "K8S01", "AWS01", "--tag", "kubernetes").startswith("1 diagram(s)")
    # GCP01 carries the kubernetes tag but its category is Google Cloud: tag and category must both hold
    assert _checked(capsys, "--tag", "kubernetes", "--category", "kubernetes").startswith("2 diagram(s)")


def test_cli_no_match_exits(capsys):
    from spinagram import cli

    with pytest.raises(SystemExit, match="no diagrams found"):
        cli.main(["check", SHOWCASE, "--tag", "aws", "--category", "kubernetes"])


def test_cli_filters_on_render_facts_layout(tmp_path, capsys):
    from spinagram import cli

    assert cli.main(["render", SHOWCASE, "--tag", "gcp", "--category", "google cloud", "-f", "svg",
                     "-o", str(tmp_path), "--no-gallery"]) == 0
    assert sorted(p.name for p in tmp_path.glob("*.svg")) == ["GCP01-global-web-application-on-google-cloud.svg"]
    assert cli.main(["facts", SHOWCASE, "--category", "AWS"]) == 0
    assert cli.main(["layout", SHOWCASE, "--tag", "kubernetes", "--only", "K8S02"]) == 0
    assert "id: K8S02" in capsys.readouterr().out

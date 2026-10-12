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

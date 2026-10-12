"""Legend placement and styling from CSS (spec: .specs/features/legend-css/spec.md)."""
from __future__ import annotations

import pytest

from spinagram import Diagram
from spinagram.theme import Theme


def _diagram(css: str = "", **legend):
    d = Diagram("LC1", "Legend CSS", layout={"engine": "flex", "direction": "right"})
    a = d.box("A", class_="web")
    b = d.box("B", class_="db")
    d.edge(a, b, class_="async")
    d.add_legend(**legend)
    d.css = css
    return d


# T1 · properties --------------------------------------------------------------------------------------
def test_legend_properties_are_computed():  # LCSS-07..11, LCSS-13
    from spinagram import css

    d = _diagram("legend { placement: left; width: 300px; columns: 3; gap: 20; padding: 30; swatch-width: 60;"
                 " swatch-height: 20; display: none }")
    comp, warnings = css.styles(d, Theme.load("default"))
    assert not warnings
    assert comp["legend"][""] == {"placement": "left", "width": 300, "columns": 3, "gap": 20, "padding": 30,
                                  "swatch-width": 60, "swatch-height": 20, "display": "none"}


@pytest.mark.parametrize("decl, words", [
    ("placement: middle", ["placement", "bottom", "left", "right", "top"]),      # LCSS-05
    ("columns: 0", ["columns", "positive integer"]),                             # edge case
    ("columns: 2.5", ["columns", "positive integer"]),
    ("display: flex", ["display", "block", "none"]),
])
def test_invalid_legend_values_warn(decl, words):
    from spinagram import css

    comp, warnings = css.styles(_diagram(f"legend {{ {decl} }}"), Theme.load("default"))
    assert decl.split(":")[0] not in comp["legend"].get("", {})
    assert len(warnings) == 1 and all(w in warnings[0] for w in words), warnings


# T2 · explicit position stays optional ----------------------------------------------------------------------
def test_position_defaults_to_none_and_explicit_values_are_kept(tmp_path):  # LCSS-04
    from spinagram.yaml_io import dump, from_dict

    assert _diagram().annotations.legend.position is None
    for side in ("right", "left", "top", "bottom"):
        assert _diagram(position=side).annotations.legend.position == side
    with pytest.raises(ValueError, match="right, bottom, left, top"):
        _diagram(position="middle")
    out = dump(_diagram())
    assert "position" not in out["annotations"]["legend"]
    assert from_dict(dump(_diagram(position="top"))).annotations.legend.position == "top"

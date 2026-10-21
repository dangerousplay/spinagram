"""Zones: model fields, outlines, CSS, headers (layout-engine ZON-01..13)."""
import pytest
import yaml

from spinagram import Diagram
from spinagram.yaml_io import dump, from_dict

ZONE_FIELD_SCENARIOS = [
    ("id", {"id": "net-a"}),
    ("dash-word", {"dash": "dotted"}),
    ("dash-list", {"dash": [4, 2]}),
    ("stroke", {"stroke": "primary", "stroke_width": 1.5}),
    ("fill-none", {"fill": "none"}),
    ("header", {"header": {"padding": 14, "strip": "primary"}}),
    ("icon-chips", {"icon": ["logos:vmware", "logos:redhat"]}),
    ("fit", {"fit": "children", "padding": 30, "equalize": "siblings"}),
    ("meaning", {"meaning": "network"}),
    ("class", {"cls": "az"}),
]


@pytest.mark.parametrize("kw", [k for _, k in ZONE_FIELD_SCENARIOS], ids=[i for i, _ in ZONE_FIELD_SCENARIOS])
def test_zone_fields_python_and_yaml_parity(kw):
    d = Diagram("Z", "Zones")
    z = d.zone("Net", x=10, y=20, w=300, h=200, **kw)
    for k, v in kw.items():
        assert getattr(z, k) == v
    ykw = {("class" if k == "cls" else k): v for k, v in kw.items()}
    y = from_dict({"id": "Z", "title": "Zones", "zones": [{"label": "Net", "x": 10, "y": 20, "w": 300, "h": 200, **ykw}]})
    assert y.zones[0] == z


def test_zone_ids_default_to_index_and_must_be_unique():
    d = Diagram("Z", "Zones")
    a = d.zone("A", x=0, y=0, w=10, h=10)
    b = d.zone("B", x=0, y=0, w=10, h=10, id="net")
    c = d.zone("C", x=0, y=0, w=10, h=10)
    assert (a.id, b.id, c.id) == ("z0", "net", "z2")
    with pytest.raises(ValueError, match="duplicate zone id 'net'"):
        d.zone("D", x=0, y=0, w=10, h=10, id="net")


@pytest.mark.parametrize("kw", [k for _, k in ZONE_FIELD_SCENARIOS], ids=[i for i, _ in ZONE_FIELD_SCENARIOS])
def test_zone_fields_survive_yaml_dump(kw):
    d = Diagram("Z", "Zones")
    z = d.zone("Net", x=10, y=20, w=300, h=200, **kw)
    again = from_dict(yaml.safe_load(yaml.safe_dump(dump(d))))
    assert again.zones[0] == z


# outlines (ZON-09, ZON-10) -----------------------------------------------------------------------------------
from spinagram import Theme, build_scene  # noqa: E402
from spinagram.backends.svg import to_svg  # noqa: E402
from spinagram.scene import Shape  # noqa: E402

THEME = Theme.load("default")
DASH_VALUES = [
    ("solid", "solid", None, None),
    ("dashed", "dashed", [8, 6], None),
    ("dotted", "dotted", [2, 6], "round"),
    ("custom", [4, 2, 1, 2], [4, 2, 1, 2], None),
]


def _zone_shape(theme=THEME, **kw):
    d = Diagram("Z", "Zones")
    d.zone("Net", x=10, y=20, w=300, h=200, **kw)
    sc = build_scene(d, theme)
    return next(i for i in sc.items if isinstance(i, Shape) and i.id == "z0"), to_svg(sc)


def _style_theme(tmp_path, style):
    import yaml
    (tmp_path / "theme.yaml").write_text("extends: default\n" + yaml.safe_dump(
        {"styles": {"zone": {"net": {"fill": "none", "label": "text-muted", "stroke": "primary", **style}}}}))
    return Theme.load(tmp_path)


@pytest.mark.parametrize("source", ["zone", "style"])
@pytest.mark.parametrize("value,dash,cap", [d[1:] for d in DASH_VALUES], ids=[d[0] for d in DASH_VALUES])
def test_zone_dash_values(tmp_path, source, value, dash, cap):
    if source == "zone":
        s, svg = _zone_shape(dash=value, stroke="primary")
    else:
        s, svg = _zone_shape(_style_theme(tmp_path, {"dash": value}), color="net")
    assert s.dash == dash and s.cap == cap and s.dashed == (dash is not None)
    if dash:
        assert f'stroke-dasharray="{" ".join(f"{v:g}" for v in dash)}"' in svg
    assert ('stroke-linecap="round"' in svg) == (cap == "round")


def test_zone_dash_beats_style_dash(tmp_path):
    s, _ = _zone_shape(_style_theme(tmp_path, {"dash": "dotted"}), color="net", dash="dashed")
    assert (s.dash, s.cap) == ([8, 6], None)


def test_legacy_dashed_style_keeps_default_pattern(tmp_path):
    s, svg = _zone_shape(_style_theme(tmp_path, {"dashed": True}), color="net")
    assert s.dashed and s.dash is None and 'stroke-dasharray="10 7"' in svg


STROKE_FILL = [
    ("stroke-token", {"stroke": "primary"}, {"stroke": THEME.color("primary"), "stroke_width": 2}),
    ("stroke-width", {"stroke": "#112233", "stroke_width": 1.5}, {"stroke": "#112233", "stroke_width": 1.5}),
    ("fill-token", {"fill": "primary-soft"}, {"fill": THEME.color("primary-soft")}),
    ("fill-none", {"fill": "none"}, {"fill": None, "opacity": 1.0}),
]


@pytest.mark.parametrize("kw,expected", [s[1:] for s in STROKE_FILL], ids=[s[0] for s in STROKE_FILL])
def test_zone_stroke_and_fill(kw, expected):
    s, svg = _zone_shape(**kw)
    assert {k: getattr(s, k) for k in expected} == expected
    if kw.get("fill") == "none":
        assert '<rect x="10.0" y="20.0" width="300.0" height="200.0" rx="26" fill="none"' in svg


def test_unknown_dash_word_raises():
    with pytest.raises(ValueError, match="zone dash 'wavy'"):
        _zone_shape(dash="wavy")

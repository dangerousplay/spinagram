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

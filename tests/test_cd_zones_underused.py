"""Nested zones count as content in ``zone-underused`` (ZUN-01..03).

Every ratio is computed by hand from the default theme's zone header: 40.8 px tall at the zone's top, so a zone's
content area is ``w × (h − 40.8)``. An outer zone 1600 × 800 has a content area of 1600 × 759.2 = 1,214,720 px².
"""
from __future__ import annotations

import pytest

from spinagram import Diagram, Theme, build_scene
from spinagram.qa import check

DEFAULT = Theme.load("default")
DETAIL = "content fills {} of the zone (< 35%); shrink it, use fit: children, or drop equalize"


@pytest.fixture(scope="module")
def every_ratio(tmp_path_factory):
    """A theme whose limit (100 %) reports every zone with content, so each fill ratio is visible."""
    root = tmp_path_factory.mktemp("all")
    (root / "theme.yaml").write_text("extends: default\ndefaults: {check: {underused: 1.0}}\n")
    return Theme.load(root)


def _account_region_vpc(declared: bool):
    def make():
        d = Diagram("Z", "Nest")
        if declared:
            with d.zone("Account", x=100, y=100, w=1600, h=800):
                with d.zone("Region", x=140, y=180, w=1520, h=680):
                    with d.zone("VPC", x=180, y=260, w=1440, h=560):
                        d.box("A", id="a", x=220, y=340, w=600, h=300)
                        d.box("B", id="b", x=980, y=340, w=600, h=300)
        else:
            d.zone("Account", x=100, y=100, w=1600, h=800)
            d.zone("Region", x=140, y=180, w=1520, h=680)
            d.zone("VPC", x=180, y=260, w=1440, h=560)
            d.box("A", id="a", x=220, y=340, w=600, h=300)
            d.box("B", id="b", x=980, y=340, w=600, h=300)
        return d
    return make


def _small_child(declared: bool):
    def make():
        d = Diagram("Z", "Small")
        if declared:
            with d.zone("Account", x=100, y=100, w=1600, h=800):
                with d.zone("Tiny", x=140, y=180, w=400, h=300):
                    d.box("A", id="a", x=160, y=240, w=360, h=200)
        else:
            d.zone("Account", x=100, y=100, w=1600, h=800)
            d.zone("Tiny", x=140, y=180, w=400, h=300)
            d.box("A", id="a", x=160, y=240, w=360, h=200)
        return d
    return make


def _partial_node():
    d = Diagram("Z", "Partial")
    with d.zone("Account", x=100, y=100, w=1600, h=800):
        d.zone("Region", x=140, y=180, w=800, h=400)
        d.box("A", id="a", x=800, y=300, w=400, h=200)                     # 140 × 200 = 35 % inside Region
    return d


def _node_inside_child():
    d = Diagram("Z", "Inside")
    with d.zone("Account", x=100, y=100, w=1600, h=800):
        d.zone("Region", x=140, y=180, w=800, h=400)
        d.box("A", id="a", x=200, y=300, w=200, h=100)                     # an Account child drawn in Region
    return d


def _node_mostly_inside_child():
    d = Diagram("Z", "Mostly inside")
    with d.zone("Account", x=100, y=100, w=1600, h=800):
        d.zone("Region", x=140, y=180, w=800, h=400)
        d.box("A", id="a", x=700, y=300, w=400, h=200)                     # 240 × 200 = 60 % inside Region
    return d


def _grandchild_sticking_out():
    d = Diagram("Z", "Grandchild")
    d.zone("Account", x=100, y=100, w=1600, h=800)
    d.zone("Region", x=140, y=180, w=800, h=400)
    d.zone("VPC", x=600, y=300, w=500, h=200)                              # 340 × 200 = 68 % inside Region
    return d


def _child_under_header():
    d = Diagram("Z", "Header")
    with d.zone("Account", x=100, y=100, w=1600, h=800):
        d.zone("Region", x=100, y=100, w=800, h=400)                       # covers Account's header
    return d


FIXTURES = [  # (id, make, fill ratio per zone with content (limit 100 %), issues at the default 35 % limit)
    # Account: Region 1520 × 680 = 1,033,600 / 1,214,720 = 85.1 %. Region: VPC 1440 × 560 = 806,400 over
    # 1520 × 639.2 = 971,584 → 83.0 %. VPC: two boxes 2 × 600 × 300 = 360,000 over 1440 × 519.2 = 747,648 → 48.2 %.
    ("account-region-vpc-declared", _account_region_vpc(True), {"z0": "85%", "z1": "83%", "z2": "48%"}, []),
    ("account-region-vpc-geometric", _account_region_vpc(False), {"z0": "85%", "z1": "83%", "z2": "48%"}, []),
    # Account: Tiny 400 × 300 = 120,000 / 1,214,720 = 9.9 %. Tiny: box 360 × 200 = 72,000 over 400 × 259.2 =
    # 103,680 → 69.4 %.
    ("small-child-declared", _small_child(True), {"z0": "10%", "z1": "69%"}, [("z0", DETAIL.format("10%"))]),
    ("small-child-geometric", _small_child(False), {"z0": "10%", "z1": "69%"}, [("z0", DETAIL.format("10%"))]),
    # Account: Region 320,000 + box 80,000 − their overlap 140 × 200 = 28,000 → 372,000 / 1,214,720 = 30.6 %
    # (33 % if the overlap were counted twice). Region: the box is not mostly inside → no content, not measured.
    ("overlap-counted-once", _partial_node, {"z0": "31%"}, [("z0", DETAIL.format("31%"))]),
    # Account: the box lies inside Region → 320,000 / 1,214,720 = 26.3 % (28 % if counted again). Region: box
    # 200 × 100 = 20,000 over 800 × 359.2 = 287,360 → 7.0 %.
    ("node-inside-child", _node_inside_child, {"z0": "26%", "z1": "7%"},
     [("z0", DETAIL.format("26%")), ("z1", DETAIL.format("7%"))]),
    # Account: the box is mostly (60 %) inside Region, so it is Region's content, not Account's: 320,000 /
    # 1,214,720 = 26.3 % (Region ∪ box = 320,000 + 80,000 − 48,000 = 352,000 → 29 % if it were counted). Region:
    # the box clipped to Region's content (x 140 → 940, y 220.8 → 580): 240 × 200 = 48,000 over 800 × 359.2 =
    # 287,360 → 16.7 %.
    ("node-mostly-inside-child", _node_mostly_inside_child, {"z0": "26%", "z1": "17%"},
     [("z0", DETAIL.format("26%")), ("z1", DETAIL.format("17%"))]),
    # Account: VPC is mostly inside Region (68 %), so it is not a direct child of Account: Region alone 320,000 /
    # 1,214,720 = 26.3 % (Region ∪ VPC = 320,000 + 100,000 − 68,000 = 352,000 → 29 % if VPC were a child too).
    # Region: VPC clipped to Region's content: 340 × 200 = 68,000 / 287,360 = 23.7 %. VPC: no content.
    ("grandchild-sticking-out", _grandchild_sticking_out, {"z0": "26%", "z1": "24%"},
     [("z0", DETAIL.format("26%")), ("z1", DETAIL.format("24%"))]),
    # Account: Region clipped to the content area below the header: 800 × (500 − 140.8) = 287,360 → 23.7 %
    # (26 % unclipped).
    ("child-clipped-to-content", _child_under_header, {"z0": "24%"}, [("z0", DETAIL.format("24%"))]),
]


def _underused(d, theme):
    return [(i.item, i.detail) for i in check(build_scene(d, theme)) if i.kind == "zone-underused"]


@pytest.mark.parametrize("make,ratios,issues", [f[1:] for f in FIXTURES], ids=[f[0] for f in FIXTURES])
def test_fill_ratio_counts_child_zones(every_ratio, make, ratios, issues):
    got = {item: detail.split()[2] for item, detail in _underused(make(), every_ratio)}
    assert got == ratios


@pytest.mark.parametrize("make,ratios,issues", [f[1:] for f in FIXTURES], ids=[f[0] for f in FIXTURES])
def test_underused_issues_at_default_limit(make, ratios, issues):
    assert _underused(make(), DEFAULT) == issues

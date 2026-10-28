"""Zone bands (BND-01): a vertical band gives the zone its y/h, and x/w default to the safe width."""
import pytest

from spinagram import Diagram, Theme, build_scene
from spinagram.scene import Shape

THEME = Theme.load("default")  # canvas 1920 x 1080, margin 80


def _theme(tmp_path, margin):
    if margin == 80:
        return THEME
    (tmp_path / "theme.yaml").write_text(f"extends: default\ncanvas: {{margin: {margin}}}\n")
    return Theme.load(tmp_path)


def _zone_rect(d, theme, zid="z0"):
    z = next(i for i in build_scene(d, theme).items if isinstance(i, Shape) and i.id == zid)
    return (z.x, z.y, z.w, z.h)


BAND_SCENARIOS = [  # (id, band, explicit x/w, margin, expected rect) — rect by hand: x = m, w = 1920 - 2m
    ("band-m80", (330, 500), {}, 80, (80, 330, 1760, 170)),
    ("band-m40", (330, 500), {}, 40, (40, 330, 1840, 170)),
    ("band-top-m80", (0, 120), {}, 80, (80, 0, 1760, 120)),
    ("band-explicit-xw-m80", (330, 500), {"x": 200, "w": 600}, 80, (200, 330, 600, 170)),
    ("band-explicit-xw-m40", (600, 900), {"x": 960, "w": 880}, 40, (960, 600, 880, 300)),
    ("band-explicit-x-only-m40", (330, 500), {"x": 300}, 40, (40, 330, 1840, 170)),  # x without w: safe width
]


@pytest.mark.parametrize("band,xw,margin,expected", [s[1:] for s in BAND_SCENARIOS],
                         ids=[s[0] for s in BAND_SCENARIOS])
def test_band_sets_zone_rect(tmp_path, band, xw, margin, expected):
    d = Diagram("B", "Bands")
    d.zone("Secrets Manager", band=band, **xw)
    assert _zone_rect(d, _theme(tmp_path, margin)) == pytest.approx(expected)


def test_band_does_not_mutate_the_spec():
    d = Diagram("B", "Bands")
    z = d.zone("Secrets Manager", band=(330, 500))
    build_scene(d, THEME)
    assert (z.x, z.y, z.w, z.h) == (0, 0, 0, 0)


def test_band_with_nodes_inside():  # hand-placed boxes keep their place; the zone gets its band geometry
    d = Diagram("B", "Bands")
    with d.zone("VPC", band=(200, 600)):
        d.box("A", id="a", x=300, y=300, w=200, h=100)
    sc = build_scene(d, THEME)
    by = {i.id: i for i in sc.items if isinstance(i, Shape)}
    assert (by["z0"].x, by["z0"].y, by["z0"].w, by["z0"].h) == (80, 200, 1760, 400)
    assert (by["a"].x, by["a"].y) == (300, 300)


def test_band_with_fit_children_raises():
    d = Diagram("B", "Bands")
    with d.zone("VPC", id="vpc", band=(200, 600), fit="children"):
        d.box("A", id="a", x=300, y=300, w=200, h=100)
    with pytest.raises(ValueError, match=r"^B: zone 'vpc' has both band and fit='children'; use one$"):
        build_scene(d, THEME)

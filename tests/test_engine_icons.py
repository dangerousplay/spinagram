"""Icons: aspect ratio, variants, badges, fallback chains, report (layout-engine ICN-01..13)."""
import pytest

from spinagram import Diagram, Theme, build_scene
from spinagram.backends.svg import to_svg
from spinagram.engine.icons import aspect, fit
from spinagram.scene import Shape

THEME = Theme.load("default")


def _svg(tmp_path, name, attrs):
    p = tmp_path / f"{name}.svg"
    p.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" {attrs}><rect width="1" height="1"/></svg>')
    return p


ASPECTS = [
    ("viewbox-wordmark", 'viewBox="0 0 400 100"', 4.0),
    ("viewbox-square", 'viewBox="0 0 24 24"', 1.0),
    ("viewbox-tall", 'viewBox="0 0 100 400"', 0.25),
    ("viewbox-commas", 'viewBox="0,0,300,100"', 3.0),
    ("width-height", 'width="200" height="50"', 4.0),
    ("unknown", "", 1.0),
]


@pytest.mark.parametrize("attrs,ratio", [a[1:] for a in ASPECTS], ids=[a[0] for a in ASPECTS])
def test_aspect_from_svg(tmp_path, attrs, ratio):  # ICN-01
    assert aspect(_svg(tmp_path, "i", attrs)) == pytest.approx(ratio)


@pytest.mark.parametrize("size,ratio", [((300, 100), 3.0), ((64, 64), 1.0)], ids=["wide-png", "square-png"])
def test_aspect_from_raster(tmp_path, size, ratio):  # ICN-01
    from PIL import Image
    p = tmp_path / "i.png"
    Image.new("RGB", size).save(p)
    assert aspect(p) == pytest.approx(ratio)


FITS = [
    # id, viewBox, height, max_width, expected (w, h)
    ("square", "0 0 10 10", 40, None, (40, 40)),
    ("wordmark-4to1", "0 0 400 100", 40, None, (160, 40)),
    ("wordmark-8to1-capped", "0 0 800 100", 40, None, (160, 20)),
    ("explicit-max-width", "0 0 400 100", 40, 100, (100, 25)),
    ("tall", "0 0 100 400", 40, None, (10, 40)),
]


@pytest.mark.parametrize("vb,height,max_w,expected", [f[1:] for f in FITS], ids=[f[0] for f in FITS])
def test_fit_by_height_with_max_width(tmp_path, vb, height, max_w, expected):  # ICN-02
    assert fit(_svg(tmp_path, "i", f'viewBox="{vb}"'), height, max_w) == pytest.approx(expected)


def test_wordmark_in_40px_header_is_at_least_24px_tall(tmp_path):  # ICN-03 (roadmap acceptance)
    p = _svg(tmp_path, "vmware", 'viewBox="0 0 400 100"')
    d = Diagram("I", "Icons")
    d.zone("Site", x=100, y=100, w=800, h=400, icon=str(p), header={"icon_size": 40})
    by = {i.id: i for i in build_scene(d, THEME).items if isinstance(i, Shape)}
    ic = by["z0-icon"].icon
    assert ic.size >= 24 and ic.width == pytest.approx(4 * ic.size)
    assert 100 < ic.x and ic.x + ic.width < 900 and 100 < ic.y and ic.y + ic.size < 500  # inside its zone
    lab = next(i for i in build_scene(d, THEME).items if getattr(i, "id", "") == "z0-label")
    assert lab.x >= ic.x + ic.width                                                         # label after it


@pytest.mark.parametrize("vb", ["0 0 10 10", "0 0 400 100"], ids=["square", "wordmark"])
def test_box_icon_keeps_aspect_and_pushes_text(tmp_path, vb):  # ICN-02 in boxes
    p = _svg(tmp_path, "i", f'viewBox="{vb}"')
    d = Diagram("I", "Icons")
    d.box("Title", id="n", x=100, y=100, w=500, h=120, icon=str(p), icon_size=40)
    s = next(i for i in build_scene(d, THEME).items if isinstance(i, Shape) and i.id == "n")
    a = aspect(p)
    assert (s.icon.width, s.icon.size) == pytest.approx((40 * a, 40))
    assert s.icon.y == pytest.approx(100 + (120 - 40) / 2)                  # centred vertically
    assert s.label.box[0] == pytest.approx(100 + 22 + 40 * a + 14)          # text after the icon


@pytest.mark.parametrize("vb,box", [("0 0 10 10", (60, 60)), ("0 0 300 100", (120, 40))], ids=["square", "wordmark"])
def test_icon_only_box_centres_its_icon(tmp_path, vb, box):  # ICN-05
    p = _svg(tmp_path, "i", f'viewBox="{vb}"')
    d = Diagram("I", "Icons")
    w, h = box
    d.box(None, id="chip", x=200, y=200, w=w, h=h, icon=str(p), align="center", icon_size=30)
    s = next(i for i in build_scene(d, THEME).items if isinstance(i, Shape) and i.id == "chip")
    ic = s.icon
    assert ic.x + ic.width / 2 == pytest.approx(200 + w / 2) and ic.y + ic.size / 2 == pytest.approx(200 + h / 2)
    assert 200 <= ic.x and ic.x + ic.width <= 200 + w and 200 <= ic.y and ic.y + ic.size <= 200 + h


def test_svg_backend_draws_icon_at_its_width(tmp_path):
    p = _svg(tmp_path, "i", 'viewBox="0 0 400 100"')
    d = Diagram("I", "Icons")
    d.box("T", id="n", x=100, y=100, w=500, h=120, icon=str(p), icon_size=40)
    assert 'width="160" height="40"' in to_svg(build_scene(d, THEME))

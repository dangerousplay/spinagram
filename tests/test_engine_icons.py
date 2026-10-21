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


# variants (ICN-04) --------------------------------------------------------------------------------------------
def _variant_theme(tmp_path, aliases):
    import yaml
    for name in ("plain", "wide", "mark"):
        _svg(tmp_path, name, 'viewBox="0 0 400 100"' if name == "wide" else 'viewBox="0 0 10 10"')
    (tmp_path / "theme.yaml").write_text("extends: default\n" + yaml.safe_dump({"icons": {"alias": aliases}}))
    return Theme.load(tmp_path)


VARIANTS = [
    # id, aliases, variant, expected file stem
    ("wordmark-alias", {"vmware": "plain.svg", "vmware-wordmark": "wide.svg"}, "wordmark", "wide"),
    ("symbol-alias", {"vmware": "plain.svg", "vmware-symbol": "mark.svg"}, "symbol", "mark"),
    ("no-alias-falls-back", {"vmware": "plain.svg"}, "wordmark", "plain"),
    ("no-variant", {"vmware": "plain.svg", "vmware-wordmark": "wide.svg"}, None, "plain"),
]


@pytest.mark.parametrize("aliases,variant,stem", [v[1:] for v in VARIANTS], ids=[v[0] for v in VARIANTS])
@pytest.mark.parametrize("where", ["box", "zone"])
def test_icon_variant_resolves_theme_alias(tmp_path, aliases, variant, stem, where):
    th = _variant_theme(tmp_path, {k: str(tmp_path / v) for k, v in aliases.items()})
    d = Diagram("I", "Icons")
    if where == "box":
        kw = {"variant": variant} if variant else {}
        d.box("T", id="n", x=100, y=100, w=500, h=120, icon="vmware", **kw)
        ic = next(i for i in build_scene(d, th).items if isinstance(i, Shape) and i.id == "n").icon
    else:
        d.zone("Z", x=100, y=100, w=800, h=400, icon="vmware", header={"variant": variant})
        ic = next(i for i in build_scene(d, th).items if isinstance(i, Shape) and i.id == "z0-icon").icon
    assert ic.path.stem == stem


def test_note_variant_is_not_an_icon_variant(tmp_path):
    th = _variant_theme(tmp_path, {"vmware": str(tmp_path / "plain.svg"), "vmware-card": str(tmp_path / "wide.svg")})
    d = Diagram("I", "Icons")
    d.note("N", id="n", x=100, y=100, w=500, h=120, icon="vmware", variant="card")
    assert next(i for i in build_scene(d, th).items if isinstance(i, Shape) and i.id == "n").icon.path.stem == "plain"


# badges (ICN-06..10) ------------------------------------------------------------------------------------------
from spinagram.text import measure  # noqa: E402


def _badge_scene(tmp_path, count, w=360, h=120, icon_size=None, title="node-a gitlab runner manager"):
    paths = [str(_svg(tmp_path, f"b{k}", 'viewBox="0 0 10 10"')) for k in range(count)]
    main = str(_svg(tmp_path, "main", 'viewBox="0 0 10 10"'))
    d = Diagram("B", "Badges")
    kw = {"icon_size": icon_size} if icon_size else {}
    d.box(title, id="n", x=100, y=100, w=w, h=h, icon=main, badges=paths, **kw)
    return {i.id: i for i in build_scene(d, THEME).items if isinstance(i, Shape)}


@pytest.mark.parametrize("count", [1, 2, 3], ids=lambda c: f"{c}badges")
@pytest.mark.parametrize("box,icon_size,size", [((360, 120), 50, 20), ((360, 120), 30, 14), ((480, 200), 60, 24)],
                         ids=["40pct", "min14", "large"])
def test_badges_size_halo_placement_and_text(tmp_path, count, box, icon_size, size):
    w, h = box
    by = _badge_scene(tmp_path, count, w, h, icon_size)
    node = by["n"]
    right = 100 + w - 6
    for k in range(count):
        b, halo = by[f"n-badge{k}"], by[f"n-badge{k}-halo"]
        assert b.icon.size == pytest.approx(size)                                    # ICN-07: 40 %, min 14
        assert halo.w == pytest.approx(size + 6) and halo.radius == pytest.approx(halo.w / 2)  # halo +3 each side
        assert halo.fill == "#FFFFFF" and halo.y == pytest.approx(106)                # ICN-08: top, inset 6
        assert halo.x + halo.w == pytest.approx(right - k * (size + 6 + 4))          # stacking leftward
    left = min(by[f"n-badge{k}-halo"].x for k in range(count))
    tx, _, tw, _ = node.label.box
    assert tx + tw <= left                                                            # ICN-09: text clear of badges
    for b in node.label.blocks:
        assert all(tx + measure(ln, b.font) <= left + 0.5 for ln in b.lines)


def test_badges_from_yaml(tmp_path):  # ICN-06 YAML
    from spinagram.yaml_io import from_dict
    p = str(_svg(tmp_path, "b", 'viewBox="0 0 10 10"'))
    d = from_dict({"id": "B", "title": "B", "nodes": [{"id": "n", "title": "T", "x": 100, "y": 100, "w": 300,
                                                       "h": 120, "badges": [p, p]}]})
    ids = [i.id for i in build_scene(d, THEME).items]
    assert "n-badge0" in ids and "n-badge1" in ids


@pytest.mark.parametrize("front", ["python", "yaml"])
def test_more_than_three_badges_raise(front):  # ICN-10
    from spinagram.yaml_io import from_dict
    with pytest.raises(ValueError, match="4 badges; at most 3"):
        if front == "python":
            Diagram("B", "B").box("T", badges=["a", "b", "c", "d"])
        else:
            from_dict({"id": "B", "title": "B", "nodes": [{"id": "n", "title": "T", "badges": ["a", "b", "c", "d"]}]})


# fallback chains and sources (ICN-11, ICN-12) -----------------------------------------------------------------
def _chain_theme(tmp_path, chain):
    import yaml
    good = _svg(tmp_path, "lb", 'viewBox="0 0 10 10"')
    other = _svg(tmp_path, "lb2", 'viewBox="0 0 10 10"')
    refs = [{"GOOD": str(good), "OTHER": str(other)}.get(r, r) for r in chain]
    (tmp_path / "theme.yaml").write_text("extends: default\n" + yaml.safe_dump(
        {"icons": {"fallback": {"load-balancer": refs}, "alias": {"lb-alias": str(good)}}}))
    return Theme.load(tmp_path), good, other


CHAINS = [
    # id, chain, expected file stem, expected source
    ("first-available", ["GOOD", "OTHER"], "lb", "theme"),
    ("second-is-fallback-1", ["missing-pack:nothing", "OTHER"], "lb2", "fallback:1"),
    ("third-is-fallback-2", ["missing-pack:a", "missing-pack:b", "GOOD"], "lb", "fallback:2"),
    ("none-available", ["missing-pack:a"], None, "missing"),
]


@pytest.mark.parametrize("chain,stem,source", [c[1:] for c in CHAINS], ids=[c[0] for c in CHAINS])
def test_concept_resolves_first_available(tmp_path, chain, stem, source):
    th, _, _ = _chain_theme(tmp_path, chain)
    d = Diagram("I", "Icons")
    d.box("LB", id="n", x=100, y=100, w=400, h=120, icon="concept:load-balancer")
    if stem is None:
        with pytest.warns(UserWarning, match="icon 'concept:load-balancer' not found"):
            sc = build_scene(d, th)
    else:
        sc = build_scene(d, th)
    s = next(i for i in sc.items if isinstance(i, Shape) and i.id == "n")
    assert (s.icon.path.stem if s.icon else None) == stem
    assert sc.icon_sources["concept:load-balancer"][1] == source


@pytest.mark.parametrize("name,source", [("aws:ec2", "official"), ("lb-alias", "theme"), ("./x.svg", "theme")],
                         ids=["pack", "alias", "path"])
def test_icon_source_kinds(tmp_path, name, source):
    th, _, _ = _chain_theme(tmp_path, ["GOOD"])
    assert th._source(name) == source


def test_icon_sources_recorded_per_scene(tmp_path):
    th, good, _ = _chain_theme(tmp_path, ["GOOD"])
    d = Diagram("I", "Icons")
    d.box("A", id="a", x=100, y=100, w=400, h=120, icon="lb-alias")
    sc = build_scene(d, th)
    assert sc.icon_sources == {"lb-alias": (str(good), "theme")}
    assert th.icon_trace is None                                   # tracing ends with the scene

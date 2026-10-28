from pathlib import Path

import pytest

from spinagram import Diagram, Theme, build_scene, load, render, scenes
from spinagram.model import parse_edge
from spinagram.qa import check
from spinagram.scene import Connector, Shape, TableGrid
from spinagram.text import wrap

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


@pytest.mark.parametrize("src,expected", [
    ("a -> b", ("a", "b", None, "end")),
    ("a.right@0.3 -> b.left: yes, go", ("a.right@0.3", "b.left", "yes, go", "end")),
    ("a <- b", ("b", "a", None, "end")),
    ("a -- b", ("a", "b", None, "none")),
    ("a <-> b: both", ("a", "b", "both", "both")),
])
def test_edge_shorthand(src, expected):
    e = parse_edge(src)
    assert (e.src, e.dst, e.label, e.arrow) == expected


def test_theme_extends_and_tokens(tmp_path):
    (tmp_path / "theme.yaml").write_text("extends: default\ncolors: {brand: '#112233', primary: brand}\n")
    t = Theme.load(tmp_path)
    assert t.color("primary") == "#112233"
    assert t.color("text") == Theme.load("default").color("text")
    assert t.node_style("default")["stroke"] == "#112233"


def test_wrap_fits_width():
    f = Theme.load("default").font("body", 400, 18)
    lines = wrap("one two three four five six seven eight nine ten", f, 120)
    assert len(lines) > 1 and all(lines)


def test_auto_side_and_binding():
    d = Diagram("T", "t")
    a = d.box("A", x=0, y=0, w=100, h=100)
    b = d.box("B", x=300, y=0, w=100, h=100)
    d.edge(a, b)
    sc = build_scene(d, Theme.load())
    c = next(i for i in sc.items if isinstance(i, Connector))
    assert c.src.side == "right" and c.dst.side == "left"
    assert c.points == [(100, 50), (300, 50)]


def test_examples_render_all_backends(tmp_path):
    diagrams = load(EXAMPLES)
    assert {d.id for d in diagrams} == {"EX1", "EX2", "L01", "L02", "Q01"}
    out = render(diagrams, tmp_path, formats=["svg", "pptx", "figma"])
    names = {p.name for p in out}
    assert "diagrams.pptx" in names
    assert any(n.endswith(".svg") for n in names)
    assert any(n.endswith("-01.js") for n in names)
    for sc in [build_scene(d, Theme.load()) for d in diagrams]:
        assert check(sc) == []


def test_quickstart_yaml_and_python_match():
    """The README shows the quickstart in both languages: they must stay the same diagram."""
    (y,), (py,) = load(EXAMPLES / "quickstart.yaml"), load(EXAMPLES / "quickstart.py")
    def boxes(d):
        sc = scenes([d])[0]
        return sorted((round(s.x), round(s.y), round(s.w), round(s.h)) for s in sc.shapes().values())

    assert boxes(y) == boxes(py)


def test_pptx_connectors_bound(tmp_path):
    pptx = pytest.importorskip("pptx")
    render(load(EXAMPLES / "decision.yaml"), tmp_path, formats=["pptx"])
    slide = pptx.Presentation(str(tmp_path / "diagrams.pptx")).slides[0]
    xml = slide._element.xml
    assert xml.count("<a:stCxn") >= 2 and "a:tailEnd" in xml
    assert any(s.has_text_frame and s.text_frame.text.startswith("Technical review") for s in slide.shapes)


def test_table_and_pill_in_scene():
    sc = build_scene(load(EXAMPLES / "release_flow.py")[0], Theme.load())
    assert any(isinstance(i, TableGrid) for i in sc.items)
    labels = [i.label for i in sc.items if isinstance(i, Connector) and i.label]
    assert labels and all(isinstance(lb, Shape) and lb.kind == "pill" for lb in labels)


def test_yaml_pitfalls_are_reported(tmp_path):
    from spinagram.yaml_io import SpecError

    bad = tmp_path / "bad.yaml"
    bad.write_text("id: X\ntitle: t\nnodes:\n  - {id: a, title: Why?, x: 0}\n")
    with pytest.raises(SpecError, match="quote"):
        load(bad)
    bad.write_text("id: X\ntitle: t\nnodes:\n  - {id: no, x: 0, y: 0, w: 10, h: 10}\n")
    with pytest.raises(ValueError, match="boolean"):
        load(bad)
    bad.write_text("id: X\ntitle: t\nnodes:\n  - {id: a, text: one, two, x: 0}\n")
    with pytest.raises(ValueError, match="unknown keys"):
        load(bad)


def test_icon_scales_with_box(tmp_path):
    icons = tmp_path / "icons"
    icons.mkdir()
    (icons / "x-dark.png").write_bytes(b"\x89PNG")
    (tmp_path / "theme.yaml").write_text("extends: default\nicons: {dir: icons}\n")
    t = Theme.load(tmp_path)
    d = Diagram("T", "t")
    d.box("small", icon="x", x=0, y=0, w=300, h=120)
    d.box("tall", icon="x", x=0, y=200, w=300, h=300)
    d.box("fixed", icon="x", icon_size=60, x=400, y=0, w=300, h=120)
    sizes = {s.id: s.icon.size for s in build_scene(d, t).items if isinstance(s, Shape) and s.icon}
    assert sizes["small"] == 44 and sizes["tall"] > 44 and sizes["fixed"] == 60


def test_facts_substitution_and_provenance(tmp_path):
    import json

    from spinagram.facts import FactRegistry, render_html

    (tmp_path / "facts.json").write_text(json.dumps({"meta": {"locale": "pt-BR"}, "facts": [
        {"id": "a", "label": "A", "format": "int", "value": 15972,
         "source": {"system": "Jira", "query": "project = X", "computed_at": "b.py:10"}},
        {"id": "b", "label": "B", "format": "int", "value": 4970, "source": {}},
        {"id": "pct", "label": "share", "format": "pct", "source": {"formula": "100*b/a", "inputs": ["b", "a"]}}]}))
    reg = FactRegistry.load(tmp_path / "facts.json")
    assert reg.display("a") == "15.972" and reg.display("pct") == "31%" and reg.display("pct", "pct", 1) == "31,1%"
    d = Diagram("F", "Fatos", facts="facts.json", base_dir=tmp_path)
    d.box("{{a}} problemas", text="{{pct}} cancelados", x=0, y=0, w=400, h=150)
    sc = build_scene(d, Theme.load())
    shape = next(s for s in sc.items if isinstance(s, Shape) and s.role == "node")
    assert shape.label.blocks[0].lines[0] == "15.972 problemas"
    assert sc.item_facts[shape.id] == ["a", "pct"]
    assert sc.sources[0]["query"] == "project = X" and sc.sources[1]["inputs"][0]["id"] == "b"
    out = render([d], tmp_path / "out", formats=["svg"])
    assert (tmp_path / "out" / "fontes.md").exists() and "project = X" in (tmp_path / "out" / "fontes.md").read_text()
    assert "<title>A: 15.972" in next(p for p in out if p.suffix == ".svg").read_text()
    page, used = render_html("<b>{{pct|pct1}}</b>", reg)
    assert used == ["pct"] and "31,1%" in page and 'data-fact="pct"' in page
    bad = Diagram("G", "g", facts="facts.json", base_dir=tmp_path)
    bad.box("{{nope}}", x=0, y=0, w=100, h=100)
    with pytest.raises(KeyError):
        build_scene(bad, Theme.load())


def test_zone_outline_and_icon(tmp_path):
    (tmp_path / "icons").mkdir()
    (tmp_path / "icons" / "vpc.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8"/>')
    (tmp_path / "theme.yaml").write_text(
        "extends: default\nicons: {dir: icons, pattern: '{name}.svg'}\n"
        "styles: {zone: {az: {fill: none, stroke: '#147EBA', dashed: true, label: '#147EBA', radius: 0},\n"
        "                 vpc: {fill: none, stroke: '#8C4FFF', label: '#8C4FFF', icon: vpc, upper: false}}}\n")
    d = Diagram("Z", "zones")
    d.zone("AZ 1a", x=10, y=10, w=200, h=100, color="az")
    d.zone("VPC", x=10, y=150, w=200, h=100, color="vpc")
    sc = build_scene(d, Theme.load(tmp_path))
    az, vpc = [i for i in sc.items if isinstance(i, Shape) and i.id in ("z0", "z1")]
    assert az.fill is None and az.dashed and az.stroke == "#147EBA" and az.radius == 0
    assert any(isinstance(i, Shape) and i.id == "z1-icon" and i.icon for i in sc.items)
    labels = {i.id: i.block.lines[0] for i in sc.items if hasattr(i, "block") and i.id.endswith("-label")}
    assert labels["z0-label"] == "AZ 1A" and labels["z1-label"] == "VPC"


def test_python_spec_imports_sibling_helper(tmp_path):
    (tmp_path / "_helpers.py").write_text("W = 321\n")
    (tmp_path / "s.py").write_text("from spinagram import Diagram\nfrom _helpers import W\n"
                                   "d = Diagram('H', 'helper'); d.box('a', x=0, y=0, w=W, h=80)\ndiagram = d\n")
    (d,) = load(tmp_path / "s.py")
    assert d.nodes[0].w == 321


def test_deck_html(tmp_path):
    from spinagram.deck import build_deck

    (tmp_path / "me.jpeg").write_bytes(b"\xff\xd8\xff\xe0fake")
    (tmp_path / "deck.yaml").write_text(
        f"title: Demo\nkicker: K\nspecs: {EXAMPLES}\n"
        "authors: [{name: Ana, role: Engineer, photo: me.jpeg}]\n"
        "sections:\n  - title: One\n    slides: [{diagram: EX1, message: first}]\n"
        "  - title: Two\n    slides: [{diagram: EX2}]\n")
    out = build_deck(tmp_path / "deck.yaml", Theme.load(), tmp_path / "deck.html")
    page = out.read_text()
    assert page.count('class="slide band"') == 3  # cover + 2 dividers
    assert 'id="EX1"' in page and 'id="EX2"' in page and "data:image/svg+xml;base64," in page
    assert "Ana" in page and "Engineer" in page and "data:image/jpeg;base64," in page
    with pytest.raises(KeyError):
        (tmp_path / "bad.yaml").write_text(f"specs: {EXAMPLES}\nsections: [{{title: X, slides: [{{diagram: NOPE}}]}}]\n")
        build_deck(tmp_path / "bad.yaml", Theme.load())


def test_figma_figjam_connectors_and_svg_icons(tmp_path):
    import shutil
    import subprocess

    from spinagram.backends.figma import to_figma_js

    (tmp_path / "icons").mkdir()
    (tmp_path / "icons" / "dot.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8"><circle r="4"/></svg>')
    (tmp_path / "theme.yaml").write_text("extends: default\nicons: {dir: icons, pattern: '{name}.svg'}\n")
    d = Diagram("F", "figjam")
    a = d.box("A", x=0, y=0, w=200, h=80, icon="dot")
    b = d.box("B", x=400, y=0, w=200, h=80)
    d.edge(a.right, b.left, label="go")
    d.edge((100, 300), (500, 300))  # free edge stays a vector
    scripts, assets = to_figma_js(build_scene(d, Theme.load(tmp_path)))
    js = "\n".join(scripts)
    assert "createConnector" in js and "svgIcon(" in js and "const SVG = {" in js
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    mock = Path(__file__).parent / "js" / "figma_mock.mjs"
    p = tmp_path / "s.js"
    p.write_text(scripts[0])
    jam = subprocess.run([node, str(mock), str(p), "figjam"], capture_output=True, text=True, check=True).stdout
    design = subprocess.run([node, str(mock), str(p), "figma"], capture_output=True, text=True, check=True).stdout
    # vectors: the free edge + the default theme's chrome rule; the bound edge is a connector in FigJam only
    assert '"connectors":1' in jam and '"vectors":2' in jam and '"svgIcons":1' in jam
    assert '"connectors":0' in design and '"vectors":3' in design


SVG_DOT = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8"><circle r="4"/></svg>'


@pytest.fixture
def icon_env(tmp_path, monkeypatch):
    """Isolated icon cache + user registry (no network)."""
    monkeypatch.setenv("SPINAGRAM_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("SPINAGRAM_OFFLINE", raising=False)  # local packs: fetched from disk on first use
    monkeypatch.chdir(tmp_path)
    from spinagram import icons

    icons._INDEX_CACHE.clear()
    return tmp_path


def test_icon_naming_rules():
    from spinagram.icons import Pack, kebab, registry

    assert kebab("AmazonAPIGateway") == "amazon-api-gateway" and kebab("compute_engine") == "compute-engine"
    builtin = registry()
    assert {"aws", "gcp", "azure", "k8s", "oci", "openstack", "terrastruct"} <= set(builtin)
    assert builtin["aws"].classify("package/icons/architecture-service/AmazonEC2.svg")[:3] == ("amazon-ec2", "light", ["ec2"])
    assert builtin["oci"].classify("resources/oci/compute/vm-white.png")[:2] == ("compute-vm", "dark")
    assert builtin["k8s"].classify("icons/svg/resources/labeled/pod.svg")[0] == "pod-labeled"
    p = Pack.parse("x", {"source": {"type": "dir", "path": "."}}, "test")
    assert p.classify("a/b/My_Icon.svg")[0] == "my-icon"


def test_icon_pack_dir_and_zip(icon_env):
    import zipfile

    from spinagram import icons

    src = icon_env / "src" / "net"
    src.mkdir(parents=True)
    (src / "Router.svg").write_text(SVG_DOT)
    (src / "router-white.svg").write_text(SVG_DOT)
    icons.register("local", {"type": "dir", "path": str(icon_env / "src")},
                   rules=[{"match": r"(?P<stem>[^/]+)-white\.svg$", "name": "{stem}", "tone": "dark"},
                          {"match": r"(?P<stem>[^/]+)\.svg$", "name": "{stem}"}])
    with zipfile.ZipFile(icon_env / "pack.zip", "w") as z:
        z.writestr("set/icons/Load_Balancer.svg", SVG_DOT)
        z.writestr("set/README.txt", "x")
    icons.register("zipped", {"type": "zip", "url": (icon_env / "pack.zip").as_uri(), "version": "1"},
                   strip=["^load-"], project=True)
    assert icons.resolve("local:router").name == "local__router.svg"
    assert icons.resolve("local:router", "dark").name == "local__router__dark.svg"
    assert icons.resolve("zipped:load-balancer").exists() and icons.resolve("zipped:balancer").exists()
    assert ("zipped", "load-balancer", "load-balancer") in icons.search("balancer", icons.registry().values())
    assert icons.unregister("zipped", project=True) and "zipped" not in icons.registry()


def test_icon_pack_listing_and_terrastruct_names(icon_env):
    from spinagram import icons

    site = icon_env / "site"
    (site / "dev").mkdir(parents=True)
    (site / "essentials").mkdir()
    (site / "dev" / "python.svg").write_text(SVG_DOT)
    (site / "essentials" / "226-alarm clock.svg").write_text(SVG_DOT)
    (site / "index.html").write_text('<div onclick=\'clickIcon("dev%2Fpython.svg")\'></div>'
                                     '<div onclick=\'clickIcon("essentials%2F226-alarm%20clock.svg")\'></div>'
                                     '<div onclick=\'clickIcon("dev%2Fgone.svg")\'></div>')
    ts = icons.registry()["terrastruct"]
    ts.source = {**ts.source, "url": (site / "index.html").as_uri(), "version": "test"}
    with pytest.warns(UserWarning, match="1 of 3 icons failed"):
        icons.fetch(ts)
    reg = {"terrastruct": ts}
    assert icons.resolve("terrastruct:python", packs=reg).name == "terrastruct__python.svg"
    assert icons.resolve("terrastruct:py", packs=reg) == icons.resolve("terrastruct:python", packs=reg)
    assert icons.resolve("terrastruct:alarm-clock", packs=reg).name == "terrastruct__essentials-alarm-clock.svg"
    assert ts.classify("aws/Database/Amazon-Aurora_light-bg.svg")[0] == "aws-aurora"
    assert ts.classify("azure/Databases Service Color/Azure Cosmos DB.svg")[0] == "azure-cosmos-db"
    assert ts.classify("tech/022-server.svg")[:3] == ("tech-server", "light", ["server"])


def test_theme_resolves_pack_icons(icon_env):
    from spinagram import icons

    (icon_env / "src").mkdir()
    (icon_env / "src" / "db.svg").write_text(SVG_DOT)
    icons.register("lab", {"type": "dir", "path": str(icon_env / "src")})
    (icon_env / "theme.yaml").write_text("extends: default\nicons: {alias: {database: 'lab:db'}}\n")
    th = Theme.load(icon_env)
    assert th.icon("lab:db").name == "lab__db.svg" and th.icon("database") == th.icon("lab:db")
    d = Diagram("P", "pack icons")
    d.box("DB", x=0, y=0, w=300, h=120, icon="lab:db")
    sc = build_scene(d, th)
    assert next(i for i in sc.items if isinstance(i, Shape) and i.id == "db").icon.path.name == "lab__db.svg"


def test_cli_icons_add_and_figjam_bundle(icon_env):
    from spinagram.cli import main

    (icon_env / "src").mkdir()
    (icon_env / "src" / "cache.svg").write_text(SVG_DOT)
    assert main(["icons", "add", "mine", "--dir", str(icon_env / "src")]) == 0
    assert main(["icons", "search", "cache", "--pack", "mine"]) == 0
    spec = icon_env / "s.yaml"
    spec.write_text("id: J\ntitle: jam\nnodes:\n  - {id: a, x: 0, y: 0, w: 300, h: 120, title: A, icon: 'mine:cache'}\n"
                    "  - {id: b, x: 500, y: 0, w: 300, h: 120, title: B}\nedges: [a -> b]\n")
    assert main(["render", str(spec), "-f", "figjam", "-o", str(icon_env / "out"), "--no-gallery"]) == 0
    fig = icon_env / "out" / "figma"
    assert (fig / "icons" / "mine__cache.svg").exists() and (fig / "icon-library.js").exists()
    js = (fig / "J-jam-01.js").read_text()
    assert 'icon("a icon", "mine__cache.svg"' in js and "const SVG = {}" in js
    assert '"mine__cache.svg":null' in (fig / "icon-library.js").read_text()


# PNG → SVG vectorization (spec: .specs/features/png-to-svg) --------------------------------------
vec = pytest.importorskip("spinagram.vectorize")
needs_vector = pytest.mark.skipif(not vec.available(), reason="vector extra not installed")


def _flat_png(path, size=128):
    from PIL import Image, ImageDraw

    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.rounded_rectangle((12, 12, size - 12, size - 12), radius=18, outline=(63, 161, 16, 255), width=10)
    dr.ellipse((44, 44, size - 44, size - 44), fill=(20, 110, 55, 255))
    im.save(path)
    return path


def _noise_png(path, size=96):
    import random

    from PIL import Image

    rnd = random.Random(7)
    im = Image.new("RGBA", (size, size))
    im.putdata([(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256), 255) for _ in range(size * size)])
    im.save(path)
    return path


@needs_vector
def test_vectorize_gate_accepts_flat_rejects_noise(tmp_path):
    good = vec.vectorize_bytes(_flat_png(tmp_path / "a.png").read_bytes())
    assert good.accepted and "<path" in good.svg and "viewBox" in good.svg and good.score.mean <= vec.MAX_MEAN
    bad = vec.vectorize_bytes(_noise_png(tmp_path / "n.png").read_bytes())
    assert not bad.accepted and bad.svg is None and "fidelity" in bad.reason


@needs_vector
def test_vectorize_maybe_cache_twin_and_switches(icon_env, monkeypatch):
    png = _flat_png(icon_env / "icon.png")
    svg = vec.maybe(png)
    assert svg.suffix == ".svg" and svg.with_suffix(".png").read_bytes() == png.read_bytes()  # raster twin (VEC-07)
    monkeypatch.setattr(vec, "vectorize_bytes", lambda b: (_ for _ in ()).throw(AssertionError("re-traced")))
    assert vec.maybe(png) == svg                                                          # cached (VEC-06)
    noise = _noise_png(icon_env / "noise.png")
    monkeypatch.undo()
    monkeypatch.setenv("SPINAGRAM_CACHE", str(icon_env / "cache"))
    assert vec.maybe(noise) == noise                                                      # rejected → PNG
    assert vec.maybe(png, False) == png                                                   # theme/pack flag
    monkeypatch.setenv("SPINAGRAM_VECTORIZE", "0")
    assert vec.maybe(png) == png                                                          # env switch


@needs_vector
def test_theme_and_pack_png_icons_become_svg(icon_env):
    import zipfile

    from spinagram import icons

    (icon_env / "icons").mkdir()
    _flat_png(icon_env / "icons" / "safe.png")
    (icon_env / "theme.yaml").write_text("extends: default\nicons: {dir: icons, pattern: '{name}.png'}\n")
    assert Theme.load(icon_env).icon("safe").suffix == ".svg"                             # VEC-04
    (icon_env / "off").mkdir()
    (icon_env / "off" / "theme.yaml").write_text(f"extends: '{icon_env}'\nicons: {{vectorize: false}}\n")
    assert Theme.load(icon_env / "off").icon("safe").suffix == ".png"
    with zipfile.ZipFile(icon_env / "p.zip", "w") as z:
        z.write(icon_env / "icons" / "safe.png", "set/Safe.png")
    icons.register("pz", {"type": "zip", "url": (icon_env / "p.zip").as_uri(), "version": "1"})
    p = icons.resolve("pz:safe")
    assert p.name == "pz__safe.svg" and p.with_suffix(".png").exists()                     # VEC-03
    entry = icons.index(icons.registry()["pz"])["icons"]["safe"]
    assert entry["raster"]["light"] == "pz__safe.png" and entry["vector"]["light"]["mean"] <= vec.MAX_MEAN
    icons.register("pz2", {"type": "zip", "url": (icon_env / "p.zip").as_uri(), "version": "1"})
    reg = icon_env / "config" / "spinagram" / "icons.yaml"
    reg.write_text(reg.read_text().replace("pz2:\n", "pz2:\n    vectorize: false\n"))
    icons._INDEX_CACHE.clear()
    assert icons.resolve("pz2:safe").suffix == ".png"


@needs_vector
def test_vectorized_icon_outputs_pptx_cli_figjam(icon_env):
    pptx = pytest.importorskip("pptx")
    from spinagram.cli import main

    (icon_env / "icons").mkdir()
    _flat_png(icon_env / "icons" / "box.png")
    (icon_env / "theme.yaml").write_text("extends: default\nicons: {dir: icons, pattern: '{name}.png'}\n")
    spec = icon_env / "s.yaml"
    spec.write_text("id: V\ntitle: vec\nnodes:\n  - {id: a, x: 0, y: 0, w: 300, h: 120, title: A, icon: box}\n")
    out = icon_env / "out"
    assert main(["render", str(spec), "-t", str(icon_env), "-f", "pptx,figjam", "-o", str(out), "--no-gallery"]) == 0
    slide = pptx.Presentation(str(out / "diagrams.pptx")).slides[0]
    assert any(s.shape_type == 13 for s in slide.shapes) or "<p:pic" in slide._element.xml   # VEC-07 picture kept
    assert [f.suffix for f in (out / "figma" / "icons").iterdir()] == [".svg"]               # VEC-09
    _flat_png(icon_env / "loose.png")
    assert main(["vectorize", str(icon_env / "loose.png"), "-o", str(icon_env / "vec")]) == 0  # VEC-08
    assert (icon_env / "vec" / "loose.svg").exists()


def test_theme_relative_dirs(tmp_path, monkeypatch):
    (tmp_path / "theme.yaml").write_text("extends: default\ncolors: {primary: '#112233'}\n")
    (tmp_path / "child").mkdir()
    (tmp_path / "child" / "theme.yaml").write_text("extends: ..\n")
    monkeypatch.chdir(tmp_path)
    assert Theme.load(".").color("primary") == "#112233"
    assert Theme.load(tmp_path / "child").color("primary") == "#112233"


def test_npm_source_custom_registry_and_scope(monkeypatch):
    from spinagram import icons

    seen = []

    def fake_get(url, timeout=300):
        seen.append(url)
        return json.dumps({"dist-tags": {"latest": "1.2.0"},
                           "versions": {"1.2.0": {"dist": {"tarball": "https://reg.example/t.tgz"}}}}).encode()

    import json
    monkeypatch.setattr(icons, "_get", fake_get)
    src = {"package": "@acme/brand-icons", "registry": "https://reg.example/api/npm/npm-virtual/"}
    assert icons._npm_tarball(src) == "https://reg.example/t.tgz"
    assert seen[-1] == "https://reg.example/api/npm/npm-virtual/@acme%2Fbrand-icons"
    with pytest.raises(ValueError):
        icons._npm_tarball({**src, "version": "9.9.9"})


def test_cli_icons_import_descriptor(icon_env):
    from spinagram import icons
    from spinagram.cli import main

    (icon_env / "d.yaml").write_text("acme:\n  title: Acme\n  source: {type: npm, package: '@acme/icons', version: 1.0.0,"
                                     " registry: 'https://reg.example/'}\n  rules:\n    - {match: 'x/(?P<stem>[^/]+)\\.svg$', name: '{stem}'}\n")
    assert main(["icons", "import", str(icon_env / "d.yaml")]) == 0
    p = icons.registry()["acme"]
    assert p.source["registry"] == "https://reg.example/" and p.classify("x/Foo.svg")[0] == "foo"


def test_theme_packs_bare_names_and_fallback(icon_env):
    (icon_env / "pk").mkdir()
    (icon_env / "pk" / "Vault-Box.svg").write_text(SVG_DOT)
    (icon_env / "packs.yaml").write_text(f"brand:\n  source: {{type: dir, path: '{icon_env / 'pk'}'}}\n"
                                        "broken:\n  source: {type: zip, url: 'file:///nonexistent.zip'}\n")
    (icon_env / "icons").mkdir()
    (icon_env / "icons" / "teams.svg").write_text(SVG_DOT)
    (icon_env / "theme.yaml").write_text("extends: default\nicons: {dir: icons, pattern: '{name}.svg', "
                                        "packs: [broken, brand], pack_files: [packs.yaml], alias: {safe: 'brand:vault-box'}}\n")
    th = Theme.load(icon_env)
    with pytest.warns(UserWarning, match="unavailable"):
        assert th.icon("vault-box").name == "brand__vault-box.svg"      # bare name → pack (broken pack skipped)
    assert th.icon("safe").name == "brand__vault-box.svg"              # theme alias onto a pack name
    assert th.icon("teams").name == "teams.svg"                         # not in packs → local dir


def test_node_operators_draw_edges():
    d = Diagram("op", "Operators")
    a, b, c, e = (d.box(t) for t in "abce")
    assert (a >> b >> c) is c
    a.to(c, "HTTPS", dashed=True)
    assert a >> [b, c] == [b, c]
    [b, c] >> e
    c << e
    a - e
    got = [(x.src, x.dst, x.label, x.arrow) for x in d.edges]
    assert got == [("a", "b", None, "end"), ("b", "c", None, "end"), ("a", "c", "HTTPS", "end"),
                   ("a", "b", None, "end"), ("a", "c", None, "end"), ("b", "e", None, "end"),
                   ("c", "e", None, "end"), ("e", "c", None, "end"), ("a", "e", None, "none")]
    assert d.edges[2].dashed


def test_unplaced_nodes_lay_out_automatically():
    d = Diagram("auto", "No layout given")
    d.box("a") >> d.box("b")
    assert d.auto
    sc = scenes([d])[0]
    assert all(s.w > 0 and s.h > 0 for s in sc.shapes().values())
    placed = Diagram("p", "Placed")
    placed.box("a", x=10, y=10, w=100, h=80)
    assert not placed.auto


def test_diagram_svg_string():
    d = Diagram("s", "Inline")
    d.box("Hello")
    svg = d._repr_svg_()
    assert svg.lstrip().startswith("<svg") and "Hello" in svg

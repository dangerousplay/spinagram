"""SVG pictures in PowerPoint: PNG fallback + asvg:svgBlip extension (spec pptx-svg)."""
import re
import shutil
import subprocess
import zipfile

import pytest

from diagramkit import Diagram, Theme, build_scene
from diagramkit.backends.pptx import SVG_EXT, PptxBackend

pptx = pytest.importorskip("pptx")

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8"><circle cx="4" cy="4" r="4" fill="#3FA110"/></svg>'
LOGO = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 12"><rect width="40" height="12" fill="#146E37"/></svg>'


@pytest.fixture
def theme(tmp_path, monkeypatch):
    monkeypatch.setenv("DIAGRAMKIT_CACHE", str(tmp_path / "cache" / "icons"))
    monkeypatch.delenv("DIAGRAMKIT_PPTX_SVG", raising=False)
    (tmp_path / "icons").mkdir()
    (tmp_path / "icons" / "dot.svg").write_text(SVG)
    (tmp_path / "logo.svg").write_text(LOGO)
    (tmp_path / "theme.yaml").write_text(
        "extends: default\nicons: {dir: icons, pattern: '{name}.svg'}\n"
        "chrome: {footer: {logo: logo.svg}}\n"
        "styles: {zone: {vpc: {fill: none, stroke: '#8C4FFF', label: '#8C4FFF', icon: dot}}}\n")
    return Theme.load(tmp_path)


def _scene(theme):
    d = Diagram("S", "svg-icons")
    for i in range(3):
        d.box(f"N{i}", x=40 + 260 * i, y=60, w=220, h=90, icon="dot")
    d.zone("VPC", x=20, y=200, w=400, h=160, color="vpc")
    d.table(["A", "B"], [["x", "y"]], x=500, y=220, widths=[160, 160], icons=["dot", None])
    return build_scene(d, theme)


def _render(tmp_path, theme, **kw):
    out = tmp_path / "out"
    return PptxBackend(**kw).render([_scene(theme)], out)[0]


def _slide_xml_and_rels(z):
    from lxml import etree

    rels = etree.fromstring(z.read("ppt/slides/_rels/slide1.xml.rels"))
    return z.read("ppt/slides/slide1.xml").decode(), {r.get("Id"): r.get("Target") for r in rels}


def test_svg_icons_embed_vector_with_png_fallback(tmp_path, theme):
    p = _render(tmp_path, theme)
    with zipfile.ZipFile(p) as z:
        names = z.namelist()
        svgs = [n for n in names if n.startswith("ppt/media/") and n.endswith(".svg")]
        pngs = [n for n in names if n.startswith("ppt/media/") and n.endswith(".png")]
        assert len(svgs) == 2 and pngs  # dot (nodes, zone, table) deduped + logo
        assert 'ContentType="image/svg+xml"' in z.read("[Content_Types].xml").decode()
        xml, rels = _slide_xml_and_rels(z)
        embeds = re.findall(r'svgBlip[^>]*r:embed="(rId\d+)"', xml)
        assert SVG_EXT in xml and "http://schemas.microsoft.com/office/drawing/2016/SVG/main" in xml
        # 3 nodes + zone corner + table cell + chrome logo
        assert len(embeds) == 6
        assert all(rels[r].endswith(".svg") for r in embeds)
        assert {z.read("ppt/media/" + rels[r].split("/")[-1]).decode() for r in embeds} == {SVG, LOGO}
    names = {s.name for s in pptx.Presentation(str(p)).slides[0].shapes}
    assert "chrome-logo" in names and any(n.endswith("[1,0] icon") for n in names)
    assert list((tmp_path / "cache" / "vector").glob("pptx-*-256x256.png"))  # resvg fallback cached


def test_sibling_png_is_preferred(tmp_path, theme):
    pytest.importorskip("PIL")
    from PIL import Image

    Image.new("RGBA", (7, 7), (255, 0, 0, 255)).save(tmp_path / "icons" / "dot.png")
    p = _render(tmp_path, theme)
    with zipfile.ZipFile(p) as z:
        sizes = {Image.open(z.open(n)).size for n in z.namelist() if n.endswith(".png") and "/media/" in n}
    assert (7, 7) in sizes


@pytest.mark.parametrize("how", ["arg", "env"])
def test_raster_opt_out(tmp_path, theme, monkeypatch, how):
    if how == "env":
        monkeypatch.setenv("DIAGRAMKIT_PPTX_SVG", "raster")
    p = _render(tmp_path, theme, **({"svg": "raster"} if how == "arg" else {}))
    with zipfile.ZipFile(p) as z:
        assert not [n for n in z.namelist() if n.endswith(".svg")]
        assert "svgBlip" not in z.read("ppt/slides/slide1.xml").decode()
        assert [n for n in z.namelist() if n.endswith(".png")]


def test_without_resvg_blank_fallback(tmp_path, theme, monkeypatch):
    import builtins
    import warnings

    from diagramkit.backends import pptx as backend

    real = builtins.__import__

    def no_resvg(name, *a, **k):
        if name == "resvg_py":
            raise ImportError(name)
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", no_resvg)
    monkeypatch.setattr(backend, "_warned", set())
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        p = _render(tmp_path, theme)
    assert sum("resvg" in str(x.message) for x in w) == 1
    with zipfile.ZipFile(p) as z:
        assert len([n for n in z.namelist() if n.endswith(".svg")]) == 2
        assert "svgBlip" in z.read("ppt/slides/slide1.xml").decode()


def test_dedupe_across_slides(tmp_path, theme):
    sc = _scene(theme)
    p = PptxBackend().render([sc, sc], tmp_path / "out")[0]
    with zipfile.ZipFile(p) as z:
        assert len([n for n in z.namelist() if n.endswith(".svg")]) == 2


def test_libreoffice_converts(tmp_path, theme):
    soffice = shutil.which("soffice")
    if not soffice:
        pytest.skip("soffice not installed")
    p = _render(tmp_path, theme)
    r = subprocess.run([soffice, f"-env:UserInstallation=file://{tmp_path / 'lo'}", "--headless",
                        "--convert-to", "pdf", "--outdir", str(tmp_path / "pdf"), str(p)],
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "pdf" / "diagrams.pdf").exists()

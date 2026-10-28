"""Smaller SVGs: font subsetting (FNT-02, FNT-05, FNT-06) and SVG font modes (FNT-01, FNT-03, FNT-04, FNT-07)."""
from __future__ import annotations

import hashlib
import io
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fontTools.ttLib import TTFont

from spinagram.backends import fontsubset

FONTS = Path(__file__).resolve().parents[1] / "src" / "spinagram" / "fonts"
SYMBOLS = FONTS / "NotoSansSymbols2-Regular.ttf"
MATH = FONTS / "NotoSansMath-Regular.ttf"


def _cmap(data: bytes) -> set[str]:
    return {chr(c) for c in TTFont(io.BytesIO(data)).getBestCmap()}


SUBSETS = [  # (id, font, chars asked, expected cmap: the asked chars plus space, those the font has)
    ("symbols-suits", SYMBOLS, "♠♣♥♦", set("♠♣♥♦")),               # neither bundled font maps U+0020
    ("symbols-missing-chars", SYMBOLS, "★A→ ", set("★")),          # 'A', '→' and space are not in Symbols 2
    ("symbols-duplicates", SYMBOLS, "✈✈⌘✈", set("✈⌘")),
    ("math", MATH, "∑∫√≤", set("∑∫√≤")),
    ("math-with-space", MATH, "∑ ∫", set("∑∫")),
]


@pytest.mark.parametrize("path,chars,want", [s[1:] for s in SUBSETS], ids=[s[0] for s in SUBSETS])
def test_subset_cmap_is_the_used_characters(path, chars, want):
    assert _cmap(fontsubset.subset(path, chars)) == want


@pytest.mark.parametrize("path", [SYMBOLS, MATH], ids=["symbols", "math"])
def test_subset_keeps_the_flavour(path):
    font = TTFont(io.BytesIO(fontsubset.subset(path, "♠∑")))
    assert font.flavor is None and font.sfntVersion == TTFont(path).sfntVersion  # TTF stays TTF


def test_subset_keeps_name_ids():
    orig = {(r.nameID, r.platformID) for r in TTFont(SYMBOLS)["name"].names}
    sub = {(r.nameID, r.platformID) for r in TTFont(io.BytesIO(fontsubset.subset(SYMBOLS, "♠")))["name"].names}
    assert sub == orig


@pytest.mark.parametrize("path,chars", [(SYMBOLS, "♠♣"), (MATH, "∑√")], ids=["symbols", "math"])
def test_subset_is_under_a_quarter_of_the_font(path, chars):
    assert len(fontsubset.subset(path, chars)) < 0.25 * path.stat().st_size


def test_subset_is_cached_per_path_and_chars():
    a = fontsubset.subset(SYMBOLS, "♠♣")
    assert fontsubset.subset(SYMBOLS, "♣♠") is a                          # same character set, any order
    assert fontsubset.subset(SYMBOLS, "♠") != a


_SCRIPT = ("import hashlib, sys; from spinagram.backends.fontsubset import subset; "
           "print(hashlib.sha256(subset(sys.argv[1], sys.argv[2])).hexdigest())")


@pytest.mark.parametrize("path,chars", [(SYMBOLS, "♠♣♥♦★"), (MATH, "∑∫√≤")], ids=["symbols", "math"])
def test_subset_bytes_identical_across_runs_and_hash_seeds(path, chars):
    fontsubset._cache.clear()
    first = hashlib.sha256(fontsubset.subset(path, chars)).hexdigest()
    fontsubset._cache.clear()
    assert hashlib.sha256(fontsubset.subset(path, chars)).hexdigest() == first        # a second run in-process
    for seed in range(4):
        env = {**os.environ, "PYTHONHASHSEED": str(seed)}
        out = subprocess.run([sys.executable, "-c", _SCRIPT, str(path), chars], env=env, capture_output=True,
                             text=True, check=True)
        assert out.stdout.strip() == first, f"PYTHONHASHSEED={seed}"


BROKEN = [  # (id, file bytes)
    ("not-a-font", b"this is not a font file"),
    ("truncated", SYMBOLS.read_bytes()[:2000]),
]


@pytest.mark.parametrize("data", [b[1] for b in BROKEN], ids=[b[0] for b in BROKEN])
def test_broken_font_falls_back_to_the_whole_file_with_a_warning(tmp_path, data):
    path = tmp_path / "broken.ttf"
    path.write_bytes(data)
    with pytest.warns(UserWarning, match=r"could not subset .*broken\.ttf.*; embedding the whole font"):
        out = fontsubset.subset(path, "abc")
    assert out == data


# T27: SVG font modes ------------------------------------------------------------------------------------------------
import base64  # noqa: E402
import math  # noqa: E402
import re  # noqa: E402
import string  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402

import yaml  # noqa: E402

from spinagram import Diagram, Theme, build_scene  # noqa: E402
from spinagram.backends.svg import to_svg  # noqa: E402
from spinagram.scene import Run, Scene, Text, TextBlock  # noqa: E402
from spinagram.theme import FontRef  # noqa: E402

FACE = re.compile(r"@font-face\{font-family:'([^']*)';src:url\(data:([^;]*);base64,([^)]*)\);"
                  r"font-weight:(\d+);font-style:(\w+)\}")
BRAND_CHARS = string.printable.strip() + " \u00a0"


def _brand_font(path, filler=2800, points=48):
    """A ~400 KB TTF: ASCII, space, NBSP and ``filler`` CJK glyphs with ``points``-point outlines."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    chars = BRAND_CHARS + "".join(chr(0x4E00 + k) for k in range(filler))
    names = [".notdef"] + [f"u{ord(c):04X}" for c in chars]
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap({ord(c): f"u{ord(c):04X}" for c in chars})
    glyphs = {}
    for k, name in enumerate(names):
        pen = TTGlyphPen(None)
        for j in range(points):
            a = 2 * math.pi * j / points
            p = (int(300 + (200 + k % 97) * math.cos(a)), int(350 + (250 + j * 7 % 31) * math.sin(a)))
            pen.moveTo(p) if j == 0 else pen.lineTo(p)
        pen.closePath()
        glyphs[name] = pen.glyph()
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({n: (600, 0) for n in names})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "Brand", "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost()
    fb.save(str(path))
    return path


@pytest.fixture(scope="module")
def brand(tmp_path_factory):
    root = tmp_path_factory.mktemp("brand")
    font = _brand_font(root / "brand.ttf")
    files = {"400": str(font), "700": str(font)}
    data = {"fonts": {r: {"family": "Brand", "files": files} for r in ("heading", "body")}}
    (root / "theme.yaml").write_text("extends: default\n" + yaml.safe_dump(data))
    return Theme.load(root)


def _style(svg: str) -> str:
    return ET.fromstring(svg).find("{http://www.w3.org/2000/svg}defs/{http://www.w3.org/2000/svg}style").text or ""


def _faces(svg: str) -> list[tuple[str, int, str, bytes]]:
    """(family, weight, style, font bytes) per @font-face."""
    return [(fam, int(w), st, base64.b64decode(b64)) for fam, _, b64, w, st in FACE.findall(_style(svg))]


# hand-built scenes: exactly the text drawn, no chrome
def _f(weight=400, italic=False, family="Brand", file=None):
    return FontRef(family, weight, italic, 20, file)


def _text(lines, font, runs=None):
    return Text(id="t", x=10, y=40, block=TextBlock(lines, lines, font, "#000000", 26, runs))


def _scene(*items):
    return Scene(id="S", title="S", slug="s", width=400, height=200, background="#FFFFFF", items=list(items))


@pytest.fixture(scope="module")
def faces(brand):
    font = Path(brand.font("body").file)
    return {"b400": _f(400, file=font), "b700": _f(700, file=font), "b400i": _f(400, True, file=font),
            "sym": _f(400, family="Noto Sans Symbols 2", file=SYMBOLS)}


SUBSET_SCENES = [  # (id, items(faces), expected {(family, weight, style): cmap}); brand maps ASCII, space, NBSP
    ("one-face", lambda f: [_text(["Hello"], f["b700"])], {("Brand", 700, "normal"): set("Helo ")}),
    ("two-faces", lambda f: [_text(["Hello"], f["b700"]), _text(["abc"], f["b400"])],
     {("Brand", 700, "normal"): set("Helo "), ("Brand", 400, "normal"): set("abc ")}),
    ("multi-line", lambda f: [_text(["ab", "cd"], f["b400"])], {("Brand", 400, "normal"): set("abcd ")}),
    ("empty-line-draws-nbsp", lambda f: [_text(["ab", ""], f["b400"])],
     {("Brand", 400, "normal"): set("ab \u00a0")}),
    ("fallback-runs", lambda f: [_text(["a ★ b"], f["b400"], [[Run("a ", f["b400"]), Run("★", f["sym"]),
                                                                Run(" b", f["b400"])]])],
     {("Brand", 400, "normal"): set("ab "), ("Noto Sans Symbols 2", 400, "normal"): set("★")}),
    ("italic-face", lambda f: [_text(["x"], f["b400i"]), _text(["y"], f["b400"])],
     {("Brand", 400, "italic"): set("x "), ("Brand", 400, "normal"): set("y ")}),
]


@pytest.mark.parametrize("make,want", [s[1:] for s in SUBSET_SCENES], ids=[s[0] for s in SUBSET_SCENES])
def test_subset_faces_hold_the_drawn_characters(faces, make, want):
    got = {(fam, w, st): _cmap(data) for fam, w, st, data in _faces(to_svg(_scene(*make(faces)), fonts="subset"))}
    assert got == want


@pytest.mark.parametrize("make,want", [s[1:] for s in SUBSET_SCENES], ids=[s[0] for s in SUBSET_SCENES])
def test_embed_faces_are_the_font_files(faces, make, want):
    svg = to_svg(_scene(*make(faces)), fonts="embed")
    files = {("Brand", 400): faces["b400"].file, ("Brand", 700): faces["b700"].file,
             ("Noto Sans Symbols 2", 400): SYMBOLS}
    got = _faces(svg)
    assert {(fam, w, st) for fam, w, st, _ in got} == set(want)
    assert all(data == Path(files[fam, w]).read_bytes() for fam, w, _, data in got)        # byte for byte (0.4)


LINKS = [  # (id, items(faces), expected style text)
    ("one-weight", lambda f: [_text(["Hi"], f["b400"])],
     "@import url('https://fonts.googleapis.com/css2?family=Brand:wght@400&display=swap');"),
    ("weights-sorted", lambda f: [_text(["Hi"], f["b700"]), _text(["Hi"], f["b400"])],
     "@import url('https://fonts.googleapis.com/css2?family=Brand:wght@400;700&display=swap');"),
    ("italic-axis", lambda f: [_text(["Hi"], f["b700"]), _text(["Hi"], f["b400i"])],
     "@import url('https://fonts.googleapis.com/css2?family=Brand:ital,wght@0,700;1,400&display=swap');"),
    ("one-import-per-family", lambda f: [_text(["a ★"], f["b400"], [[Run("a ", f["b400"]), Run("★", f["sym"])]])],
     "@import url('https://fonts.googleapis.com/css2?family=Brand:wght@400&display=swap');"
     "@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Symbols+2:wght@400&display=swap');"),
]


@pytest.mark.parametrize("make,style", [s[1:] for s in LINKS], ids=[s[0] for s in LINKS])
def test_link_imports_google_fonts(faces, make, style):
    svg = to_svg(_scene(*make(faces)), fonts="link")
    assert _style(svg) == style                     # parsed: the XML escapes '&' as &amp;
    assert "@font-face" not in svg and "base64" not in svg


def test_fonts_without_files_are_never_embedded():
    sc = _scene(_text(["Hi"], _f()))
    assert {_style(to_svg(sc, fonts=m)) for m in ("subset", "embed", "link")} == {""}


def test_subset_is_the_default(brand):
    d = Diagram("F", "Fonts")
    d.box("Hello", id="a", x=200, y=200, w=400, h=120)
    sc = build_scene(d, brand)
    assert to_svg(sc) == to_svg(sc, fonts="subset") != to_svg(sc, fonts="embed")


def test_short_title_subset_svg_under_a_quarter_of_embed(brand):
    assert Path(brand.font("body").file).stat().st_size > 400_000                     # a ~400 KB face
    d = Diagram("F", "Fonts")
    d.box("Hello", id="a", x=200, y=200, w=400, h=120)
    sc = build_scene(d, brand)
    assert len(to_svg(sc, fonts="subset")) < 0.25 * len(to_svg(sc, fonts="embed"))


def test_scene_text_everywhere_is_collected(brand):
    """Node, zone label, edge pill, table cell and chrome texts all reach their face's subset."""
    d = Diagram("F", "TQ")                       # upper case: zone labels are drawn upper-cased
    with d.zone("ZR", x=100, y=150, w=1200, h=600):
        d.box("AB", id="a", x=200, y=300, w=300, h=120)
        d.box("CD", id="b", x=800, y=300, w=300, h=120)
    d.edge("a", "b", "EF")
    d.table(["GH"], [["IJ"]], x=200, y=800, widths=[200])
    svg = to_svg(build_scene(d, brand), fonts="subset")
    drawn = set().union(*(_cmap(data) for *_, data in _faces(svg)))
    assert set("TQZRABCDEFGHIJ") <= drawn


BAD_MODES = ["woff", "", "SUBSET"]


@pytest.mark.parametrize("mode", BAD_MODES, ids=["woff", "empty", "upper"])
def test_invalid_mode(mode):
    from spinagram.backends import get_backend
    from spinagram.backends.png import PngBackend

    msg = f"fonts must be subset, embed or link, not {mode!r}"
    for make in (lambda: to_svg(_scene(), fonts=mode), lambda: get_backend("svg", fonts=mode),
                 lambda: PngBackend(fonts=mode)):
        with pytest.raises(ValueError) as err:
            make()
        assert str(err.value) == msg


@pytest.mark.parametrize("mode", ["subset", "embed", "link"])
def test_api_backend_options(tmp_path, brand, mode):
    from spinagram.api import render

    d = Diagram("F", "Fonts")
    d.box("Hello", id="a", x=200, y=200, w=400, h=120)
    out = render([d], tmp_path, theme=brand, formats=["svg"], backend_options={"svg": {"fonts": mode}})
    svg = next(p for p in out if p.suffix == ".svg").read_text()
    assert svg == to_svg(build_scene(d, brand), fonts=mode)


def _spec(tmp_path):
    (tmp_path / "s.yaml").write_text("id: F1\ntitle: Fonts\nnodes:\n  - {id: a, title: Hello, x: 200, y: 200, w: 400, h: 120}\n")
    return tmp_path / "s.yaml"


@pytest.mark.parametrize("args,mode", [([], "subset"), (["--fonts", "subset"], "subset"),
                                       (["--fonts", "embed"], "embed"), (["--fonts", "link"], "link")],
                         ids=["default", "subset", "embed", "link"])
def test_cli_render_fonts(tmp_path, capsys, brand, args, mode):
    from spinagram import load
    from spinagram.cli import main

    spec = _spec(tmp_path)
    assert main(["render", str(spec), "-t", str(brand.root), "-f", "svg", "-o", str(tmp_path / "out"),
                 "--no-gallery", *args]) == 0
    svg = next((tmp_path / "out").glob("*.svg")).read_text()
    assert svg == to_svg(build_scene(load(spec)[0], brand), fonts=mode)


def test_cli_render_invalid_fonts(tmp_path, capsys):
    from spinagram.cli import main

    with pytest.raises(SystemExit) as err:
        main(["render", str(_spec(tmp_path)), "-f", "svg", "--fonts", "woff"])
    assert err.value.code == 2
    assert "argument --fonts: invalid choice: 'woff'" in capsys.readouterr().err  # choices quoting varies by Python


@pytest.mark.parametrize("args,mode", [([], "subset"), (["--fonts", "embed"], "embed")], ids=["default", "embed"])
def test_png_renders_the_svg_of_the_same_mode(tmp_path, monkeypatch, brand, args, mode):
    pytest.importorskip("playwright")
    from spinagram.backends import png
    from spinagram.cli import main

    seen = []
    real = png.to_svg

    def spy(sc, fonts="subset"):
        seen.append(fonts)
        return real(sc, fonts=fonts)

    monkeypatch.setattr(png, "to_svg", spy)
    try:
        main(["render", str(_spec(tmp_path)), "-t", str(brand.root), "-f", "png", "-o", str(tmp_path / "out"),
              "--no-gallery", *args])
    except Exception as exc:  # noqa: BLE001 - no browser installed
        if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc):
            pytest.skip("chromium not installed for playwright")
        raise
    assert seen == [mode] and next((tmp_path / "out").glob("*.png")).stat().st_size > 0

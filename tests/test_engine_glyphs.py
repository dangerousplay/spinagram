"""Glyph fallback (layout-engine TXT-10..15)."""
import re
import string

import pytest

from spinagram import Diagram, Theme, build_scene
from spinagram.backends.svg import to_svg
from spinagram.engine.glyphs import chain, runs
from spinagram.scene import Shape
from spinagram.text import BUNDLED, _plain, bundled_fonts, covers, measure

ASCII = string.printable.strip() + " "


def make_font(path, chars, family):
    """A TTF whose cmap holds exactly ``chars`` (empty outlines, 600-unit advances)."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    names = [".notdef"] + [f"u{ord(c):04X}" for c in chars]
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap({ord(c): f"u{ord(c):04X}" for c in chars})
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0)), pen.lineTo((0, 10)), pen.lineTo((10, 10)), pen.closePath()
    glyph = pen.glyph()
    fb.setupGlyf({n: glyph for n in names})
    fb.setupHorizontalMetrics({n: (600, 0) for n in names})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": family, "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost()
    fb.save(str(path))
    return path


@pytest.fixture
def theme(tmp_path):
    """Heading font: ASCII only (like a display font without '×'); body font: ASCII + Latin-1 symbols."""
    import yaml
    head = make_font(tmp_path / "head.ttf", ASCII, "Head")
    body = make_font(tmp_path / "body.ttf", ASCII + "×·", "Body")
    data = {"fonts": {"heading": {"family": "Head", "files": {"400": str(head), "700": str(head)}},
                      "body": {"family": "Body", "files": {"400": str(body), "700": str(body)}}}}
    (tmp_path / "theme.yaml").write_text("extends: default\n" + yaml.safe_dump(data))
    return Theme.load(tmp_path)


def test_bundled_fonts_ship_with_licence():
    assert all(p.exists() for _, p in BUNDLED) and (BUNDLED[0][1].parent / "OFL.txt").exists()


CHAIN = [
    # id, char, role, expected font for that char
    ("heading-times-to-body", "×", "heading", "Body"),
    ("heading-middot-to-body", "·", "heading", "Body"),
    ("heading-arrow-to-math", "→", "heading", "Noto Sans Math"),
    ("heading-warning-to-symbols", "⚠", "heading", "Noto Sans Symbols 2"),
    ("body-check-to-symbols", "✓", "body", "Noto Sans Symbols 2"),
    ("body-times-stays", "×", "body", "Body"),
    ("ascii-stays", "A", "heading", "Head"),
]


@pytest.mark.parametrize("ch,role,family", [c[1:] for c in CHAIN], ids=[c[0] for c in CHAIN])
def test_fallback_chain_per_character(theme, ch, role, family):  # TXT-10, TXT-11
    f = theme.font(role, 700 if role == "heading" else 400, 24)
    got = runs(f"a{ch}b", f, chain(f, theme))
    assert next(r.font.family for r in got if ch in r.text) == family
    assert "".join(r.text for r in got) == f"a{ch}b"


def test_chain_order_is_body_then_bundled(theme):  # TXT-11
    assert [f.family for f in chain(theme.font("heading", 700, 24), theme)] == \
        ["Body", "Noto Sans Symbols 2", "Noto Sans Math"]


def test_font_without_file_never_falls_back():  # no cmap: the renderer falls back on its own
    f = Theme.load("default").font("body", 400, 18)
    assert f.file is None and all(covers(f, ch) for ch in "× → ⚠ ✓ ·")


ACCEPTANCE = "× → ⚠ ✓ ·"


@pytest.mark.parametrize("role", ["heading", "body"])
def test_every_role_renders_the_acceptance_string(theme, role):  # roadmap T2 acceptance: no tofu
    d = Diagram("G", "Glyphs")
    d.box(ACCEPTANCE if role == "heading" else "T", id="n", x=200, y=200, w=600, h=200,
          text=ACCEPTANCE if role == "body" else None)
    sc = build_scene(d, theme)
    s = next(i for i in sc.items if isinstance(i, Shape) and i.id == "n")
    blk = s.label.blocks[0] if role == "heading" else s.label.blocks[-1]
    for line in blk.runs:
        for r in line:
            assert all(ch.isspace() or covers(r.font, ch) for ch in r.text)     # every glyph has a font
    assert {(ch, role) for ch, rl, _ in sc.fallbacks if rl == role} >= {("→", role), ("⚠", role), ("✓", role)}


def test_block_without_missing_glyphs_has_no_runs(theme):
    d = Diagram("G", "Glyphs")
    d.box("Plain title", id="n", x=200, y=200, w=500, h=160)
    s = next(i for i in build_scene(d, theme).items if isinstance(i, Shape) and i.id == "n")
    assert all(b.runs is None for b in s.label.blocks)


@pytest.mark.parametrize("ch", ["⚠", "✓", "→"])
def test_measure_uses_fallback_metrics(theme, ch):  # TXT-15
    f = theme.font("body", 400, 20)
    fb = next(b for b in bundled_fonts(20) if covers(b, ch))
    assert measure(f"ab{ch}", f) == pytest.approx(_plain("ab", f) + _plain(ch, fb))


# SVG (TXT-12) -------------------------------------------------------------------------------------------------
SVG_CASES = [
    ("warning-check", "ok ⚠ ✓", ["Noto Sans Symbols 2"]),
    ("arrows", "a → b ⇄ c", ["Noto Sans Math"]),
    ("both", "⚠ → ✓", ["Noto Sans Symbols 2", "Noto Sans Math"]),
]


@pytest.mark.parametrize("body,families", [c[1:] for c in SVG_CASES], ids=[c[0] for c in SVG_CASES])
def test_svg_draws_fallback_runs_and_embeds_fonts(theme, body, families):
    d = Diagram("G", "Glyphs")
    d.box("Status", id="n", x=200, y=200, w=600, h=160, text=body)
    svg = to_svg(build_scene(d, theme))
    for fam in families:
        assert f"@font-face{{font-family:'{fam}';src:url(data:font/ttf;base64," in svg
        spans = re.findall(rf'<tspan font-family="&apos;{fam}&apos;[^"]*">([^<]+)</tspan>', svg)
        assert spans and all(not covers(theme.font("body", 400, 18), ch) for sp in spans for ch in sp.strip())
    assert body in re.sub(r"<[^>]+>", "", svg).replace("&#160;", " ")   # nothing lost or reordered


def test_svg_without_fallback_is_unchanged(theme):
    d = Diagram("G", "Glyphs")
    d.box("Plain", id="n", x=200, y=200, w=600, h=160, text="text only")
    assert "Noto Sans" not in to_svg(build_scene(d, theme))


# PPTX (TXT-13) ------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("body,char,family", [("ok ⚠ done", "⚠", "Noto Sans Symbols 2"),
                                              ("a → b", "→", "Noto Sans Math"),
                                              ("✓ checked", "✓", "Noto Sans Symbols 2")],
                         ids=["warning", "arrow", "check"])
def test_pptx_writes_fallback_runs(tmp_path, theme, body, char, family):
    pptx = pytest.importorskip("pptx")
    from pptx.oxml.ns import qn

    from spinagram import render
    d = Diagram("G", "Glyphs")
    d.box("Status", id="n", x=200, y=200, w=600, h=160, text=body)
    render([d], tmp_path / "out", theme=theme, formats=["pptx"])
    sh = next(s for s in pptx.Presentation(str(tmp_path / "out" / "diagrams.pptx")).slides[0].shapes
              if s.has_text_frame and body in s.text_frame.text)
    rs = [r for p in sh.text_frame.paragraphs for r in p.runs]
    fb = next(r for r in rs if char in r.text)
    assert fb.text.strip() == char and fb.font.name == family
    assert fb._r.get_or_add_rPr().find(qn("a:sym")).get("typeface") == family
    assert all(r.font.name in ("Head", "Body") for r in rs if char not in r.text)
    assert "".join(r.text for p in sh.text_frame.paragraphs[1:] for r in p.runs) == body


# check (TXT-14) -----------------------------------------------------------------------------------------------
def test_glyph_missing_issue_once_per_char_and_role(theme):
    from spinagram.qa import check
    d = Diagram("G", "Glyphs")
    d.box("Managers default · 2×", id="a", x=200, y=200, w=600, h=160, text="ok ⚠ and ⚠ again")
    d.box("Second · 2×", id="b", x=200, y=500, w=600, h=160)
    got = sorted(str(i) for i in check(build_scene(d, theme)) if i.kind == "glyph-missing")
    assert got == sorted([
        "G:glyphs: glyph-missing — '·' (U+00B7) in heading font, fell back to Body",
        "G:glyphs: glyph-missing — '×' (U+00D7) in heading font, fell back to Body",
        "G:glyphs: glyph-missing — '⚠' (U+26A0) in body font, fell back to Noto Sans Symbols 2",
    ])
    assert all(i.severity == "P1" for i in check(build_scene(d, theme)) if i.kind == "glyph-missing")

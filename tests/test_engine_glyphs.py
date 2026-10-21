"""Glyph fallback (layout-engine TXT-10..15)."""
from pathlib import Path

import pytest

from spinagram import Diagram, Theme, build_scene
from spinagram.engine.glyphs import chain, runs
from spinagram.scene import Shape
from spinagram.text import BUNDLED, covers, measure

THEME = Theme.load("default")
SYMBOLS = "× → ⚠ ✓ ·"
ARIAL_LIKE = [p for p in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
                          "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf") if Path(p).exists()]


def test_bundled_fonts_ship_with_licence():
    root = BUNDLED[0][1].parent
    assert all(p.exists() for _, p in BUNDLED) and (root / "OFL.txt").exists()


def _theme_with_heading(tmp_path, heading_file):
    import yaml
    data = {"fonts": {"heading": {"family": "Thin", "files": {"700": str(heading_file), "400": str(heading_file)}}}}
    (tmp_path / "theme.yaml").write_text("extends: default\n" + yaml.safe_dump(data))
    return Theme.load(tmp_path)


@pytest.fixture
def no_times_font(tmp_path):
    """A heading font without '×': a subset of a bundled font keeping only ASCII-free symbol glyphs."""
    from fontTools import subset
    out = tmp_path / "thin.ttf"
    opts = subset.Options()
    opts.layout_features = []
    font = subset.load_font(str(BUNDLED[1][1]), opts)          # Noto Sans Math: has → but we drop it
    s = subset.Subsetter(opts)
    s.populate(unicodes=[ord("★")])
    s.subset(font)
    subset.save_font(font, str(out), opts)
    return out


CHAIN_CHARS = [
    # id, char, expected fallback family (role font lacks everything but ★)
    ("times-to-body", "×", "Arial"),            # Latin-1: the body font has it
    ("arrow-to-math", "→", "Noto Sans Math"),
    ("warning-to-symbols", "⚠", "Noto Sans Symbols 2"),
    ("check-to-symbols", "✓", "Noto Sans Symbols 2"),
    ("covered-stays", "★", "Thin"),
]


@pytest.mark.parametrize("ch,family", [c[1:] for c in CHAIN_CHARS], ids=[c[0] for c in CHAIN_CHARS])
def test_fallback_chain_per_character(tmp_path, no_times_font, ch, family):  # TXT-10, TXT-11
    th = _theme_with_heading(tmp_path, no_times_font)
    f = th.font("heading", 700, 24)
    got = runs(f"a{ch}b", f, chain(f, th))
    fam = next(r.font.family for r in got if ch in r.text)
    if family == "Thin":
        assert fam == "Thin"
    else:
        # body font (Arial, no file) covers Latin; symbols come from the bundled fonts
        assert fam == family


def test_chain_order_is_body_then_bundled(tmp_path, no_times_font):  # TXT-11
    th = _theme_with_heading(tmp_path, no_times_font)
    fams = [f.family for f in chain(th.font("heading", 700, 24), th)]
    assert fams == ["Arial", "Noto Sans Symbols 2", "Noto Sans Math"]


def test_body_font_catches_latin1_before_bundled(tmp_path, no_times_font):  # TXT-11: '·' is not in bundled fonts
    th = _theme_with_heading(tmp_path, no_times_font)
    f = th.font("heading", 700, 24)
    got = runs("a·b", f, chain(f, th))
    assert next(r.font.family for r in got if "·" in r.text) == "Arial"


@pytest.mark.parametrize("role", ["heading", "body"])
def test_scene_blocks_get_runs_and_fallback_records(tmp_path, no_times_font, role):  # TXT-10, TXT-11
    th = _theme_with_heading(tmp_path, no_times_font)
    d = Diagram("G", "Glyphs")
    d.box("Managers default · 2×" if role == "heading" else "M", id="n", x=200, y=200, w=500, h=160,
          text="ok → next ✓" if role == "body" else None)
    sc = build_scene(d, th)
    s = next(i for i in sc.items if isinstance(i, Shape) and i.id == "n")
    blk = s.label.blocks[0] if role == "heading" else s.label.blocks[-1]
    if role == "heading":
        assert blk.runs is not None and any("×" in r.text and r.font.family == "Arial"
                                            for ln in blk.runs for r in ln)
        assert ("×", "heading", "Arial") in sc.fallbacks
    else:  # default body font has no file: symbol blocks fall back, Latin stays
        assert ("→", "body", "Noto Sans Math") in sc.fallbacks and ("✓", "body", "Noto Sans Symbols 2") in sc.fallbacks


def test_block_without_missing_glyphs_has_no_runs():
    d = Diagram("G", "Glyphs")
    d.box("Plain title", id="n", x=200, y=200, w=500, h=160)
    s = next(i for i in build_scene(d, THEME).items if isinstance(i, Shape) and i.id == "n")
    assert all(b.runs is None for b in s.label.blocks)


@pytest.mark.parametrize("ch", ["⚠", "✓", "→"])
def test_measure_uses_fallback_metrics(ch):  # TXT-15
    from spinagram.text import _plain, bundled_fonts
    f = THEME.font("body", 400, 20)
    fb = next(b for b in bundled_fonts(20) if covers(b, ch))
    assert measure(f"ab{ch}", f) == pytest.approx(_plain("ab", f) + _plain(ch, fb))


# SVG (TXT-12) -------------------------------------------------------------------------------------------------
from spinagram.backends.svg import to_svg  # noqa: E402

SVG_CASES = [
    # id, title, body, expected fallback families
    ("warning-check", "Status", "ok ⚠ ✓", ["Noto Sans Symbols 2"]),
    ("arrows", "Flow", "a → b ⇄ c", ["Noto Sans Math"]),
    ("both", "Mixed", "⚠ → ✓", ["Noto Sans Symbols 2", "Noto Sans Math"]),
]


@pytest.mark.parametrize("title,body,families", [c[1:] for c in SVG_CASES], ids=[c[0] for c in SVG_CASES])
def test_svg_draws_fallback_runs_and_embeds_fonts(title, body, families):
    import re
    d = Diagram("G", "Glyphs")
    d.box(title, id="n", x=200, y=200, w=600, h=160, text=body)
    svg = to_svg(build_scene(d, THEME))
    for fam in families:
        assert f"@font-face{{font-family:'{fam}';src:url(data:font/ttf;base64," in svg
        spans = re.findall(rf'<tspan font-family="&apos;{fam}&apos;[^"]*">([^<]+)</tspan>', svg)
        assert spans and all(not covers(THEME.font("body", 400, 18), ch) for sp in spans for ch in sp.strip())
    text = re.sub(r"<[^>]+>", "", svg).replace("&#160;", " ")
    assert body in text                                                     # nothing lost or reordered


def test_svg_without_fallback_is_unchanged():
    d = Diagram("G", "Glyphs")
    d.box("Plain", id="n", x=200, y=200, w=600, h=160, text="text only")
    assert "Noto Sans" not in to_svg(build_scene(d, THEME))

"""Text measurement and wrapping shared by every backend.

Real glyph advances come from the theme's font files through Pillow. Without a file
the width is estimated from an average advance per character, which errs wide so
text still fits.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .theme import FontRef

_HEURISTIC = {False: 0.53, True: 0.60}  # average advance / size; bold is wider


@lru_cache(maxsize=256)
def _pil_font(path: str, size_tenths: int):
    from PIL import ImageFont

    # Measure at 10x and scale down: Pillow rounds advances to integer pixels.
    return ImageFont.truetype(path, size_tenths)


@lru_cache(maxsize=16)
def _cmap(path: str) -> set[int]:
    from fontTools.ttLib import TTFont

    return set(TTFont(path, lazy=True).getBestCmap() or {})


FONTS_DIR = Path(__file__).resolve().parent / "fonts"
# last links of the glyph fallback chain (role font → body font → these), bundled under OFL
BUNDLED = (("Noto Sans Symbols 2", FONTS_DIR / "NotoSansSymbols2-Regular.ttf"),
           ("Noto Sans Math", FONTS_DIR / "NotoSansMath-Regular.ttf"))
def covers(font: FontRef, ch: str) -> bool:
    """Does ``font`` have a glyph for ``ch``? From its cmap; a font without a file is unknown and counts as
    covering everything (the renderer falls back on its own)."""
    if font.file is None:
        return True
    try:
        return ord(ch) in _cmap(str(font.file))
    except ImportError:
        return True


def bundled_fonts(size: float, weight: int = 400) -> list[FontRef]:
    return [FontRef(family=fam, weight=weight, size=size, file=path, fallback="sans-serif", figma_style="Regular")
            for fam, path in BUNDLED if path.exists()]


def _plain(text: str, font: FontRef) -> float:
    if font.file is not None:
        return _pil_font(str(font.file), max(1, round(font.size * 10))).getlength(text) / 10
    return len(text) * font.size * _HEURISTIC[font.weight >= 600]


def measure(text: str, font: FontRef) -> float:
    """Width of ``text``; characters the font lacks are measured with the bundled fallback that has them."""
    if not text:
        return 0.0
    width, run = 0.0, ""
    for ch in text:
        if ch.isspace() or covers(font, ch):
            run += ch
            continue
        width += _plain(run, font)
        run = ""
        fb = next((f for f in bundled_fonts(font.size, font.weight) if covers(f, ch)), None)
        width += _plain(ch, fb) if fb is not None else font.size * 0.5
    return width + _plain(run, font)


def wrap(text: str, font: FontRef, width: float) -> list[str]:
    """Greedy word wrap to ``width`` pixels. Words longer than a line stay whole."""
    lines: list[str] = []
    cur = ""
    for word in str(text).split():
        cand = f"{cur} {word}" if cur else word
        if cur and measure(cand, font) > width:
            lines.append(cur)
            cur = word
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


def wrap_paragraphs(paragraphs: list[str], font: FontRef, width: float) -> list[str]:
    """Wrap each paragraph; an empty paragraph keeps an empty line."""
    out: list[str] = []
    for p in paragraphs:
        out.extend(wrap(p, font, width) if str(p).strip() else [""])
    return out


def ascent(font: FontRef) -> float:
    """Distance from the top of the em box to the baseline (approximate, font-independent)."""
    return font.size * 0.8


__all__ = ["measure", "wrap", "wrap_paragraphs", "ascent", "Path"]

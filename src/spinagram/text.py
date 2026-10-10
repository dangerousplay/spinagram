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


@lru_cache(maxsize=4096)
def _has_glyph(path: str, ch: str) -> bool:
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return True
    cmap = _cmap(path)
    return ord(ch) in cmap


@lru_cache(maxsize=16)
def _cmap(path: str) -> set[int]:
    from fontTools.ttLib import TTFont

    return set(TTFont(path, lazy=True).getBestCmap() or {})


def measure(text: str, font: FontRef) -> float:
    if not text:
        return 0.0
    if font.file is not None:
        f = _pil_font(str(font.file), max(1, round(font.size * 10)))
        width = f.getlength(text) / 10
        # glyphs missing from the font (e.g. arrows) render with a wider fallback font
        missing = sum(1 for ch in text if ord(ch) > 0x2000 and not _has_glyph(str(font.file), ch))
        return width + missing * font.size * 0.5
    return len(text) * font.size * _HEURISTIC[font.weight >= 600]


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

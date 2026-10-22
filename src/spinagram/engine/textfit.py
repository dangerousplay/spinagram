"""Fit text to a box: wrap at spaces, break long tokens at safe points, shrink, then grow (roadmap T1)."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from ..scene import TextBlock
from ..text import measure, wrap_paragraphs
from ..theme import FontRef

BREAK_ON = "-./:·"
MODES = ("none", "shrink", "grow", "shrink-then-grow")
MIN_SCALE = 0.85
# IPv4 addresses and CIDR blocks are read as one unit: never break inside them
_ATOMIC = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?")


def _segments(token: str, break_on: str) -> list[str]:
    """``token`` cut after each break character that is not inside an IPv4/CIDR run."""
    protected = [(m.start(), m.end()) for m in _ATOMIC.finditer(token)]
    out, start = [], 0
    for i, ch in enumerate(token):
        cut = i + 1
        if ch in break_on and cut < len(token) and not any(a < cut < b for a, b in protected):
            out.append(token[start:cut])
            start = cut
    out.append(token[start:])
    return [s for s in out if s]


def break_token(token: str, font: FontRef, width: float, break_on: str = BREAK_ON) -> list[str]:
    """Lines of ``token`` no wider than ``width``, cut only after ``break_on`` characters (no hyphen added).
    A piece wider than ``width`` with no safe break point stays whole."""
    lines: list[str] = []
    cur = ""
    for seg in _segments(token, break_on):
        if cur and measure(cur + seg, font) > width:
            lines.append(cur)
            cur = seg
        else:
            cur += seg
    if cur:
        lines.append(cur)
    return lines


def wrap_fit(paragraphs: list[str], font: FontRef, width: float, break_on: str = BREAK_ON) -> list[str]:
    """Greedy wrap at spaces; a word wider than ``width`` is broken at safe points (:func:`break_token`)
    and its pieces join the flow like words with no space between them. An empty paragraph keeps a line."""
    out: list[str] = []
    for p in paragraphs:
        if not str(p).strip():
            out.append("")
            continue
        pieces: list[tuple[str, str]] = []  # (text, separator before it)
        for word in str(p).split():
            parts = break_token(word, font, width, break_on) if measure(word, font) > width else [word]
            pieces += [(parts[0], " ")] + [(q, "") for q in parts[1:]]
        cur = ""
        for text, sep in pieces:
            cand = f"{cur}{sep}{text}" if cur else text
            if cur and measure(cand, font) > width:
                out.append(cur)
                cur = text
            else:
                cur = cand
        out.append(cur)
    return out


@dataclass
class BlockSpec:
    """One text block to fit: source paragraphs, font at its base size, line height factor, colour."""
    paragraphs: list[str]
    font: FontRef
    leading: float
    color: str


@dataclass
class FitResult:
    blocks: list[TextBlock]
    height: float      # height the blocks need, gaps included
    strategy: str      # last strategy used: none | wrap | break | shrink | grow
    ok: bool           # every line fits the width and the blocks fit the (possibly grown) height
    size: float        # final size of the first block (for diagnostics)


def _floor_step(sp: BlockSpec, min_scale: float) -> int:
    """Largest whole-px reduction that keeps the block at or above ``min_scale`` of its size."""
    return math.floor(sp.font.size - sp.font.size * min_scale + 1e-9)


def _lay(specs: list[BlockSpec], step: int, width: float, break_on: str, plain: bool,
         min_scale: float = MIN_SCALE) -> list[TextBlock]:
    out = []
    for sp in specs:
        s = min(step, _floor_step(sp, min_scale))
        f = sp.font.with_size(sp.font.size - s) if s else sp.font
        lines = wrap_paragraphs(sp.paragraphs, f, width) if plain else wrap_fit(sp.paragraphs, f, width, break_on)
        out.append(TextBlock(lines=lines, paragraphs=sp.paragraphs, font=f, color=sp.color,
                             leading=f.size * sp.leading))
    return out


def _height(blocks: list[TextBlock], gap: float) -> float:
    return sum(b.height for b in blocks) + gap * max(0, len(blocks) - 1)


def _fits_width(blocks: list[TextBlock], width: float) -> bool:
    return all(measure(ln, b.font) <= width + 0.5 for b in blocks for ln in b.lines)


def fit_blocks(specs: list[BlockSpec], width: float, height: float, mode: str = "shrink",
               min_scale: float = MIN_SCALE, break_on: str = BREAK_ON, gap: float = 10) -> FitResult:
    """Fit ``specs`` into ``width`` x ``height``: wrap at spaces, break tokens at safe points, then (by
    ``mode``) shrink every block in 1 px steps down to ``min_scale`` of its size, then grow the height."""
    if mode not in MODES:
        raise ValueError(f"fit {mode!r}; use one of {', '.join(MODES)}")
    specs = [sp for sp in specs if sp.paragraphs]
    if not specs:
        return FitResult([], 0.0, "none", True, 0.0)
    plain = mode == "none"
    blocks = _lay(specs, 0, width, break_on, plain)
    strategy = "wrap" if plain or all(
        b.lines == wrap_paragraphs(sp.paragraphs, b.font, width) for b, sp in zip(blocks, specs)) else "break"
    if plain or (_fits_width(blocks, width) and _height(blocks, gap) <= height + 0.5):
        return FitResult(blocks, _height(blocks, gap), strategy,
                         _fits_width(blocks, width) and _height(blocks, gap) <= height + 0.5, blocks[0].font.size)
    first_width_fit = blocks if _fits_width(blocks, width) else None
    if "shrink" in mode:
        strategy = "shrink"
        for step in range(1, max(_floor_step(sp, min_scale) for sp in specs) + 1):
            blocks = _lay(specs, step, width, break_on, plain, min_scale)
            if first_width_fit is None and _fits_width(blocks, width):
                first_width_fit = blocks
            if _fits_width(blocks, width) and _height(blocks, gap) <= height + 0.5:
                return FitResult(blocks, _height(blocks, gap), strategy, True, blocks[0].font.size)
    if "grow" in mode:
        if first_width_fit is not None:  # the largest size whose lines fit, taller box
            return FitResult(first_width_fit, _height(first_width_fit, gap), "grow", True,
                             first_width_fit[0].font.size)
        strategy = "grow"  # tried last: no size makes the lines fit the width, so height cannot help
    return FitResult(blocks, _height(blocks, gap), strategy, False, blocks[0].font.size)

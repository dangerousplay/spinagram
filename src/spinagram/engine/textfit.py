"""Fit text to a box: wrap at spaces, break long tokens at safe points, shrink, then grow (roadmap T1)."""
from __future__ import annotations

import re

from ..text import measure
from ..theme import FontRef

BREAK_ON = "-./:·"
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

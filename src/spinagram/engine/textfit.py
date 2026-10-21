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

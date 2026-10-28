"""Font subsetting for embedded SVG fonts: keep only the glyphs a diagram draws (FNT-02, FNT-05, FNT-06)."""
from __future__ import annotations

import io
import warnings
from pathlib import Path

_cache: dict[tuple[str, frozenset[str]], bytes] = {}


def subset(path: str | Path, chars) -> bytes:
    """The font at ``path`` cut down to ``chars`` plus space (those the font maps), in its own flavour (TTF/OTF),
    byte-identical for the same input. Cached per (path, character set). When fontTools cannot subset the font,
    the whole file is returned and a warning says so."""
    key = (str(path), frozenset(chars) | {" "})
    if key in _cache:
        return _cache[key]
    data = Path(path).read_bytes()
    try:
        out = _subset(data, key[1])
    except Exception as exc:  # any fontTools failure: embed the whole font (spec edge case)
        warnings.warn(f"could not subset {path} ({exc}); embedding the whole font", stacklevel=2)
        return data
    _cache[key] = out
    return out


def _subset(data: bytes, chars: frozenset[str]) -> bytes:
    from fontTools import subset as ft
    from fontTools.ttLib import TTFont

    opts = ft.Options()
    opts.name_IDs = ["*"]
    opts.name_languages = ["*"]
    opts.recalc_timestamp = False
    opts.notdef_outline = True
    opts.flavor = None
    opts.bidi_closure = False  # exactly the drawn characters: no mirrored twins ('≤' would add '≥')
    font = TTFont(io.BytesIO(data), recalcTimestamp=False, lazy=False)
    sub = ft.Subsetter(opts)
    sub.populate(unicodes=sorted(ord(c) for c in chars))
    sub.subset(font)
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()

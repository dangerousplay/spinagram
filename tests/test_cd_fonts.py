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

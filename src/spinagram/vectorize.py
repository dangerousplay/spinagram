"""PNG → SVG for icons: colour tracing (vtracer) behind a fidelity gate (resvg render + pixel diff).

A traced SVG is only used when it looks like the PNG: it is rendered back at the source size with
resvg and compared over a neutral grey; the result is accepted when the mean channel difference is
≤ ``MAX_MEAN`` and at most ``MAX_STRONG`` of the pixels differ by more than 128. Anti-aliased edges
pass, photos and heavy gradients do not (they stay PNG).

On by default when the ``vector`` extra is installed (``vtracer`` + ``resvg-py``). Turn it off with
``SPINAGRAM_VECTORIZE=0``, ``icons: {vectorize: false}`` in a theme, or ``vectorize: false`` in an
icon pack. Results — accepted or not — are cached by the PNG's sha256 and ``PARAMS_VERSION``.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

PARAMS = dict(colormode="color", hierarchical="stacked", mode="spline", filter_speckle=2, color_precision=8,
              layer_difference=8, corner_threshold=60, length_threshold=3.5, splice_threshold=45,
              path_precision=3)
PARAMS_VERSION = 1  # bump when PARAMS or the gate change: invalidates cached results
MAX_MEAN = 8.0      # mean |Δ| per channel (0–255) over a grey background
MAX_STRONG = 0.01   # share of pixels with max-channel |Δ| > 128
GREY = (128, 128, 128, 255)

_warned = False


@dataclass
class Score:
    mean: float
    strong: float

    @property
    def accepted(self) -> bool:
        return self.mean <= MAX_MEAN and self.strong <= MAX_STRONG


@dataclass
class Result:
    svg: str | None
    score: Score | None
    accepted: bool
    reason: str = ""


def available() -> bool:
    try:
        import resvg_py  # noqa: F401
        import vtracer  # noqa: F401
    except ImportError:
        return False
    return True


def enabled(flag: bool | None = None) -> bool:
    """Active unless switched off (env / theme / pack flag) or the extra is missing (warns once)."""
    global _warned
    if os.environ.get("SPINAGRAM_VECTORIZE", "").strip().lower() in ("0", "false", "no", "off"):
        return False
    if flag is False:
        return False
    if not available():
        if not _warned:
            warnings.warn("PNG icons stay raster: install the 'vector' extra (vtracer, resvg-py) to vectorize them",
                          stacklevel=2)
            _warned = True
        return False
    return True


def cache_dir() -> Path:
    from .icons import cache_root

    return cache_root().parent / "vector"


# tracing ------------------------------------------------------------------------------------------
def png_to_svg(png: bytes) -> tuple[str, int, int]:
    """Trace a PNG into SVG text (transparency kept); the SVG gets a viewBox so it scales."""
    import vtracer

    im = Image.open(io.BytesIO(png)).convert("RGBA")
    w, h = im.size
    pixels = list(im.get_flattened_data()) if hasattr(im, "get_flattened_data") else list(im.getdata())
    svg = vtracer.convert_pixels_to_svg(pixels, size=(w, h), **PARAMS)
    if "viewBox" not in svg:
        svg = svg.replace("<svg ", f'<svg viewBox="0 0 {w} {h}" ', 1)
    return svg, w, h


def _flat(im: Image.Image) -> Image.Image:
    bg = Image.new("RGBA", im.size, GREY)
    bg.alpha_composite(im.convert("RGBA"))
    return bg.convert("RGB")


def score(png: bytes, svg: str) -> Score:
    """Render the SVG at the PNG's size and measure how far it is from the PNG."""
    import resvg_py

    src = Image.open(io.BytesIO(png)).convert("RGBA")
    w, h = src.size
    out = resvg_py.svg_to_bytes(svg_string=svg, width=w, height=h)
    back = Image.open(io.BytesIO(bytes(out))).convert("RGBA").resize((w, h))
    diff = ImageChops.difference(_flat(src), _flat(back))
    mean = sum(ImageStat.Stat(diff).mean) / 3
    # max-channel difference > 128: threshold each channel, combine with lighter()
    r, g, b = (c.point(lambda v: 255 if v > 128 else 0) for c in diff.split())
    strong_mask = ImageChops.lighter(ImageChops.lighter(r, g), b)
    strong = ImageStat.Stat(strong_mask).mean[0] / 255
    return Score(round(mean, 3), round(strong, 5))


def vectorize_bytes(png: bytes) -> Result:
    try:
        svg, _, _ = png_to_svg(png)
    except Exception as exc:  # noqa: BLE001 — a bad PNG must never break a render
        return Result(None, None, False, f"trace failed: {exc}")
    if "<path" not in svg:
        return Result(None, None, False, "empty trace")
    sc = score(png, svg)
    return Result(svg if sc.accepted else None, sc, sc.accepted,
                  "" if sc.accepted else f"fidelity: mean {sc.mean} > {MAX_MEAN} or strong {sc.strong} > {MAX_STRONG}")


# cache-backed entry point -------------------------------------------------------------------------
def maybe(path: Path, flag: bool | None = None) -> Path:
    """PNG → its cached vector twin when enabled and faithful; any other file is returned unchanged.

    The original PNG is copied next to the SVG (same stem) so backends that need a raster
    (PowerPoint) find it with ``svg.with_suffix('.png')``.
    """
    if path.suffix.lower() != ".png" or not enabled(flag):
        return path
    data = path.read_bytes()
    sha = hashlib.sha256(data + f"|v{PARAMS_VERSION}".encode()).hexdigest()[:32]
    d = cache_dir()
    rec, svg = d / f"{sha}.json", d / f"{sha}.svg"
    if rec.exists():
        meta = json.loads(rec.read_text(encoding="utf-8"))
        return svg if meta.get("accepted") and svg.exists() else path
    d.mkdir(parents=True, exist_ok=True)
    res = vectorize_bytes(data)
    if res.accepted:
        svg.write_text(res.svg, encoding="utf-8")
        shutil.copyfile(path, d / f"{sha}.png")
    rec.write_text(json.dumps({"source": str(path), "accepted": res.accepted, "reason": res.reason,
                               "score": asdict(res.score) if res.score else None, "params": PARAMS_VERSION}),
                   encoding="utf-8")
    return svg if res.accepted else path

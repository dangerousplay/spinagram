"""Icon geometry: intrinsic aspect ratio and fit-by-height placement (roadmap I1)."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from ..scene import Icon

MAX_WIDTH = 4.0  # a wordmark is at most this many heights wide


@lru_cache(maxsize=512)
def _aspect(path: str, mtime: float) -> float:
    p = Path(path)
    if p.suffix.lower() == ".svg":
        text = p.read_text(encoding="utf-8", errors="ignore")[:4000]
        m = re.search(r'viewBox\s*=\s*["\']\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', text)
        if m and float(m.group(2)):
            return float(m.group(1)) / float(m.group(2))
        w = re.search(r'<svg[^>]*\swidth\s*=\s*["\']([\d.]+)', text)
        h = re.search(r'<svg[^>]*\sheight\s*=\s*["\']([\d.]+)', text)
        return float(w.group(1)) / float(h.group(1)) if w and h and float(h.group(1)) else 1.0
    try:
        from PIL import Image

        with Image.open(p) as im:
            return im.width / im.height if im.height else 1.0
    except Exception:  # noqa: BLE001 - unreadable raster: treat as square
        return 1.0


def aspect(path: Path) -> float:
    """Width / height of an icon from its SVG ``viewBox`` (or width/height) or raster size; 1.0 if unknown."""
    p = Path(path)
    return _aspect(str(p), p.stat().st_mtime if p.exists() else 0.0)


def fit(path: Path, height: float, max_width: float | None = None) -> tuple[float, float]:
    """(w, h) of an icon fitted by ``height``, no wider than ``max_width`` (default 4 × height)."""
    a = aspect(path)
    limit = max_width if max_width is not None else MAX_WIDTH * height
    w = height * a
    return (limit, limit / a) if w > limit else (w, height)


def place(path: Path, x: float, slot_y: float, slot_h: float, height: float, max_width: float | None = None,
          center_x: float | None = None) -> Icon:
    """An icon fitted by height and centred vertically in the slot; centred on ``center_x`` when given."""
    w, h = fit(path, height, max_width)
    ix = center_x - w / 2 if center_x is not None else x
    return Icon(path, ix, slot_y + (slot_h - h) / 2, h, w=w)

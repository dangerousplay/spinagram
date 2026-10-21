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


ICON_VARIANTS = ("wordmark", "symbol")


def variant_name(theme, name: str | None, variant: str | None) -> str | None:
    """``name`` swapped for the theme alias ``<name>-<variant>`` when the theme defines one."""
    if not name or variant not in ICON_VARIANTS:
        return name
    alias = ((theme.data.get("icons") or {}).get("alias") or {})
    key = f"{name}-{variant}"
    return key if key in alias else name


MAX_BADGES = 3
BADGE_SCALE, BADGE_MIN, BADGE_INSET, BADGE_HALO, BADGE_GAP = 0.4, 14.0, 6.0, 3.0, 4.0


def badge_size(main_icon: float) -> float:
    return max(BADGE_MIN, main_icon * BADGE_SCALE)


def badges(node_id: str, paths: list[Path], box: tuple[float, float, float, float], size: float) -> tuple[list, float]:
    """Halo + icon shapes for up to three corner badges, from the top-right corner leftward, and the x of the
    leftmost halo (text must end before it)."""
    from ..scene import Shape

    x, y, w, _ = box
    halo = size + 2 * BADGE_HALO
    right = x + w - BADGE_INSET
    items, left = [], right
    for k, p in enumerate(paths):
        hx = right - (k + 1) * halo - k * BADGE_GAP
        hy = y + BADGE_INSET
        bw, bh = fit(p, size, size)
        items.append(Shape(id=f"{node_id}-badge{k}-halo", kind="rect", x=hx, y=hy, w=halo, h=halo, fill="#FFFFFF",
                           radius=halo / 2, role="node-part"))
        ix, iy = hx + (halo - bw) / 2, hy + (halo - bh) / 2
        items.append(Shape(id=f"{node_id}-badge{k}", kind="rect", x=ix, y=iy, w=bw, h=bh, fill=None,
                           icon=Icon(p, ix, iy, bh, w=bw), role="node-part"))
        left = hx
    return items, left

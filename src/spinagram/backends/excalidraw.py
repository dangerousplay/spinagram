"""Excalidraw: native ``.excalidraw`` scenes, one file per diagram.

Clean, theme-true style: ``roughness`` 0, solid fills and the theme's colours. Boxes and diamonds are
native shapes; a frame named ``spinagram:<id>`` holds the slide. Ids, seeds and nonces derive from the
scene item ids, so the same spec writes the same bytes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Sequence

from .. import shapes as _shapes
from ..scene import Scene, Shape

SOURCE = "https://github.com/dangerousplay/spinagram"
_BACK, _FRONT = ("zone", "chrome"), ("pill", "swatch")


def _n(v: float) -> float:
    v = round(v, 2)
    return int(v) if v == int(v) else v


def _seed(key: str) -> int:
    return int.from_bytes(hashlib.sha1(key.encode()).digest()[:4], "big") % 2_000_000_000


def _flatten(sp: _shapes.Subpath) -> list[tuple[float, float]]:
    """A subpath as points: line ends, and 8 points per cubic Bézier."""
    cur, out = sp.start, [sp.start]
    for cmd, pts in sp.segments:
        if cmd == "L":
            cur = pts[0]
            out.append(cur)
            continue
        (x1, y1), (x2, y2), (x3, y3) = pts
        for i in range(1, 9):
            t = i / 8
            a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
            out.append((a * cur[0] + b * x1 + c * x2 + d * x3, a * cur[1] + b * y1 + c * y2 + d * y3))
        cur = (x3, y3)
    if sp.closed and out[-1] != out[0]:
        out.append(out[0])  # an Excalidraw polygon ends on its first point
    return out


def _style(dashed: bool, dash: list[float] | None) -> str:
    if dash:
        return "dotted" if dash[0] <= 2 else "dashed"
    return "dashed" if dashed else "solid"


class _Doc:
    def __init__(self, scene: Scene):
        self.scene = scene
        self.elements: list[dict] = []
        self.ids: set[str] = set()

    def uid(self, key: str) -> str:
        out, n = key, 1
        while out in self.ids:
            n += 1
            out = f"{key}~{n}"
        self.ids.add(out)
        return out

    def add(self, key: str, type: str, x: float, y: float, w: float, h: float, **fields) -> dict:
        id = self.uid(key)
        el = {"id": id, "type": type, "x": _n(x), "y": _n(y), "width": _n(w), "height": _n(h), "angle": 0,
              "strokeColor": "transparent", "backgroundColor": "transparent", "fillStyle": "solid",
              "strokeWidth": 1, "strokeStyle": "solid", "roughness": 0, "opacity": 100, "groupIds": [],
              "frameId": None, "roundness": None, "seed": _seed(id), "version": 1, "versionNonce": _seed(id + "#"),
              "isDeleted": False, "boundElements": None, "updated": 1, "link": None, "locked": False}
        el.update(fields)
        self.elements.append(el)
        return el

    def polyline(self, key: str, pts: list[tuple[float, float]], **fields) -> dict:
        x0, y0 = pts[0]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return self.add(key, fields.pop("type", "line"), x0, y0, max(xs) - min(xs), max(ys) - min(ys),
                        points=[[_n(x - x0), _n(y - y0)] for x, y in pts], **fields)

    def shape(self, s: Shape) -> None:
        paint = {"backgroundColor": s.fill or "transparent", "strokeStyle": _style(s.dashed, s.dash),
                 "opacity": round(s.opacity * s.fill_opacity * 100)}
        if s.stroke and s.stroke_width:
            paint |= {"strokeColor": s.stroke, "strokeWidth": _n(s.stroke_width)}
        if s.parts:
            group = [f"g:{s.id}"]
            for part in s.parts:
                p = dict(paint)
                if part.paint == "solid":
                    p |= {"backgroundColor": s.stroke or s.fill or "transparent", "strokeColor": "transparent",
                          "strokeWidth": 1}
                elif part.paint == "stroke":
                    p["backgroundColor"] = "transparent"
                for sp in _shapes.parse(part.d):
                    self.polyline(s.id, _flatten(sp), polygon=sp.closed, groupIds=group, **p)
            return
        if s.kind == "diamond":
            self.add(s.id, "diamond", s.x, s.y, s.w, s.h, **paint)
            return
        radius = s.h / 2 if s.kind == "pill" else s.radius
        self.add(s.id, "rectangle", s.x, s.y, s.w, s.h, **paint,
                 roundness={"type": 3, "value": _n(radius)} if radius else None)

    def build(self) -> dict:
        sc = self.scene
        frame = self.add(f"frame:{sc.id}", "frame", 0, 0, sc.width, sc.height, name=f"spinagram:{sc.id}")

        def layer(it) -> int:
            role = getattr(it, "role", None)
            return 0 if role in _BACK else 2 if role in _FRONT else 1

        for it in sorted(sc.items, key=layer):
            if isinstance(it, Shape):
                self.shape(it)
        for el in self.elements[1:]:
            el["frameId"] = frame["id"]
        return {"type": "excalidraw", "version": 2, "source": SOURCE, "elements": self.elements,
                "appState": {"viewBackgroundColor": sc.background, "gridSize": None}, "files": {}}


def to_excalidraw(scene: Scene) -> dict:
    """The ``.excalidraw`` document of ``scene``."""
    return _Doc(scene).build()


class ExcalidrawBackend:
    name = "excalidraw"

    def render(self, scenes: Sequence[Scene], out_dir: Path) -> list[Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for sc in scenes:
            p = out_dir / f"{sc.slug}.excalidraw"
            p.write_text(json.dumps(to_excalidraw(sc), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            paths.append(p)
        return paths

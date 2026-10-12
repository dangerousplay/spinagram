"""Self-contained SVG: fonts and images embedded as data URIs."""
from __future__ import annotations

import base64
import html
from functools import lru_cache
from pathlib import Path
from typing import Sequence

from ..scene import Cell, Connector, Icon, Image, Label, Line, Scene, Shape, TableGrid, Text, TextBlock

DASH = ' stroke-dasharray="10 7"'


def _dash(dashed: bool, pattern: list[float] | None) -> str:
    if pattern:
        return f' stroke-dasharray="{" ".join(f"{v:g}" for v in pattern)}"'
    return DASH if dashed else ""


_MARKERS = {  # kind → marker body (viewBox 0 0 10 10); {c} = colour
    "open-arrow": '<path d="M1,1 L9,5 L1,9" fill="none" stroke="{c}" stroke-width="1.5"/>',
    "diamond": '<path d="M0,5 L5,0 L10,5 L5,10 z" fill="{c}"/>',
    "open-diamond": '<path d="M0,5 L5,0 L10,5 L5,10 z" fill="#FFFFFF" stroke="{c}" stroke-width="1.2"/>',
    "circle": '<circle cx="5" cy="5" r="4" fill="{c}"/>',
    "bar": '<path d="M8,0 L8,10" stroke="{c}" stroke-width="2"/>',
}


@lru_cache(maxsize=None)
def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def _esc(s) -> str:
    return html.escape(str(s), quote=False)


def _attr(s) -> str:
    return html.escape(str(s), quote=True)


def _mime(path: Path) -> str:
    return {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".otf": "font/otf", ".ttf": "font/ttf", ".woff2": "font/woff2", ".woff": "font/woff"}.get(
        path.suffix.lower(), "application/octet-stream")


def _family(block: TextBlock) -> str:
    return f"&apos;{_attr(block.font.family)}&apos;, {_attr(block.font.fallback)}"


class _Svg:
    def __init__(self, scene: Scene):
        self.s = scene
        self.defs: list[str] = []
        self.back: list[str] = []
        self.mid: list[str] = []
        self.front: list[str] = []
        self._markers: set[str] = set()
        self._filters: dict[tuple, str] = {}

    # primitives ---------------------------------------------------------------
    def text_lines(self, out: list[str], block: TextBlock, x: float, baseline: float, anchor: str,
                   letter_spacing: float = 0) -> None:
        f = block.font
        spans = "".join(f'<tspan x="{x:.1f}" dy="{0 if i == 0 else block.leading:.1f}">{_esc(line) or "&#160;"}</tspan>'
                        for i, line in enumerate(block.lines))
        ls = f' letter-spacing="{letter_spacing}"' if letter_spacing else ""
        style = ' font-style="italic"' if f.italic else ""
        out.append(f'<text x="{x:.1f}" y="{baseline:.1f}" font-family="{_family(block)}" font-size="{f.size:g}" '
                   f'font-weight="{f.weight}"{style} fill="{block.color}" text-anchor="{anchor}"{ls}>{spans}</text>')

    def label(self, out: list[str], label: Label) -> None:
        anchor = "middle" if label.align == "center" else "start"
        for block, x, top in label.place():
            self.text_lines(out, block, x, top + block.baseline_offset(), anchor)

    def image(self, out: list[str], path: Path, x: float, y: float, w: float, h: float) -> None:
        out.append(f'<image x="{x:.1f}" y="{y:.1f}" width="{w:g}" height="{h:g}" '
                   f'href="data:{_mime(path)};base64,{_b64(path)}"/>')

    def icon(self, out: list[str], icon: Icon) -> None:
        self.image(out, icon.path, icon.x, icon.y, icon.size, icon.size)

    def shadow(self, sh: tuple | None) -> str:
        """`` filter="url(#…)"`` for a CSS box-shadow (one drop shadow), defined once per value."""
        if not sh:
            return ""
        if sh not in self._filters:
            fid = f"sh{len(self._filters)}"
            dx, dy, blur, color, alpha = sh
            self.defs.append(f'<filter id="{fid}" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow '
                             f'dx="{dx:g}" dy="{dy:g}" stdDeviation="{blur / 2:g}" flood-color="{color}" '
                             f'flood-opacity="{alpha:g}"/></filter>')
            self._filters[sh] = fid
        return f' filter="url(#{self._filters[sh]})"'

    def marker(self, color: str, kind: str = "arrow") -> str:
        if kind != "arrow" and kind in _MARKERS:
            mid = f"m{kind}-{color.strip('#')}"
            if mid not in self._markers:
                self._markers.add(mid)
                self.defs.append(f'<marker id="{mid}" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="8" '
                                 f'markerHeight="8" orient="auto-start-reverse">{_MARKERS[kind].format(c=color)}</marker>')
            return mid
        mid = "m" + color.strip("#")
        if mid not in self._markers:
            self._markers.add(mid)
            self.defs.append(f'<marker id="{mid}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
                             f'markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" '
                             f'fill="{color}"/></marker>')
        return mid

    def tip(self, item_id: str) -> str:
        """<title> tooltip with the provenance of the facts shown on an item."""
        ids = self.s.item_facts.get(item_id) or []
        if not ids:
            return ""
        text = "\n\n".join(self.s.meta_tooltips.get(i, i) for i in ids)
        return f"<title>{_esc(text)}</title>"

    @staticmethod
    def _with_tip(el: str, tag: str, tip: str) -> str:
        return el[:-2] + f">{tip}</{tag}>" if tip and el.endswith("/>") else el

    # items --------------------------------------------------------------------
    def shape(self, s: Shape) -> None:
        layer = self.back if s.role in ("zone", "chrome") else (self.front if s.role in ("pill", "swatch") else self.mid)
        stroke = (f' stroke="{s.stroke}" stroke-width="{s.stroke_width:g}"' if s.stroke and s.stroke_width
                  else "")
        dash = _dash(s.dashed, s.dash)
        op = f' opacity="{s.opacity:g}"' if s.opacity < 1 else ""
        op += self.shadow(s.shadow)
        fill = s.fill or "none"
        fop = f' fill-opacity="{s.fill_opacity:g}"' if s.fill_opacity < 1 and s.fill else ""
        if s.parts:
            for i, part in enumerate(s.parts):
                if part.paint == "solid":
                    paint = f'fill="{s.stroke or fill}"'
                elif part.paint == "stroke":
                    paint = f'fill="none" stroke="{s.stroke}" stroke-width="{s.stroke_width:g}"'
                else:
                    paint = f'fill="{fill}"{fop}{stroke}'
                el = f'<path d="{part.d}" {paint}{dash}{op}/>'
                layer.append(self._with_tip(el, "path", self.tip(s.id)) if i == 0 else el)
        elif s.kind == "diamond":
            cx, cy = s.x + s.w / 2, s.y + s.h / 2
            pts = f"{cx:.1f},{s.y:.1f} {s.x + s.w:.1f},{cy:.1f} {cx:.1f},{s.y + s.h:.1f} {s.x:.1f},{cy:.1f}"
            layer.append(self._with_tip(f'<polygon points="{pts}" fill="{fill}"{fop}{stroke}{dash}{op}/>', "polygon",
                                        self.tip(s.id)))
        else:
            layer.append(self._with_tip(f'<rect x="{s.x:.1f}" y="{s.y:.1f}" width="{s.w:.1f}" height="{s.h:.1f}" '
                                        f'rx="{s.radius:g}" fill="{fill}"{fop}{stroke}{dash}{op}/>', "rect", self.tip(s.id)))
        tl = self.front if s.role != "zone" else self.back
        if s.icon:
            self.icon(self.front, s.icon)
        if s.label:
            self.label(tl, s.label)

    def connector(self, c: Connector) -> None:
        pts = c.points
        if c.route == "curve":
            (x1, y1), (cx, cy), (x2, y2) = pts
            d = f"M{x1:.1f},{y1:.1f} Q{cx:.1f},{cy:.1f} {x2:.1f},{y2:.1f}"
        else:
            d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        ends = (f' marker-end="url(#{self.marker(c.color, c.marker_end)})"' if c.arrow_end else "") + (
            f' marker-start="url(#{self.marker(c.color, c.marker_start)})"' if c.arrow_start else "")
        op = f' opacity="{c.opacity:g}"' if c.opacity < 1 else ""
        self.mid.append(f'<path d="{d}" fill="none" stroke="{c.color}" stroke-width="{c.width:g}"'
                        f'{_dash(c.dashed, c.dash)}{op}{ends}/>')
        if c.label:
            self.shape(c.label)

    def table(self, t: TableGrid) -> None:
        x0, total = t.x, t.w
        y = t.y
        for r, (rh, row) in enumerate(zip(t.row_heights, t.cells)):
            if r == 0:
                fill = row[0].fill if row else "none"
                self.mid.append(f'<rect x="{x0:.1f}" y="{y:.1f}" width="{total:.1f}" height="{rh:.1f}" '
                                f'rx="{t.header_radius:g}" fill="{fill}"/>')
            else:
                self.mid.append(f'<rect x="{x0:.1f}" y="{y:.1f}" width="{total:.1f}" height="{rh:.1f}" '
                                f'fill="{row[0].fill}"/>')
                self.mid.append(f'<line x1="{x0:.1f}" y1="{y + rh:.1f}" x2="{x0 + total:.1f}" y2="{y + rh:.1f}" '
                                f'stroke="{t.border}" stroke-width="1"/>')
            cx = x0
            for wcol, cell in zip(t.col_widths, row):
                self.cell(cell, cx, y, wcol, rh)
                cx += wcol
            y += rh
        tip = self.tip(t.id)
        if tip:
            self.front.append(f'<rect x="{t.x:.1f}" y="{t.y:.1f}" width="{t.w:.1f}" height="{t.h:.1f}" fill="none" '
                              f'pointer-events="all">{tip}</rect>')

    def cell(self, cell: Cell, x: float, y: float, w: float, h: float) -> None:
        if cell.icon:
            self.image(self.front, cell.icon.path, x + 14, y + (h - cell.icon.size) / 2, cell.icon.size,
                       cell.icon.size)
        b = cell.block
        top = y + (h - b.height) / 2
        self.text_lines(self.front, b, x + cell.pad_left, top + b.baseline_offset(), "start")

    def render(self) -> str:
        s = self.s
        for it in s.items:
            if isinstance(it, Shape):
                self.shape(it)
            elif isinstance(it, Connector):
                self.connector(it)
            elif isinstance(it, Text):
                layer = self.back if it.id.startswith("z") else self.front
                self.text_lines(layer, it.block, it.x, it.y, it.anchor, it.letter_spacing)
                tip = self.tip(it.id)
                if tip:
                    layer[-1] = layer[-1].replace("</text>", f"{tip}</text>", 1)
            elif isinstance(it, Line):
                self.front.append(f'<line x1="{it.x1:.1f}" y1="{it.y1:.1f}" x2="{it.x2:.1f}" y2="{it.y2:.1f}" '
                                  f'stroke="{it.color}" stroke-width="{it.width:g}"/>')
            elif isinstance(it, Image):
                self.image(self.front, it.path, it.x, it.y, it.w, it.h)
            elif isinstance(it, TableGrid):
                self.table(it)
        faces = []
        for f in s.fonts():
            if f.file:
                faces.append(f"@font-face{{font-family:'{f.family}';src:url(data:{_mime(f.file)};base64,"
                             f"{_b64(f.file)});font-weight:{f.weight};font-style:{'italic' if f.italic else 'normal'}}}")
        W, H = s.width, s.height
        meta = ""
        if s.sources:
            import json as _json
            meta = f'<metadata id="spinagram-sources">{_esc(_json.dumps(s.sources, ensure_ascii=False))}</metadata>'
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:g} {H:g}" width="{W:g}" height="{H:g}">'
                f'<title>{_esc(s.title)}</title>{meta}<defs><style>{"".join(faces)}</style>{"".join(self.defs)}</defs>'
                f'<rect width="{W:g}" height="{H:g}" fill="{s.background}"/>'
                + "".join(self.back) + "".join(self.mid) + "".join(self.front) + "</svg>")


def to_svg(scene: Scene) -> str:
    return _Svg(scene).render()


class SvgBackend:
    name = "svg"

    def render(self, scenes: Sequence[Scene], out_dir: Path) -> list[Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for sc in scenes:
            p = out_dir / f"{sc.slug}.svg"
            p.write_text(to_svg(sc), encoding="utf-8")
            paths.append(p)
        return paths

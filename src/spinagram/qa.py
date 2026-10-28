"""Layout checks on a resolved scene: text that does not fit its box."""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass

from .scene import Connector, Scene, Shape, TableGrid, Text
from .text import measure


# P0: the diagram renders wrong; P1: visibly degraded; P2: advisory. Unlisted kinds are P1.
SEVERITY = {"overflow-x": "P0", "overflow-y": "P0", "overflow": "P0", "label-collision": "P0",
            "icon-touches-border": "P0", "header-overlap": "P0", "icon-overflows-box": "P0",
            "outside-safe-area": "P0", "zone-clips-child": "P0", "glyph-missing": "P1", "low-contrast": "P1",
            "zone-underused": "P2", "edge-crossings": "P2", "icon-size-mismatch": "P2", "not-straight": "P2",
            "version-mismatch": "P2", "style": "P2", "edge-through-box": "P1",
            "edge-crosses-zone-header": "P0", "icon-overlaps-text": "P0", "icon-generic-for-service": "P2"}


@dataclass
class Issue:
    scene: str
    item: str
    kind: str
    detail: str
    fix: dict | None = None    # machine-readable fix: {"op": "move-label" | "resize" | "nudge" | "shrink-font", ...}
    severity: str | None = None

    def __post_init__(self) -> None:
        if self.severity is None:
            self.severity = SEVERITY.get(self.kind, "P1")

    def __str__(self) -> str:
        return f"{self.scene}:{self.item}: {self.kind} — {self.detail}"

    def to_dict(self) -> dict:
        return asdict(self)


def behavior_issues(d) -> list[tuple[str, str]]:
    """Model-level rules for behavior diagrams: (item, message) pairs."""
    out: list[tuple[str, str]] = []
    kinds = {n.id: n.kind for n in d.nodes}
    outgoing: dict[str, int] = {}
    for e in d.edges:
        src = e.src.partition(".")[0] if isinstance(e.src, str) else None
        if src:
            outgoing[src] = outgoing.get(src, 0) + 1
    for n in d.nodes:
        k = outgoing.get(n.id, 0)
        if n.kind == "decision" and k < 2:
            out.append((n.id, f"decision {n.id} has {k} outgoing edges (expected ≥ 2)"))
        if n.kind == "fork" and k < 2:
            out.append((n.id, f"fork {n.id} has {k} branch"))
    in_group = {c for g in d.groups for c in g.children}
    scopes = [(d.id, [n.id for n in d.nodes if n.id not in in_group])] + [(g.id, g.children) for g in d.groups]
    for sid, children in scopes:
        direct = [kinds.get(c) for c in children]
        if "state" in direct and "initial" not in direct:
            out.append((sid, f"region {sid} has no initial state"))
    return out


def segment_hits(p, q, rect, inset: float = 1.0) -> bool:
    """Does segment p→q enter the interior of ``rect`` (x, y, w, h) shrunk by ``inset``? (Liang-Barsky)"""
    x, y, w, h = rect
    x0, y0, x1, y1 = x + inset, y + inset, x + w - inset, y + h - inset
    if x1 <= x0 or y1 <= y0:
        return False
    (px, py), (qx, qy) = p, q
    dx, dy = qx - px, qy - py
    t0, t1 = 0.0, 1.0
    for pk, qk in ((-dx, px - x0), (dx, x1 - px), (-dy, py - y0), (dy, y1 - py)):
        if pk == 0:
            if qk < 0:
                return False
            continue
        t = qk / pk
        if pk < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return t1 - t0 > 1e-9


def polyline(c: Connector) -> list[tuple[float, float]]:
    """A connector's path as points (a quadratic curve sampled in 24 steps)."""
    if c.route != "curve":
        return list(c.points)
    (x0, y0), (qx, qy), (x2, y2) = c.points
    return [((1 - t) ** 2 * x0 + 2 * (1 - t) * t * qx + t * t * x2, (1 - t) ** 2 * y0 + 2 * (1 - t) * t * qy + t * t * y2)
            for t in (i / 24 for i in range(25))]


def edges_through_boxes(scene: Scene) -> list[Issue]:
    """Edges crossing a node they do not connect. Zones are never obstacles, so an edge that ends on a zone
    border (a group target) is never reported for that zone."""
    nodes = [s for s in scene.items if isinstance(s, Shape) and s.role == "node"]
    out = []
    for c in (i for i in scene.items if isinstance(i, Connector)):
        ends = {b.shape_id for b in (c.src, c.dst) if b is not None}
        pts = polyline(c)
        for s in nodes:
            if s.id in ends:
                continue
            if any(segment_hits(a, b, (s.x, s.y, s.w, s.h)) for a, b in zip(pts, pts[1:])):
                out.append(Issue(scene.id, c.id, "edge-through-box", f"edge passes through {s.id!r}"))
    return out


def header_crossings(scene: Scene) -> list[Issue]:
    """Edges entering a zone header (HDR-02); the segment that ends on that zone's own border is exempt (HDR-03).
    One issue per (edge, zone)."""
    out = []
    for c in (i for i in scene.items if isinstance(i, Connector)):
        pts = polyline(c)
        segs = list(zip(pts, pts[1:]))
        for zid, rect in scene.zone_headers.items():
            own = [b is not None and b.target == "zone" and b.shape_id == zid for b in (c.src, c.dst)]
            hits = [k for k, (a, b) in enumerate(segs) if segment_hits(a, b, rect)]
            hits = [k for k in hits if not (k == 0 and own[0]) and not (k == len(segs) - 1 and own[1])]
            if hits:
                out.append(Issue(scene.id, c.id, "edge-crosses-zone-header", f"crosses the header of zone {zid!r}"))
    return out


BORDER_BAND = 4.0  # an icon closer than this to a zone outline touches it


def _icon_rect(s: Shape) -> tuple[float, float, float, float]:
    i = s.icon
    return (i.x, i.y, getattr(i, "w", None) or i.size, getattr(i, "h", None) or i.size)


def _overlap(a, b) -> float:
    w = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    h = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


def _touches_outline(r, z: Shape, band: float = BORDER_BAND) -> bool:
    """Is rect ``r`` within ``band`` px of zone ``z``'s outline (inside or outside)?"""
    outer = (z.x - band, z.y - band, z.w + 2 * band, z.h + 2 * band)
    inner = (z.x + band, z.y + band, z.w - 2 * band, z.h - 2 * band)
    if not _overlap(r, outer):
        return False
    inside = inner[2] > 0 and inner[3] > 0 and r[0] >= inner[0] and r[1] >= inner[1] and \
        r[0] + r[2] <= inner[0] + inner[2] and r[1] + r[3] <= inner[1] + inner[3]
    return not inside


def icon_issues(scene: Scene) -> list[Issue]:
    """Icons on zone outlines, icons outside their box, and zone headers covered by content."""
    out: list[Issue] = []
    shapes = [s for s in scene.items if isinstance(s, Shape)]
    zones = {s.id: s for s in shapes if s.role == "zone" and s.icon is None and re.fullmatch(r"z\d+", s.id)}
    for s in shapes:
        if s.icon is None:
            continue
        r = _icon_rect(s)
        own = s.id.split("-")[0] if s.role == "zone" else None
        for zid, z in zones.items():
            if zid == own and zid in scene.flush_headers:
                continue  # flush corner icon (AWS convention)
            if _touches_outline(r, z):
                out.append(Issue(scene.id, s.id, "icon-touches-border", f"icon touches the outline of zone {zid!r}"))
        if s.role == "node" and (r[0] < s.x - 0.5 or r[1] < s.y - 0.5 or r[0] + r[2] > s.x + s.w + 0.5 or
                                 r[1] + r[3] > s.y + s.h + 0.5):
            out.append(Issue(scene.id, s.id, "icon-overflows-box", "icon extends outside its box"))
    covers = [(s.id, (s.x, s.y, s.w, s.h)) for s in shapes if s.role == "node"]
    covers += [(c.id, (c.label.x, c.label.y, c.label.w, c.label.h)) for c in scene.items
               if isinstance(c, Connector) and c.label is not None]
    covers += [(t.id, (t.x - (t.width or 0) * {"middle": 0.5, "end": 1.0}.get(t.anchor, 0), t.top,
                       t.width or 0, t.block.height))
               for t in scene.items if isinstance(t, Text) and not t.id.startswith("chrome-")
               and not re.match(r"z\d+-", t.id)]
    for zid, hdr in scene.zone_headers.items():
        for cid, r in covers:
            if _overlap(hdr, r) >= 0.5:
                out.append(Issue(scene.id, zid, "header-overlap", f"{cid!r} covers the header of zone {zid!r}"))
    return out


def icon_text_issues(scene: Scene) -> list[Issue]:
    """A node icon over the first line of its own text (ICO-04): both axes overlap by more than 0.5 px."""
    out: list[Issue] = []
    for s in scene.items:
        if not (isinstance(s, Shape) and s.role == "node" and s.icon is not None and s.label and s.label.blocks):
            continue
        b, bx, top = s.label.place()[0]
        if not b.lines:
            continue
        w = measure(b.lines[0], b.font)
        x0 = bx - w / 2 if s.label.align == "center" else bx
        ix, iy, iw, ih = _icon_rect(s)
        ox = min(ix + iw, x0 + w) - max(ix, x0)
        oy = min(iy + ih, top + b.leading) - max(iy, top)
        if ox > 0.5 and oy > 0.5:
            out.append(Issue(scene.id, s.id, "icon-overlaps-text", f"icon overlaps the first text line by {oy:.0f}px",
                             fix=_icon_text_fix(scene, s, oy)))
    return out


def _icon_text_fix(scene: Scene, s: Shape, overlap: float) -> dict | None:
    """Taller box (ICO-05). SPEC_DEVIATION: design.md says h + overlap + gap; the text is centred vertically in its
    box, so it moves down by half the added height: h + 2 × overlap + gap clears it in one round.
    Reason: with the design formula an overlap larger than the gap survives the fix."""
    gap = scene.check_options.get("icon_text_gap", 8)
    h = math.ceil(s.h + 2 * overlap + gap)
    return {"op": "resize", "node": s.id, "h": h} if _inside((s.x, s.y, s.w, h), scene.check_options.get(
        "margin", 80), scene) else None


def luminance(hex_colour: str) -> float:
    """WCAG relative luminance of ``#RRGGBB``."""
    h = hex_colour.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    """WCAG contrast ratio of two ``#RRGGBB`` colours (1 to 21)."""
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _blend(fg: str, bg: str, alpha: float) -> str:
    f, b = (fg.lstrip("#"), bg.lstrip("#"))
    mix = [round(int(f[i:i + 2], 16) * alpha + int(b[i:i + 2], 16) * (1 - alpha)) for i in (0, 2, 4)]
    return "#{:02X}{:02X}{:02X}".format(*mix)


def icon_colour(path) -> str | None:
    """The fill of a single-colour SVG icon; None for rasters and multi-colour or unpainted icons (their
    contrast cannot be judged from one colour)."""
    from pathlib import Path

    p = Path(path)
    if p.suffix.lower() != ".svg" or not p.exists():
        return None
    found = {c.upper() for c in re.findall(r'fill[=:]\s*"?\s*(#[0-9A-Fa-f]{6})\b',
                                           p.read_text(encoding="utf-8", errors="ignore"))}
    return found.pop() if len(found) == 1 else None


# Defaults flag near-invisible text and icons only; a theme raises them to WCAG AA with
# defaults.check.contrast: {title: 3, body: 4.5, icon: 3}.
CONTRAST = {"title": 2.0, "body": 2.0, "icon": 1.5}


def contrast_issues(scene: Scene) -> list[Issue]:
    lim = {**CONTRAST, **(scene.check_options.get("contrast") or {})}
    out: list[Issue] = []
    bg = scene.background if scene.background.startswith("#") else "#FFFFFF"
    pills = [c.label for c in scene.items if isinstance(c, Connector) and c.label is not None]
    for s in [i for i in scene.items if isinstance(i, Shape) and i.role in ("node", "pill")] + pills:
        fill = s.fill if s.fill and s.fill.startswith("#") else bg
        a = s.opacity * s.fill_opacity
        if a < 1 and s.fill:
            fill = _blend(fill, bg, a)
        for b in (s.label.blocks if s.label else []):
            if not str(b.color).startswith("#"):
                continue
            part = "title" if b.font.weight >= 600 else "body"
            need = lim[part]
            r = contrast(b.color, fill)
            if r < need:
                out.append(Issue(scene.id, s.id, "low-contrast",
                                 f"{part} {b.color} on {fill} is {r:.2f}:1 < {need:g}:1"))
        col = icon_colour(s.icon.path) if s.icon else None
        if col and contrast(col, fill) < lim["icon"]:
            out.append(Issue(scene.id, s.id, "low-contrast",
                             f"icon {col} on {fill} is {contrast(col, fill):.2f}:1 < {lim['icon']:g}:1"))
    return out


def safe_area_issues(scene: Scene, margin: float) -> list[Issue]:
    """Nodes, edge labels and free text past the canvas margin (zones may frame content into it)."""
    x0, y0, x1, y1 = margin, margin, scene.width - margin, scene.height - margin
    rects = [(s.id, (s.x, s.y, s.w, s.h)) for s in scene.items if isinstance(s, Shape) and s.role == "node"]
    rects += [(c.id, (c.label.x, c.label.y, c.label.w, c.label.h)) for c in scene.items
              if isinstance(c, Connector) and c.label is not None]
    rects += [(t.id, (t.x - (t.width or 0) * {"middle": 0.5, "end": 1.0}.get(t.anchor, 0), t.top, t.width or 0,
                      t.block.height)) for t in scene.items
              if isinstance(t, Text) and not t.id.startswith("chrome-") and not re.match(r"z\d+-", t.id)]
    out = []
    for item, (x, y, w, h) in rects:
        past = {"left": x0 - x, "top": y0 - y, "right": x + w - x1, "bottom": y + h - y1}
        worst = max(past, key=lambda k: past[k])
        if past[worst] > 0.5:
            out.append(Issue(scene.id, item, "outside-safe-area",
                             f"{past[worst]:.0f}px past the {worst} margin ({margin:g}px)"))
    return out


def _shape(scene: Scene, item: str) -> Shape | None:
    return next((s for s in scene.items if isinstance(s, Shape) and s.id == item), None)


def _inside(r, margin: float, scene: Scene) -> bool:
    x, y, w, h = r
    return x >= margin - 0.5 and y >= margin - 0.5 and x + w <= scene.width - margin + 0.5 and \
        y + h <= scene.height - margin + 0.5


def _label_obstacles(scene: Scene, skip: str) -> list:
    from .engine.labels import arrowheads

    conns = [c for c in scene.items if isinstance(c, Connector)]
    obs = [(s.x, s.y, s.w, s.h) for s in scene.items if isinstance(s, Shape) and s.role == "node"]
    obs += list(scene.zone_headers.values()) + arrowheads(conns)
    obs += [(c.label.x, c.label.y, c.label.w, c.label.h) for c in conns if c.label is not None and c.id != skip]
    return obs


def _move_label_fix(scene: Scene, edge_id: str, margin: float) -> dict | None:
    from .engine.labels import free_spot

    c = next((c for c in scene.items if isinstance(c, Connector) and c.id == edge_id), None)
    if c is None or c.label is None:
        return None
    spot = free_spot(c, _label_obstacles(scene, edge_id),
                     (margin, margin, scene.width - 2 * margin, scene.height - 2 * margin), polyline)
    if spot is None:
        return None
    size = c.label.h - 14  # pill height = font size + 14; label_at is the pill's anchor (centre + size/2 - 4)
    return {"op": "move-label", "edge": edge_id, "to": [round(spot[0], 1), round(spot[1] + size / 2 - 4, 1)]}


FRACTIONS = (0.5, 0.65, 0.35, 0.8, 0.2, 0.85, 0.15)  # anchor fix candidates, in order (HDR-04)


def _anchor_fix(scene: Scene, edge_id: str) -> dict | None:
    """First anchor pair on the edge's sides (source fraction outer loop) whose straight segment crosses no
    header and no other node; else reroute to ortho. Only straight edges between two nodes get one."""
    c = next((c for c in scene.items if isinstance(c, Connector) and c.id == edge_id), None)
    if c is None or c.route != "straight" or c.src is None or c.dst is None or \
            c.src.target != "node" or c.dst.target != "node":
        return None
    shapes = scene.shapes()
    a, b = shapes[c.src.shape_id], shapes[c.dst.shape_id]
    nodes = [(s.x, s.y, s.w, s.h) for s in shapes.values() if s.role == "node" and s.id not in (a.id, b.id)]
    blocks = list(scene.zone_headers.values()) + nodes
    for fs in FRACTIONS:
        for fd in FRACTIONS:
            p, q = a.anchor(c.src.side, fs), b.anchor(c.dst.side, fd)
            if not any(segment_hits(p, q, r) for r in blocks):
                return {"op": "anchor", "edge": edge_id, "src": f"{a.id}.{c.src.side}@{fs:g}",
                        "dst": f"{b.id}.{c.dst.side}@{fd:g}"}
    return {"op": "reroute", "edge": edge_id, "route": "ortho"}


def fix_for(scene: Scene, i: Issue) -> dict | None:
    """A safe, geometry-only fix for an issue, or None."""
    m = scene.check_options.get("margin", 80)
    if i.kind in ("overflow-x", "overflow-y"):
        s = _shape(scene, i.item)
        if s is None or s.label is None:
            return None
        x, y, w, h = s.label.box
        if i.kind == "overflow-x":
            need = max(measure(ln, b.font) for b in s.label.blocks for ln in b.lines)
            nw = math.ceil(s.w + need - w + 1)
            if _inside((s.x, s.y, nw, s.h), m, scene):
                return {"op": "resize", "node": s.id, "w": nw}
        else:
            total = sum(b.height for b in s.label.blocks) + s.label.gap * (len(s.label.blocks) - 1)
            nh = math.ceil(s.h + total - h + 1)
            if _inside((s.x, s.y, s.w, nh), m, scene):
                return {"op": "resize", "node": s.id, "h": nh}
        top = s.label.blocks[0].font.size
        return {"op": "shrink-font", "node": s.id, "title_size": max(1, math.floor(top * 0.85) - 1)}
    if i.kind == "icon-overflows-box":
        s = _shape(scene, i.item)
        r = _icon_rect(s)
        return {"op": "resize", "node": s.id, "w": math.ceil(max(s.w, r[0] + r[2] - s.x + 8)),
                "h": math.ceil(max(s.h, r[3] + 16))}  # the icon is centred vertically: 8 px above and below
    if i.kind == "outside-safe-area":
        if re.fullmatch(r"e\d+", i.item):
            return _move_label_fix(scene, i.item, m)
        s = _shape(scene, i.item)
        if s is None:
            return None
        dx = max(0, m - s.x) - max(0, s.x + s.w - (scene.width - m))
        dy = max(0, m - s.y) - max(0, s.y + s.h - (scene.height - m))
        return {"op": "nudge", "node": s.id, "dx": round(dx, 1), "dy": round(dy, 1)}
    if i.kind == "label-collision":
        return _move_label_fix(scene, i.item, m)
    if i.kind == "edge-crosses-zone-header":
        return _anchor_fix(scene, i.item)
    if i.kind == "header-overlap":
        cid = re.search(r"'([^']+)' covers", i.detail).group(1)
        if re.fullmatch(r"e\d+", cid):
            return _move_label_fix(scene, cid, m)
        s = _shape(scene, cid)
        if s is None:
            return None
        hx, hy, hw, hh = scene.zone_headers[i.item]
        return {"op": "nudge", "node": cid, "dx": 0, "dy": round(hy + hh + 12 - s.y, 1)}
    return None


UNDERUSED = 0.35  # content fill ratio below which a zone is reported (theme defaults.check.underused)


def zone_issues(scene: Scene) -> list[Issue]:
    """Children sticking out of their zone, and zones mostly empty."""
    out: list[Issue] = []
    shapes = scene.shapes()
    zones = {k: s for k, s in shapes.items() if s.role == "zone" and re.fullmatch(r"z\d+", k)}
    limit = scene.check_options.get("underused", UNDERUSED)
    for zid, z in zones.items():
        if zid in scene.zone_children:
            kids = [shapes[c] for c in scene.zone_children[zid] if c in shapes]
        else:  # undeclared: nodes mostly inside the outline
            kids = [s for s in shapes.values() if s.role == "node" and s.w * s.h and
                    _overlap((s.x, s.y, s.w, s.h), (z.x, z.y, z.w, z.h)) > 0.5 * s.w * s.h]
        for c in kids:
            past = {"left": z.x - c.x, "top": z.y - c.y, "right": c.x + c.w - z.x - z.w, "bottom": c.y + c.h - z.y - z.h}
            side = max(past, key=lambda k: past[k])
            if past[side] > 0.5:
                out.append(Issue(scene.id, zid, "zone-clips-child", f"{c.id!r} extends {past[side]:.0f}px past "
                                 f"the {side} side"))
        hx, hy, hw, hh = scene.zone_headers.get(zid, (z.x, z.y, 0, 0))  # header "none": no header rect
        area = z.w * (z.y + z.h - (hy + hh))
        used = sum(_overlap((c.x, c.y, c.w, c.h), (z.x, hy + hh, z.w, z.y + z.h - hy - hh)) for c in kids)
        if kids and area > 0 and used / area < limit:
            out.append(Issue(scene.id, zid, "zone-underused", f"content fills {used / area:.0%} of the zone "
                             f"(< {limit:.0%}); shrink it, use fit: children, or drop equalize"))
    return out


def check(scene: Scene) -> list[Issue]:
    issues: list[Issue] = [Issue(scene.id, item, "behavior", msg) for item, msg in scene.model_issues]
    issues += [Issue(scene.id, "css", "style", msg) for msg in scene.style_warnings]
    issues += [Issue(scene.id, item, kind, detail) for item, kind, detail in scene.annotation_issues]
    issues += [Issue(scene.id, "glyphs", "glyph-missing", f"{ch!r} (U+{ord(ch):04X}) in {role} font, fell back to {fam}")
               for ch, role, fam in scene.fallbacks]
    over = scene.layout_overflow
    if over:
        issues.append(Issue(scene.id, "layout", "overflow", f"auto layout exceeds its area by {over[0]}px wide, "
                            f"{over[1]}px tall — enlarge layout.area/canvas, shrink nodes or change direction"))
    issues += _hidden_heads(scene)
    if not scene.laid_out:  # engines route their own edges and size groups; these check hand-placed diagrams
        issues += edges_through_boxes(scene)
        issues += header_crossings(scene)
        issues += icon_issues(scene)
        issues += safe_area_issues(scene, scene.check_options.get("margin", 80))
        issues += zone_issues(scene)
        from .engine.route import crossings

        n = crossings([c for c in scene.items if isinstance(c, Connector)])
        if n:
            issues.append(Issue(scene.id, "edges", "edge-crossings",
                                f"{n} crossing(s); try route: ortho or swap anchor sides"))
    issues += icon_text_issues(scene)
    issues += [Issue(scene.id, nid, "icon-generic-for-service", f"'{title}' matches {ref}; icon '{icon}' is generic")
               for nid, (title, ref, icon) in scene.vendor_hints.items()]
    issues += contrast_issues(scene)
    if scene.version_mismatch:
        req, have = scene.version_mismatch
        issues.append(Issue(scene.id, "requires", "version-mismatch", f"spec requires spinagram {req}; "
                            f"installed {have}"))
    issues += [Issue(scene.id, cid, "not-straight", "the boxes share no span on either axis; move one or drop "
                     "straight") for cid in scene.not_straight]
    shapes = scene.shapes()
    for name, ids, uniform in scene.rows:  # explicit rows/columns should show one icon size
        sizes = {round(shapes[i].icon.size, 1) for i in ids if i in shapes and shapes[i].icon is not None}
        if not uniform and len(sizes) > 1:
            issues.append(Issue(scene.id, name, "icon-size-mismatch",
                                f"icons of {', '.join(sorted(map(str, ids)))} differ: {sorted(sizes)} px"))
    for it in scene.items:
        if isinstance(it, Shape) and it.label and it.role == "node":
            x, y, w, h = it.label.box
            how = scene.fits.get(it.id)
            after = f" after {how[0]} to {how[1]:g}px" if how else ""
            for b in it.label.blocks:
                for line in b.lines:
                    lw = measure(line, b.font)
                    if lw > w + 1:
                        issues.append(Issue(scene.id, it.id, "overflow-x",
                                            f"{line!r} is {lw:.0f}px > {w:.0f}px{after}"))
            total = sum(b.height for b in it.label.blocks) + it.label.gap * (len(it.label.blocks) - 1)
            if total > h + 1:
                issues.append(Issue(scene.id, it.id, "overflow-y", f"text {total:.0f}px > box {h:.0f}px{after}"))
        elif isinstance(it, TableGrid):
            for r, (rh, row) in enumerate(zip(it.row_heights, it.cells)):
                for c, (cw, cell) in enumerate(zip(it.col_widths, row)):
                    if cell.block.height > rh:
                        issues.append(Issue(scene.id, f"{it.id}[{r},{c}]", "overflow-y",
                                            f"{cell.block.height:.0f}px > row {rh:.0f}px"))
                    for line in cell.block.lines:
                        if measure(line, cell.block.font) > cw - cell.pad_left:
                            issues.append(Issue(scene.id, f"{it.id}[{r},{c}]", "overflow-x", repr(line)))
    for i in issues:
        if i.fix is None:
            i.fix = fix_for(scene, i)
    return issues


HEAD = 10.0  # how close to an arrowhead's tip a label may come before it hides the head
COVER = 0.25  # share of a label pill that may lie over a box before the label is reported


def _hidden_heads(scene: Scene) -> list[Issue]:
    """Edge labels drawn over an arrowhead (their own or another edge's)."""
    conns = [it for it in scene.items if isinstance(it, Connector) and len(it.points) >= 2]
    heads = []
    for c in conns:
        if c.arrow_end and c.marker_end != "none":
            heads.append((c.id, c.points[-1]))
        if c.arrow_start and c.marker_start != "none":
            heads.append((c.id, c.points[0]))
    out: list[Issue] = []
    nodes = [it for it in scene.items if isinstance(it, Shape) and it.role == "node"]
    for c in conns:  # an edge drawn through a box it does not connect
        if c.route == "curve":
            continue
        ends = {b.shape_id for b in (c.src, c.dst) if b is not None}
        for n in nodes:
            if n.id in ends or n.id.split(":")[-1] in ends:
                continue
            if any(_through(p, q, n) for p, q in zip(c.points, c.points[1:])):
                out.append(Issue(scene.id, c.id, "edge", f"edge passes through box {n.id} — use layout "
                                 "route: ortho, another direction, or via points"))
                break
    for c in conns:
        if c.label is None:
            continue
        lab = c.label
        for n in nodes:
            nx, ny, nw, nh = n.x, n.y, n.w, n.h
            if n.kind == "diamond":  # the rhombus, not its bounding box: its inscribed rectangle
                nx, ny, nw, nh = nx + nw / 4, ny + nh / 4, nw / 2, nh / 2
            ox = min(lab.x + lab.w, nx + nw) - max(lab.x, nx)
            oy = min(lab.y + lab.h, ny + nh) - max(lab.y, ny)
            if ox > 0 and oy > 0 and ox * oy > COVER * lab.w * lab.h:  # touching a corner is fine, covering is not
                out.append(Issue(scene.id, c.id, "label", f"label covers box {n.id} — widen the gap or place "
                                 "the label with label_at"))
                break
        lx, ly, lw, lh = c.label.x, c.label.y, c.label.w, c.label.h
        for cid, (tx, ty) in heads:
            if lx - HEAD < tx < lx + lw + HEAD and ly - HEAD < ty < ly + lh + HEAD:
                whose = "its own arrowhead" if cid == c.id else f"the arrowhead of {cid}"
                out.append(Issue(scene.id, c.id, "label", f"label hides {whose} — widen the gap between the "
                                 "boxes or place the label with label_at"))
                break
    return out


def _through(p, q, n: Shape, inset: float = 6.0) -> bool:
    """Does the segment p–q cross the inside of ``n`` (shrunk by ``inset``)? Liang–Barsky clipping."""
    x0, y0, x1, y1 = n.x + inset, n.y + inset, n.x + n.w - inset, n.y + n.h - inset
    if x1 <= x0 or y1 <= y0:
        return False
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pk, qk in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if pk == 0:
            if qk < 0:
                return False
            continue
        t = qk / pk
        if pk < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return t1 - t0 > 1e-6

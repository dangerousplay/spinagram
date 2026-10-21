"""Zones: outline patterns (roadmap Z2) and the header model (Z1)."""
from __future__ import annotations

from ..model import Zone
from ..theme import Theme

DASHES: dict[str, list[float] | None] = {"solid": None, "dashed": [8.0, 6.0], "dotted": [2.0, 6.0]}


def dash_pattern(value) -> tuple[list[float] | None, str | None]:
    """``solid | dashed | dotted | [numbers]`` → (dash pattern, line cap); dotted strokes use round caps."""
    if value is None:
        return None, None
    if isinstance(value, str):
        if value not in DASHES:
            raise ValueError(f"zone dash {value!r}; use solid, dashed, dotted or a list of numbers")
        return (list(DASHES[value]) if DASHES[value] else None), ("round" if value == "dotted" else None)
    return [float(v) for v in value], None


def outline(z: Zone, zs: dict, theme: Theme) -> dict:
    """Fill, stroke, width, dash and cap of a zone: the zone's own fields beat its style's."""
    out = {"fill": zs["fill"], "stroke": zs["stroke"], "stroke_width": zs["stroke_width"], "dashed": zs["dashed"],
           "dash": None, "cap": None}
    style_dash = zs.get("dash")
    if style_dash is not None:
        out["dash"], out["cap"] = dash_pattern(style_dash)
        out["dashed"] = out["dash"] is not None
    if z.fill is not None:
        out["fill"] = None if z.fill == "none" else theme.color(z.fill)
    if z.stroke is not None:
        out["stroke"] = None if z.stroke == "none" else theme.color(z.stroke)
        out["stroke_width"] = z.stroke_width if z.stroke_width is not None else (out["stroke_width"] or 2)
    elif z.stroke_width is not None:
        out["stroke_width"] = z.stroke_width
    if z.dash is not None:
        out["dash"], out["cap"] = dash_pattern(z.dash)
        out["dashed"] = out["dash"] is not None
    return out


HEADER = {"inset": True, "padding": 14, "icon_size": 28, "gap": 12, "chip_gap": 8, "label_gap": 10,
          "strip": None, "upper": None, "variant": None}


def header_options(z: Zone, zs: dict | None, theme: Theme | None) -> dict:
    """Header settings: built-in defaults < theme ``defaults.zone.header`` < zone style ``header`` < the zone's."""
    out = dict(HEADER)
    if theme is not None:
        out.update(theme.defaults("zone").get("header") or {})
    out.update((zs or {}).get("header") or {})
    out.update(z.header or {})
    return out


def label_baseline(center_y: float, size: float) -> float:
    """Baseline that centres a one-line label block (leading 1.3) on ``center_y``."""
    leading = size * 1.3
    return center_y - leading / 2 + (leading - size) / 2 + size * 0.8


def header_layout(z: Zone, opts: dict, icons, label_size: float, flush_icon: float) -> dict:
    """Geometry of a zone header: icon slots (x, y, slot height), label origin (x, baseline) and header bottom.
    ``icons`` is a count (square icons) or the list of icon widths at the slot height.

    Inset (default): icons ``padding`` inside the outline at ``icon_size``, the label centred on them.
    Flush (``inset: false``): the 0.3 corner icon at the outline. Without icons the label keeps its 0.3 place."""
    isz = opts["icon_size"] if opts["inset"] else flush_icon
    widths = [isz] * icons if isinstance(icons, int) else list(icons)
    if widths:
        p, gap, y = (opts["padding"], opts["chip_gap"], z.y + opts["padding"]) if opts["inset"] else (0, 4, z.y)
        slots, x = [], z.x + p
        for w in widths:
            slots.append((x, y, isz))
            x += w + gap
        right = slots[-1][0] + widths[-1]
        if opts["inset"]:
            return {"icons": slots, "label": (right + opts["label_gap"], label_baseline(y + isz / 2, label_size)),
                    "bottom": y + isz}
        return {"icons": slots, "label": (right + 10, z.y + 22), "bottom": z.y + isz}
    return {"icons": [], "label": (z.x + 24, z.y + 36), "bottom": z.y + 36 + label_size * 0.3}


def content_top(z: Zone, icons: int, label_size: float = 16, opts: dict | None = None, flush_icon: float = 32) -> float:
    """First free y below the header: header bottom + ``gap`` (12 px)."""
    opts = opts or header_options(z, None, None)
    return header_layout(z, opts, icons, label_size, flush_icon)["bottom"] + opts["gap"]


FIT_PADDING = 24.0


def _parents(zones: list[Zone]) -> dict[str, str]:
    return {c: z.id for z in zones for c in z.children if any(o.id == c for o in zones)}


def _depth(zid: str, parents: dict[str, str]) -> int:
    n = 0
    while zid in parents:
        zid, n = parents[zid], n + 1
    return n


def fit_children(d, theme: Theme) -> None:
    """Zones with ``fit="children"`` wrap their children (padding on three sides, the header on top), innermost
    first; then sibling zones with ``equalize="siblings"`` take the tallest sibling's height."""
    zones = [z for z in d.zones if z.id is not None]
    parents = _parents(zones)
    nodes = {n.id: n for n in d.nodes}
    by_id = {z.id: z for z in zones}
    label_size = theme.defaults("zone").get("label_size", 16)
    for z in sorted(zones, key=lambda z: -_depth(z.id, parents)):
        if z.fit != "children":
            continue
        rects = [(c.x, c.y, c.w, c.h) for c in (nodes.get(i) or by_id.get(i) for i in z.children) if c is not None]
        if not rects:
            continue
        x0, y0 = min(r[0] for r in rects), min(r[1] for r in rects)
        x1, y1 = max(r[0] + r[2] for r in rects), max(r[1] + r[3] for r in rects)
        pad = z.padding if z.padding is not None else FIT_PADDING
        icons = len(z.icon) if isinstance(z.icon, list) else int(bool(z.icon or theme.zone_style(z.color)["icon"]))
        probe = Zone(x=0, y=0, w=0, h=0, label=z.label, icon=z.icon, header=z.header, color=z.color)
        head = content_top(probe, icons, label_size, header_options(probe, theme.zone_style(z.color), theme))
        z.x, z.y, z.w, z.h = x0 - pad, y0 - head, x1 - x0 + 2 * pad, y1 - y0 + head + pad
    groups: dict[str | None, list[Zone]] = {}
    for z in zones:
        if z.equalize == "siblings":
            groups.setdefault(parents.get(z.id), []).append(z)
    for sibs in groups.values():
        tallest = max(z.h for z in sibs)
        for z in sibs:
            z.h = tallest

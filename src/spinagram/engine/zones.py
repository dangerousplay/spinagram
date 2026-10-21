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
          "strip": None, "upper": None}


def header_options(z: Zone, zs: dict, theme: Theme) -> dict:
    """Header settings: built-in defaults < theme ``defaults.zone.header`` < zone style ``header`` < the zone's."""
    out = dict(HEADER)
    out.update(theme.defaults("zone").get("header") or {})
    out.update(zs.get("header") or {})
    out.update(z.header or {})
    return out


def label_baseline(center_y: float, size: float) -> float:
    """Baseline that centres a one-line label block (leading 1.3) on ``center_y``."""
    leading = size * 1.3
    return center_y - leading / 2 + (leading - size) / 2 + size * 0.8


def header_layout(z: Zone, opts: dict, icons: int, label_size: float, flush_icon: float) -> dict:
    """Geometry of a zone header: icon slots (x, y, size), label origin (x, baseline) and header bottom.

    Inset (default): icons ``padding`` inside the outline at ``icon_size``, the label centred on them.
    Flush (``inset: false``): the 0.3 corner icon at the outline. Without icons the label keeps its 0.3 place."""
    if icons and opts["inset"]:
        p, isz = opts["padding"], opts["icon_size"]
        slots = [(z.x + p + k * (isz + opts["chip_gap"]), z.y + p, isz) for k in range(icons)]
        lx = slots[-1][0] + isz + opts["label_gap"]
        return {"icons": slots, "label": (lx, label_baseline(z.y + p + isz / 2, label_size)), "bottom": z.y + p + isz}
    if icons:
        slots = [(z.x + k * (flush_icon + 4), z.y, flush_icon) for k in range(icons)]
        return {"icons": slots, "label": (slots[-1][0] + flush_icon + 10, z.y + 22), "bottom": z.y + flush_icon}
    return {"icons": [], "label": (z.x + 24, z.y + 36), "bottom": z.y + 36 + label_size * 0.3}

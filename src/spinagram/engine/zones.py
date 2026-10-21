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

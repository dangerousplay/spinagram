"""Theme token sheets for the UI: resolved colours, font roles, styles and specimen SVGs."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..backends.svg import to_svg
from ..layout import build_scene
from ..model import Diagram
from ..theme import BUILTIN, Theme

ACTIVE = "active"
PREVIEW_KINDS = ("node", "zone")
SAMPLE = "Diagrams as code — 0123456789"


def list_themes(active_ref: str | Path | None) -> list[dict]:
    """Built-in themes plus the session's active theme (``ref`` ``active`` when it is not built-in)."""
    out = []
    active_name = str(active_ref or "default")
    builtin_names = sorted(d.name for d in BUILTIN.iterdir() if (d / "theme.yaml").is_file())
    for name in builtin_names:
        out.append({"ref": name, "name": name, "builtin": True, "active": name == active_name, "error": None})
    if active_name not in builtin_names:
        entry: dict[str, Any] = {"ref": ACTIVE, "name": Path(active_name).name, "builtin": False,
                                 "active": True, "error": None}
        try:
            entry["name"] = Theme.load(active_ref).data.get("name") or entry["name"]
        except Exception as exc:  # noqa: BLE001
            entry["error"] = str(exc)
        out.insert(0, entry)
    return out


def resolve_ref(ref: str, active_ref: str | Path | None) -> str | Path:
    if ref == ACTIVE:
        return active_ref or "default"
    if (BUILTIN / ref / "theme.yaml").is_file():
        return ref
    raise KeyError(f"unknown theme {ref!r}")


def _colour_entry(theme: Theme, token: str, value: Any) -> dict:
    v = str(value)
    try:
        resolved = theme.color(token)
    except KeyError:
        resolved = None
    return {"token": token, "value": v, "hex": resolved, "via": None if v.startswith("#") else v}


def _resolve(theme: Theme, v: Any) -> Any:
    """Colour-ish strings → hex (for swatches next to raw values); anything else unchanged."""
    if isinstance(v, str):
        try:
            return theme.color(v)
        except KeyError:
            return None
    return None


def theme_sheet(ref: str, active_ref: str | Path | None) -> dict:
    theme = Theme.load(resolve_ref(ref, active_ref))
    d = theme.data
    fonts = []
    for role, spec in (d.get("fonts") or {}).items():
        files = (spec or {}).get("files") or {}
        fonts.append({"role": role, "family": spec.get("family"), "fallback": spec.get("fallback"),
                      "figma": spec.get("figma") or {},
                      "files": [{"key": k, "weight": int(re.sub(r"\D", "", k) or 400), "italic": k.endswith("italic"),
                                 "format": Path(p).suffix.lstrip(".").lower(), "available": Path(p).exists()}
                                for k, p in files.items()]})
    styles: dict[str, list[dict]] = {}
    for kind, items in (d.get("styles") or {}).items():
        rows = []
        for name, val in (items or {}).items():
            if isinstance(val, dict):
                swatches = {k: _resolve(theme, v) for k, v in val.items() if k in
                            ("fill", "stroke", "title", "body", "label", "color")}
                rows.append({"name": name, "value": val, "swatches": {k: v for k, v in swatches.items() if v},
                             "preview": kind in PREVIEW_KINDS})
            else:
                rows.append({"name": name, "value": val, "swatches": {"color": _resolve(theme, val)}
                             if _resolve(theme, val) else {}, "preview": False})
        styles[kind] = rows
    return {
        "ref": ref, "name": d.get("name"), "extends": d.get("extends"), "root": str(theme.root),
        "canvas": d.get("canvas") or {},
        "colors": [_colour_entry(theme, k, v) for k, v in (d.get("colors") or {}).items()],
        "fonts": fonts, "sample": SAMPLE, "styles": styles,
        "defaults": d.get("defaults") or {}, "chrome": d.get("chrome") or {},
        "icons": {k: v for k, v in (d.get("icons") or {}).items() if k not in ("dirs",)},
    }


def font_file(ref: str, active_ref: str | Path | None, role: str, key: str) -> Path:
    """A font file the theme declares (never an arbitrary path)."""
    theme = Theme.load(resolve_ref(ref, active_ref))
    p = ((theme.get("fonts", role) or {}).get("files") or {}).get(key)
    if not p or not Path(p).is_file():
        raise KeyError(f"{role}/{key}")
    return Path(p)


def _crop(svg: str, x: float, y: float, w: float, h: float) -> str:
    return re.sub(r'viewBox="[^"]*" width="[^"]*" height="[^"]*"',
                  f'viewBox="{x:g} {y:g} {w:g} {h:g}" width="{w:g}" height="{h:g}"', svg, count=1)


def style_preview(ref: str, active_ref: str | Path | None, kind: str, style: str) -> str:
    """A cropped specimen SVG of one node or zone style."""
    theme = Theme.load(resolve_ref(ref, active_ref))
    if kind not in PREVIEW_KINDS or style not in (theme.get("styles", kind) or {}):
        raise KeyError(f"{kind}/{style}")
    d = Diagram("", "")
    if kind == "node":
        d.box(style, text="body text", style=style, x=200, y=300, w=340, h=130)
        box = (180, 280, 380, 170)
    else:
        d.zone(style, x=200, y=300, w=380, h=170, color=style)
        box = (180, 280, 420, 210)
    return _crop(to_svg(build_scene(d, theme)), *box)


SAMPLE_STYLES = ("default", "dark", "soft", "warning", "alert", "neutral")


def sample_diagram(theme: Theme, name: str) -> Diagram:
    """A small diagram that shows a theme's chrome, fonts, a zone and its common node styles."""
    defined = theme.get("styles", "node") or {}
    styles = [s for s in SAMPLE_STYLES if s in defined]
    d = Diagram("THEME", name, subtitle="Node styles, a group and edges in this theme",
                layout={"engine": "flex", "direction": "right", "gap": 56, "route": "ortho"})
    size = {"w": 440, "h": 230}
    with d.group("Group", columns=3, gap=80):
        nodes = [d.box(s.capitalize(), text=f"style: {s}", style=None if s == "default" else s, **size)
                 for s in styles or ["default"]]
    # neighbours only (flex routes do not avoid boxes): along each row, and down the first column
    for row in (nodes[:3], nodes[3:]):
        for i, (a, b) in enumerate(zip(row, row[1:])):
            d.edge(a, b, dashed=i == 1)
    if len(nodes) > 3:
        d.edge(nodes[0], nodes[3])
    return d


def theme_thumbnail(ref: str, active_ref: str | Path | None) -> str:
    """The sample diagram rendered with theme ``ref`` as a full-slide SVG."""
    theme = Theme.load(resolve_ref(ref, active_ref))
    name = theme.data.get("name") or Path(str(ref)).name
    return to_svg(build_scene(sample_diagram(theme, name), theme))

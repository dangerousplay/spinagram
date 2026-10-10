"""Themes: a directory with ``theme.yaml`` and its assets (fonts, icons, logo).

Themes inherit with ``extends: <name or relative path>``; mappings merge deeply and
asset paths stay relative to the theme that declared them.
"""
from __future__ import annotations

import copy
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

BUILTIN = Path(__file__).resolve().parent / "themes"


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _builtin(ref: str | Path) -> Path | None:
    name = str(ref)
    if name in (".", "..") or "/" in name or "\\" in name:
        return None
    d = BUILTIN / name
    return d if (d / "theme.yaml").is_file() else None


def _resolve_dir(ref: str | Path, relative_to: Path | None = None) -> Path:
    if _builtin(ref):
        return _builtin(ref)
    p = Path(ref).expanduser()
    if not p.is_absolute() and relative_to is not None and (relative_to / p).exists():
        p = relative_to / p
    if p.is_dir():
        return p.resolve()
    raise FileNotFoundError(f"theme {ref!r} not found (dir with theme.yaml, or built-in: "
                            f"{', '.join(sorted(x.name for x in BUILTIN.iterdir()))})")


def _absolutize(data: dict, root: Path) -> dict:
    """Turn asset paths declared in this theme file into absolute paths."""
    data = copy.deepcopy(data)
    for role in (data.get("fonts") or {}).values():
        if isinstance(role, dict) and role.get("files"):
            role["files"] = {k: str((root / v).resolve()) for k, v in role["files"].items()}
    icons = data.get("icons") or {}
    if icons.get("pack_files"):
        icons["pack_files"] = [str((root / f).resolve()) for f in icons["pack_files"]]
    dirs = icons.get("dir")
    if dirs:
        icons["dirs"] = [str((root / d).resolve()) for d in (dirs if isinstance(dirs, list) else [dirs])]
    footer = (data.get("chrome") or {}).get("footer") or {}
    if footer.get("logo"):
        footer["logo"] = str((root / footer["logo"]).resolve())
    deck = data.get("deck") or {}
    for key in ("logo", "logo_negative"):
        if deck.get(key):
            deck[key] = str((root / deck[key]).resolve())
    return data


def _load_raw(ref: str | Path, relative_to: Path | None = None, seen: set[Path] | None = None) -> dict:
    root = _resolve_dir(ref, relative_to)
    seen = seen or set()
    if root in seen:
        raise ValueError(f"theme inheritance cycle at {root}")
    seen.add(root)
    raw = yaml.safe_load((root / "theme.yaml").read_text(encoding="utf-8")) or {}
    own = _absolutize(raw, root)
    parent = raw.get("extends")
    if parent:
        base = _load_raw(parent, root, seen)
        # icon search path accumulates: child first, then parent
        child_dirs = (own.get("icons") or {}).get("dirs") or []
        parent_dirs = (base.get("icons") or {}).get("dirs") or []
        own = _merge(base, own)
        own.setdefault("icons", {})["dirs"] = child_dirs + [d for d in parent_dirs if d not in child_dirs]
    own["_root"] = str(root)
    return own


@dataclass
class FontRef:
    family: str
    weight: int = 400
    italic: bool = False
    size: float = 16
    file: Path | None = None
    fallback: str = "sans-serif"
    figma_style: str = "Regular"

    def with_size(self, size: float) -> "FontRef":
        return FontRef(self.family, self.weight, self.italic, size, self.file, self.fallback, self.figma_style)


@dataclass
class Theme:
    data: dict[str, Any]
    root: Path
    _icon_cache: dict = field(default_factory=dict)

    @classmethod
    def load(cls, ref: str | Path | None = None) -> "Theme":
        ref = ref or os.environ.get("SPINAGRAM_THEME") or "default"
        raw = _load_raw(ref)
        return cls(raw, Path(raw["_root"]))

    # tokens -------------------------------------------------------------------
    def get(self, *path: str, default: Any = None) -> Any:
        cur: Any = self.data
        for k in path:
            if not isinstance(cur, dict) or k not in cur:
                return default
            cur = cur[k]
        return cur

    def color(self, value: str | None, default: str = "#000000") -> str:
        """Hex passthrough, or a token name from ``colors``."""
        if not value:
            return default
        v = str(value)
        if v.startswith("#"):
            return v.upper()
        colors = self.data.get("colors") or {}
        seen = set()
        while v in colors and v not in seen:  # tokens may point at tokens
            seen.add(v)
            v = str(colors[v])
            if v.startswith("#"):
                return v.upper()
        if v.lower() in {"white", "black"}:
            return "#FFFFFF" if v.lower() == "white" else "#000000"
        raise KeyError(f"unknown colour token {value!r} in theme {self.data.get('name')}")

    def style_key(self, group: str, name: str | None) -> str | None:
        """Apply ``aliases.<group>`` (e.g. legacy names) to a style name."""
        if name is None:
            return None
        return (self.get("aliases", group) or {}).get(name, name)

    def node_style(self, name: str | None) -> dict[str, Any]:
        styles = self.get("styles", "node") or {}
        key = self.style_key("node", name) or "default"
        if key not in styles:
            raise KeyError(f"unknown node style {name!r}; theme has {sorted(styles)}")
        s = dict(styles[key])
        return {"fill": self.color(s.get("fill")), "stroke": self.color(s.get("stroke")),
                "title": self.color(s.get("title")), "body": self.color(s.get("body")),
                "tone": s.get("tone", "light")}

    def _named(self, group: str, name: str | None, fallback: str = "default") -> str:
        styles = self.get("styles", group) or {}
        key = self.style_key(group, name) or fallback
        if key in styles:
            v = styles[key]
            return self.color(v if isinstance(v, str) else v.get("color"))
        return self.color(key)  # token or hex

    def edge_color(self, name: str | None) -> str:
        return self._named("edge", name, self.get("defaults", "edge", "color", default="default"))

    def legend_color(self, name: str | None) -> str:
        return self._named("legend", name)

    def zone_style(self, name: str | None) -> dict[str, str]:
        zones = self.get("styles", "zone") or {}
        key = self.style_key("zone", name) or "soft"
        z = zones.get(key) or {"fill": key, "label": "text-muted"}
        fill = z.get("fill", "none")
        out = {"fill": None if fill in (None, "none") else self.color(fill), "label": self.color(z["label"])}
        # optional group outline (AWS-style: dashed AZ, solid VPC/Region) and corner icon
        out["stroke"] = self.color(z["stroke"]) if z.get("stroke") else None
        out["stroke_width"] = z.get("stroke_width", 2 if z.get("stroke") else 0)
        out["dashed"] = bool(z.get("dashed", False))
        out["icon"] = z.get("icon")
        out["radius"] = z.get("radius")
        out["opacity"] = z.get("opacity")
        out["upper"] = z.get("upper", True)
        return out

    def defaults(self, group: str) -> dict[str, Any]:
        return dict(self.get("defaults", group) or {})

    # fonts --------------------------------------------------------------------
    def font(self, role: str, weight: int = 400, size: float = 16, italic: bool = False) -> FontRef:
        spec = self.get("fonts", role) or self.get("fonts", "body") or {"family": "sans-serif"}
        files = spec.get("files") or {}
        key = f"{weight}{'italic' if italic else ''}"
        path = files.get(key) or files.get(str(weight))
        if path is None and files:  # nearest weight with the same slant
            same = [k for k in files if k.endswith("italic") == italic] or list(files)
            near = min(same, key=lambda k: abs(int("".join(c for c in k if c.isdigit()) or 400) - weight))
            path = files[near]
        figma = spec.get("figma") or {}
        style = figma.get(str(weight)) or ("Bold" if weight >= 600 else "Regular")
        if italic:
            style = f"{style} Italic" if style != "Regular" else "Italic"
        return FontRef(family=spec["family"], weight=weight, italic=italic, size=size,
                       file=Path(path) if path and Path(path).exists() else None,
                       fallback=spec.get("fallback", "sans-serif"), figma_style=style)

    # icons --------------------------------------------------------------------
    def icon(self, name: str | None, tone: str = "light", base_dir: Path | None = None) -> Path | None:
        """Resolve an icon: ``pack:name`` (icon packs, see :mod:`spinagram.icons`), a theme alias
        (``icons.alias: {ec2: aws:ec2}``), a path relative to the spec, or a name in the theme's icon dirs."""
        if not name:
            return None
        key = (name, tone, str(base_dir))
        if key in self._icon_cache:
            return self._icon_cache[key]
        found = None
        alias = ((self.data.get("icons") or {}).get("alias") or {}).get(name)
        ref = alias or name
        direct = Path(ref)
        if re.match(r"^[a-z0-9][a-z0-9_-]*:[^/\\]", ref):
            from .icons import resolve

            found = resolve(ref, tone, packs=self.icon_packs())
            self._icon_cache[key] = found
            return found
        if not direct.suffix:  # bare name: the theme's packs first (icons.packs), then its icon dirs
            from .icons import resolve

            for pack in (self.data.get("icons") or {}).get("packs") or []:
                found = resolve(f"{pack}:{ref}", tone, packs=self.icon_packs())
                if found is not None:
                    self._icon_cache[key] = found
                    return found
        name = ref
        if direct.suffix and base_dir is not None and (base_dir / direct).exists():
            found = (base_dir / direct).resolve()
        elif direct.suffix and direct.is_absolute() and direct.exists():
            found = direct
        else:
            icons = self.data.get("icons") or {}
            variant = (icons.get("variants") or {}).get(tone, tone)
            patterns = icons.get("pattern") or "{name}.svg"
            patterns = patterns if isinstance(patterns, list) else [patterns]
            for d in icons.get("dirs") or []:
                for pat in patterns:
                    p = Path(d) / pat.format(name=name, variant=variant)
                    if p.exists():
                        found = p
                        break
                if found:
                    break
        if found is not None and found.suffix.lower() == ".png":
            from .vectorize import maybe  # PNG → faithful SVG twin (cached), else the PNG itself

            found = maybe(found, (self.data.get("icons") or {}).get("vectorize"))
        self._icon_cache[key] = found
        return found

    def icon_packs(self):
        """Icon packs seen by this theme: ``icons.pack_files`` shipped with it are defaults; built-in,
        user, project and ``$SPINAGRAM_ICON_PACKS`` registries override them (e.g. to pin another version)."""
        if getattr(self, "_packs", None) is None:
            from .icons import _load_file, registry

            packs = {}
            for f in (self.data.get("icons") or {}).get("pack_files") or []:
                if Path(f).exists():
                    packs.update(_load_file(Path(f), "theme"))
            packs.update(registry())
            self._packs = packs
        return self._packs

    @property
    def canvas(self) -> tuple[float, float]:
        c = self.data.get("canvas") or {}
        return float(c.get("width", 1920)), float(c.get("height", 1080))

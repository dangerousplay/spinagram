"""High-level entry points."""
from __future__ import annotations

import html
from pathlib import Path
from typing import Iterable, Sequence

from .backends import get_backend
from .layout import build_scene
from .model import Diagram
from .scene import Scene
from .theme import Theme


def _theme(theme: Theme | str | Path | None) -> Theme:
    return theme if isinstance(theme, Theme) else Theme.load(theme)


NAME_FROM = ("slug", "id", "file")


def _name(d: Diagram, name_from: str, per_file: dict) -> str | None:
    """The output name ``name_from`` gives a diagram without ``output`` (None: keep the slug)."""
    if name_from == "id":
        return d.id
    if name_from == "file":
        src = d.__dict__.get("_source")
        if src is None:
            return d.id
        stem = Path(src).stem
        return stem if per_file[str(src)] == 1 else f"{stem}-{d.id}"  # several diagrams in one file
    return None


def scenes(diagrams: Iterable[Diagram], theme: Theme | str | Path | None = None,
           layout: str | None = None, name_from: str = "slug") -> list[Scene]:
    """Resolve diagrams into scenes; ``layout`` overrides the engine of diagrams that use ``layout:``;
    ``name_from`` (slug, id, file) names the outputs of diagrams without ``output``."""
    from .autolayout import apply_layout

    if name_from not in NAME_FROM:
        raise ValueError(f"name_from {name_from!r}; use one of {', '.join(NAME_FROM)}")
    th = _theme(theme)
    diagrams = list(diagrams)
    per_file: dict = {}
    for d in diagrams:
        per_file[str(d.__dict__.get("_source"))] = per_file.get(str(d.__dict__.get("_source")), 0) + 1
    out = []
    for d in diagrams:
        sc = build_scene(apply_layout(d, th, layout), th)
        name = None if d.output else _name(d, name_from, per_file)
        if name:
            sc.slug = name
        out.append(sc)
    return out


def render(diagrams: Iterable[Diagram], out_dir: str | Path, *, theme: Theme | str | Path | None = None,
           formats: Sequence[str] = ("svg",), gallery: bool = False, layout: str | None = None,
           name_from: str = "slug", backend_options: dict | None = None, **options) -> list[Path]:
    """Render to ``out_dir`` in each format. ``backend_options`` (or keyword arguments named after a format)
    configure the backends: ``backend_options={"svg": {"fonts": "link"}}``."""
    out = Path(out_dir)
    backend_options = {**options, **(backend_options or {})}
    scs = scenes(diagrams, theme, layout, name_from)
    written: list[Path] = []
    for fmt in formats:
        written += get_backend(fmt, **backend_options.get(fmt, {})).render(scs, out)
    if gallery:
        written.append(write_gallery(scs, out, formats))
    written += write_sources(scs, out)
    return written


def write_sources(scs: Sequence[Scene], out: Path) -> list[Path]:
    """fontes.md (human review) + sources.json (machine) when any diagram shows facts."""
    import json

    from .facts import sources_markdown

    used = [(sc.id, sc.title, sc.sources) for sc in scs if sc.sources]
    if not used:
        return []
    out.mkdir(parents=True, exist_ok=True)
    md, js = out / "fontes.md", out / "sources.json"
    md.write_text(sources_markdown(used), encoding="utf-8")
    js.write_text(json.dumps({sid: src for sid, _, src in used}, ensure_ascii=False, indent=1), encoding="utf-8")
    return [md, js]


def write_gallery(scs: Sequence[Scene], out: Path, formats: Sequence[str]) -> Path:
    def links(sc: Scene) -> str:
        ls = [f'<a href="{sc.slug}.{f}">{f.upper()}</a>' for f in ("svg", "png") if f in formats]
        return " · ".join(ls)

    img = "png" if "png" in formats else "svg"
    cards = "".join(f'<figure><img src="{sc.slug}.{img}" alt="{html.escape(sc.title)}"/><figcaption>'
                    f'<b>{html.escape(sc.id)}</b> {html.escape(sc.title)} · {links(sc)}</figcaption></figure>'
                    for sc in scs)
    extra = []
    if "pptx" in formats:
        extra.append('<a href="diagrams.pptx">PowerPoint (all slides)</a>')
    if "figma" in formats:
        extra.append('<a href="figma/">Figma scripts</a>')
    page = ("<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' "
            "content='width=device-width,initial-scale=1'><title>Diagrams</title><style>"
            "body{margin:0;padding:24px;background:#f4f5f4;font-family:system-ui,sans-serif;color:#222}"
            "figure{margin:0 0 28px;background:#fff;border-radius:16px;padding:14px;"
            "box-shadow:0 8px 24px rgba(0,0,0,.06)}img{width:100%;height:auto;display:block}"
            "figcaption{margin-top:8px;font-size:14px}</style></head><body>"
            f"<p>{' · '.join(extra)}</p>{cards}</body></html>")
    p = out / "index.html"
    p.write_text(page, encoding="utf-8")
    return p

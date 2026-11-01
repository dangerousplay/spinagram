"""Scenes as versioned JSON: the language-neutral form other front-ends and the Rust core read.

``dumps(scene)`` carries every field the SVG writer and ``Scene.fonts()`` read: items tagged by ``type``
(``shape``, ``connector``, ``text``, ``line``, ``image``, ``table``), nested labels, text blocks, runs, fonts,
icons, symbol parts and table cells. Paths are absolute strings and tuples are arrays. QA-only fields of
``Scene`` (issues, fits, zone bookkeeping) are not written. The format is described by
``rust/schema/scene.schema.json``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .scene import Binding, Cell, Connector, Icon, Image, Label, Line, Scene, Shape, TableGrid, Text, TextBlock
from .theme import FontRef

VERSION = 1


def _path(p: Path | str) -> str:
    return str(Path(p).absolute())


def _font(f: FontRef) -> dict[str, Any]:
    return {"family": f.family, "weight": f.weight, "italic": f.italic, "size": f.size,
            "file": None if f.file is None else _path(f.file), "fallback": f.fallback, "figma_style": f.figma_style}


def _block(b: TextBlock) -> dict[str, Any]:
    runs = None
    if b.runs is not None:  # ``base``: the run uses the block's own font object (the SVG writer tells by identity)
        runs = [[{"text": r.text, "font": _font(r.font), "base": r.font is b.font} for r in line] for line in b.runs]
    return {"lines": list(b.lines), "paragraphs": list(b.paragraphs), "font": _font(b.font), "color": b.color,
            "leading": b.leading, "runs": runs}


def _label(label: Label | None) -> dict[str, Any] | None:
    if label is None:
        return None
    return {"blocks": [_block(b) for b in label.blocks], "box": list(label.box), "align": label.align,
            "gap": label.gap, "valign": label.valign}


def _icon(icon: Icon | None) -> dict[str, Any] | None:
    if icon is None:
        return None
    return {"path": _path(icon.path), "x": icon.x, "y": icon.y, "size": icon.size, "w": icon.w}


def _binding(b: Binding | None) -> dict[str, Any] | None:
    return None if b is None else {"shape_id": b.shape_id, "side": b.side, "frac": b.frac, "target": b.target}


def _shape(s: Shape) -> dict[str, Any]:
    return {"type": "shape", "id": s.id, "kind": s.kind, "x": s.x, "y": s.y, "w": s.w, "h": s.h, "fill": s.fill,
            "stroke": s.stroke, "stroke_width": s.stroke_width, "radius": s.radius, "dashed": s.dashed,
            "opacity": s.opacity, "label": _label(s.label), "icon": _icon(s.icon), "role": s.role,
            "parts": None if s.parts is None else [{"d": p.d, "paint": p.paint} for p in s.parts],
            "dash": None if s.dash is None else list(s.dash),
            "shadow": None if s.shadow is None else list(s.shadow), "fill_opacity": s.fill_opacity, "cap": s.cap}


def _connector(c: Connector) -> dict[str, Any]:
    return {"type": "connector", "id": c.id, "points": [list(p) for p in c.points], "route": c.route,
            "color": c.color, "width": c.width, "dashed": c.dashed, "arrow_start": c.arrow_start,
            "arrow_end": c.arrow_end, "src": _binding(c.src), "dst": _binding(c.dst),
            "label": None if c.label is None else _shape(c.label),
            "dash": None if c.dash is None else list(c.dash), "marker_start": c.marker_start,
            "marker_end": c.marker_end, "opacity": c.opacity}


def _cell(c: Cell) -> dict[str, Any]:
    return {"block": _block(c.block), "fill": c.fill, "icon": _icon(c.icon), "pad_left": c.pad_left,
            "bold": c.bold}


def _item(it) -> dict[str, Any]:
    if isinstance(it, Shape):
        return _shape(it)
    if isinstance(it, Connector):
        return _connector(it)
    if isinstance(it, Text):
        return {"type": "text", "id": it.id, "x": it.x, "y": it.y, "block": _block(it.block), "anchor": it.anchor,
                "letter_spacing": it.letter_spacing, "width": it.width}
    if isinstance(it, Line):
        return {"type": "line", "id": it.id, "x1": it.x1, "y1": it.y1, "x2": it.x2, "y2": it.y2,
                "color": it.color, "width": it.width}
    if isinstance(it, Image):
        return {"type": "image", "id": it.id, "path": _path(it.path), "x": it.x, "y": it.y, "w": it.w, "h": it.h}
    if isinstance(it, TableGrid):
        return {"type": "table", "id": it.id, "x": it.x, "y": it.y, "col_widths": list(it.col_widths),
                "row_heights": list(it.row_heights), "cells": [[_cell(c) for c in row] for row in it.cells],
                "border": it.border, "header_radius": it.header_radius}
    raise TypeError(f"unknown scene item {type(it).__name__}")


def to_dict(scene: Scene) -> dict[str, Any]:
    return {"version": VERSION, "id": scene.id, "title": scene.title, "slug": scene.slug, "width": scene.width,
            "height": scene.height, "background": scene.background, "items": [_item(i) for i in scene.items],
            "item_facts": {k: list(v) for k, v in scene.item_facts.items()}, "sources": list(scene.sources),
            "meta_tooltips": dict(scene.meta_tooltips)}


def dumps(scene: Scene) -> str:
    return json.dumps(to_dict(scene), ensure_ascii=False)

"""Annotations as scene primitives: the legend card, numbered steps, callouts.

Legends and step panels sit in a band reserved at the right or bottom of the layout area (``band``), so they
never overlap content. Everything is drawn with the scene's own shapes, connectors and text, which every
backend already renders natively and editably.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .model import Diagram
from .text import measure, wrap_paragraphs
from .theme import Theme


@dataclass
class Entry:
    key: str            # as written: ``.web``, ``edge.async``, ``style:dark``, ``aws:s3``
    label: str
    kind: str           # node | edge | style | icon
    ref: str | None     # style-tree key of the first element carrying the key (``node:a``, ``edge:0``)
    used: bool = True
    value: str = ""     # class, style or icon name


def humanize(name: str) -> str:
    """``edge-svc`` → ``Edge svc``."""
    s = re.sub(r"[-_]+", " ", name).strip()
    return s[:1].upper() + s[1:]


def _classes(cls: str | None) -> list[str]:
    return (cls or "").split()


def _parse_key(key: str) -> tuple[str, str]:
    """``(kind, value)`` of a legend key."""
    if key.startswith("edge."):
        return "edge", key[5:]
    if key.startswith("node."):
        return "node", key[5:]
    if key.startswith("."):
        return "node", key[1:]
    if key.startswith("style:"):
        return "style", key[6:]
    if ":" in key:
        return "icon", key
    return "node", key


def _first(d: Diagram, kind: str, value: str) -> str | None:
    if kind == "edge":
        return next((f"edge:{i}" for i, e in enumerate(d.edges) if value in _classes(e.cls)), None)
    if kind == "node":
        return next((f"node:{n.id}" for n in d.nodes if value in _classes(n.cls) or n.style == value), None)
    if kind == "style":
        return next((f"node:{n.id}" for n in d.nodes
                     if (n.style or "default") == value and n.kind in ("box", "note")), None)
    return next((f"node:{n.id}" for n in d.nodes if n.icon == value), None)


def legend_entries(d: Diagram) -> list[Entry]:
    """The legend's entries: the given items in order, or every node class, non-default node style and edge
    class the diagram uses, once each, in first-use order (nodes, then edges)."""
    lg = d.annotations.legend
    if lg is None:
        return []
    if lg.items is not None:
        out = []
        for key, label in lg.items.items():
            kind, value = _parse_key(key)
            ref = _first(d, kind, value)
            out.append(Entry(key, str(label), kind, ref, ref is not None, value))
        return out
    out, seen = [], set()

    def add(key: str, kind: str, value: str, ref: str) -> None:
        if key not in seen:
            seen.add(key)
            out.append(Entry(key, humanize(value), kind, ref, True, value))

    for n in d.nodes:
        for c in _classes(n.cls):
            add(f".{c}", "node", c, f"node:{n.id}")
        if n.style and n.style != "default":
            add(f"style:{n.style}", "style", n.style, f"node:{n.id}")
    for i, e in enumerate(d.edges):
        for c in _classes(e.cls):
            add(f"edge.{c}", "edge", c, f"edge:{i}")
    return out


# geometry -----------------------------------------------------------------------------------------
def settings(theme: Theme) -> dict:
    base = {"band": 360, "gap": 32, "padding": 22, "radius": 18, "title_size": 20, "text_size": 16, "row_gap": 12,
            "swatch_w": 46, "swatch_h": 28, "badge": 30, "badge_size": 15, "callout_width": 320,
            "callout_gap": 36}
    return base | (theme.defaults("annotations") or {})


def _head(a: dict) -> float:
    """Card padding plus the title line."""
    return a["padding"] + a["title_size"] * 1.3 + 10


def legend_rows(entries: list[Entry], width: float, theme: Theme, columns: int = 1) -> list[list[Entry]]:
    """Entries packed into rows: ``columns`` per row in a right band, or flowed by label width when
    ``columns`` is 0 (bottom band)."""
    if columns:
        return [entries[i:i + columns] for i in range(0, len(entries), columns)]
    a = settings(theme)
    font = theme.font("body", 400, a["text_size"])
    inner = width - 2 * a["padding"]
    rows: list[list[Entry]] = [[]]
    used = 0.0
    for e in entries:
        w = a["swatch_w"] + 10 + measure(e.label, font)
        if rows[-1] and used + 28 + w > inner:
            rows.append([])
            used = 0.0
        used += (28 if rows[-1] else 0) + w
        rows[-1].append(e)
    return rows if rows[0] else []


def legend_height(rows: list[list[Entry]], theme: Theme) -> float:
    a = settings(theme)
    n = len(rows)
    return _head(a) + n * a["swatch_h"] + max(0, n - 1) * a["row_gap"] + a["padding"]


def step_lines(text: str, width: float, theme: Theme) -> list[str]:
    a = settings(theme)
    font = theme.font("body", 400, a["text_size"])
    return wrap_paragraphs([text], font, width - 2 * a["padding"] - a["badge"] - 12)


def step_row_height(lines: list[str], theme: Theme) -> float:
    a = settings(theme)
    return max(a["badge"], len(lines) * a["text_size"] * 1.35)


def steps_height(d: Diagram, width: float, theme: Theme) -> float:
    a = settings(theme)
    steps = d.annotations.steps
    rows = [step_row_height(step_lines(s.text, width, theme), theme) for s in steps]
    return _head(a) + sum(rows) + max(0, len(rows) - 1) * a["row_gap"] + a["padding"]


def band(d: Diagram, theme: Theme, width: float) -> tuple[str, float] | None:
    """``(side, thickness)`` reserved for the legend and steps panels (thickness includes the gap to the
    content), or ``None``. ``width`` is the layout area's width (for a bottom band's rows)."""
    ann = d.annotations
    if not (ann.legend or ann.steps):
        return None
    a = settings(theme)
    side = ann.legend.position if ann.legend else "right"
    if side == "right":
        return "right", a["band"] + a["gap"]
    steps_w = a["band"] if ann.steps else 0
    legend_w = width - (steps_w + a["gap"] if steps_w and ann.legend else 0) if ann.legend else 0
    h = 0.0
    if ann.legend:
        h = legend_height(legend_rows(legend_entries(d), legend_w, theme, columns=0), theme)
    if ann.steps:
        h = max(h, steps_height(d, steps_w, theme))
    return "bottom", h + a["gap"]

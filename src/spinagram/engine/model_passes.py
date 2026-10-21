"""Geometry decided on the model before the scene is built (roadmap B1, G1, Z3).

Each pass works on a copy of a hand-placed diagram; diagrams laid out by an engine are returned as they are."""
from __future__ import annotations

import copy

from ..model import Diagram
from ..theme import Theme

SIZED_KINDS_SKIP = ("text", "pill")  # free labels and pills size themselves from their text


def content_size(d: Diagram, theme: Theme) -> None:
    """Boxes placed by hand without ``w``/``h`` get the size of their content (icon, title, body, padding)."""
    from ..autolayout.sizing import auto_size

    for n in d.nodes:
        if n.kind in SIZED_KINDS_SKIP or (n.w and n.h):
            continue
        n.w, n.h = auto_size(n, theme)


def apply(d: Diagram, theme: Theme) -> Diagram:
    """A copy of ``d`` with every model pass applied (``d`` itself when there is nothing to do)."""
    if d.auto or d.meta.get("laid_out"):
        return d
    if not any(not (n.w and n.h) and n.kind not in SIZED_KINDS_SKIP for n in d.nodes):
        return d
    d = copy.deepcopy(d)
    content_size(d, theme)
    return d

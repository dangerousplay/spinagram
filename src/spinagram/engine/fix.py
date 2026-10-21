"""Apply the safe fixes ``check`` attaches to issues (roadmap C1)."""
from __future__ import annotations

import copy

from ..model import Diagram

SAFE_OPS = ("move-label", "resize", "nudge", "shrink-font")


def _inside(x: float, y: float, w: float, h: float, canvas: tuple[float, float], margin: float) -> bool:
    W, H = canvas
    return x >= margin - 0.5 and y >= margin - 0.5 and x + w <= W - margin + 0.5 and y + h <= H - margin + 0.5


def apply_to_diagram(d: Diagram, issues, canvas: tuple[float, float] = (1920, 1080), margin: float = 80
                     ) -> tuple[Diagram, list, list]:
    """A copy of ``d`` with every safe fix applied, plus (applied, skipped) issues. A fix that would leave an
    element outside the safe area is skipped and its issue kept (CHK-08)."""
    out = copy.deepcopy(d)
    nodes = {n.id: n for n in out.nodes}
    applied, skipped = [], []
    done: set[tuple] = set()
    for i in issues:
        f = i.fix
        if not f or f.get("op") not in SAFE_OPS:
            continue
        key = tuple(sorted((k, str(v)) for k, v in f.items()))
        if key in done:  # the same fix proposed twice (one node, two overflowing lines)
            continue
        done.add(key)
        op = f["op"]
        if op == "move-label":
            idx = int(f["edge"][1:])
            if idx >= len(out.edges):
                skipped.append(i)
                continue
            out.edges[idx].label_at = (float(f["to"][0]), float(f["to"][1]))
            applied.append(i)
            continue
        n = nodes.get(f.get("node"))
        if n is None:
            skipped.append(i)
            continue
        x, y, w, h = n.x, n.y, f.get("w", n.w), f.get("h", n.h)
        if op == "nudge":
            x, y = n.x + f.get("dx", 0), n.y + f.get("dy", 0)
        if op in ("nudge", "resize") and not _inside(x, y, w, h, canvas, margin):
            skipped.append(i)
            continue
        if op == "shrink-font":
            n.title_size = f["title_size"]
        n.x, n.y, n.w, n.h = x, y, w, h
        applied.append(i)
    return out, applied, skipped


def fix_until_clean(d: Diagram, theme, rounds: int = 3) -> tuple[Diagram, list, list]:
    """Check, apply, rebuild — up to ``rounds`` times or until no fix applies. Returns the fixed diagram, every
    applied issue, and the issues still open at the end."""
    from ..layout import build_scene
    from ..qa import check

    canvas = tuple(theme.canvas)
    margin = (theme.get("canvas") or {}).get("margin", 80)
    applied_all: list = []
    cur = d
    for _ in range(rounds):
        issues = check(build_scene(cur, theme))
        cur, applied, _ = apply_to_diagram(cur, issues, canvas, margin)
        applied_all += applied
        if not applied:
            break
    return cur, applied_all, check(build_scene(cur, theme))

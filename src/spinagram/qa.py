"""Layout checks on a resolved scene: text that does not fit its box."""
from __future__ import annotations

from dataclasses import dataclass

from .scene import Scene, Shape, TableGrid
from .text import measure


@dataclass
class Issue:
    scene: str
    item: str
    kind: str
    detail: str

    def __str__(self) -> str:
        return f"{self.scene}:{self.item}: {self.kind} — {self.detail}"


def behavior_issues(d) -> list[tuple[str, str]]:
    """Model-level rules for behavior diagrams: (item, message) pairs."""
    out: list[tuple[str, str]] = []
    kinds = {n.id: n.kind for n in d.nodes}
    outgoing: dict[str, int] = {}
    for e in d.edges:
        src = e.src.partition(".")[0] if isinstance(e.src, str) else None
        if src:
            outgoing[src] = outgoing.get(src, 0) + 1
    for n in d.nodes:
        k = outgoing.get(n.id, 0)
        if n.kind == "decision" and k < 2:
            out.append((n.id, f"decision {n.id} has {k} outgoing edges (expected ≥ 2)"))
        if n.kind == "fork" and k < 2:
            out.append((n.id, f"fork {n.id} has {k} branch"))
    in_group = {c for g in d.groups for c in g.children}
    scopes = [(d.id, [n.id for n in d.nodes if n.id not in in_group])] + [(g.id, g.children) for g in d.groups]
    for sid, children in scopes:
        direct = [kinds.get(c) for c in children]
        if "state" in direct and "initial" not in direct:
            out.append((sid, f"region {sid} has no initial state"))
    return out


def check(scene: Scene) -> list[Issue]:
    issues: list[Issue] = [Issue(scene.id, item, "behavior", msg) for item, msg in scene.model_issues]
    issues += [Issue(scene.id, "css", "style", msg) for msg in scene.style_warnings]
    over = scene.layout_overflow
    if over:
        issues.append(Issue(scene.id, "layout", "overflow", f"auto layout exceeds its area by {over[0]}px wide, "
                            f"{over[1]}px tall — enlarge layout.area/canvas, shrink nodes or change direction"))
    for it in scene.items:
        if isinstance(it, Shape) and it.label and it.role == "node":
            x, y, w, h = it.label.box
            for b in it.label.blocks:
                for line in b.lines:
                    lw = measure(line, b.font)
                    if lw > w + 1:
                        issues.append(Issue(scene.id, it.id, "overflow-x", f"{line!r} is {lw:.0f}px > {w:.0f}px"))
            total = sum(b.height for b in it.label.blocks) + it.label.gap * (len(it.label.blocks) - 1)
            if total > h + 1:
                issues.append(Issue(scene.id, it.id, "overflow-y", f"text {total:.0f}px > box {h:.0f}px"))
        elif isinstance(it, TableGrid):
            for r, (rh, row) in enumerate(zip(it.row_heights, it.cells)):
                for c, (cw, cell) in enumerate(zip(it.col_widths, row)):
                    if cell.block.height > rh:
                        issues.append(Issue(scene.id, f"{it.id}[{r},{c}]", "overflow-y",
                                            f"{cell.block.height:.0f}px > row {rh:.0f}px"))
                    for line in cell.block.lines:
                        if measure(line, cell.block.font) > cw - cell.pad_left:
                            issues.append(Issue(scene.id, f"{it.id}[{r},{c}]", "overflow-x", repr(line)))
    return issues

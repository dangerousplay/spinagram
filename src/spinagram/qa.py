"""Layout checks on a resolved scene: text that does not fit its box."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from .scene import Connector, Scene, Shape, TableGrid
from .text import measure


# P0: the diagram renders wrong; P1: visibly degraded; P2: advisory. Unlisted kinds are P1.
SEVERITY = {"overflow-x": "P0", "overflow-y": "P0", "overflow": "P0", "label-collision": "P0",
            "icon-touches-border": "P0", "header-overlap": "P0", "icon-overflows-box": "P0",
            "outside-safe-area": "P0", "zone-clips-child": "P0", "glyph-missing": "P1", "low-contrast": "P1",
            "zone-underused": "P2", "edge-crossings": "P2", "icon-size-mismatch": "P2", "not-straight": "P2",
            "version-mismatch": "P2", "style": "P2"}


@dataclass
class Issue:
    scene: str
    item: str
    kind: str
    detail: str
    fix: dict | None = None    # machine-readable fix: {"op": "move-label" | "resize" | "nudge" | "shrink-font", ...}
    severity: str | None = None

    def __post_init__(self) -> None:
        if self.severity is None:
            self.severity = SEVERITY.get(self.kind, "P1")

    def __str__(self) -> str:
        return f"{self.scene}:{self.item}: {self.kind} — {self.detail}"

    def to_dict(self) -> dict:
        return asdict(self)


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
    issues += [Issue(scene.id, item, kind, detail) for item, kind, detail in scene.annotation_issues]
    over = scene.layout_overflow
    if over:
        issues.append(Issue(scene.id, "layout", "overflow", f"auto layout exceeds its area by {over[0]}px wide, "
                            f"{over[1]}px tall — enlarge layout.area/canvas, shrink nodes or change direction"))
    issues += _hidden_heads(scene)
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


HEAD = 10.0  # how close to an arrowhead's tip a label may come before it hides the head
COVER = 0.25  # share of a label pill that may lie over a box before the label is reported


def _hidden_heads(scene: Scene) -> list[Issue]:
    """Edge labels drawn over an arrowhead (their own or another edge's)."""
    conns = [it for it in scene.items if isinstance(it, Connector) and len(it.points) >= 2]
    heads = []
    for c in conns:
        if c.arrow_end and c.marker_end != "none":
            heads.append((c.id, c.points[-1]))
        if c.arrow_start and c.marker_start != "none":
            heads.append((c.id, c.points[0]))
    out: list[Issue] = []
    nodes = [it for it in scene.items if isinstance(it, Shape) and it.role == "node"]
    for c in conns:  # an edge drawn through a box it does not connect
        if c.route == "curve":
            continue
        ends = {b.shape_id for b in (c.src, c.dst) if b is not None}
        for n in nodes:
            if n.id in ends or n.id.split(":")[-1] in ends:
                continue
            if any(_through(p, q, n) for p, q in zip(c.points, c.points[1:])):
                out.append(Issue(scene.id, c.id, "edge", f"edge passes through box {n.id} — use layout "
                                 "route: ortho, another direction, or via points"))
                break
    for c in conns:
        if c.label is None:
            continue
        lab = c.label
        for n in nodes:
            nx, ny, nw, nh = n.x, n.y, n.w, n.h
            if n.kind == "diamond":  # the rhombus, not its bounding box: its inscribed rectangle
                nx, ny, nw, nh = nx + nw / 4, ny + nh / 4, nw / 2, nh / 2
            ox = min(lab.x + lab.w, nx + nw) - max(lab.x, nx)
            oy = min(lab.y + lab.h, ny + nh) - max(lab.y, ny)
            if ox > 0 and oy > 0 and ox * oy > COVER * lab.w * lab.h:  # touching a corner is fine, covering is not
                out.append(Issue(scene.id, c.id, "label", f"label covers box {n.id} — widen the gap or place "
                                 "the label with label_at"))
                break
        lx, ly, lw, lh = c.label.x, c.label.y, c.label.w, c.label.h
        for cid, (tx, ty) in heads:
            if lx - HEAD < tx < lx + lw + HEAD and ly - HEAD < ty < ly + lh + HEAD:
                whose = "its own arrowhead" if cid == c.id else f"the arrowhead of {cid}"
                out.append(Issue(scene.id, c.id, "label", f"label hides {whose} — widen the gap between the "
                                 "boxes or place the label with label_at"))
                break
    return out


def _through(p, q, n: Shape, inset: float = 6.0) -> bool:
    """Does the segment p–q cross the inside of ``n`` (shrunk by ``inset``)? Liang–Barsky clipping."""
    x0, y0, x1, y1 = n.x + inset, n.y + inset, n.x + n.w - inset, n.y + n.h - inset
    if x1 <= x0 or y1 <= y0:
        return False
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pk, qk in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if pk == 0:
            if qk < 0:
                return False
            continue
        t = qk / pk
        if pk < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return t1 - t0 > 1e-6

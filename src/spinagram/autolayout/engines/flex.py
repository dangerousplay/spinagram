"""Nested flex layout (pure Python, deterministic).

Each group places its children as a row, a column or a grid (``columns``), aligned on the cross axis,
then wraps them in its padding. Sizes are computed bottom-up, positions top-down. Default direction:
a group whose children are all groups is a row (AZs side by side), otherwise a column (stacked nodes);
the root follows ``layout.direction``. A gap between two neighbours that a labelled edge connects grows to
fit the label pill and the arrowhead beside it, unless the group sets its ``gap``. No edge routing — edges keep spinagram's auto sides.
"""
from __future__ import annotations

from ..graph import LGraph, LGroup, LNode, LResult

HEADS = 40.0  # room beside a label for the arrowhead (and the tail stub) on a labelled edge
PILL_H = 31.0  # height of a label pill at the default size, for labels between stacked neighbours


class FlexEngine:
    name = "flex"

    def available(self) -> str | None:
        return None

    def run(self, graph: LGraph) -> LResult:
        self.g = graph
        self.size: dict[str, tuple[float, float]] = {}
        self.natural: dict[str, tuple[float, float]] = {}
        self.leaves: dict[str, set[str]] = {}
        self._collect(graph.root)
        self.labelled = [(e.src, e.dst, e.label_w) for e in graph.edges if e.label_w]
        self._measure(graph.root, root=True)
        boxes: dict[str, tuple[float, float, float, float]] = {}
        self._place(graph.root, 0.0, 0.0, boxes, root=True)
        return LResult(boxes=boxes)

    # sizes --------------------------------------------------------------------------------------
    def _dir(self, grp: LGroup, root: bool) -> str:
        d = grp.hints.get("direction")
        if d:
            return {"right": "row", "down": "column"}.get(d, d)
        if root:
            return "row" if self.g.direction == "right" else "column"
        return "row" if grp.children and all(isinstance(c, LGroup) for c in grp.children) else "column"

    def _gap(self, grp: LGroup) -> float:
        g = grp.hints.get("gap")
        if g is not None:
            return float(g)
        # top-level items are ranks (room for edge labels); inside groups siblings sit closer
        return self.g.spacing.get("rank_gap", 80) if grp is self.g.root else self.g.spacing.get("gap", 40)

    def _collect(self, item) -> set[str]:
        """Node ids under each item."""
        ids = {item.id} if isinstance(item, LNode) else set().union(*(self._collect(c) for c in item.children))
        self.leaves[item.id] = ids
        return ids

    def _gaps(self, grp: LGroup, root: bool, cols: int, rows: int) -> tuple[list[float], list[float]]:
        """Gaps between consecutive columns and rows. In a single row or column, neighbours joined by a
        labelled edge get room for the pill and its arrowhead."""
        gap = self._gap(grp)
        gx, gy = [gap] * max(0, cols - 1), [gap] * max(0, rows - 1)
        kids = grp.children
        explicit = grp.hints.get("gap") is not None or grp is self.g.root  # root ranks are sized for labels already
        if self.labelled and not explicit and (rows == 1 or cols == 1):  # an explicit gap is the author's
            for k in range(len(kids) - 1):
                a, b = self.leaves[kids[k].id], self.leaves[kids[k + 1].id]
                need = max((w for s, t, w in self.labelled if (s in a and t in b) or (s in b and t in a)), default=0)
                if not need:
                    continue
                if rows == 1:  # side by side: the pill lies along the edge
                    gx[k] = max(gx[k], need + HEADS)
                else:  # stacked: the pill sits on or beside a vertical edge
                    gy[k] = max(gy[k], PILL_H + HEADS)
        return gx, gy

    def _cells(self, grp: LGroup, root: bool) -> tuple[list[float], list[float], int]:
        """Column widths, row heights and column count of the child grid."""
        kids = [self.size[c.id] for c in grp.children]
        cols = grp.hints.get("columns")
        if not cols:
            cols = len(kids) if self._dir(grp, root) == "row" else 1
        cols = max(1, min(int(cols), len(kids) or 1))
        rows = -(-len(kids) // cols) if kids else 0
        cw = [max((kids[r * cols + c][0] for r in range(rows) if r * cols + c < len(kids)), default=0)
              for c in range(cols)]
        rh = [max(k[1] for k in kids[r * cols:(r + 1) * cols]) for r in range(rows)]
        return cw, rh, cols

    def _measure(self, item, root: bool = False) -> tuple[float, float]:
        if isinstance(item, LNode):
            self.size[item.id] = (item.w, item.h)
            return self.size[item.id]
        for c in item.children:
            self._measure(c)
        cw, rh, cols = self._cells(item, root)
        gx, gy = self._gaps(item, root, cols, len(rh))
        t, r, b, l = item.pad
        w = sum(cw) + sum(gx) + l + r
        h = sum(rh) + sum(gy) + t + b
        self.size[item.id] = self.natural[item.id] = (w, h)
        return w, h

    # positions ----------------------------------------------------------------------------------
    def _place(self, grp: LGroup, x: float, y: float, boxes, root: bool = False) -> None:
        if not root:
            boxes[grp.id] = (x, y, *self.size[grp.id])
        cw, rh, cols = self._cells(grp, root)
        gx, gy = self._gaps(grp, root, cols, len(rh))
        t, _, _, l = grp.pad
        if not root:  # a stretched group keeps its content centred horizontally
            x += (self.size[grp.id][0] - self.natural[grp.id][0]) / 2
        align = grp.hints.get("align") or "center"
        fx = {"start": 0, "end": 1}.get(align, 0.5)
        for i, c in enumerate(grp.children):
            r, k = divmod(i, cols)
            cx = x + l + sum(cw[:k]) + sum(gx[:k])
            cy = y + t + sum(rh[:r]) + sum(gy[:r])
            w, h = self.size[c.id]
            if isinstance(c, LGroup) and align in ("center", "stretch"):
                # sibling groups share the row height / column width (equal AZ boxes)
                w, h = (w, rh[r]) if cols > 1 else (cw[k], h)
                self.size[c.id] = (w, h)
            cx += (cw[k] - w) * fx
            if cols > 1:
                cy += (rh[r] - h) * fx
            if isinstance(c, LGroup):
                self._place(c, cx, cy, boxes)
            else:
                boxes[c.id] = (cx, cy, w, h)

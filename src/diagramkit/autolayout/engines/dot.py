"""Graphviz ``dot`` layout (layered, hierarchical clusters).

The LGraph becomes DOT text: groups are nested ``cluster_*`` subgraphs, nodes fixed-size boxes
(1 px = 1 pt). ``dot -Tjson`` gives node centres, cluster bounding boxes and edge splines; y is flipped
to y-down. A cluster's margin is uniform, so the group's top band (label) is reserved with a blank,
top-placed cluster label whose font size fills the band — we render our own labels on top of it.
``graph.options`` go verbatim into the graph attributes (default ``splines=ortho``).
"""
from __future__ import annotations

import json
import shutil
import subprocess

from ..graph import LGraph, LGroup, LNode, LResult

_SAMPLES = 8


def _q(s: str) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _attr(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return f"{v:g}"
    return _q(v)


def _pt(s: str) -> tuple[float, float]:
    x, y = s.split(",")[:2]
    return float(x), float(y)


def _bezier(p0, p1, p2, p3, n: int = _SAMPLES) -> list[tuple[float, float]]:
    out = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        out.append((u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
                    u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]))
    return out


def _simplify(pts: list[tuple[float, float]], tol: float = 0.5) -> list[tuple[float, float]]:
    """Drop duplicate and collinear interior points (ortho splines come back as straight Béziers)."""
    dedup: list[tuple[float, float]] = []
    for p in pts:
        if not dedup or abs(p[0] - dedup[-1][0]) > 0.01 or abs(p[1] - dedup[-1][1]) > 0.01:
            dedup.append(p)
    if len(dedup) < 3:
        return dedup
    out = [dedup[0]]
    for i in range(1, len(dedup) - 1):
        a, b, c = out[-1], dedup[i], dedup[i + 1]
        cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        seg = max(abs(c[0] - a[0]) + abs(c[1] - a[1]), 1e-9)
        if abs(cross) / seg > tol:
            out.append(b)
    out.append(dedup[-1])
    return out


class DotEngine:
    name = "dot"

    def available(self) -> str | None:
        if shutil.which("dot"):
            return None
        return "Graphviz `dot` not found on PATH — install graphviz (apt install graphviz / brew install graphviz)"

    # DOT emission -------------------------------------------------------------------------------
    def to_dot(self, graph: LGraph) -> str:
        sp = graph.spacing
        attrs = {
            "rankdir": "TB" if graph.direction == "down" else "LR",
            "nodesep": round(sp.get("node_gap", 48) / 72, 4),
            "ranksep": round(sp.get("rank_gap", 80) / 72, 4),
            "compound": True,
            "newrank": True,
            "splines": "ortho",
            "outputorder": "edgesfirst",
        }
        attrs.update(graph.options)
        lines = ["digraph G {",
                 "  graph [" + ", ".join(f"{k}={_attr(v)}" for k, v in attrs.items()) + "];",
                 '  node [shape=box, fixedsize=true, label="", margin=0];',
                 "  edge [arrowhead=none];"]
        for c in graph.root.children:
            self._emit(c, lines, "  ")
        for e in graph.edges:
            lines.append(f"  {_q(e.src)} -> {_q(e.dst)};")
        lines.append("}")
        return "\n".join(lines)

    def _emit(self, item, lines: list[str], ind: str) -> None:
        if isinstance(item, LNode):
            lines.append(f"{ind}{_q(item.id)} [width={item.w / 72:.4f}, height={item.h / 72:.4f}];")
            return
        t, r, b, l = item.pad
        margin = max(r, b, l, 0)
        band = max(t - margin, 0)
        lines.append(f"{ind}subgraph {_q('cluster_' + item.id)} {{")
        lines.append(f"{ind}  margin={margin:g};")
        if band > 0:
            # blank top label reserves the band; dot's label box is ~1.2 * fontsize + 4pt (measured
            # on graphviz 2.43), so invert that to land the children right below the band
            fs = max((band - 4) / 1.2, 1.0)
            lines.append(f'{ind}  label=" "; labelloc=t; labeljust=l; fontsize={fs:.2f};')
        else:
            lines.append(f'{ind}  label="";')
        for c in item.children:
            self._emit(c, lines, ind + "  ")
        lines.append(f"{ind}}}")

    # run ----------------------------------------------------------------------------------------
    def run(self, graph: LGraph) -> LResult:
        src = self.to_dot(graph)
        try:
            p = subprocess.run(["dot", "-Tjson"], input=src, capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("dot layout timed out after 60s") from exc
        if p.returncode != 0:
            raise RuntimeError(f"dot failed (exit {p.returncode}): {p.stderr.strip()}")
        data = json.loads(p.stdout)
        H = float(data["bb"].split(",")[3])
        sizes = {c.id: (c.w, c.h) for c in graph.root.walk() if isinstance(c, LNode)}
        groups = {c.id for c in graph.root.walk() if isinstance(c, LGroup)} - {graph.root.id}

        boxes: dict[str, tuple[float, float, float, float]] = {}
        names: dict[int, str] = {}
        for o in data.get("objects", []):
            name = o.get("name", "")
            names[o.get("_gvid")] = name
            if name.startswith("cluster_") and name[8:] in groups and "bb" in o:
                x0, y0, x1, y1 = (float(v) for v in o["bb"].split(","))
                boxes[name[8:]] = (x0, H - y1, x1 - x0, y1 - y0)
            elif name in sizes and "pos" in o:
                cx, cy = _pt(o["pos"])
                w, h = sizes[name]
                boxes[name] = (cx - w / 2, H - cy - h / 2, w, h)

        # edges come back in declaration order; pair them per (tail, head) to keep multi-edges apart
        pending: dict[tuple[str, str], list[str]] = {}
        for e in graph.edges:
            pending.setdefault((e.src, e.dst), []).append(e.id)
        routes: dict[str, list[tuple[float, float]]] = {}
        for e in data.get("edges", []):
            key = (names.get(e.get("tail")), names.get(e.get("head")))
            ids = pending.get(key)
            if not ids or "pos" not in e:
                continue
            route = self._route(e["pos"])
            routes[ids.pop(0)] = [(x, H - y) for x, y in route]
        return LResult(boxes=boxes, routes=routes)

    @staticmethod
    def _route(pos: str) -> list[tuple[float, float]]:
        start = end = None
        ctrl: list[tuple[float, float]] = []
        for tok in pos.split():
            if tok.startswith("s,"):
                start = _pt(tok[2:])
            elif tok.startswith("e,"):
                end = _pt(tok[2:])
            else:
                ctrl.append(_pt(tok))
        pts: list[tuple[float, float]] = []
        if start:
            pts.append(start)
        if ctrl:
            pts.append(ctrl[0])
            for i in range(1, len(ctrl) - 2, 3):
                pts.extend(_bezier(ctrl[i - 1], ctrl[i], ctrl[i + 1], ctrl[i + 2]))
        if end:
            pts.append(end)
        return _simplify(pts)

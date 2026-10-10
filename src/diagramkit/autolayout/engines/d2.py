"""d2 adapter: LGraph → D2 text → ``d2 --layout <engine>`` → geometry read back from the SVG.

d2's SVG is not a public API (pinned against d2 0.7.x): every shape and container is
``<g class="base64(html-escaped D2 path)">`` holding ``<g class="shape"><rect x y width height>``;
connections are groups whose class decodes to ``[prefix.](src -> dst)[i]`` (paths relative to the
deepest common container) holding a ``<path d="M … L/C …">``. All coordinates share the frame of the
inner ``<svg>``; the caller translates by the bounding box, so that frame is used as-is.

Container padding cannot be set per container in d2, so the label band (``LGroup.pad[0]``) is
reserved with a one-character label placed ``near: top-center`` whose font size is chosen so the
top padding d2 leaves is at least the band (measured: band ≈ 1.25 · font-size + 11, elk and dagre).

Options (``layout.options``): ``layout`` = dagre | elk (default) | tala; keys prefixed ``elk-`` or
``dagre-`` become d2 CLI flags (``--elk-nodeNodeBetweenLayers 90``). Anything else is ignored.
Group hints (direction, columns, gap, align) are ignored — d2 places children itself.
"""
from __future__ import annotations

import base64
import html
import math
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from ..graph import LGraph, LGroup, LNode, LResult

SVG = "{http://www.w3.org/2000/svg}"
_CONN = re.compile(r"^(?:(?P<prefix>.*)\.)?\((?P<src>.*) -> (?P<dst>.*)\)\[(?P<i>\d+)\]$")
_TRANSLATE = re.compile(r"translate\(\s*([-\d.eE]+)[\s,]*([-\d.eE]*)\s*\)")
_TOKEN = re.compile(r"[MmLlHhVvCcSsQqTtZzAa]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def _q(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _font_for_band(band: float) -> int:
    """Label font size whose top padding (≈ 1.25·fs + 11) covers ``band``."""
    return max(8, math.ceil((band - 11) / 1.25) + 1)


def _segments(path: str) -> list[str]:
    """Split a D2 key path on dots outside quotes; strip the quotes."""
    out, cur, quote, esc = [], "", None, False
    for ch in path:
        if esc:
            cur += ch
            esc = False
        elif ch == "\\" and quote:
            esc = True
        elif quote:
            if ch == quote:
                quote = None
            else:
                cur += ch
        elif ch in "\"'":
            quote = ch
        elif ch == ".":
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    out.append(cur.strip())
    return out


def _decode(cls: str) -> str | None:
    try:
        return html.unescape(base64.b64decode(cls, validate=True).decode("utf-8"))
    except Exception:
        return None


def _cubic(p0, p1, p2, p3, n=6):
    return [((1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t * t * p2[0] + t ** 3 * p3[0],
             (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t * t * p2[1] + t ** 3 * p3[1])
            for t in (k / n for k in range(1, n + 1))]


def _quad(p0, p1, p2, n=6):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1])
            for t in (k / n for k in range(1, n + 1))]


def parse_path(d: str) -> list[tuple[float, float]]:
    """SVG path data → polyline (curves sampled; arcs reduced to their end point)."""
    toks = _TOKEN.findall(d)
    pts: list[tuple[float, float]] = []
    i, cmd = 0, None
    cur = start = (0.0, 0.0)
    last_ctrl = None  # (cmd-kind, point) for S/T reflection

    def num() -> float:
        nonlocal i
        v = float(toks[i])
        i += 1
        return v

    while i < len(toks):
        if toks[i].isalpha():
            cmd = toks[i]
            i += 1
            if cmd in "Zz":
                cur = start
                pts.append(cur)
                last_ctrl = None
                continue
        if cmd is None:
            break
        rel = cmd.islower()
        c = cmd.upper()
        ox, oy = cur if rel else (0.0, 0.0)
        if c == "M":
            cur = start = (ox + num(), oy + num())
            pts.append(cur)
            cmd = "l" if rel else "L"  # implicit lineto after the first pair
            last_ctrl = None
        elif c == "L":
            cur = (ox + num(), oy + num())
            pts.append(cur)
            last_ctrl = None
        elif c == "H":
            cur = ((cur[0] if rel else 0.0) + num(), cur[1])
            pts.append(cur)
            last_ctrl = None
        elif c == "V":
            cur = (cur[0], (cur[1] if rel else 0.0) + num())
            pts.append(cur)
            last_ctrl = None
        elif c == "C":
            p1, p2, p3 = (ox + num(), oy + num()), (ox + num(), oy + num()), (ox + num(), oy + num())
            pts += _cubic(cur, p1, p2, p3)
            cur, last_ctrl = p3, ("C", p2)
        elif c == "S":
            p1 = (2 * cur[0] - last_ctrl[1][0], 2 * cur[1] - last_ctrl[1][1]) if last_ctrl and last_ctrl[0] == "C" else cur
            p2, p3 = (ox + num(), oy + num()), (ox + num(), oy + num())
            pts += _cubic(cur, p1, p2, p3)
            cur, last_ctrl = p3, ("C", p2)
        elif c == "Q":
            p1, p2 = (ox + num(), oy + num()), (ox + num(), oy + num())
            pts += _quad(cur, p1, p2)
            cur, last_ctrl = p2, ("Q", p1)
        elif c == "T":
            p1 = (2 * cur[0] - last_ctrl[1][0], 2 * cur[1] - last_ctrl[1][1]) if last_ctrl and last_ctrl[0] == "Q" else cur
            p2 = (ox + num(), oy + num())
            pts += _quad(cur, p1, p2)
            cur, last_ctrl = p2, ("Q", p1)
        elif c == "A":
            for _ in range(5):
                num()
            cur = (ox + num(), oy + num())
            pts.append(cur)
            last_ctrl = None
        else:  # unknown command: stop rather than misread
            break
    dedup = [pts[0]] if pts else []
    for p in pts[1:]:
        if abs(p[0] - dedup[-1][0]) > 1e-6 or abs(p[1] - dedup[-1][1]) > 1e-6:
            dedup.append(p)
    return dedup


class D2Engine:
    name = "d2"

    def available(self) -> str | None:
        if shutil.which("d2"):
            return None
        return "d2 not found on PATH — install: curl -fsSL https://d2lang.com/install.sh | sh"

    # D2 source ----------------------------------------------------------------------------------
    def to_d2(self, graph: LGraph) -> str:
        lines = [f"direction: {'down' if graph.direction == 'down' else 'right'}"]
        self.paths: dict[str, str] = {}

        def emit(item, prefix: list[str], depth: int) -> None:
            ind = "  " * depth
            path = prefix + [item.id]
            self.paths[item.id] = ".".join(_q(s) for s in path)
            if isinstance(item, LNode):
                lines.append(f"{ind}{_q(item.id)}: {{ label: \"\"; width: {round(item.w)}; "
                             f"height: {round(item.h)}; shape: rectangle }}")
                return
            lines.append(f"{ind}{_q(item.id)}: {{")
            lines.append(f"{ind}  label: \"M\"")
            lines.append(f"{ind}  label.near: top-center")
            lines.append(f"{ind}  style.font-size: {_font_for_band(item.pad[0])}")
            for c in item.children:
                emit(c, path, depth + 1)
            lines.append(f"{ind}}}")

        for c in graph.root.children:
            emit(c, [], 0)
        for e in graph.edges:
            if e.src in self.paths and e.dst in self.paths:
                lines.append(f"{self.paths[e.src]} -> {self.paths[e.dst]}")
        return "\n".join(lines) + "\n"

    def _flags(self, graph: LGraph) -> list[str]:
        layout = str(graph.options.get("layout", "elk"))
        opts = {k: v for k, v in graph.options.items() if k.startswith(("elk-", "dagre-"))}
        sp = graph.spacing
        if layout == "elk":
            opts.setdefault("elk-nodeNodeBetweenLayers", round(sp.get("rank_gap", 80)))
            # elk padding is global: use the tightest side padding (the top band comes from the label)
            sides = [v for g in graph.root.walk() if isinstance(g, LGroup) and g is not graph.root
                     for v in g.pad[1:]]
            if sides:
                p = round(min(sides))
                opts.setdefault("elk-padding", f"[top={p},left={p},bottom={p},right={p}]")
        elif layout == "dagre":
            opts.setdefault("dagre-nodesep", round(sp.get("node_gap", 48)))
        flags = ["--layout", layout, "--pad", "0"]
        for k, v in opts.items():
            flags += [f"--{k}", str(v)]
        return flags

    # run ----------------------------------------------------------------------------------------
    def run(self, graph: LGraph) -> LResult:
        src = self.to_d2(graph)
        with tempfile.TemporaryDirectory(prefix="diagramkit-d2-") as tmp:
            fin, fout = Path(tmp) / "in.d2", Path(tmp) / "out.svg"
            fin.write_text(src, encoding="utf-8")
            try:
                proc = subprocess.run(["d2", *self._flags(graph), str(fin), str(fout)],
                                      capture_output=True, text=True, timeout=60)
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("d2 layout timed out after 60 s") from exc
            if proc.returncode != 0 or not fout.exists():
                raise RuntimeError(f"d2 failed (exit {proc.returncode}): {(proc.stderr or proc.stdout).strip()}")
            svg = fout.read_text(encoding="utf-8")
        return self.parse_svg(svg, graph)

    # SVG → result -------------------------------------------------------------------------------
    def parse_svg(self, svg: str, graph: LGraph) -> LResult:
        ids = {c.id for c in graph.root.walk() if c is not graph.root}
        boxes: dict[str, tuple[float, float, float, float]] = {}
        conns: dict[tuple[str, str, int], list[tuple[float, float]]] = {}

        def walk(el, dx: float, dy: float) -> None:
            for ch in el:
                tx, ty = dx, dy
                m = _TRANSLATE.search(ch.get("transform", ""))
                if m:
                    tx += float(m.group(1))
                    ty += float(m.group(2) or 0)
                if ch.tag == SVG + "g":
                    key = _decode(ch.get("class", "")) if ch.get("class") else None
                    if key is not None:
                        self._read_item(ch, key, tx, ty, ids, boxes, conns)
                walk(ch, tx, ty)

        walk(ET.fromstring(svg), 0.0, 0.0)
        routes: dict[str, list[tuple[float, float]]] = {}
        seen: dict[tuple[str, str], int] = {}
        for e in graph.edges:
            i = seen.get((e.src, e.dst), 0)
            seen[(e.src, e.dst)] = i + 1
            pts = conns.get((e.src, e.dst, i))
            if pts and len(pts) >= 2:
                routes[e.id] = pts
        missing = ids - boxes.keys()
        if missing:
            raise RuntimeError(f"d2 output lacks boxes for: {', '.join(sorted(missing))}")
        return LResult(boxes=boxes, routes=routes)

    @staticmethod
    def _read_item(g, key, dx, dy, ids, boxes, conns) -> None:
        m = _CONN.match(key)
        if m:
            path = g.find(f".//{SVG}path")
            if path is None or not path.get("d"):
                return
            a, b = _segments(m.group("src"))[-1], _segments(m.group("dst"))[-1]
            pts = [(x + dx, y + dy) for x, y in parse_path(path.get("d"))]
            conns[(a, b, int(m.group("i")))] = pts
            return
        nid = _segments(key)[-1]
        if nid not in ids or nid in boxes:
            return
        shape = next((c for c in g if c.tag == SVG + "g" and c.get("class") == "shape"), None)
        rect = shape.find(f"{SVG}rect") if shape is not None else None
        if rect is None:
            return
        sx, sy = dx, dy
        m2 = _TRANSLATE.search(shape.get("transform", ""))
        if m2:
            sx += float(m2.group(1))
            sy += float(m2.group(2) or 0)
        boxes[nid] = (float(rect.get("x")) + sx, float(rect.get("y")) + sy,
                      float(rect.get("width")), float(rect.get("height")))

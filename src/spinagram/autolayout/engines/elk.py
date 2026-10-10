"""ELK layered layout via ``elkjs`` run by ``bun`` (preferred) or ``node``.

The diagram becomes a hierarchical ELK graph: groups are compound nodes with ``elk.padding`` (top
includes the label band), every edge sits on the root and ``elk.hierarchyHandling: INCLUDE_CHILDREN``
lets ELK route cross-group edges orthogonally. ``elkjs`` (pinned) is installed into the spinagram
cache on first use with ``npm`` (honours ``~/.npmrc`` / ``npm_config_registry``), else ``bun``.
ELK coordinates are relative to the parent node; edge sections are relative to the edge's
``container`` — both are accumulated to absolute positions here.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path

from ...icons import cache_root
from ..graph import LGraph, LNode, LResult

ELKJS_VERSION = "0.12.0"
RUNNER = Path(__file__).with_name("elk_runner.mjs")
TIMEOUT = 60
HINT = "ELK needs bun or node on PATH (https://bun.sh or https://nodejs.org)"


def elk_dir() -> Path:
    return Path(os.environ.get("SPINAGRAM_ELK_DIR") or cache_root().parent / "elk")


def _runtime() -> str | None:
    return shutil.which("bun") or shutil.which("node")


def _installed(base: Path) -> bool:
    pkg = base / "node_modules" / "elkjs" / "package.json"
    try:
        return json.loads(pkg.read_text()).get("version") == ELKJS_VERSION
    except (OSError, ValueError):
        return False


@contextmanager
def _lock(base: Path):
    base.mkdir(parents=True, exist_ok=True)
    with open(base / ".lock", "w") as fh:
        try:
            import fcntl
            fcntl.flock(fh, fcntl.LOCK_EX)
        except ImportError:  # Windows: best effort, no lock
            pass
        yield


def ensure_elkjs() -> Path:
    """Directory holding ``node_modules/elkjs@ELKJS_VERSION``; installs it on first use."""
    base = elk_dir()
    if _installed(base):
        return base
    with _lock(base):
        if _installed(base):  # another process finished first
            return base
        spec = f"elkjs@{ELKJS_VERSION}"
        if shutil.which("npm"):
            cmd = ["npm", "install", "--no-save", "--no-audit", "--no-fund", "--prefix", str(base), spec]
        elif shutil.which("bun"):
            (base / "package.json").exists() or (base / "package.json").write_text('{"private": true}\n')
            cmd = ["bun", "add", "--exact", spec]
        else:
            raise RuntimeError(f"cannot install {spec}: neither npm nor bun on PATH. {HINT}")
        try:
            p = subprocess.run(cmd, cwd=base, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"installing {spec} timed out ({' '.join(cmd)})") from e
        if p.returncode != 0 or not _installed(base):
            raise RuntimeError(
                f"installing {spec} into {base} failed ({' '.join(cmd)}):\n{p.stderr.strip()}\n"
                "check the npm registry in ~/.npmrc (npm_config_registry) or install it there by hand")
    return base


class ElkEngine:
    name = "elk"

    def available(self) -> str | None:
        return None if _runtime() else HINT

    # graph → ELK JSON ---------------------------------------------------------------------------
    def _dir(self, d: str | None) -> str | None:
        return {"right": "RIGHT", "row": "RIGHT", "down": "DOWN", "column": "DOWN"}.get(d or "")

    def _item(self, item) -> dict:
        if isinstance(item, LNode):
            return {"id": item.id, "width": item.w, "height": item.h}
        t, r, b, l = item.pad
        opts = {"elk.padding": f"[top={t},left={l},bottom={b},right={r}]"}
        if d := self._dir(item.hints.get("direction")):
            opts["elk.direction"] = d
        if (gap := item.hints.get("gap")) is not None:
            opts["elk.spacing.nodeNode"] = gap
        return {"id": item.id, "layoutOptions": opts, "children": [self._item(c) for c in item.children]}

    def to_elk(self, graph: LGraph) -> dict:
        sp = graph.spacing
        node_gap = sp.get("node_gap", 48)
        opts = {
            "elk.algorithm": "layered",
            "elk.direction": self._dir(graph.direction) or "RIGHT",
            "elk.hierarchyHandling": "INCLUDE_CHILDREN",
            "elk.edgeRouting": "ORTHOGONAL",
            "elk.spacing.nodeNode": node_gap,
            "elk.layered.spacing.nodeNodeBetweenLayers": sp.get("rank_gap", 80),
            "elk.spacing.edgeNode": node_gap / 2,
            "elk.spacing.edgeEdge": max(8, node_gap / 4),
            "elk.layered.spacing.edgeNodeBetweenLayers": node_gap / 2,
            "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
            "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",  # keep author order (AZ a, b, c)
        }
        opts.update(graph.options or {})  # LAY-16: verbatim passthrough wins
        return {
            "id": "root",
            "layoutOptions": {k: str(v) for k, v in opts.items()},
            "children": [self._item(c) for c in graph.root.children],
            "edges": [{"id": e.id, "sources": [e.src], "targets": [e.dst]} for e in graph.edges],
        }

    # run + read back ----------------------------------------------------------------------------
    def run(self, graph: LGraph) -> LResult:
        rt = _runtime()
        if not rt:
            raise RuntimeError(HINT)
        base = ensure_elkjs()
        try:
            p = subprocess.run([rt, str(RUNNER), str(base)], input=json.dumps(self.to_elk(graph)),
                               capture_output=True, text=True, timeout=TIMEOUT)
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"elk layout timed out after {TIMEOUT}s") from e
        if p.returncode != 0:
            raise RuntimeError(f"elk layout failed ({os.path.basename(rt)}):\n{p.stderr.strip()}")
        return self.from_elk(json.loads(p.stdout))

    def from_elk(self, out: dict) -> LResult:
        boxes: dict[str, tuple[float, float, float, float]] = {}
        offset: dict[str, tuple[float, float]] = {"root": (0.0, 0.0)}
        edges: list[dict] = list(out.get("edges", []))

        def walk(n: dict, ox: float, oy: float) -> None:
            for c in n.get("children", []) or []:
                x, y = ox + c.get("x", 0.0), oy + c.get("y", 0.0)
                boxes[c["id"]] = (x, y, c.get("width", 0.0), c.get("height", 0.0))
                offset[c["id"]] = (x, y)
                edges.extend(c.get("edges", []) or [])
                walk(c, x, y)

        walk(out, 0.0, 0.0)
        routes: dict[str, list[tuple[float, float]]] = {}
        for e in edges:
            secs = e.get("sections") or []
            if not secs:
                continue
            ox, oy = offset.get(e.get("container") or "root", (0.0, 0.0))
            pts: list[tuple[float, float]] = []
            for s in secs:
                for p in [s["startPoint"], *(s.get("bendPoints") or []), s["endPoint"]]:
                    q = (ox + p["x"], oy + p["y"])
                    if not pts or pts[-1] != q:
                        pts.append(q)
            routes[e["id"]] = pts
        return LResult(boxes=boxes, routes=routes)

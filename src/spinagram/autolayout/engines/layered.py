"""Layered (Sugiyama) layout, pure Python and deterministic: the default for flow, activity and state.

Each group level is laid out on its own, bottom-up: a group's direct children (nodes, and child groups
as fixed blocks) are ranked along the flow, ordered to reduce crossings and placed; the group is then
sized from that content plus its padding. Per level:

1. cycles are broken by reversing DFS back-edges (they are drawn in their original direction);
2. ranks by longest path, sources pulled next to their first successor;
3. edges spanning several ranks get one dummy per rank, reserving a channel for their route;
4. order by barycentre sweeps (ties by declaration order), keeping the ordering with fewest crossings;
5. coordinates along each rank by isotonic regression (pool adjacent violators) toward the neighbours,
   with the minimum gaps as constraints;
6. orthogonal routes: vertical through ports and dummy channels, horizontal on staggered tracks in the
   gaps between ranks; back-edges spanning several ranks go round the outer side.

Work happens in a rank frame (``o`` along a rank, ``r`` along the flow): ``down`` maps o→x, r→y and
``right`` maps o→y, r→x. Disconnected components are laid out apart and placed side by side.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field

from ..graph import LEdge, LGraph, LGroup, LNode, LResult
from ..route import loop, route

DIAMONDS = {"decision", "diamond", "choice", "merge"}
ROUND = {"initial", "final", "flow_final", "connector", "history", "deep_history"}
MAX_NODES = 300
SWEEPS = 24
PASSES = 8
TRACK = 16.0  # spacing of parallel outer tracks


@dataclass
class _Item:
    id: str
    o: float                  # size along a rank
    r: float                  # size along the flow
    kind: str = "box"
    dummy: bool = False
    rank: int = 0
    pos: float = 0.0          # centre along the rank
    order: int = 0


@dataclass
class _Level:
    """Result of one level in its rank frame (top-left boxes; routes in the same frame)."""
    boxes: dict[str, tuple[float, float, float, float]] = field(default_factory=dict)  # id → o, r, os, rs
    routes: dict[str, list[tuple[float, float]]] = field(default_factory=dict)
    size: tuple[float, float] = (0.0, 0.0)  # extent along o, r


def _pav(d: list[float], w: list[float]) -> list[float]:
    """Weighted isotonic regression: non-decreasing y minimising sum w·(y - d)²."""
    blocks: list[list[float]] = []  # [sum w·d, sum w, count]
    for di, wi in zip(d, w):
        blocks.append([di * wi, wi, 1])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
            s, ww, c = blocks.pop()
            blocks[-1][0] += s
            blocks[-1][1] += ww
            blocks[-1][2] += c
    out: list[float] = []
    for s, ww, c in blocks:
        out += [s / ww] * int(c)
    return out


class LayeredEngine:
    name = "layered"

    def available(self) -> str | None:
        return None

    # entry --------------------------------------------------------------------------------------
    def run(self, graph: LGraph) -> LResult:
        self.g = graph
        self.gap = float(graph.spacing.get("node_gap", 48))
        self.rank_gap = float(graph.spacing.get("rank_gap", 80))
        n_nodes = sum(1 for c in graph.root.walk() if isinstance(c, LNode))
        if n_nodes > MAX_NODES:
            warnings.warn(f"layered layout: {n_nodes} nodes exceeds the {MAX_NODES}-node bound; "
                          "the result may be slow and hard to read", stacklevel=2)
        self.parent: dict[str, str] = {}
        for item in graph.root.walk():
            if isinstance(item, LGroup):
                for c in item.children:
                    self.parent[c.id] = item.id
        self.local: dict[str, tuple[float, float, float, float]] = {}  # id → x, y, w, h in parent content
        self.local_routes: dict[str, tuple[str, list[tuple[float, float]]]] = {}  # eid → (group id, pts)
        self.sizes: dict[str, tuple[float, float]] = {}
        self.loop_nodes = {e.src for e in graph.loops}
        self.loop_w = 40.0 + 12.0 + float(graph.spacing.get("loop_label", 0))
        self.dir_of: dict[str, str] = {}
        self._measure(graph.root, graph.direction)
        boxes: dict[str, tuple[float, float, float, float]] = {}
        origin: dict[str, tuple[float, float]] = {graph.root.id: (0.0, 0.0)}
        for item in graph.root.walk():
            if item is graph.root:
                continue
            ox, oy = origin[self.parent[item.id]]
            x, y, w, h = self.local[item.id]
            boxes[item.id] = (round(ox + x, 1), round(oy + y, 1), round(w, 1), round(h, 1))
            if isinstance(item, LGroup):
                origin[item.id] = (ox + x, oy + y)
        routes = {}
        for eid, (gid, pts) in self.local_routes.items():
            ox, oy = origin[gid]
            routes[eid] = [(round(ox + x, 1), round(oy + y, 1)) for x, y in pts]
        nodes = [boxes[c.id] for c in graph.root.walk() if isinstance(c, LNode)]
        for e in graph.edges:  # edges between nested items: routed around every node on the final geometry
            if e.id not in routes and e.src in boxes and e.dst in boxes:
                routes[e.id] = route(boxes[e.src], boxes[e.dst], nodes)
        for e in graph.loops:
            side = "right" if self.dir_of.get(e.src, "down") == "down" else "bottom"
            routes[e.id] = [(round(x, 1), round(y, 1)) for x, y in loop(boxes[e.src], side)]
        return LResult(boxes=boxes, routes=routes)

    # levels -------------------------------------------------------------------------------------
    def _chain(self, nid: str) -> list[str]:
        out = [nid]
        while out[-1] in self.parent:
            out.append(self.parent[out[-1]])
        return out[::-1]  # root … nid

    def _level_edges(self, group: LGroup) -> list[tuple[str, str, str, bool]]:
        """(edge id, src item, dst item, direct) for edges whose lowest common group is ``group``."""
        kids = {c.id for c in group.children}
        out = []
        for e in self.g.edges:
            ca, cb = self._chain(e.src), self._chain(e.dst)
            i = 0
            while i < min(len(ca), len(cb)) and ca[i] == cb[i]:
                i += 1
            if i == 0 or ca[i - 1] != group.id or i >= len(ca) or i >= len(cb):
                continue
            a, b = ca[i], cb[i]
            if a in kids and b in kids and a != b:
                out.append((e.id, a, b, a == e.src and b == e.dst))
        return out

    def _measure(self, group: LGroup, direction: str) -> tuple[float, float]:
        direction = group.hints.get("direction", direction) if group is not self.g.root else direction
        direction = "down" if direction in ("down", "column") else "right"
        if group.hints.get("lanes"):
            return self._measure_lanes(group, direction)
        for c in group.children:
            self.dir_of[c.id] = direction
            if isinstance(c, LGroup):
                self.sizes[c.id] = self._measure(c, direction)
            else:
                self.sizes[c.id] = (c.w, c.h)
        kinds = {c.id: getattr(c, "kind", "box") for c in group.children if isinstance(c, LNode)}
        items = [c.id for c in group.children]
        edges = self._level_edges(group)
        lvl = self._layout_level(items, kinds, edges, direction)
        top, right, bottom, left = group.pad
        for iid, (o, r, os_, rs) in lvl.boxes.items():
            x, y, w, h = (o, r, os_, rs) if direction == "down" else (r, o, rs, os_)
            self.local[iid] = (left + x, top + y, w, h)
        for eid, pts in lvl.routes.items():
            pts = pts if direction == "down" else [(r, o) for o, r in pts]
            self.local_routes[eid] = (group.id, [(left + x, top + y) for x, y in pts])
        so, sr = lvl.size
        w, h = (so, sr) if direction == "down" else (sr, so)
        return (w + left + right, h + top + bottom)

    def _measure_lanes(self, group: LGroup, direction: str) -> tuple[float, float]:
        """Swimlanes: every lane member is laid out at one level (shared ranks), lanes become bands."""
        down = direction == "down"
        lanes = [c for c in group.children if isinstance(c, LGroup)]
        loose = [c for c in group.children if not isinstance(c, LGroup)]
        lane_ids = {ln.id for ln in lanes}
        buckets: list[tuple[LGroup | None, list]] = ([(None, loose)] if loose else []) + [(ln, ln.children) for ln in lanes]
        members: list[str] = []
        lane_of: dict[str, int] = {}
        kinds: dict[str, str] = {}
        for li, (_, kids) in enumerate(buckets):
            for c in kids:
                self.dir_of[c.id] = direction
                if isinstance(c, LGroup):
                    self.sizes[c.id] = self._measure(c, direction)
                else:
                    self.sizes[c.id] = (c.w, c.h)
                    kinds[c.id] = getattr(c, "kind", "box")
                members.append(c.id)
                lane_of[c.id] = li
        edges = []
        for e in self.g.edges:
            ends = []
            for nid in (e.src, e.dst):
                ch = self._chain(nid)
                if group.id not in ch:
                    break
                p = ch.index(group.id)
                if p + 1 >= len(ch):
                    break
                item = ch[p + 1]
                if item in lane_ids:
                    if p + 2 >= len(ch):
                        break
                    item = ch[p + 2]
                ends.append(item)
            if len(ends) == 2 and ends[0] != ends[1]:
                a, b = ends
                edges.append((e.id, a, b, a == e.src and b == e.dst and lane_of[a] == lane_of[b]))
        lvl = self._sugiyama(members, kinds, edges, direction, lane_of=lane_of)
        top, right, bottom, left = group.pad

        def opads(g: LGroup | None) -> tuple[float, float, float, float]:
            if g is None:
                return 0.0, 0.0, 0.0, 0.0
            t, rt, b, lf = g.pad
            return (lf, rt, t, b) if down else (t, b, lf, rt)  # o-start, o-end, r-start, r-end

        r0 = max([opads(g)[2] for g, _ in buckets] + [0.0])
        r1 = max([opads(g)[3] for g, _ in buckets] + [0.0])
        r_end = lvl.size[1]
        cursor = 0.0
        shift: dict[int, float] = {}
        lane_box: dict[str, tuple[float, float, float, float]] = {}
        for li, (g, kids) in enumerate(buckets):
            os0, os1, _, _ = opads(g)
            if kids:
                lo = min(lvl.boxes[c.id][0] for c in kids)
                hi = max(lvl.boxes[c.id][0] + lvl.boxes[c.id][2] for c in kids)
            else:
                lo = hi = 0.0
            width = max(os0 + (hi - lo) + os1, 200.0 if g is not None and not kids else 0.0)
            shift[li] = cursor + os0 - lo
            if g is not None:
                lane_box[g.id] = (cursor, 0.0, width, r_end + r0 + r1)
            cursor += width
        frame: dict[str, tuple[float, float, float, float]] = {}
        for m in members:
            o, r, os_, rs = lvl.boxes[m]
            frame[m] = (o + shift[lane_of[m]], r + r0, os_, rs)

        def to_xy(b):
            o, r, os_, rs = b
            return (o, r, os_, rs) if down else (r, o, rs, os_)

        for g, kids in buckets:
            if g is not None:
                lx, ly, lw, lh = to_xy(lane_box[g.id])
                self.local[g.id] = (left + lx, top + ly, lw, lh)
                self.sizes[g.id] = (lw, lh)
                for c in kids:
                    x, y, w, h = to_xy(frame[c.id])
                    self.local[c.id] = (x - lx, y - ly, w, h)
            else:
                for c in kids:
                    x, y, w, h = to_xy(frame[c.id])
                    self.local[c.id] = (left + x, top + y, w, h)
        for eid, pts in lvl.routes.items():
            a = next(e[1] for e in edges if e[0] == eid)
            dx = shift[lane_of[a]]
            moved = [(o + dx, r + r0) for o, r in pts]
            moved = moved if down else [(r, o) for o, r in moved]
            self.local_routes[eid] = (group.id, [(left + x, top + y) for x, y in moved])
        so, sr = cursor, r_end + r0 + r1
        w, h = (so, sr) if down else (sr, so)
        return (w + left + right, h + top + bottom)

    def _layout_level(self, items: list[str], kinds: dict[str, str], edges, direction: str) -> _Level:
        """Components laid out apart, then placed side by side along the rank axis."""
        comp = {i: i for i in items}

        def find(i: str) -> str:
            while comp[i] != i:
                comp[i] = comp[comp[i]]
                i = comp[i]
            return i

        for _, a, b, _ in edges:
            ra, rb = find(a), find(b)
            if ra != rb:
                comp[max(ra, rb, key=items.index)] = min(ra, rb, key=items.index)
        groups: dict[str, list[str]] = {}
        for i in items:
            groups.setdefault(find(i), []).append(i)
        out = _Level()
        cursor, height = 0.0, 0.0
        for members in groups.values():
            ms = set(members)
            sub = self._sugiyama(members, kinds, [e for e in edges if e[1] in ms], direction)
            for iid, (o, r, os_, rs) in sub.boxes.items():
                out.boxes[iid] = (o + cursor, r, os_, rs)
            for eid, pts in sub.routes.items():
                out.routes[eid] = [(o + cursor, r) for o, r in pts]
            cursor += sub.size[0] + self.gap
            height = max(height, sub.size[1])
        out.size = (max(0.0, cursor - self.gap), height)
        return out

    # the pipeline -------------------------------------------------------------------------------
    def _sugiyama(self, members: list[str], kinds: dict[str, str], edges, direction: str,
                  lane_of: dict[str, int] | None = None) -> _Level:
        idx = {m: i for i, m in enumerate(members)}
        down = direction == "down"
        lane = dict(lane_of or {})
        it: dict[str, _Item] = {}
        extra: dict[str, float] = {}
        for m in members:
            w, h = self.sizes[m]
            extra[m] = self.loop_w if m in self.loop_nodes else 0.0  # room for a self-loop on the o-end side
            it[m] = _Item(m, (w if down else h) + extra[m], h if down else w, kinds.get(m, "box"))

        # 1. cycles: DFS in declaration order; edges to a node on the stack are reversed
        out_adj: dict[str, list[tuple[str, str]]] = {m: [] for m in members}
        for eid, a, b, _ in edges:
            out_adj[a].append((eid, b))
        state: dict[str, int] = {}
        reversed_: set[str] = set()
        for root in members:
            if root in state:
                continue
            stack = [(root, iter(out_adj[root]))]
            state[root] = 1
            while stack:
                v, nxt = stack[-1]
                step = next(nxt, None)
                if step is None:
                    state[v] = 2
                    stack.pop()
                    continue
                eid, w = step
                if state.get(w) == 1:
                    reversed_.add(eid)
                elif w not in state:
                    state[w] = 1
                    stack.append((w, iter(out_adj[w])))
        dag = [(eid, b, a) if eid in reversed_ else (eid, a, b) for eid, a, b, _ in edges]

        # 2. ranks: longest path over the DAG (Kahn, declaration order), sources pulled down
        preds: dict[str, list[str]] = {m: [] for m in members}
        succs: dict[str, list[str]] = {m: [] for m in members}
        for _, a, b in dag:
            succs[a].append(b)
            preds[b].append(a)
        indeg = {m: len(preds[m]) for m in members}
        ready = [m for m in members if not indeg[m]]
        topo: list[str] = []
        while ready:
            ready.sort(key=idx.get)
            v = ready.pop(0)
            topo.append(v)
            for w in succs[v]:
                indeg[w] -= 1
                if not indeg[w]:
                    ready.append(w)
        rank = {m: 0 for m in members}
        for v in topo:
            for w in succs[v]:
                rank[w] = max(rank[w], rank[v] + 1)
        for v in reversed(topo):
            if not preds[v] and succs[v]:
                rank[v] = max(rank[v], min(rank[w] for w in succs[v]) - 1)
        for m in members:
            it[m].rank = rank[m]
        n_ranks = max(rank.values()) + 1 if members else 0

        # 3. dummies on forward edges spanning several ranks
        chains: dict[str, list[str]] = {}
        dummy_o = 2.0
        for eid, a, b in dag:
            if eid in reversed_:
                continue
            chain = [a]
            for k in range(rank[a] + 1, rank[b]):
                did = f"__d{eid}_{k}"
                it[did] = _Item(did, dummy_o, 0.0, "dummy", True, k)
                lane[did] = lane.get(a, 0)
                chain.append(did)
            chain.append(b)
            chains[eid] = chain
        segs: list[tuple[str, str, float]] = []  # (upper, lower, weight) between consecutive ranks
        for chain in chains.values():
            for u, v in zip(chain, chain[1:]):
                weight = 8.0 if it[u].dummy and it[v].dummy else (2.0 if it[u].dummy or it[v].dummy else 1.0)
                segs.append((u, v, weight))
        up_n: dict[str, list[tuple[str, float]]] = {k: [] for k in it}
        dn_n: dict[str, list[tuple[str, float]]] = {k: [] for k in it}
        for u, v, wgt in segs:
            dn_n[u].append((v, wgt))
            up_n[v].append((u, wgt))

        # 4. ordering
        ranks: list[list[str]] = [[] for _ in range(n_ranks)]
        key = {m: float(idx[m]) for m in members}
        for k, item in it.items():
            if item.dummy:
                key[k] = float(idx[chains[k[3:].rsplit("_", 1)[0]][0]]) + 0.5
        for k in sorted(it, key=lambda k: (lane.get(k, 0), key[k], k)):
            ranks[it[k].rank].append(k)

        def positions() -> None:
            for row in ranks:
                for i, k in enumerate(row):
                    it[k].order = i

        def crossings() -> int:
            total = 0
            for i in range(n_ranks - 1):
                pairs = [(it[u].order, it[v].order) for u in ranks[i] for v, _ in dn_n[u]]
                for x in range(len(pairs)):
                    for y in range(x + 1, len(pairs)):
                        (a1, b1), (a2, b2) = pairs[x], pairs[y]
                        if (a1 - a2) * (b1 - b2) < 0:
                            total += 1
            return total

        positions()
        best, best_c = [list(r) for r in ranks], crossings()
        for sweep in range(SWEEPS):
            rng = range(1, n_ranks) if sweep % 2 == 0 else range(n_ranks - 2, -1, -1)
            for i in rng:
                nb = up_n if sweep % 2 == 0 else dn_n

                def bary(k: str) -> float:
                    ns = nb[k]
                    return sum(it[n].order for n, _ in ns) / len(ns) if ns else float(it[k].order)

                ranks[i].sort(key=lambda k: (lane.get(k, 0), bary(k), it[k].order))
                for j, k in enumerate(ranks[i]):
                    it[k].order = j
            c = crossings()
            if c < best_c:
                best, best_c = [list(r) for r in ranks], c
        ranks = best
        positions()

        # 5. coordinates along each rank
        def sep(a: str, b: str) -> float:
            g = self.gap if not (it[a].dummy or it[b].dummy) else self.gap / 2
            return it[a].o / 2 + g + it[b].o / 2

        for row in ranks:
            x = 0.0
            for i, k in enumerate(row):
                if i:
                    x += sep(row[i - 1], k)
                it[k].pos = x

        def solve(row: list[str], desired: list[float]) -> None:
            offs = [0.0]
            for i in range(1, len(row)):
                offs.append(offs[-1] + sep(row[i - 1], row[i]))
            w = [4.0 if it[k].dummy else 1.0 for k in row]
            ys = _pav([d - s for d, s in zip(desired, offs)], w)
            for k, yv, s in zip(row, ys, offs):
                it[k].pos = yv + s

        def target(k: str, nbrs) -> float:
            ns = nbrs[k]
            if not ns:
                return it[k].pos
            tw = sum(w for _, w in ns)
            return sum(it[n].pos * w for n, w in ns) / tw

        for p in range(PASSES):
            if p % 2 == 0:
                for i in range(1, n_ranks):
                    solve(ranks[i], [target(k, up_n) for k in ranks[i]])
            else:
                for i in range(n_ranks - 2, -1, -1):
                    solve(ranks[i], [target(k, dn_n) for k in ranks[i]])
        both = {k: up_n[k] + dn_n[k] for k in it}
        for i in range(n_ranks):
            solve(ranks[i], [target(k, both) for k in ranks[i]])
        lo = min((it[k].pos - it[k].o / 2 for k in it), default=0.0)
        for k in it:
            it[k].pos -= lo

        # rank bands
        band = [max([it[k].r for k in row if not it[k].dummy] + [0.0]) for row in ranks]
        r_top, r = [], 0.0
        for i in range(n_ranks):
            r_top.append(r)
            r += band[i] + self.rank_gap
        r_end = r - self.rank_gap if n_ranks else 0.0
        lvl = _Level()
        for m in members:
            item = it[m]
            k = item.rank
            lvl.boxes[m] = (item.pos - item.o / 2, r_top[k] + (band[k] - item.r) / 2, item.o - extra[m], item.r)

        # 6. routes (direct edges only; edges to nested items are routed after layout)
        direct = {eid for eid, a, b, d in edges if d and not (lane_of is not None and eid in reversed_)}
        self._route(lvl, it, chains, dag, reversed_, direct, ranks, r_top, band)
        o_end = max((it[k].pos + it[k].o / 2 for k in it), default=0.0)
        for pts in lvl.routes.values():
            o_end = max([o_end] + [o for o, _ in pts])
        lvl.size = (o_end, r_end)
        return lvl

    # routing ------------------------------------------------------------------------------------
    def _route(self, lvl: _Level, it, chains, dag, reversed_, direct, ranks, r_top, band) -> None:
        def box(k):
            return lvl.boxes[k]

        def top(k):
            return box(k)[1]

        def bottom(k):
            b = box(k)
            return b[1] + b[3]

        # attachments per node side: list of (sort key, edge id, role)
        att_top: dict[str, list[tuple[float, str]]] = {}
        att_bot: dict[str, list[tuple[float, str]]] = {}
        outer_x = 1e9
        for eid, a, b in dag:
            if eid not in direct:
                continue
            if eid in reversed_:
                # drawn from the lower node (b in the DAG… original src) up to the upper one
                att_top.setdefault(b, []).append((outer_x, eid))
                att_bot.setdefault(a, []).append((outer_x, eid))
            else:
                chain = chains[eid]
                att_bot.setdefault(a, []).append((it[chain[1]].pos, eid))
                att_top.setdefault(b, []).append((it[chain[-2]].pos, eid))
        port_bot: dict[tuple[str, str], tuple[float, float, int]] = {}  # (node, eid) → o, r, side (-1/0/1)
        port_top: dict[tuple[str, str], tuple[float, float, int]] = {}
        for node, lst in att_bot.items():
            lst.sort()
            self._ports(node, lst, box(node), it[node].kind, port_bot, bottom_side=True)
        for node, lst in att_top.items():
            lst.sort()
            self._ports(node, lst, box(node), it[node].kind, port_top, bottom_side=False)

        # skeletons: (o, gap index or None, …) resolved after track assignment
        gaps: dict[int, list[tuple[float, str, int]]] = {}  # gap index → (sort o, eid, seq)
        skel: dict[str, list] = {}
        n_ranks = len(ranks)
        rev_idx = 0
        for eid, a, b in dag:
            if eid not in direct:
                continue
            if eid not in reversed_:
                chain = chains[eid]
                so, sr, side = port_bot[(a, eid)]
                pts: list = [("p", so, sr)]
                o_prev = so
                if side:
                    o_prev = so + side * min(self.gap / 2, 20)
                    pts.append(("p", o_prev, sr))
                for k in range(1, len(chain)):
                    g = it[chain[k - 1]].rank
                    o_next = it[chain[k]].pos if it[chain[k]].dummy else port_top[(b, eid)][0]
                    seq = len(pts)
                    pts.append(("g", o_prev, g, seq))
                    pts.append(("g", o_next, g, seq))
                    gaps.setdefault(g, []).append((min(o_prev, o_next), eid, seq))
                    o_prev = o_next
                to, tr, _ = port_top[(b, eid)]
                pts.append(("p", to, tr))
                skel[eid] = pts
            else:
                # original edge: src = b (lower), dst = a (upper); leaves b's top, enters a's bottom
                uo, ur, _ = port_top[(b, eid)]
                vo, vr, _ = port_bot[(a, eid)]
                ru, rv = it[b].rank, it[a].rank
                if ru - rv <= 1:
                    g = rv
                    seq = 1
                    pts = [("p", uo, ur), ("g", uo, g, seq), ("g", vo, g, seq), ("p", vo, vr)]
                    gaps.setdefault(g, []).append((min(uo, vo), eid, seq))
                else:
                    right = max(it[k].pos + it[k].o / 2 for row in ranks[rv:ru + 1] for k in row)
                    x = right + self.gap / 2 + TRACK * rev_idx
                    rev_idx += 1
                    pts = [("p", uo, ur), ("g", uo, ru - 1, 1), ("g", x, ru - 1, 1),
                           ("g", x, rv, 3), ("g", vo, rv, 3), ("p", vo, vr)]
                    gaps.setdefault(ru - 1, []).append((uo, eid, 1))
                    gaps.setdefault(rv, []).append((vo, eid, 3))
                skel[eid] = pts

        track: dict[tuple[str, int], float] = {}
        for g, lst in gaps.items():
            lo = r_top[g] + band[g]
            hi = r_top[g + 1] if g + 1 < n_ranks else lo + self.rank_gap
            lst.sort()
            for i, (_, eid, seq) in enumerate(lst):
                track[(eid, seq)] = lo + (i + 1) * (hi - lo) / (len(lst) + 1)
        for eid, pts in skel.items():
            out = []
            for p in pts:
                if p[0] == "p":
                    out.append((p[1], p[2]))
                else:
                    out.append((p[1], track[(eid, p[3])]))
            lvl.routes[eid] = _clean(out)

    def _ports(self, node, lst, b, kind, ports, bottom_side: bool) -> None:
        o, r, os_, rs = b
        edge_r = r + rs if bottom_side else r
        n = len(lst)
        if kind in ROUND or (kind in DIAMONDS and not bottom_side):
            for _, eid in lst:
                ports[(node, eid)] = (o + os_ / 2, edge_r, 0)
            return
        if kind in DIAMONDS:
            mid_r = r + rs / 2
            cx = o + os_ / 2
            if n == 1:
                slots = [(cx, edge_r, 0)]
            elif n == 2:
                if lst[1][0] > cx:
                    slots = [(cx, edge_r, 0), (o + os_, mid_r, 1)]
                else:
                    slots = [(o, mid_r, -1), (cx, edge_r, 0)]
            else:
                slots = [(o, mid_r, -1)] + [(cx, edge_r, 0)] * (n - 2) + [(o + os_, mid_r, 1)]
            for (_, eid), s in zip(lst, slots):
                ports[(node, eid)] = s
            return
        for i, (_, eid) in enumerate(lst):
            ports[(node, eid)] = (o + os_ * (i + 1) / (n + 1), edge_r, 0)


def _clean(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Drop repeated and collinear interior points."""
    out: list[tuple[float, float]] = []
    for p in pts:
        p = (round(p[0], 2), round(p[1], 2))
        if out and abs(out[-1][0] - p[0]) < 1e-6 and abs(out[-1][1] - p[1]) < 1e-6:
            continue
        if len(out) >= 2:
            (ax, ay), (bx, by) = out[-2], out[-1]
            if (abs(ax - bx) < 1e-6 and abs(bx - p[0]) < 1e-6) or (abs(ay - by) < 1e-6 and abs(by - p[1]) < 1e-6):
                out[-1] = p
                continue
        out.append(p)
    return out


__all__ = ["LayeredEngine", "LEdge"]

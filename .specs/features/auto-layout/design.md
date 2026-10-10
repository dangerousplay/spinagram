# Design — auto-layout

## Pipeline

```
YAML / DSL ──► Diagram (+ groups, layout)                       unchanged when no `layout:`
                 │
                 ▼ layout/__init__.py: apply_layout(d, theme, engine=None) -> Diagram (copy)
              1. sizing.py   auto w/h for unsized nodes (text.measure/wrap, icon)
              2. graph.py    Diagram → LGraph (tree of LGroup/LNode + LEdge, group label band/padding)
              3. engine      LGraph → LResult  (flex | dot | d2 | elk | entry point)
              4. place.py    translate/align LResult into layout.area; overflow → d.meta["layout_overflow"]
              5. writeback   node x/y/w/h, groups → Zone(x,y,w,h,label,color=style,icon),
                             routes → Edge.via + side-bound endpoints (unless user via/curve)
                 │
                 ▼
              build_scene (layout.py, unchanged)  → backends
```

`api.scenes()` calls `apply_layout` before `build_scene` (single choke point; render/check/deck/facts
all benefit). QA (`qa.check`) gains an `overflow` issue from `meta["layout_overflow"]`.

## Model (model.py)

```python
@dataclass
class Group:
    id: str
    label: str | None = None
    style: str | None = None          # zone style name (aws-region, aws-az, soft…)
    icon: str | None = None
    children: list[str] = []          # node ids and group ids, in order
    direction: str | None = None      # row | column (flex); engines treat as rank hint
    columns: int | None = None        # flex grid
    gap: float | None = None
    padding: float | None = None
    align: str | None = None          # start | center | end (cross axis)

Diagram.groups: list[Group]; Diagram.layout: dict | None
Diagram.group(label, *, id=None, style=None, **hints) -> context manager: nodes/groups created inside
    are appended to its children (stack on the diagram).
Node: `in` accepted in YAML (stored as extra["in"]) → appended to that group's children.
```
YAML `groups:` is a tree (`children:` may hold strings or nested group mappings); the loader flattens
into `Diagram.groups` with child ids preserved. Validation: unknown ids, a node in two groups, cycles.

## LGraph (layout/graph.py) — backend-neutral

```python
@dataclass class LNode:  id; w; h
@dataclass class LGroup: id; children: list[LNode|LGroup]; pad: (t,r,b,l); hints: dict
@dataclass class LEdge:  id; src; dst            # node ids (endpoints only; sides ignored)
@dataclass class LGraph: root: LGroup; edges: list[LEdge]; direction: str; spacing: dict; options: dict
@dataclass class LResult: boxes: dict[id, (x,y,w,h)]; routes: dict[edge_id, list[(x,y)]]  # abs, root at 0,0
```
Top padding of a group = `padding + label band` (label size × 1.2 + 12, or icon size when the zone
style has a corner icon) so labels are never covered. Nodes not in any group are root children.
Absolute nodes (explicit x/y and no group, when `layout.include` is not `all`) are excluded (LAY-06).

## Engines (layout/engines/*.py)

Protocol: `class Engine: name: str; def available(self) -> str | None  # None ok, else install hint;
def run(self, g: LGraph) -> LResult`. Registry mirrors `backends/__init__.py` (built-ins + entry point
group `spinagram.layouts`).

- **flex** (pure Python): post-order. A group measures children, places them in row/column/grid with
  `gap`, aligns cross-axis, adds padding → its size. Root uses `layout.direction`. Edges: no routes
  (LAY-21 elbow is computed in writeback when `route: ortho`).
- **dot**: emit DOT: `graph [rankdir=LR|TB, nodesep, ranksep, compound=true]`; groups → nested
  `subgraph cluster_<id> { label=" "; margin=<pad>; … }` with an invisible label sized to the band;
  nodes `shape=box fixedsize=true width=w/72 height=h/72` (1 px = 1 pt). Run `dot -Tjson`. Read
  `objects[].pos` (centre, pt) / `bb` for clusters; flip y with graph `bb` height. Edge `pos`
  `"e,x,y p0 p1 …"` = cubic Bézier control points → sample 8 pts/segment, then simplify collinear.
- **elk**: `layout/elk_runner.mjs` (shipped) reads ELK JSON on stdin, prints result. Runtime: `bun`
  else `node`; `elkjs@0.12.0` installed with `npm install --prefix <cache>/elk elkjs@0.12.0` on first use
  (`NODE_PATH` set). Graph: hierarchical `children`, `edges` on the root with
  `elk.hierarchyHandling: INCLUDE_CHILDREN`, `elk.algorithm: layered`, `elk.edgeRouting: ORTHOGONAL`,
  `elk.direction`, `elk.padding` per group `[top=..,left=..,bottom=..,right=..]`. Coordinates are relative
  to the parent → accumulate. Routes from `sections[].startPoint/bendPoints/endPoint` (container offset
  per `edge.container`).
- **d2**: emit D2 with quoted keys (`"az-1": { "vault-1": { width: 200; height: 80; label: "" } }`),
  `direction: right|down`, edges by full path. Run `d2 --layout <opts.layout|elk> --pad 0 in.d2 out.svg`.
  Parse SVG: `<g class="base64(path)">` → first `rect` → box; connection groups `"(a -> b)[i]"` →
  first `path d` (M/L/C → polyline). Map paths back to ids by the last segment.

All subprocess engines: `timeout=60`, stderr surfaced in the error.

## Writeback (layout/writeback.py)

- Node boxes → x/y/w/h (keep user w/h when given; engine got them as fixed).
- Group → `Zone(x,y,w,h,label=g.label, color=g.style or "soft", icon=g.icon)` appended **before**
  user zones (zones render first → behind nodes; nested order: outer before inner = pre-order).
- Route → interior points become `via`; first/last point decide sides: the side of the node box the
  point lies on (tolerance 2 px) → endpoint `"id.side@frac"`; frac 0.5 snaps when within 3 px of the
  centre (keeps PPTX bound connectors).

## CLI

- `render|check|deck ... --layout ENGINE` → env/param override passed into `api.scenes`.
- `spinagram layout SPEC -o OUT.yaml [--layout ENGINE]` → `yaml_io.dump(apply_layout(d))` (new
  `dump` writes nodes with `at:`, zones, edges with via; drops `layout:` and `groups:`).

## Theme

`defaults.layout: {gap: 40, padding: 24, node_gap: 48, rank_gap: 80, align: top-center}` and
`defaults.node.auto: {min_w: 220, max_w: 360, min_h: 96}`. External themes: zone styles `aws-region`,
`aws-vpc`, `aws-az` already exist — reuse.

## Risks

- Engines measure nothing: label band must be reserved by us (done via padding) — else labels overlap.
- d2 SVG format is not a public API → P2, adapter isolated, test pins d2 0.7.x behaviour.
- dot cluster label placement differs; we render our own labels, dot label is a blank spacer.

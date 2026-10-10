# Feature: Automatic layout with nested groups

**Status:** Done (2026-10-08) · **Size:** Complex · **Owner:** spinagram

## Problem

Every node needs an explicit `x, y, w, h`, and every zone (AWS Region / VPC / AZ) a hand-computed
rectangle that must enclose its nodes. Architecture diagrams are mostly *structure* (what lives in which
AZ, what talks to what); computing coordinates is slow, error-prone (overlaps, nodes poking out of an
AZ box) and every insertion means moving everything after it. Earlier projects needed a `dk.py`
helper each to fake this.

## Goal

A human (or an agent) writes **structure only** — nodes, nested groups, edges — and spinagram places
everything, sizing groups around their content, through **pluggable layout engines**: a built-in
nested-flex engine (no dependencies) and adapters to Graphviz `dot`, `d2` and ELK. Output then flows
through the existing scene → SVG/PNG/PPTX/Figma backends unchanged.

## Users & scenarios

1. AWS deployment view: Region ⊃ VPC ⊃ 3 AZs, each with Vault + Consul nodes; ALB and S3 outside the
   VPC; edges crossing AZs. Written without a single coordinate.
2. A process flow (left → right) with swimlane-like groups, auto-routed orthogonal edges (ELK/dot).
3. A hand-placed slide where only one region is auto-laid (`layout.area`), the rest absolute.

## Requirements

### Model & syntax
| ID | Pri | Requirement | Acceptance |
|---|---|---|---|
| LAY-01 | P1 | **Groups**: nested containers with `id`, `label`, `style` (a theme zone style, e.g. `aws-region`, `aws-az`), `icon`, `children` (node ids and/or nested groups) and optional layout hints (`direction: row\|column`, `columns`, `gap`, `padding`, `align`). YAML `groups:` tree **and** node-side `in: <group>` both work; DSL `d.group(...)` context manager | YAML + DSL produce the same model; unknown child id → error naming it |
| LAY-02 | P1 | **Layout opt-in**: a diagram with `layout: {engine: flex\|dot\|d2\|elk, direction: right\|down, …}` gets positions computed; diagrams without it behave exactly as today | all existing tests/specs render byte-identical |
| LAY-03 | P1 | **Auto size**: nodes without `w/h` get a size from their content (title/body wrap, icon) bounded by theme `defaults.node.auto: {min_w, max_w, min_h}`; explicit `w/h` are kept | long title wraps within `max_w`; icon box ≥ icon+padding |
| LAY-04 | P1 | **Groups render as zones** with label and corner icon from the zone style; group box = children bbox + padding + label band | `aws-az` group renders dashed with AZ icon, label not overlapped by children |
| LAY-05 | P1 | **Area & placement**: laid-out content goes into `layout.area: [x,y,w,h]` (default: canvas minus margins and chrome bands), aligned by `layout.align` (default top-center); no font scaling — overflow is a QA issue naming the overflow in px | oversized layout → `check` reports overflow; fits → 0 issues |
| LAY-06 | P1 | **Mixed mode**: nodes/zones with explicit coordinates and not inside a laid-out group stay absolute; laid-out items may reference them in edges | slide with absolute legend + auto core renders |

### Engines
| ID | Pri | Requirement | Acceptance |
|---|---|---|---|
| LAY-10 | P1 | **Engine interface**: an engine receives a backend-neutral `LGraph` (nested groups, node sizes, edges, options) and returns absolute boxes for every node/group plus optional edge routes. Engines are registered via entry point `spinagram.layouts` (like backends) | a toy engine in a test registers and runs |
| LAY-11 | P1 | **flex** (built-in, pure Python, default): each group lays its children out as row / column / grid (`columns`) with gap, padding, cross-axis alignment, recursively bottom-up; top-level children follow `layout.direction`. Deterministic | Region⊃VPC⊃3 AZ example: no overlaps, children inside parents, same output every run |
| LAY-12 | P1 | **dot** adapter: Graphviz via `dot -Tjson`; groups → `cluster_*` subgraphs with label margin; node sizes fixed; reads positions (flip y), cluster `bb` and edge splines (→ polyline via Bézier sampling) | same example via dot: invariants hold; edges get `via` points |
| LAY-13 | P1 | **elk** adapter: ELK layered via `elkjs` run by `bun` or `node` (whichever is on PATH); hierarchical graph with `INCLUDE_CHILDREN` so cross-group edges are routed; orthogonal routing; `elkjs` installed on first use into the spinagram cache from the configured npm registry (pinned version) | same example via elk: invariants hold; orthogonal bends |
| LAY-14 | P2 | **d2** adapter: generates D2 text (shapes with `width/height`, nested containers, edges), runs `d2 --layout <dagre\|elk\|tala>`, reads geometry back from the SVG (`g.class` = base64 of the D2 path; `rect` x/y/w/h; connection paths) | same example via d2: invariants hold |
| LAY-15 | P1 | **Missing engine binary** → clear error naming the binary and how to install it (`apt install graphviz`, d2 install script, bun/node); never a stack trace | `engine: dot` with PATH emptied → one-line error |
| LAY-16 | P1 | **Engine options passthrough**: `layout.options` dict goes verbatim to the engine (ELK properties, dot graph attrs, d2 vars); spinagram sets sane defaults (spacing from theme `defaults.layout`) | `elk.spacing.nodeNode` override changes output |

### Edges
| ID | Pri | Requirement | Acceptance |
|---|---|---|---|
| LAY-20 | P1 | Routes returned by an engine become the edge's `via` (interior bends) and endpoints bind to the node sides the route enters/leaves, so PPTX/Figma connectors stay attached | PPTX: route endpoints on side centres where the engine gave them |
| LAY-21 | P2 | flex routes edges as today (auto sides) plus `route: ortho` = one-elbow orthogonal path when sides are perpendicular | elbow drawn, no diagonal |
| LAY-22 | P1 | User-set `via`/`curve` on an edge always win over the engine route | edge with `via` unchanged |

### Tooling & docs
| ID | Pri | Requirement | Acceptance |
|---|---|---|---|
| LAY-30 | P1 | `spinagram render/check --layout <engine>` overrides the spec's engine (compare engines quickly) | same spec, 4 engines, 4 outputs |
| LAY-31 | P1 | `spinagram layout <spec> -o out.yaml` freezes the computed positions into an explicit spec (escape hatch for hand-tuning) | frozen spec renders identical to auto |
| LAY-32 | P1 | Example `examples/aws_layout.yaml` (Region⊃VPC⊃3 AZ, ALB, S3, Vault/Consul) + README section + skill doc update | example renders with each available engine, `check` 0 issues |
| LAY-33 | P1 | Invariant test suite shared by all engines (children inside parent, no sibling overlap, label band free, every node placed); engines whose binary is missing are skipped | `pytest` green with/without binaries |

## Out of scope (v1)

- Incremental/stable layout across edits (positions may shift when the graph changes; use LAY-31 to freeze).
- Edge label placement by engines (labels stay at route midpoint).
- Text-size-driven re-layout after font fallback.

# Layered Layout Engine Specification

## Problem Statement

Flow, activity and state diagrams are graphs whose meaning is the direction of their edges. The default
`flex` engine places nodes by group only and ignores edges: a six-node flowchart becomes one column with
overlapping edges, and the last node falls off the canvas (probe, 2026-10-12). The ranked engines (`dot`,
`elk`, `d2`) need Graphviz, bun/node or the d2 binary. spinagram needs a built-in, dependency-free layered
engine so edge-driven diagrams lay out well out of the box.

## Goals

- [ ] Flowcharts, activity and state diagrams render with ranked, crossing-reduced, orthogonally routed edges with no external tool installed.
- [ ] Loops, back-edges and self-transitions are drawn as distinct routes that never pass through node interiors.
- [ ] Layout is deterministic: the same diagram renders byte-identically on every run and platform.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Force-directed / organic layout | Not needed for flow, activity or state diagrams |
| Replacing `dot`, `elk`, `d2` engines | They stay as optional alternatives |
| Interactive or incremental layout (stable across edits) | Already a deferred idea; separate feature |
| Graphs above 300 nodes | Diagrams for slides; performance bound documented, not optimised beyond it |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Engine choice | New pure-Python engine named `layered` (Sugiyama: cycle removal, ranking, ordering, coordinate assignment, orthogonal routing) | User chose a built-in engine (2026-10-12); zero dependencies like `flex` | y (2026-10-12) |
| When it is used | Default for `Flowchart`, `StateMachine`, `Activity` builders and their embedded regions; selectable anywhere with `layout={"engine": "layered"}`; `flex` stays the default for plain `Diagram` | Plain architecture diagrams are group-driven and already work with `flex` | n |
| Edge routing style | Orthogonal (horizontal/vertical segments) with rounded corners | Matches flowchart conventions and existing `route: ortho` | n |
| Crossing reduction | Barycentre heuristic with a fixed number of sweeps (24) and deterministic tie-breaks by declaration order | Good quality, predictable runtime, deterministic | n |
| Performance bound | 300 nodes / 600 edges laid out in under 2 s on a laptop-class CPU | Larger graphs do not fit a slide | n |
| Swimlanes | Lanes are partitions: every node in a lane stays inside its band; ranks run across lanes | Activity diagrams require it (see behavior-diagrams spec) | n |

**Open questions:** none - all resolved or logged above (required before the spec is confirmed).

---

## User Stories

### P1: Ranked layout for directed diagrams ⭐ MVP

**User Story**: As an author of a flowchart, I want nodes placed in ranks following edge direction so that the flow reads top to bottom (or left to right) without coordinates.

**Why P1**: Without it, none of the new diagram types are usable without external tools.

**Acceptance Criteria**:

1. WHEN a diagram uses the `layered` engine THEN the system SHALL place every edge's target in a later rank than its source, except for edges reversed to break cycles.  <!-- LAY-01 -->
2. WHEN `direction` is `down` THEN the system SHALL assign ranks to increasing y; WHEN `direction` is `right` THEN to increasing x.  <!-- LAY-02 -->
3. The system SHALL keep at least the theme's `rank_gap` between consecutive ranks and `node_gap` between nodes in one rank.  <!-- LAY-03 -->
4. The system SHALL produce no overlapping node boxes.  <!-- LAY-04 -->
5. WHEN the same diagram is laid out twice THEN the system SHALL produce identical coordinates.  <!-- LAY-05 -->
6. WHEN the graph has no edges THEN the system SHALL place nodes in one rank in declaration order.  <!-- LAY-06 -->

**Independent Test**: Lay out the six-node order flow (start, action, decision, two branches, merge); assert rank order of each edge, no overlaps, and identical output on two runs.

---

### P1: Cycles, back-edges and self-loops ⭐ MVP

**User Story**: As an author of a state machine or a retry loop, I want loops drawn as clear return paths so that cycles are readable.

**Why P1**: State machines are cyclic by nature; activity loops are common.

**Acceptance Criteria**:

1. WHEN the graph has cycles THEN the system SHALL reverse the back-edges found by a depth-first search in declaration order for ranking, and draw them with their original direction.  <!-- LAY-07 -->
2. WHEN a back-edge spans more than one rank THEN the system SHALL route it on the outer side of the ranks it spans; WHEN it connects adjacent ranks THEN the system SHALL route it inside the gap between them; in both cases no segment SHALL pass through a node box.  <!-- LAY-08 -->
3. WHEN an edge's source equals its target THEN the system SHALL draw a loop leaving and re-entering the same side of the node, with its label beside the loop.  <!-- LAY-09 -->
4. WHEN two or more edges connect the same pair of nodes THEN the system SHALL draw them as separate parallel routes with separate labels.  <!-- LAY-10 -->

**Independent Test**: Lay out a 4-state machine with a back-edge, a self-transition and two parallel transitions; assert no route segment intersects a node box and each route ends on its declared target.

---

### P1: Orthogonal edge routing and label placement ⭐ MVP

**User Story**: As a reader, I want edges drawn with straight horizontal and vertical segments and labels that never overlap boxes.

**Why P1**: Flowchart convention; labels on decisions (yes/no) carry the logic.

**Acceptance Criteria**:

1. The system SHALL route every non-self edge as a polyline whose segments are horizontal or vertical.  <!-- LAY-11 -->
2. The system SHALL place each routed edge's label on one of its segments or beside it (pill edge within 6 px of the segment) so that the label box intersects no node box and no other label placed before it.  <!-- LAY-12 -->
3. WHEN edges leave a decision node THEN the system SHALL attach them to distinct sides or distinct positions of the node.  <!-- LAY-13 -->
4. WHEN the author anchored an edge (`a.right`) THEN the system SHALL keep that anchor and leave the edge exactly as the author defined it (no engine route).  <!-- LAY-14 -->

**Independent Test**: Route the order flow; assert all segments axis-aligned, label boxes disjoint from node boxes, decision edges on distinct ports.

---

### P1: Groups and lanes ⭐ MVP

**User Story**: As an author, I want composite states, nested regions and swimlanes kept together so that hierarchy and responsibility stay visible.

**Why P1**: Composite states and swimlanes are core to state and activity diagrams.

**Acceptance Criteria**:

1. WHEN nodes belong to a group THEN the system SHALL place them inside the group's box with the group's padding and label band, and no non-member node SHALL be inside that box.  <!-- LAY-15 -->
2. WHEN a group is marked as lanes THEN the system SHALL draw each lane as a band spanning the full diagram along the flow direction and keep every lane member inside its band.  <!-- LAY-16 -->
3. WHEN an edge crosses a group or lane border THEN the system SHALL route it through the border without passing through other nodes.  <!-- LAY-17 -->

**Independent Test**: Lay out an activity with three lanes and a composite state; assert containment of every member and band order.

---

### P2: Quality controls

**User Story**: As a power user, I want to nudge the layout so that important paths stay straight.

**Why P2**: Defaults should suffice; controls help polish slides.

**Acceptance Criteria**:

1. WHEN an edge has `weight` greater than 1 THEN the system SHALL prefer aligning its endpoints in the same column (down) or row (right) over lighter edges.  <!-- LAY-18 -->
2. WHEN nodes are given `same_rank=[a, b]` THEN the system SHALL place them in one rank.  <!-- LAY-19 -->

---

## Edge Cases

- IF the laid-out graph exceeds the layout area THEN the system SHALL report the overflow through `spinagram check` with the excess in px.  <!-- LAY-20 -->
- WHEN a graph has disconnected components THEN the system SHALL lay out each component and place them side by side in declaration order.  <!-- LAY-21 -->
- IF a diagram exceeds 300 nodes THEN the system SHALL still complete and emit a warning naming the bound.  <!-- LAY-22 -->

---

## Implicit-Requirement Dimensions

| Dimension | Coverage |
| --------- | -------- |
| Input validation & bounds | LAY-20, LAY-22 |
| Failure / partial-failure states | N/A because layout is a pure computation; overflow is reported, not failed |
| Idempotency / retry / duplicate handling | LAY-05 (deterministic), LAY-10 (duplicate edges) |
| Auth boundaries & rate limits | N/A because local library code |
| Concurrency / ordering | LAY-05 (order-only tie-breaks; no hash ordering) |
| Data lifecycle / expiry | N/A because no stored state |
| Observability | LAY-20 overflow through `check` |
| External-dependency failure | N/A because the engine has no dependencies |
| State-transition integrity | N/A because stateless |

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| LAY-01 | P1: Ranked layout | Design | Pending |
| LAY-02 | P1: Ranked layout | Design | Pending |
| LAY-03 | P1: Ranked layout | Design | Pending |
| LAY-04 | P1: Ranked layout | Design | Pending |
| LAY-05 | P1: Ranked layout | Design | Pending |
| LAY-06 | P1: Ranked layout | Design | Pending |
| LAY-07 | P1: Cycles | Design | Pending |
| LAY-08 | P1: Cycles | Design | Pending |
| LAY-09 | P1: Cycles | Design | Pending |
| LAY-10 | P1: Cycles | Design | Pending |
| LAY-11 | P1: Routing | Design | Pending |
| LAY-12 | P1: Routing | Design | Pending |
| LAY-13 | P1: Routing | Design | Pending |
| LAY-14 | P1: Routing | Design | Pending |
| LAY-15 | P1: Groups and lanes | Design | Pending |
| LAY-16 | P1: Groups and lanes | Design | Pending |
| LAY-17 | P1: Groups and lanes | Design | Pending |
| LAY-18 | P2: Quality controls | - | Pending |
| LAY-19 | P2: Quality controls | - | Pending |
| LAY-20 | Edge cases | Design | Pending |
| LAY-21 | Edge cases | Design | Pending |
| LAY-22 | Edge cases | Design | Pending |

**ID format:** `LAY-NN`

**Coverage:** 22 total, 0 mapped to tasks, 22 unmapped ⚠️

---

## Success Criteria

- [ ] The flow probe from 2026-10-12 renders with every node on canvas, zero overlaps and zero edge-through-node intersections.
- [ ] A 300-node random DAG lays out in under 2 s.
- [ ] Layout output is identical across two runs and across Python 3.11-3.13.

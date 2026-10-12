# Behavior Diagrams (Flow, Activity, State) Specification

## Problem Statement

spinagram draws architecture diagrams well, but teams also need flowcharts, UML activity diagrams and
state machines, often on the same slide as the architecture they describe. Today an author must fake
them with boxes and diamonds, has no start/end/fork/join or history symbols, no swimlanes, no
transition syntax, and no layout that follows the flow. Specialized builders with the right symbols and
semantics, composable into one diagram, make spinagram usable for process and behavior documentation.

## Goals

- [ ] Authors build a flowchart, an activity diagram and a state machine in Python with domain verbs, without coordinates.
- [ ] One diagram can contain several typed regions (e.g. an architecture view next to a state machine), each with its own layout, connected by edges.
- [ ] Every symbol renders natively in SVG, PNG, PowerPoint (editable shapes) and Figma.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Sequence, timing, BPMN 2.0 full notation | Separate diagram families; BPMN events/gateways overlap but the full standard is large |
| Executable state machines (simulation, code generation) | spinagram documents behavior, it does not run it |
| Validation of UML well-formedness beyond the rules listed here | Authoring tool, not a modelling tool |
| D2/PlantUML import of these diagrams | Parked import feature; this work makes it cheaper later |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Authoring model | Specialized builders `Flowchart`, `Activity`, `StateMachine`, usable standalone (each is a `Diagram`) and embeddable as typed regions inside any diagram | User answer (2026-10-12): "allow multiple diagrams into one with different types by allowing specialized builders" | n (interpretation to confirm) |
| Embedding API | `with d.flowchart("Checkout") as fc:`, `with d.state_machine("Order") as sm:`, `with d.activity("Fulfilment") as act:`; a region is a group with its own type, layout engine and direction | Mirrors `with d.group(...)`; regions reuse group containment and zones | n |
| Cross-region edges | Allowed with the normal operators (`api >> sm.state("Paid")`); routed by the parent layout | Linking architecture to behavior is the point of mixing | n |
| Layout per region | Each region is laid out by the `layered` engine (layered-layout spec) by default; the parent places regions with its own engine (`flex` by default) | Regions are boxes to the parent | n |
| Symbol set | Shared native shape kinds (below) available to every builder and plain `Diagram` | One shape library; builders add semantics and verbs | n |
| Transition labels | `event [guard] / action` composed from `on(event, target, guard=, action=)` | UML convention | n |
| Notation defaults | UML 2.5 for activity and state; ISO 5807-style symbols for flowcharts | Recognisable to readers | n |
| YAML | Every builder has a YAML form (`type: state_machine`, `regions:`) loading to the same model | Both front-ends share every feature (project convention) | n |

**Open questions:** none - all resolved or logged above (required before the spec is confirmed).

---

## User Stories

### P1: Shape library for behavior symbols ⭐ MVP

**User Story**: As an author, I want the standard flow, activity and state symbols drawn natively so that diagrams read correctly and stay editable in PowerPoint and Figma.

**Why P1**: Every builder depends on it.

**Acceptance Criteria**:

1. The system SHALL support node kinds `terminator`, `process`, `decision`, `io`, `document`, `predefined`, `data`, `connector`, `initial`, `final`, `flow_final`, `fork`, `join`, `merge`, `choice`, `history`, `deep_history`, `state`, `action`, `object`, `signal_send`, `signal_receive`, `note`.  <!-- BHV-01 -->
2. WHEN a node of one of these kinds is rendered to SVG THEN the system SHALL draw the geometry listed in the design's shape table (e.g. `initial` filled circle 24 px, `final` bullseye, `fork` filled bar 8 px thick spanning its incoming/outgoing edges, `io` parallelogram, `state` rounded rectangle).  <!-- BHV-02 -->
3. WHEN such a node is rendered to PowerPoint THEN the system SHALL use a native preset geometry (or a grouped native shape for `final` and `history`) with any text inside the shape.  <!-- BHV-03 -->
4. WHEN such a node is rendered to Figma THEN the system SHALL draw it as editable vectors with the text inside.  <!-- BHV-04 -->
5. WHEN a pseudostate (`initial`, `final`, `flow_final`, `fork`, `join`, `choice`, `history`) has no title THEN the system SHALL size it from the built-in symbol sizes of the shape table (`spinagram.shapes`), not from text.  <!-- BHV-05 -->

**Independent Test**: Render one node of each kind to SVG, PPTX and Figma JS; assert geometry per the shape table and that `check` reports no overflow.

---

### P1: Flowchart builder ⭐ MVP

**User Story**: As an analyst, I want `Flowchart` with process, decision and terminator verbs so that I can write a flowchart in a few lines.

**Why P1**: The most common behavior diagram.

**Acceptance Criteria**:

1. WHEN the author calls `fc.start()`, `fc.process(title)`, `fc.decision(title)`, `fc.io(title)`, `fc.document(title)`, `fc.end()` THEN the system SHALL create nodes of kinds `terminator`, `process`, `decision`, `io`, `document`, `terminator`.  <!-- BHV-06 -->
2. WHEN the author writes `decision.yes(a)` / `decision.no(b)` (or `decision.to(a, "label")`) THEN the system SHALL create edges labelled `Yes` / `No` (or the label) leaving distinct sides of the decision.  <!-- BHV-07 -->
3. WHEN a `Flowchart` has no explicit layout THEN the system SHALL lay it out with the `layered` engine, direction `down`.  <!-- BHV-08 -->
4. IF a `decision` has fewer than two outgoing edges THEN `spinagram check` SHALL report "decision X has N outgoing edges (expected ≥ 2)".  <!-- BHV-09 -->

**Independent Test**: Build the order flow with the builder; assert kinds, Yes/No labels on distinct sides, layered layout, and a `check` warning for a one-branch decision.

---

### P1: State machine builder ⭐ MVP

**User Story**: As an engineer, I want `StateMachine` with states, transitions, composite states and pseudostates so that I can document lifecycles.

**Why P1**: State machines are a primary request.

**Acceptance Criteria**:

1. WHEN the author calls `sm.state(title, entry=, do=, exit=)` THEN the system SHALL create a `state` node whose body lists `entry / …`, `do / …`, `exit / …` lines for the given activities.  <!-- BHV-10 -->
2. WHEN the author calls `s.on(event, target, guard=None, action=None)` THEN the system SHALL create a transition labelled `event [guard] / action`, omitting empty parts.  <!-- BHV-11 -->
3. WHEN the author writes `sm.initial >> s` or `s >> sm.final` THEN the system SHALL connect `s` to the scope's `initial` or `final` pseudostate, created on first access and the same node on every later access (one per scope).  <!-- BHV-12 -->
4. WHEN the author opens `with sm.composite(title) as c:` THEN the system SHALL create a composite state drawn as a rounded state box containing its substates, with its own initial pseudostate available as `c.initial`.  <!-- BHV-13 -->
5. WHEN the author opens orthogonal regions with `c.region()` THEN the system SHALL draw each region as a dashed box inside the composite (dashed dividers deferred).  <!-- BHV-14 -->
6. WHEN the author calls `sm.choice()` or `c.history(deep=False)` THEN the system SHALL create a `choice` diamond or an `H` / `H*` history pseudostate.  <!-- BHV-15 -->
7. IF a state machine or composite region has no initial pseudostate THEN `spinagram check` SHALL report "region X has no initial state".  <!-- BHV-16 -->
8. WHEN a transition's source equals its target THEN the system SHALL draw a self-transition loop (layered-layout LAY-09).  <!-- BHV-17 -->

**Independent Test**: Build an order lifecycle (Created → Paid → Shipped, Cancelled from two states, a retry self-transition, a composite "Fulfilment" with two regions); assert node kinds, labels, containment, region dividers and check messages.

---

### P1: Activity builder with swimlanes ⭐ MVP

**User Story**: As a process owner, I want `Activity` with actions, decisions, merges, forks, joins and swimlanes so that I can show who does what and what runs in parallel.

**Why P1**: Swimlanes and parallelism are why people choose activity diagrams.

**Acceptance Criteria**:

1. WHEN the author calls `act.action(title)`, `act.decision(title)`, `act.merge()`, `act.start()`, `act.end()`, `act.flow_end()` THEN the system SHALL create `action`, `decision`, `merge`, `initial`, `final`, `flow_final` nodes.  <!-- BHV-18 -->
2. WHEN the author writes `with act.parallel() as p:` with branches `p.branch()` THEN the system SHALL create a `fork` before and a `join` after the branches and connect each branch between them.  <!-- BHV-19 -->
3. WHEN the author writes `with act.lane("Customer"):` THEN the system SHALL assign nodes created inside to that lane, and the layout SHALL draw lanes as labelled bands (LAY-16), vertical for direction `down` and horizontal for `right`.  <!-- BHV-20 -->
4. WHEN the author calls `act.send(title)` / `act.receive(title)` / `act.object(title)` THEN the system SHALL create `signal_send`, `signal_receive` and `object` nodes, with object flows drawn dashed.  <!-- BHV-21 -->
5. WHEN consecutive actions are created without explicit edges inside `with act.sequence():` THEN the system SHALL connect them in creation order.  <!-- BHV-22 -->

**Independent Test**: Build an order fulfilment activity with three lanes and one fork/join; assert lane membership, band geometry, fork/join placement and implicit sequence edges.

---

### P1: Mixed diagrams with typed regions ⭐ MVP

**User Story**: As an architect, I want an architecture view and the state machine of one of its services on the same slide, connected, so that structure and behavior are explained together.

**Why P1**: Explicit user requirement (2026-10-12).

**Acceptance Criteria**:

1. WHEN the author opens `with d.state_machine(title) as sm:` (or `d.flowchart`, `d.activity`) inside a `Diagram` THEN the system SHALL create a region whose builder methods are those of the corresponding builder.  <!-- BHV-23 -->
2. WHEN a region has its own `layout` THEN the system SHALL lay out the region's contents with that layout and treat the region as one box in the parent layout.  <!-- BHV-24 -->
3. WHEN an edge connects a node outside a region to a node inside it THEN the system SHALL route it across the region border (LAY-17).  <!-- BHV-25 -->
4. WHEN a standalone builder (`StateMachine(...)`) is laid out THEN its nodes SHALL have the same sizes and relative positions as the same content embedded as a region in an otherwise empty `Diagram` (the region adds only its own box).  <!-- BHV-26 -->
5. The YAML front-end SHALL express regions as `regions: [{type: state_machine, id, title, layout, states: …, transitions: …}]` loading to the same model.  <!-- BHV-27 -->

**Independent Test**: Render a diagram with an architecture group and an embedded state machine connected by one edge; assert both layouts, the region box and the crossing edge.

---

### P2: Flowchart extras

**User Story**: As an analyst, I want off-page connectors, predefined processes and data stores so that larger flowcharts stay readable.

**Acceptance Criteria**:

1. WHEN the author calls `fc.connector("A")` twice with the same label THEN the system SHALL draw two circular connectors labelled `A` and no edge between them.  <!-- BHV-28 -->
2. WHEN the author calls `fc.predefined(title)` or `fc.data(title)` THEN the system SHALL create `predefined` and `data` nodes.  <!-- BHV-29 -->

---

### P3: Interruptible regions and exception handlers

**User Story**: As a process owner, I want interruptible regions with interrupting edges (lightning) so that cancellation paths are shown in UML style.

**Acceptance Criteria**:

1. WHEN the author opens `with act.interruptible():` and adds `x.interrupt(target, event)` THEN the system SHALL draw a dashed rounded region and a zig-zag interrupting edge labelled with the event.  <!-- BHV-30 -->

---

## Edge Cases

- IF an edge targets a `final` or `flow_final` as its source THEN the system SHALL raise `ValueError("final node X cannot have outgoing edges")` at build time.  <!-- BHV-31 -->
- IF an edge targets an `initial` pseudostate THEN the system SHALL raise `ValueError("initial node X cannot have incoming edges")`.  <!-- BHV-32 -->
- WHEN a `fork` has one outgoing edge THEN `spinagram check` SHALL report "fork X has 1 branch".  <!-- BHV-33 -->
- WHEN a lane is empty THEN the system SHALL still draw the lane band with its label at minimum width 200 px.  <!-- BHV-34 -->
- IF two regions in one diagram share an id THEN the system SHALL raise `ValueError` naming the duplicate id.  <!-- BHV-35 -->

---

## Implicit-Requirement Dimensions

| Dimension | Coverage |
| --------- | -------- |
| Input validation & bounds | BHV-09, BHV-16, BHV-31-35 |
| Failure / partial-failure states | Build-time `ValueError` for structural errors (BHV-31, 32, 35); soft issues via `check` |
| Idempotency / retry / duplicate handling | BHV-35 duplicate ids; deterministic layout inherited (LAY-05) |
| Auth boundaries & rate limits | N/A because local library code |
| Concurrency / ordering | Creation order defines implicit sequences (BHV-22) and tie-breaks |
| Data lifecycle / expiry | N/A because no stored state |
| Observability | `check` messages (BHV-09, 16, 33) |
| External-dependency failure | N/A because the default layout is built in |
| State-transition integrity | BHV-31, BHV-32 enforce valid pseudostate directions |

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| BHV-01 | P1: Shape library | Design | Pending |
| BHV-02 | P1: Shape library | Design | Pending |
| BHV-03 | P1: Shape library | Design | Pending |
| BHV-04 | P1: Shape library | Design | Pending |
| BHV-05 | P1: Shape library | Design | Pending |
| BHV-06 | P1: Flowchart | Design | Pending |
| BHV-07 | P1: Flowchart | Design | Pending |
| BHV-08 | P1: Flowchart | Design | Pending |
| BHV-09 | P1: Flowchart | Design | Pending |
| BHV-10 | P1: State machine | Design | Pending |
| BHV-11 | P1: State machine | Design | Pending |
| BHV-12 | P1: State machine | Design | Pending |
| BHV-13 | P1: State machine | Design | Pending |
| BHV-14 | P1: State machine | Design | Pending |
| BHV-15 | P1: State machine | Design | Pending |
| BHV-16 | P1: State machine | Design | Pending |
| BHV-17 | P1: State machine | Design | Pending |
| BHV-18 | P1: Activity | Design | Pending |
| BHV-19 | P1: Activity | Design | Pending |
| BHV-20 | P1: Activity | Design | Pending |
| BHV-21 | P1: Activity | Design | Pending |
| BHV-22 | P1: Activity | Design | Pending |
| BHV-23 | P1: Mixed diagrams | Design | Pending |
| BHV-24 | P1: Mixed diagrams | Design | Pending |
| BHV-25 | P1: Mixed diagrams | Design | Pending |
| BHV-26 | P1: Mixed diagrams | Design | Pending |
| BHV-27 | P1: Mixed diagrams | Design | Pending |
| BHV-28 | P2: Flowchart extras | - | Pending |
| BHV-29 | P2: Flowchart extras | - | Pending |
| BHV-30 | P3: Interruptible regions | - | Pending |
| BHV-31 | Edge cases | Design | Pending |
| BHV-32 | Edge cases | Design | Pending |
| BHV-33 | Edge cases | Design | Pending |
| BHV-34 | Edge cases | Design | Pending |
| BHV-35 | Edge cases | Design | Pending |

**ID format:** `BHV-NN`

**Coverage:** 35 total, 0 mapped to tasks, 35 unmapped ⚠️

**Depends on:** `layered-layout` (LAY-01..17).

---

## Success Criteria

- [ ] Example gallery: one flowchart, one activity with lanes and fork/join, one state machine with a composite and history, one mixed architecture + state machine slide; all render to SVG, PPTX and Figma with zero `check` issues.
- [ ] Each example is under 30 lines of Python.

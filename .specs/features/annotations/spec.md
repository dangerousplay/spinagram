# Annotations Specification

## Problem Statement

Reference-architecture slides explain themselves: a legend decodes colours and line styles, numbered steps
walk the reader through the flow, and callouts point at the parts that matter. In spinagram a legend is a
hand-placed row of colour dots and a note is a sticky box, so authors draw these by hand or skip them.
Annotations should be first-class, styled by the same CSS, placed by the layout, and editable in every output.

## Goals

- [ ] A diagram gets a legend, numbered steps, callouts and illustrative notes with one call each, and none of them overlaps diagram content.
- [ ] Annotations render natively (editable shapes and text) in SVG, PNG, PowerPoint and Figma.
- [ ] The showcase diagrams use all four and pass `spinagram check` with 0 issues.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Free-corner placement of panels | User chose reserved side bands |
| Animated step-through (reveal steps one by one) | Presentation feature; later |
| Hand-drawn / sketch rendering style | Separate visual-style feature |
| Callouts on groups and edges | Nodes cover the reference-architecture use; groups/edges later |
| Changing the existing fixed legend (`set_legend`, YAML `legend: {x, y, items}`) | Kept as is for compatibility |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Scope | Smart legend, numbered steps, callouts, illustrative notes | User choice | y |
| Backends | All four native, by composing existing scene primitives (shapes, connectors, text, images) | User choice; primitives already render natively everywhere | y |
| Panel placement | Reserved band on the right (default) or bottom; the layout area shrinks by the band | User choice | y |
| Python API names | `d.add_legend(...)`, `d.step(...)`, `d.callout(...)`, `d.note(..., variant=...)` | `legend` is already a `Diagram` field; `add_legend` avoids the clash | n |
| Legend entry keys | `.class` / `node.class` (node class), `edge.class` (edge class), `style:<name>` (theme node style), `pack:name` (icon) | Mirrors CSS selectors and icon refs the author already writes | n |
| Automatic legend | Without `items`, every node class, edge class and non-default node style used appears once, labelled from its name (`async-event` → "Async event") | Zero-config legend; explicit labels override | n |
| Legend swatch | Drawn with the computed style of the first element carrying that key (fill, stroke, width, dash for nodes, radius scaled to the swatch; colour, width, dash, markers for edges) | The legend must look like the diagram; an unscaled 22 px radius turns a 28 px swatch into an oval | n |
| Step badges | Numbered circles at the edge's label position (beside the label when present) or a node's top-left corner | Reference-architecture convention | n |
| Step numbering | Explicit `n`, or the next free number in call order | Deterministic | n |
| Steps panel | Same band as the legend, below it, titled "Steps" | One band, one reading column | n |
| Callout kinds | `info`, `tip`, `warning`, `risk`, each with a theme colour token and a glyph | Common annotation vocabulary | n |
| Callout placement | `side="auto"` picks, in order top, right, bottom, left, the first side where the bubble fits the canvas and overlaps no node, zone or other callout; a leader line joins bubble and node | Deterministic and readable | n |
| Note variants | `sticky` (today's note), `card` (white card with an accent bar), `quote` (large quote mark, italic body) | Narrative slides need more than sticky notes | n |
| CSS | New type selectors `legend`, `step`, `callout`, with `.info|.tip|.warning|.risk` on callouts and `::title`/`::body`/`::label` text parts; notes keep `note` kind + `.card|.quote|.sticky` | Same styling story as nodes | n |
| YAML | Top-level `annotations: {legend: {...}, steps: [...], callouts: [...]}`; notes are nodes with `kind: note`, `variant:` | Keeps today's `legend:` key untouched | n |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Smart legend ⭐ MVP

**User Story**: As an author, I want a legend built from what my diagram uses so that readers decode colours and line styles without me drawing it.

**Acceptance Criteria**:

1. WHEN `d.add_legend()` is called without items THEN the legend SHALL list each node class, edge class and non-default node style used in the diagram exactly once, in first-use order (node classes and styles in node order first, then edge classes in edge order), labelled from its name with dashes as spaces and the first letter capitalised.
2. WHEN items are given as `{key: label}` THEN the legend SHALL list exactly those entries in the given order with the given labels.
3. IF an item key matches nothing in the diagram THEN `spinagram check` SHALL report `legend: unused entry '<key>'` and the entry SHALL still be drawn from the theme default.
4. WHEN a node entry is drawn THEN its swatch SHALL use the computed fill, stroke, stroke width and dash pattern of the first node carrying that key, and its corner radius scaled by swatch height / node height.
5. WHEN an edge entry is drawn THEN its sample line SHALL use the computed colour, width, dash pattern and end markers of the first edge carrying that key.
6. WHEN an icon entry (`pack:name`) is drawn THEN it SHALL show that icon at swatch size.
7. The legend SHALL be drawn as a titled card (default title "Legend") inside the reserved band.

**Independent Test**: AWS01 with `d.add_legend()` shows Web, App, Database… swatches matching the cards and an "Async" dashed line sample.

---

### P1: Reserved annotation band ⭐ MVP

**User Story**: As an author, I want legends and step panels to sit in a band that never overlaps the diagram.

**Acceptance Criteria**:

1. WHEN a diagram has a legend or steps with `position="right"` (default) THEN automatic layout SHALL place content in the layout area minus a right band of the panel width plus a 32 px gap.
2. WHEN `position="bottom"` THEN automatic layout SHALL place content in the layout area minus a bottom band of the panel height plus a 32 px gap.
3. The panel width SHALL be 360 px for a right band; a bottom band SHALL span the layout area width.
4. IF the panels do not fit in the band THEN `spinagram check` SHALL report `annotations: overflow` with the excess in pixels.
5. WHILE a diagram uses manual coordinates, the system SHALL place the band at the canvas edge inside the margins and `spinagram check` SHALL report `annotations: overlap` for every node or zone the band intersects.

**Independent Test**: AWS02 with a right legend lays out without overlap; `check` reports 0 issues.

---

### P1: Numbered steps ⭐ MVP

**User Story**: As an author, I want to number the flow of a reference architecture and explain each step beside the diagram.

**Acceptance Criteria**:

1. WHEN `d.step("text", on=edge)` or `edge.step("text")` is called THEN the edge SHALL get a numbered circular badge and the steps panel SHALL list the number and text.
2. WHEN `on=` is a node THEN the badge SHALL sit on the node's top-left corner.
3. WHEN `n` is omitted THEN the step SHALL take the next number after the highest used so far; WHEN `n` is given it SHALL be used as is.
4. IF two steps share a number THEN `spinagram check` SHALL report `steps: duplicate number <n>`.
5. The steps panel SHALL list steps in ascending number order, each with a badge identical to the one in the diagram.
6. WHEN an edge with a step has a label THEN the badge SHALL be placed beside the label without overlapping it.
7. WHEN a YAML spec lists `annotations: steps: [{on: "a -> b", text: ...}]` THEN the step SHALL attach to the first edge from `a` to `b`; IF no such edge or node exists THEN loading SHALL fail naming the reference.

**Independent Test**: AWS01 with steps 1–6 shows badges along the request path and a "Steps" panel in the band.

---

### P1: Callouts ⭐ MVP

**User Story**: As an author, I want to point at a node with a short explanation so that readers notice what matters.

**Acceptance Criteria**:

1. WHEN `d.callout(node, "text", title=None, kind="info")` is called THEN a bubble with the text (and title when given) SHALL be drawn with a leader line from the bubble to the node's nearest side.
2. The bubble SHALL use the kind's colour token (`info`→primary, `tip`→success, `warning`→warning, `risk`→alert) for its accent and show the kind's glyph.
3. WHEN `side="auto"` THEN the bubble SHALL go on the first side in order top, right, bottom, left where it fits the canvas and overlaps no node, zone, panel or other callout.
4. WHEN `side` is given THEN the bubble SHALL go on that side.
5. IF no side fits THEN the bubble SHALL go on the first side in the order and `spinagram check` SHALL report `callout: overlap` naming the node.
6. IF `kind` is not one of info, tip, warning, risk THEN creating the callout SHALL fail naming the allowed kinds.

**Independent Test**: K8S01 with a warning callout on the PVC shows a bubble with a leader line and no overlap.

---

### P2: Illustrative notes

**User Story**: As an author of narrative slides, I want notes that look designed, not like sticky notes.

**Acceptance Criteria**:

1. WHEN `d.note(title, text=..., variant="card")` is created THEN it SHALL render as a card with a 6 px accent bar on its left edge in the primary colour.
2. WHEN `variant="quote"` THEN it SHALL render with a large opening quote mark and an italic body.
3. WHEN `variant` is omitted or `"sticky"` THEN the note SHALL render exactly as today.
4. IF `variant` is not sticky, card or quote THEN creating the note SHALL fail naming the allowed variants.
5. WHEN a note has an `icon` THEN the icon SHALL be drawn like a node icon.

**Independent Test**: a slide with one note of each variant renders three distinct designs.

---

### P2: CSS styling of annotations

**User Story**: As an author, I want to restyle legends, steps and callouts with my stylesheet.

**Acceptance Criteria**:

1. WHEN a stylesheet sets `legend { fill; stroke; border-radius; box-shadow }` THEN the legend card SHALL use those values.
2. WHEN a stylesheet sets `step { fill; stroke }` and `step::label { color }` THEN every step badge in the diagram and panel SHALL use them.
3. WHEN a stylesheet sets `callout.warning { fill; stroke }` THEN warning callouts SHALL use them; text parts SHALL accept `::title` and `::body`.
4. WHEN a stylesheet targets `note.card` THEN card notes SHALL match it.
5. WHEN `spinagram check --styles` runs THEN annotation elements SHALL appear in the report with their matched rules.

**Independent Test**: a dark stylesheet turns the legend card and step badges dark; `check --styles --select legend` explains it.

---

### P2: Showcase

**User Story**: As a visitor, I want the showcase to demonstrate annotations at their best.

**Acceptance Criteria**:

1. The AWS three-tier and hub-and-spoke showcases SHALL use an automatic legend and numbered steps.
2. The Kubernetes and Google Cloud showcases SHALL use at least one callout and a legend.
3. A new showcase diagram SHALL demonstrate the three note variants.
4. `spinagram check examples/showcase` SHALL report 0 issues.

**Independent Test**: render `examples/showcase` and review the PNGs.

---

## Edge Cases

- WHEN a diagram has steps but no legend THEN the steps panel SHALL take the band alone.
- WHEN the legend has more entries than fit THEN the right band SHALL flow entries into two columns before reporting overflow.
- IF a callout targets a node of another diagram THEN creating it SHALL fail.
- WHEN annotations are present in a PowerPoint export THEN badges, panels and bubbles SHALL be native shapes with editable text.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| ANN-01 | P1: Legend - automatic entries | Tasks | Verified |
| ANN-02 | P1: Legend - explicit items | Tasks | Verified |
| ANN-03 | P1: Legend - unused entry check | Tasks | Verified |
| ANN-04 | P1: Legend - node swatch style | Tasks | Verified |
| ANN-05 | P1: Legend - edge sample style | Tasks | Verified |
| ANN-06 | P1: Legend - icon entries | Tasks | Verified |
| ANN-07 | P1: Legend - titled card in band | Tasks | Verified |
| ANN-08 | P1: Band - right band area | Tasks | Verified |
| ANN-09 | P1: Band - bottom band area | Tasks | Verified |
| ANN-10 | P1: Band - sizes | Tasks | Verified |
| ANN-11 | P1: Band - overflow check | Tasks | Verified |
| ANN-12 | P1: Band - manual layout overlap check | Tasks | Verified |
| ANN-13 | P1: Steps - edge badge and panel | Tasks | Verified |
| ANN-14 | P1: Steps - node badge | Tasks | Verified |
| ANN-15 | P1: Steps - numbering | Tasks | Verified |
| ANN-16 | P1: Steps - duplicate check | Tasks | Verified |
| ANN-17 | P1: Steps - panel order and badges | Tasks | Verified |
| ANN-18 | P1: Steps - badge beside label | Tasks | Verified |
| ANN-19 | P1: Steps - YAML references | Tasks | Verified |
| ANN-20 | P1: Callouts - bubble and leader | Tasks | Verified |
| ANN-21 | P1: Callouts - kind colour and glyph | Tasks | Verified |
| ANN-22 | P1: Callouts - auto side | Tasks | Verified |
| ANN-23 | P1: Callouts - explicit side | Tasks | Verified |
| ANN-24 | P1: Callouts - overlap check | Tasks | Verified |
| ANN-25 | P1: Callouts - kind validation | Tasks | Verified |
| ANN-26 | P2: Notes - card | Tasks | Verified |
| ANN-27 | P2: Notes - quote | Tasks | Verified |
| ANN-28 | P2: Notes - sticky unchanged | Tasks | Verified |
| ANN-29 | P2: Notes - variant validation | Tasks | Verified |
| ANN-30 | P2: Notes - icon | Tasks | Verified |
| ANN-31 | P2: CSS - legend | Tasks | Verified |
| ANN-32 | P2: CSS - steps | Tasks | Verified |
| ANN-33 | P2: CSS - callouts | Tasks | Verified |
| ANN-34 | P2: CSS - note variants | Tasks | Verified |
| ANN-35 | P2: CSS - inspector report | Tasks | Verified |
| ANN-36 | P2: Showcase - AWS legend and steps | Tasks | Verified |
| ANN-37 | P2: Showcase - K8s/GCP callouts and legend | Tasks | Verified |
| ANN-38 | P2: Showcase - notes slide | Tasks | Verified |
| ANN-39 | P2: Showcase - check clean | Tasks | Verified |

**Coverage:** 39 total, 39 mapped to tasks, 0 unmapped

---

## Success Criteria

- [ ] The showcase renders legends, steps, callouts and notes with `spinagram check` at 0 issues.
- [ ] The PowerPoint export of an annotated showcase opens with every annotation as an editable shape.

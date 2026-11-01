# Feature: Rich diagram editor on the Rust engine (WASM)

**Status:** Specify · **Size:** Complex · **Owner:** spinagram
**Research:** `.specs/research/web-editor-wasm-runtime.md` §8 · **Decision:** STATE.md 2026-11-01 "Rich editor platform"
**Related:** `features/canvas-editor/spec.md` defines the canvas interactions (palette, search, zones, groups). This
spec defines the engine and platform underneath them.

## Problem Statement

The editor renders on the Python server: every edit pays a save and a server round-trip, nothing can move while
the engine works, and a static site cannot render at all. Editing logic would be written separately for the canvas,
the MCP agent and Python. We want one Rust engine, already the default for text, routing, CSS, SVG and PNG, to own
the YAML → scene pipeline and the edit operations, run in the browser, and drive an editor where diagrams reflow
live, code and canvas stay in sync, and agents edit through the same operations as people.

## Goals

- [ ] A hand-placed YAML diagram renders fully in the browser with SVG byte-identical to `spinagram render`.
- [ ] Dragging a node in a 50-node diagram reflows its zone and re-routes its edges at ≥ 50 fps.
- [ ] Every canvas or agent edit changes only the YAML text it touches; comments and formatting elsewhere survive byte-for-byte.
- [ ] One web build runs under `spinagram serve`, on any static host and browser-only, rendering through the same Rust engine as the server.

## Out of Scope

| Feature | Reason |
|---|---|
| Canvas editing of Python specs | User decision: convert one way with `yaml_io.dump`; Python stays in code editing and preview |
| RustPython / Pyodide | Dropped: no user Python runs in the browser |
| VS Code extension, embeddable web component | Not a one-year target (user choice); the WASM bundle keeps them possible |
| Visual diff bot, share-by-URL | Not in the first feature set (user choice) |
| Multiplayer | Later; the operation log is the foundation |
| dot / d2 layouts in the browser | Subprocess engines; server fallback in `serve`, unsupported in the static playground |
| PPTX / Figma export in the browser | Stay in Python |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
|---|---|---|---|
| Canvas source format | YAML only; "Edit on canvas" on a Python spec or an engine-laid-out diagram writes `<name>.yaml` with `yaml_io.dump` and opens it | User decision | y |
| Targets | Local `spinagram serve` and a static web playground | User choice | y |
| Shared rendering | One Rust engine renders for both hosts: the server calls it natively (PyO3), the browser calls the same code compiled to WASM. One web bundle serves `serve`, self-hosted and in-browser use; a host only adds storage (disk, watch, packs) | User direction: easy self-hosting and try-in-browser with no second renderer | y |
| Python engine fallback | Only for features not yet ported to Rust and for previewing Python specs; it disappears per feature as the port lands | Keeps the editor complete during the port | n |
| Edit operations | Implemented in Rust, shared by canvas (WASM), MCP, CLI and Python (PyO3) | User choice | y |
| Render path | Worker sends scene diffs keyed by element id; React updates only changed SVG elements | User choice | y |
| First features | Live reflow + smart edges; code↔canvas sync + live QA; AI edits via operations | User choice | y |
| Port order | Hand-placed pipeline first (YAML loader, model, manual layout, zones, containers, theme, icons from host bytes), then autolayout, then QA | Canvas diagrams are hand-placed; smallest path to a browser render | n |
| Unsupported features in WASM | The engine reports a capability miss; `serve` falls back to the server render, the playground shows "This diagram needs the server: <feature>" | Ship before full parity | n |
| Parity oracle | The Python engine: SVG byte-equality on `examples/` and test fixtures, as in the existing Rust slices | Same method as rust-core-* features | n |
| YAML editing in Rust | Byte-range patching from parser spans (saphyr marks); `yaml-edit` (rowan CST) evaluated in Design | Comment preservation needs source ranges, not re-serialisation | n |
| Fonts and icons in WASM | The host passes font and icon bytes; the core never reads disk or network; the playground caches packs in IndexedDB | WASM has no file system or system fonts | n |
| Files in the playground | File System Access API where available, otherwise in-browser storage with import/export | Static hosting | n |
| Reflow scope during drag | Re-layout the dragged node's ancestors (zone, container) and re-route edges touching moved items; the rest stays put | Incremental work keeps ≥ 50 fps | n |
| AI ghost preview | The MCP server sends operations; the canvas shows them as a translucent preview with Accept / Reject | Agent and human share one operation model | n |

**Open questions:** none blocking Design; defaults above with `Confirmed? n` are for review.

---

## User Stories

### P1: Element ids and render contract ⭐ foundation

**User Story**: As the canvas, I want every rendered element tagged with its diagram id and one render contract
so that the server and the WASM engine are interchangeable.

**Acceptance Criteria**:

1. The system SHALL wrap each node, zone, container, edge and label in an SVG `<g data-id="…">` with its diagram id, in both engines and every output.  <!-- ubiquitous -->
2. WHEN a render is requested with `{yaml, files}` THEN the renderer SHALL return `{scene, svg, srcmap, diagnostics, capabilities_missing}`, from the server or the worker alike.  <!-- event-driven -->
3. The `srcmap` SHALL map every element id to the byte range of its YAML entry.  <!-- ubiquitous -->
4. WHEN "Edit on canvas" is chosen on a Python spec or an engine-laid-out diagram THEN the system SHALL write `<name>.yaml` from `yaml_io.dump`, refuse if it exists, and open it.  <!-- event-driven -->
5. WHEN a dumped YAML is rendered THEN its SVG SHALL be byte-identical to the source diagram's SVG for every diagram in `examples/`.  <!-- event-driven -->

---

### P1: Hand-placed pipeline in WASM ⭐ MVP

**User Story**: As a playground user, I want hand-placed YAML diagrams rendered in my browser so that editing needs
no server.

**Acceptance Criteria**:

1. WHEN the worker renders a hand-placed YAML diagram (nodes, zones, rows/columns, edges, labels, legend, theme, CSS, icons) THEN its SVG SHALL be byte-identical to `spinagram render` with the Python engine.  <!-- event-driven -->
2. IF the diagram uses a feature the WASM engine lacks THEN the render SHALL name it in `capabilities_missing`; `serve` SHALL use the server render and the playground SHALL show "This diagram needs the server: <feature>".  <!-- unwanted-behavior -->
3. The core SHALL read fonts and icons only from bytes passed by the host.  <!-- ubiquitous -->
4. WHEN the editor first loads THEN it SHALL show the server render (serve) or a loading state (playground) until the worker is ready, without blocking input.  <!-- event-driven -->
5. The Python package SHALL use the same Rust pipeline through PyO3 for the ported parts, keeping the full test suite green.  <!-- ubiquitous -->

---

### P1: Edit operations in Rust ⭐ MVP

**User Story**: As any client (canvas, agent, CLI, Python), I want typed edit operations that update the diagram
and patch the YAML minimally so that every surface edits the same way.

**Acceptance Criteria**:

1. The core SHALL provide operations AddNode, AddZone, Move, Resize, Rename, Delete, Group (row/column), Ungroup, Reparent (zone), Connect, Disconnect and SetLabel, each returning the new scene diff and a YAML text patch.  <!-- ubiquitous -->
2. WHEN an operation is applied THEN bytes outside the patched ranges SHALL be unchanged (comments, blank lines, key order, flow/block style).  <!-- event-driven -->
3. IF an operation is invalid (unknown id, zone cycle, duplicate id) THEN the core SHALL reject it with a reason and change nothing.  <!-- unwanted-behavior -->
4. WHEN a list of operations is applied as one batch THEN the core SHALL apply all or none.  <!-- event-driven -->
5. The same operations SHALL be callable from Python, the CLI (`spinagram edit`) and the MCP server.  <!-- ubiquitous -->

---

### P1: Scene diffs to the canvas ⭐ MVP

**User Story**: As the canvas, I want only changed elements updated so that edits never flicker and transitions can
animate.

**Acceptance Criteria**:

1. WHEN a render or operation completes THEN the worker SHALL send the added, changed and removed elements keyed by id.  <!-- event-driven -->
2. WHEN a diff arrives THEN the canvas SHALL update only those SVG elements, leaving selection and pointer state intact.  <!-- event-driven -->
3. WHEN elements move because of an operation THEN the canvas SHALL animate them to their new place within 150 ms; WHILE a drag is active the dragged items SHALL not animate.  <!-- event-driven + state-driven -->
4. The DOM after applying diffs SHALL equal the DOM from rendering the full SVG of the same state.  <!-- ubiquitous -->

---

### P2: Live reflow and smart edges

**User Story**: As a diagram author, I want zones, rows and edges to follow while I drag so that I see the result
before I drop.

**Acceptance Criteria**:

1. WHILE a node is dragged the system SHALL re-layout its zone and container and re-route edges touching it on every frame, at ≥ 50 fps for a 50-node diagram.  <!-- state-driven -->
2. WHILE a dragged node is over a zone or container the system SHALL preview its membership (zone grows, row opens a gap).  <!-- state-driven -->
3. WHEN the drag ends THEN the system SHALL commit one Move/Reparent operation and the final scene SHALL equal a fresh render of the patched YAML.  <!-- event-driven -->
4. WHILE an edge is dragged from a handle the system SHALL show the routed path to the target under the pointer, snapping to the nearest side.  <!-- state-driven -->

---

### P2: Code↔canvas sync

**User Story**: As a diagram author, I want the code and the canvas to point at each other so that I always know
which YAML draws what.

**Acceptance Criteria**:

1. WHEN an element is selected on the canvas THEN the code panel SHALL highlight and scroll to its YAML range.  <!-- event-driven -->
2. WHEN the code cursor enters an element's YAML range THEN the canvas SHALL highlight that element.  <!-- event-driven -->
3. WHEN the user types in the code panel THEN the canvas SHALL update within 100 ms of the last keystroke for a 50-node diagram, without saving.  <!-- event-driven -->
4. IF the YAML does not parse THEN the canvas SHALL keep the last good scene and mark the error line.  <!-- unwanted-behavior -->

---

### P2: Live QA

**User Story**: As a diagram author, I want problems shown as I edit so that I fix them before export.

**Acceptance Criteria**:

1. WHEN a render completes THEN the system SHALL run the QA checks ported to Rust (text overflow, overlaps, label collisions, contrast) and mark each finding on its element and in the code panel.  <!-- event-driven -->
2. WHERE a finding has a safe fix the system SHALL offer it as an operation.  <!-- optional-feature -->
3. The Rust QA findings SHALL equal `spinagram check` findings on `examples/`.  <!-- ubiquitous -->

---

### P2: AI edits through operations

**User Story**: As a diagram author working with an agent, I want its changes previewed on the canvas so that I
accept or reject them like a suggestion.

**Acceptance Criteria**:

1. WHEN the MCP server proposes an operation batch for the open diagram THEN the canvas SHALL show it as a translucent preview with Accept and Reject.  <!-- event-driven -->
2. WHEN the user accepts THEN the system SHALL apply the batch as one undoable step; WHEN the user rejects THEN nothing SHALL change.  <!-- event-driven -->
3. IF the diagram changed since the batch was proposed THEN the system SHALL re-validate it and refuse with "Diagram changed; ask the agent again" when invalid.  <!-- unwanted-behavior -->

---

### P1: One bundle, any host ⭐ MVP

**User Story**: As someone trying or self-hosting spinagram, I want the same editor whether it runs from
`spinagram serve`, from my own static hosting, or straight in the browser, so that there is one thing to deploy and
one renderer to trust.

**Acceptance Criteria**:

1. The web app SHALL build once as static files; `spinagram serve`, self-hosting and the browser playground SHALL serve that same build.  <!-- ubiquitous -->
2. WHEN the app starts THEN it SHALL detect a storage host (the serve API) and otherwise run browser-only, with no other difference in editing or rendering.  <!-- event-driven -->
3. The server and the browser SHALL render through the same Rust engine; for the same YAML, fonts and icons, the server SVG and the worker SVG SHALL be byte-identical.  <!-- ubiquitous -->
4. WHERE the app runs browser-only and the user opens a folder the app SHALL use the File System Access API where available, otherwise in-browser storage with import and export.  <!-- optional-feature -->
5. WHEN an icon pack is first needed browser-only THEN the app SHALL fetch it once and cache it in IndexedDB.  <!-- event-driven -->
6. Self-hosting SHALL need only a static file server for browser-only use, and `spinagram serve` (or its container image) for shared disk storage.  <!-- ubiquitous -->

---

## Edge Cases

- WHEN the worker crashes THEN the editor SHALL restart it and re-render the current YAML.
- WHEN the file changes on disk while idle (serve) THEN the editor SHALL re-render from the new text.
- IF a YAML patch would produce invalid YAML THEN the operation SHALL be rejected (re-parse check before commit).

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
|---|---|---|---|
| CTR-01 | P1: Element ids and render contract | - | Pending |
| CTR-02 | P1: Element ids and render contract | MVP | Partial (T6: scene endpoint; render contract pending) |
| CTR-03 | P1: Element ids and render contract | MVP | Done (T2, T3, T5: srcmap) |
| CTR-04 | P1: Element ids and render contract | - | Pending |
| CTR-05 | P1: Element ids and render contract | - | Pending |
| WSM-01 | P1: Hand-placed pipeline in WASM | - | Pending |
| WSM-02 | P1: Hand-placed pipeline in WASM | - | Pending |
| WSM-03 | P1: Hand-placed pipeline in WASM | - | Pending |
| WSM-04 | P1: Hand-placed pipeline in WASM | - | Pending |
| WSM-05 | P1: Hand-placed pipeline in WASM | - | Pending |
| OPS-01 | P1: Edit operations in Rust | MVP | Partial (T2: move, resize, rename, delete, add node, connect, disconnect; zones/groups pending) |
| OPS-02 | P1: Edit operations in Rust | MVP | Done (T2) |
| OPS-03 | P1: Edit operations in Rust | MVP | Done (T2) |
| OPS-04 | P1: Edit operations in Rust | MVP | Done (T2) |
| OPS-05 | P1: Edit operations in Rust | MVP | Partial (T3 Python, T5/T7 browser; CLI and MCP pending) |
| DIF-01 | P1: Scene diffs to the canvas | - | Pending |
| DIF-02 | P1: Scene diffs to the canvas | - | Pending |
| DIF-03 | P1: Scene diffs to the canvas | - | Pending |
| DIF-04 | P1: Scene diffs to the canvas | - | Pending |
| LRF-01 | P2: Live reflow and smart edges | MVP | Partial (T4, T7: edges re-route live; zone reflow pending) |
| LRF-02 | P2: Live reflow and smart edges | - | Pending |
| LRF-03 | P2: Live reflow and smart edges | - | Pending |
| LRF-04 | P2: Live reflow and smart edges | - | Pending |
| SYN-01 | P2: Code↔canvas sync | MVP | Done (T7: highlights when the code panel is open) |
| SYN-02 | P2: Code↔canvas sync | - | Pending |
| SYN-03 | P2: Code↔canvas sync | - | Pending |
| SYN-04 | P2: Code↔canvas sync | - | Pending |
| LQA-01 | P2: Live QA | - | Pending |
| LQA-02 | P2: Live QA | - | Pending |
| LQA-03 | P2: Live QA | - | Pending |
| AIE-01 | P2: AI edits through operations | - | Pending |
| AIE-02 | P2: AI edits through operations | - | Pending |
| AIE-03 | P2: AI edits through operations | - | Pending |
| HST-01 | P1: One bundle, any host | MVP | Partial (T8: the wasm ships in the UI bundle) |
| HST-02 | P1: One bundle, any host | - | Pending |
| HST-03 | P1: One bundle, any host | MVP | Partial (T1, T5: shared draw stage; body byte-identical) |
| HST-04 | P1: One bundle, any host | - | Pending |
| HST-05 | P1: One bundle, any host | - | Pending |
| HST-06 | P1: One bundle, any host | - | Pending |

**Coverage:** 39 total; the rich editor MVP (`tasks.md` T1-T8) covers CTR-03, OPS-02..04, SYN-01 and parts of CTR-02, OPS-01, OPS-05, LRF-01, HST-01, HST-03.

## Success Criteria

- [ ] Goals 1–4 measured and met.
- [ ] Each P1 story ships with a parity harness against the Python engine, like the rust-core-* features.

# Feature: Code panel width fix and element inspector with declarations

**Status:** Implementing (2026-10-19) · **Size:** Large · **Owner:** spinagram

## Problem Statement

Opening the code panel in `spinagram serve` leaves an empty strip to its right (black in dark mode): the
panel's wrapper has no width, sizes to its content (~900 px) and the panel inside resolves `w-[44%]` to its
420 px minimum. Inspect mode only works for diagrams with a stylesheet: an unstyled diagram returns no
elements, so clicks select nothing, the panel shows only "uses no stylesheet", and the code panel's
click-to-line jump fails (it reads the node title from the same empty list, and only finds quoted titles).
The hover outline is a faint dashed line with no label. Users want a browser-devtools-like inspector: a clear
highlight of the clickable area, a label naming the element, and the element's details including where it is
declared in the source.

## Goals

- [ ] With the code panel open, the panel fills the space right of the diagram: no empty strip.
- [ ] In inspect mode every element of any diagram (styled or not) highlights on hover with a name/size label
      and shows its details, including the file and line that declares it, on click.

## Out of Scope

| Feature | Reason |
|---|---|
| Editing styles or attributes from the inspector | Deferred idea in STATE.md; not requested |
| Exact source positions from the Python interpreter (call-site capture in the model) | Touches the core model and every backend's dataclass equality; a text search is enough for the specs we ship |
| Declarations of annotations (legend, steps, callouts) | They have no geometry in the inspector today |
| Box-model (margin/padding) layers in the highlight | spinagram has no box model per element |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
|---|---|---|---|
| "Hide the doc on the left" | Collapse the Recent sidebar to a rail, like the code panel; key `[`; remembered per browser | Same pattern users already know from the code rail | n |
| "Black right doc" | The empty strip right of the code panel (dark-mode body colour) | Reproduced in the browser: wrapper 912 px, panel 420 px | n |
| Declaration source | Server-side text search of the spec file (`spinagram.ui.declare.locate`), first matching line | Pure, testable, no model change | n |
| YAML node / group match | A line with `id: <id>` (quoted or not); else `title:`/`label:` equal to the element's label | YAML specs declare ids; auto ids come from titles | n |
| Python node / group match | A line with `id="<id>"`/`id='<id>'`; else the label as a quoted string (`"Users"`) | `d.box("Users")` derives the id from the title | n |
| YAML edge match | A line with `<from> -> <to>` (the string form), else a line holding both `from: <from>` and `to: <to>` | The two edge forms of the YAML loader | n |
| Python edge match | The edge label as a quoted string; no label → not found | Variable names in `a.to(b)` are not ids | n |
| Declaration payload | Each element of the styles report gets `declaration: {file, line, text}` or `null`; `file` is the spec's path relative to the workspace (same as `SpecFile.rel`) | Same keys the code panel already uses | n |
| Unstyled diagrams | `css.inspect(..., all_elements=True)` lists the element tree with empty `styles`/`trace`; the CLI keeps calling it without the flag, so `check --styles --json` is unchanged | Inspector needs the tree; CLI output stays stable | n |
| Hover label | A chip above the box (below when no room) with `elementLabel` and `W × H` in scene px, rounded | Mirrors the devtools tooltip | n |
| "Show in code" | Opens the code panel and selects the declaration line in the spec tab | Reuses the existing jump path | n |
| Code panel jump | Driven by the declaration line instead of a title search in the browser; `jumpLine` is removed | One locator, server side; fixes unquoted YAML titles | n |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: The code panel fills its column ⭐ MVP

**User Story**: As a diagram author, I want the code panel to take the whole right column so that no empty
dark strip sits next to it.

**Acceptance Criteria**:

1. WHEN the code panel is open THEN the UI SHALL give the code panel the full width of its column: the panel's width SHALL equal its wrapper's width (difference 0 px). <!-- LAYOUT-01 -->
2. WHILE the code panel is open the UI SHALL size its column to 44 % of the diagram view row, at least 420 px. <!-- LAYOUT-02 -->

**Independent Test**: open a diagram, press `e`, compare `aside[aria-label=Code]` width with its parent's.

### P1: Inspect any diagram's elements ⭐ MVP

**User Story**: As a diagram author, I want inspect mode to work on diagrams without a stylesheet so that I can
see what each box is.

**Acceptance Criteria**:

1. WHEN `css.inspect` is called with `all_elements=True` on an unstyled diagram THEN it SHALL return `styled: false` and one element per tree item (diagram, groups, nodes, edges) with empty `styles` and `trace`. <!-- ELI-01 -->
2. WHEN `css.inspect` is called without `all_elements` on an unstyled diagram THEN it SHALL return `elements: []` (CLI output unchanged). <!-- ELI-02 -->
3. WHEN the styles endpoint serves an unstyled diagram THEN its report SHALL list the same element keys a styled copy of the diagram lists. <!-- ELI-03 -->
4. WHILE inspect mode is on and the diagram is unstyled the panel SHALL list the elements and, for a selected element, show its type, id, classes and attributes. <!-- ELI-04 -->

**Independent Test**: inspect `examples/aws_layout.yaml`, click "Applications", see `node#users`.

### P1: Highlight the clickable area ⭐ MVP

**User Story**: As a diagram author, I want the element under the pointer highlighted with a label so that I
know what a click will select.

**Acceptance Criteria**:

1. WHILE inspect mode is on, WHEN the pointer is over an element THEN the overlay SHALL fill its box with a translucent tint and draw a solid outline. <!-- HIL-01 -->
2. WHILE inspect mode is on, WHEN the pointer is over an element THEN the overlay SHALL show a chip with the element label and its size as `W × H` (scene px rounded to integers, e.g. `node#users 182 × 64`). <!-- HIL-02 -->
3. WHEN the hovered element is an edge THEN the chip SHALL show the edge label (`edge a → b`) without a size. <!-- HIL-03 -->
4. WHEN the chip would go above the scene's top edge THEN the overlay SHALL place it below the box. <!-- HIL-04 -->

**Independent Test**: hover "Applications" in inspect mode; a tinted box and `node#users 182 × 64`-style chip appear.

### P1: See where an element is declared ⭐ MVP

**User Story**: As a diagram author, I want the inspector to show the source line that declares the element
so that I can go and change it.

**Acceptance Criteria**:

1. WHEN `locate` searches a YAML spec for a node or group THEN it SHALL return the 1-based line of the first `id: <id>` entry (quoted or bare, ended by `,`, `}`, `#`, space or end of line); without one, the first `title:`/`label:` entry equal to the label. <!-- DECL-01 -->
2. WHEN `locate` searches a Python spec for a node or group THEN it SHALL return the first line holding `id="<id>"` or `id='<id>'`; without one, the first line holding the label as a quoted string. <!-- DECL-02 -->
3. WHEN `locate` searches a YAML spec for an edge THEN it SHALL return the first line matching `<from>\s*->\s*<to>` (word-bounded), else the first line holding both `from: <from>` and `to: <to>`. <!-- DECL-03 -->
4. WHEN `locate` searches a Python spec for an edge with a label THEN it SHALL return the first line holding the label as a quoted string. <!-- DECL-04 -->
5. IF no line matches THEN `locate` SHALL return `None`. <!-- DECL-05 -->
6. WHEN the styles endpoint serves a diagram THEN each element SHALL carry `declaration` = `{file, line, text}` (`text` the stripped source line) or `null` when not found; the `diagram` element SHALL point at the line holding `id: <id>` or the `Diagram("<id>"` call. <!-- DECL-06 -->
7. WHEN an element is selected THEN the panel SHALL show a Declaration section with `file:line` and the source line in monospace. <!-- DECL-07 -->
8. IF the element has no declaration THEN the panel SHALL show "Declaration not found in <file>". <!-- DECL-08 -->
9. WHEN the user clicks "Show in code" THEN the code panel SHALL open (if collapsed) and select the declaration line in the spec tab. <!-- DECL-09 -->
10. WHILE the code panel is open and inspect mode is off, WHEN the user clicks an element with a declaration THEN the editor SHALL select that line. <!-- DECL-10 -->

**Independent Test**: inspect `examples/aws_layout.yaml`, click "Applications": Declaration `aws_layout.yaml:22`.

### P2: Hide the left sidebar

**User Story**: As a diagram author, I want to fold the Recent sidebar away so that the diagram and code get
the room. (Added 2026-10-19 during execution.)

**Acceptance Criteria**:

1. WHEN the user clicks the collapse button (`«`) in the sidebar header THEN the UI SHALL replace the 256 px sidebar with a 32 px rail labelled "Recent". <!-- SIDE-01 -->
2. WHEN the user clicks the rail or presses `[` while collapsed THEN the UI SHALL show the 256 px sidebar again; `[` while expanded SHALL collapse it. <!-- SIDE-02 -->
3. WHEN the page reloads THEN the UI SHALL restore the last state from `localStorage["spinagram.sidebar"]` (`"0"` collapsed); IF storage is unavailable THEN the sidebar SHALL start expanded. <!-- SIDE-03 -->

**Independent Test**: click `«`, sidebar becomes a rail; reload, still a rail; press `[`, sidebar returns.

### P1: Shortcuts stay out of the editor ⭐ MVP

**User Story**: As a diagram author, I want to type `e`, `i`, `f` or `[` in the code editor without toggling
panels. (Found 2026-10-19 during execution: typing `e` in the editor collapsed the code panel and dropped the
letter, because the shortcut guard skipped inputs and textareas but not CodeMirror's contenteditable.)

**Acceptance Criteria**:

1. IF a key is pressed while focus is in an input, textarea, select or contenteditable element THEN the UI SHALL run no single-key shortcut and SHALL let the key reach the element. <!-- KEY-01 -->

**Independent Test**: focus the code editor, type `e`: the letter appears and the panel stays open.

---

## Edge Cases

- IF the spec file cannot be read THEN the styles endpoint SHALL return every `declaration` as `null` and still 200.
- WHEN an id contains regex characters (`.`, `-`) THEN `locate` SHALL match it literally.
- WHEN a title is a list (multi-line title) THEN the label searched SHALL be the joined title the report shows.

Remaining implicit-requirement dimensions (auth, concurrency, persistence, external calls) N/A: read-only
additions to an existing local endpoint.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
|---|---|---|---|
| LAYOUT-01 | P1: Code panel column | Tasks | Implemented |
| LAYOUT-02 | P1: Code panel column | Tasks | Implemented |
| ELI-01 | P1: Inspect any diagram | Tasks | Implemented |
| ELI-02 | P1: Inspect any diagram | Tasks | Implemented |
| ELI-03 | P1: Inspect any diagram | Tasks | Implemented |
| ELI-04 | P1: Inspect any diagram | Tasks | Implemented |
| HIL-01 | P1: Highlight | Tasks | Implemented |
| HIL-02 | P1: Highlight | Tasks | Implemented |
| HIL-03 | P1: Highlight | Tasks | Implemented |
| HIL-04 | P1: Highlight | Tasks | Implemented |
| DECL-01 | P1: Declarations | Tasks | Implemented |
| DECL-02 | P1: Declarations | Tasks | Implemented |
| DECL-03 | P1: Declarations | Tasks | Implemented |
| DECL-04 | P1: Declarations | Tasks | Implemented |
| DECL-05 | P1: Declarations | Tasks | Implemented |
| DECL-06 | P1: Declarations | Tasks | Implemented |
| DECL-07 | P1: Declarations | Tasks | Implemented |
| DECL-08 | P1: Declarations | Tasks | Implemented |
| DECL-09 | P1: Declarations | Tasks | Implemented |
| DECL-10 | P1: Declarations | Tasks | Implemented |
| KEY-01 | P1: Shortcuts stay out of the editor | Tasks | Implemented |
| SIDE-01 | P2: Hide sidebar | Tasks | Implemented |
| SIDE-02 | P2: Hide sidebar | Tasks | Implemented |
| SIDE-03 | P2: Hide sidebar | Tasks | Implemented |

**Coverage:** 24 total, 24 mapped to tasks, 0 unmapped

---

## Success Criteria

- [ ] Code panel width equals its column width in the browser (0 px gap).
- [ ] Every node of `examples/aws_layout.yaml` and `examples/quickstart.py` shows a declaration line.

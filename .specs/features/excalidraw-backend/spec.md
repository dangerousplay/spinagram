# Feature: Excalidraw backend

**Status:** Accepted by the user without a passing verification (2026-10-19; see validation.md) · **Size:** Large · **Owner:** spinagram

## Problem Statement

Teams sketch and review architecture in Excalidraw. spinagram can hand a diagram to PowerPoint and Figma as
editable shapes, but to Excalidraw only as a flat SVG/PNG image, so boxes, arrows and text cannot be moved or
edited there. An `excalidraw` backend writes native `.excalidraw` scenes that keep spinagram's geometry and
theme colours.

## Goals

- [ ] `spinagram render x.yaml -f excalidraw` writes `<slug>.excalidraw` that opens in Excalidraw with every box, arrow, text and icon as its own editable element.
- [ ] The scene matches the SVG output's positions and colours (clean style: no hand-drawn roughness).

## Out of Scope

| Feature | Reason |
|---|---|
| Hand-drawn (sketch) style | User chose clean, theme-true output (2026-10-19) |
| Importing `.excalidraw` into a spinagram spec | Separate feature (diagram-import) |
| Theme fonts inside Excalidraw | Excalidraw only renders its own font families |
| Live collaboration links / excalidraw.com upload | Publishes user content to an external service |
| `.excalidrawlib` icon libraries | Not requested |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
|---|---|---|---|
| Style | `roughness: 0`, `fillStyle: "solid"`, theme hex colours, `strokeWidth` from the scene | User choice | y |
| File | One `<slug>.excalidraw` per diagram, `{"type":"excalidraw","version":2,"source":"https://github.com/dangerousplay/spinagram","elements","appState","files"}` | Excalidraw's file format (excalidraw master, 2026-10) | n |
| Fonts | `fontFamily` 2 (Helvetica) for every text; 3 (Cascadia) when the theme family is monospace | Closest neutral sans/mono in Excalidraw's fixed set | n |
| Text | Lines as wrapped by the scene joined with `\n`, `autoResize: false`, `width` = box width, `lineHeight` = leading / font size | Keeps spinagram's wrapping; Excalidraw measures with its own font so widths may differ slightly | n |
| Shape labels | A label with one block → text bound to the shape (`containerId`, `boundElements`); several blocks (title + body) → one free text per block, grouped with the shape | Excalidraw binds one text per container | n |
| Kinds | `rect` → rectangle; `pill` → rectangle with `roundness {type:3, value:h/2}`; `diamond` → diamond; radius > 0 → `roundness {type:3, value:radius}`; kinds with `parts` (cylinder, document, …) → one `line` per subpath (`polygon: true` when closed; curves flattened to 8 segments per Bézier), grouped; part paint `solid` fills with the stroke colour, `stroke` has no fill | Native where Excalidraw has the shape, faithful polygons otherwise | n |
| Edges | Connector → `arrow` with relative `points`; `curve` → 3 points with `roundness {type:2}`; others `roundness: null`, `elbowed: false` | Keeps spinagram's exact route | n |
| Bindings | `src`/`dst` → `startBinding`/`endBinding` `{elementId, focus: 0, gap: 1, fixedPoint: [fx, fy], mode: "orbit"}` (fixed point = anchor relative to the shape) and the arrow in the shape's `boundElements` | `fixedPoint`/`mode` is current; `focus`/`gap` lets older releases restore it | n |
| Arrowheads | `arrow` → `triangle`, `open-arrow` → `arrow`, `diamond` → `diamond`, `open-diamond` → `diamond_outline`, `circle` → `circle`, `bar` → `bar`, `none`/no arrow → `null` | spinagram's `arrow` is a filled triangle; Excalidraw's `arrow` is the open chevron | n |
| Edge labels | The label pill (rectangle + text) at the scene position, grouped with its arrow | Excalidraw's bound arrow text sits at the midpoint; spinagram places labels (`label_at`) | n |
| Icons / images | `image` elements; `files[<sha1 of bytes>] = {mimeType, id, dataURL, created: 0}`; same bytes stored once | Excalidraw's image format; dedupe keeps files small | n |
| Tables | Rectangle + text per cell, grouped under the table id | No table element in Excalidraw | n |
| Canvas | A `frame` named `spinagram:<id>` sized to the scene holds every element (`frameId`); `appState.viewBackgroundColor` = scene background | Export keeps the slide bounds, like the Figma container | n |
| Determinism | Element ids from scene item ids (`<item id>` + suffix), `seed`/`versionNonce` from a hash of the id, `version: 1`, `updated: 1` | Same spec → byte-identical file, diff-friendly | n |
| Transparent | Fill `None` → `backgroundColor: "transparent"`; no stroke → `strokeColor: "transparent"`, `strokeWidth: 1` | Excalidraw has no "none" paint | n |
| Dashes | `dashed` or a `dash` pattern → `strokeStyle: "dashed"`; a pattern whose dash ≤ 2 px → `"dotted"` | Excalidraw has three stroke styles | n |
| Opacity | `opacity` × 100, rounded; `fill_opacity` multiplies it on shapes | Excalidraw has one opacity per element | n |
| Shadows | Dropped | Excalidraw has no shadows | n |
| Verification in the app | User opens one file in Excalidraw (UAT); automated tests check structure | Loading Excalidraw needs a browser + external site | n |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Render native Excalidraw ⭐ MVP

**User Story**: As a diagram author, I want `-f excalidraw` so that I can keep editing a spinagram diagram
in Excalidraw.

**Acceptance Criteria**:

1. The system SHALL register a backend `excalidraw` (built-in and the `spinagram.backends` entry point) listed by `render --help`. <!-- EXC-01 -->
2. WHEN a diagram renders with `excalidraw` THEN the system SHALL write `<out>/<slug>.excalidraw` as UTF-8 JSON with the top-level keys `type`, `version`, `source`, `elements`, `appState`, `files`. <!-- EXC-02 -->
3. The system SHALL give every element `roughness` 0 and every filled shape `fillStyle` `"solid"`. <!-- EXC-03 -->
4. WHEN the scene has a `Shape` THEN the system SHALL emit one element with its `x`, `y`, `width`, `height`, fill as `backgroundColor`, stroke as `strokeColor` and `strokeWidth`, with the type and roundness of the Kinds row. <!-- EXC-04 -->
5. WHEN a shape kind has `parts` THEN the system SHALL emit one `line` element per subpath of each part, `polygon` true when the subpath is closed, whose absolute points lie on the outline (within 1 px of the path flattened to 8 segments per Bézier), all grouped with the shape. <!-- EXC-05 -->
6. WHEN a shape label has one block THEN the system SHALL emit a text with `containerId` = the shape's id, listed in the shape's `boundElements`, `textAlign`/`verticalAlign` from the label. <!-- EXC-06 -->
7. WHEN a shape label has several blocks THEN the system SHALL emit one text per block, `width` = the label box width, `y` = the block top `Label.place()` gives and `x` = its x for left-aligned labels or its x − width / 2 for centred ones (Excalidraw's `x` is the left edge), with that block's font size and colour, grouped with the shape. <!-- EXC-07 -->
8. WHEN the scene has a `Connector` THEN the system SHALL emit an `arrow` whose `x + points[i]` equal the connector's points (curve: start, control, end), with the arrowheads of the Arrowheads row and `strokeStyle` from its dash. <!-- EXC-08 -->
9. WHEN a connector end has a binding THEN the arrow SHALL carry that binding (`elementId` = the shape's element id, `fixedPoint` = anchor relative to the shape, 0–1) and the shape's `boundElements` SHALL list the arrow. <!-- EXC-09 -->
10. WHEN a connector has a label THEN the system SHALL emit its pill and text at the scene position, sharing a group id with the arrow. <!-- EXC-10 -->
11. WHEN the scene has an icon or `Image` THEN the system SHALL emit an `image` element at its box with a `fileId` present in `files`, whose `dataURL` decodes to the file's bytes and `mimeType` is the file's type. <!-- EXC-11 -->
12. WHEN two images use the same bytes THEN `files` SHALL hold one entry. <!-- EXC-12 -->
13. WHEN the scene has `Text`, `Line` or `TableGrid` items THEN the system SHALL emit free texts (`textAlign` from the anchor), `line` elements and per-cell rectangles + texts grouped by table. <!-- EXC-13 -->
14. The system SHALL emit a `frame` named `spinagram:<id>` at 0,0 with the scene size, every other element's `frameId` set to it, and `appState.viewBackgroundColor` = the scene background. <!-- EXC-14 -->
15. The system SHALL use `fontFamily` 2, or 3 for a monospace theme family, and `fontSize` = the block's font size. <!-- EXC-15 -->
16. The system SHALL give every element a unique `id`, and rendering the same scene twice SHALL write byte-identical files. <!-- EXC-16 -->
17. The system SHALL order elements like the SVG backend's layers: the frame, then `zone`/`chrome` shapes, then the other items, then `pill`/`swatch` shapes, scene order within each layer, each item's texts and icons right after it. <!-- EXC-17 -->

**Independent Test**: Render `examples/` with `-f excalidraw`; parse each file; check element counts, a bound arrow, an icon file and determinism. Open one file in Excalidraw (UAT).

---

### P2: Docs

**Acceptance Criteria**:

1. The `spinagram` skill's `## Outputs` section SHALL describe `-f excalidraw` (native elements, clean style, Excalidraw fonts, what is dropped). <!-- EXC-18 -->

---

## Edge Cases

- IF a scene has no items THEN the file SHALL hold only the frame.
- IF an icon file is missing on disk THEN rendering SHALL fail with the same error the SVG backend gives.
- WHEN a connector has no binding at an end THEN that binding SHALL be `null`.
- WHEN a fill is `None` and the shape has no stroke THEN both colours SHALL be `"transparent"`.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
|---|---|---|---|
| EXC-01 | P1: Render native Excalidraw | Tasks | Implementing |
| EXC-02 | P1: Render native Excalidraw | Tasks | Implementing |
| EXC-03 | P1: Render native Excalidraw | Tasks | Implementing |
| EXC-04 | P1: Render native Excalidraw | Tasks | Implementing |
| EXC-05 | P1: Render native Excalidraw | Tasks | Implementing |
| EXC-06 | P1: Render native Excalidraw | Tasks | Implementing |
| EXC-07 | P1: Render native Excalidraw | Tasks | Implementing |
| EXC-08 | P1: Render native Excalidraw | Tasks | Implementing |
| EXC-09 | P1: Render native Excalidraw | Tasks | Implementing |
| EXC-10 | P1: Render native Excalidraw | Tasks | Implementing |
| EXC-11 | P1: Render native Excalidraw | Tasks | Implementing |
| EXC-12 | P1: Render native Excalidraw | Tasks | Implementing |
| EXC-13 | P1: Render native Excalidraw | Tasks | Implementing |
| EXC-14 | P1: Render native Excalidraw | Tasks | Implementing |
| EXC-15 | P1: Render native Excalidraw | Tasks | Implementing |
| EXC-16 | P1: Render native Excalidraw | Tasks | Implementing |
| EXC-17 | P1: Render native Excalidraw | Tasks | Implementing |
| EXC-18 | P2: Docs | Tasks | Implementing |

**Coverage:** 18 total, 18 mapped to tasks (T1–T12), 0 unmapped

---

## Success Criteria

- [ ] Every example renders to `.excalidraw` and opens in Excalidraw with editable boxes, arrows that follow their boxes, and icons.
- [ ] Positions match the SVG output within 1 px.

# Diagram Import (D2 and PlantUML) Specification

## Problem Statement

Teams that want to adopt spinagram already have architecture diagrams in D2 and PlantUML. Redrawing
them by hand blocks migration. spinagram should read `.d2` and `.puml` files, convert them into its own
model, and either render them directly (SVG, PNG, PowerPoint, Figma) or write an editable spinagram
Python (or YAML) spec, so a team can switch tools in one command and keep editing in Python.

Feasibility is confirmed (see `design.md` § Research): D2.js (the official WASM build of D2) returns a
fully resolved diagram as JSON, and PlantUML's `--preproc` flattens `!include` and C4 macros into plain
syntax, with structure metadata (`entity`, `cluster`, `link`) present in its SVG output.

## Goals

- [ ] A user converts a D2 or PlantUML architecture diagram into a spinagram Python spec with one command, and the generated file runs unchanged.
- [ ] `spinagram render`, `check` and `serve` accept `.d2` and `.puml` files directly, like `.yaml` and `.py`.
- [ ] Every source construct that cannot be represented is reported with its source line; nothing is dropped silently.
- [ ] On the bundled migration corpus (examples per format), every element and connection of the supported diagram families appears in the output.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| PlantUML sequence, timing, Gantt, mind map, WBS, JSON/YAML, salt diagrams | spinagram has no model for them (time axes, lifelines); they are not architecture box-and-arrow diagrams |
| D2 `sequence_diagram` shapes | Same as above |
| Exporting spinagram diagrams back to D2 or PlantUML | Migration is one-way into spinagram |
| Mermaid, draw.io, Structurizr DSL input | Separate frontends; this feature builds the shared import pipeline they can reuse later |
| Pixel-identical reproduction of the source tool's styling (fonts, sketch mode, themes) | Imported diagrams take the active spinagram theme; that is the point of migrating |
| Writing a full D2 parser in Python | D2.js already resolves vars, globs, classes and imports exactly as D2 does |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| How D2 is parsed | D2.js `compile()` run by bun or node; `@terrastruct/d2` pinned and installed into the spinagram cache on first use | Same pattern as the ELK engine (`autolayout/engines/elk.py`); exact D2 semantics without a parser to maintain; the native `d2` CLI has no JSON export | y (2026-10-12) |
| How PlantUML is parsed | Own Python parser for the description-diagram grammar (component, deployment, use case, C4), applied to `--preproc` output when Java is available, to the raw file otherwise | PlantUML has no AST export and no maintained Python parser; `--preproc` resolves `!include`, `!define` and the C4 stdlib | y (2026-10-12) |
| PlantUML jar | Pinned `plantuml-mit` jar downloaded into the cache on first use (checksum verified); `SPINAGRAM_PLANTUML_JAR` overrides | MIT licence; mirrors icon-pack download behaviour, honours `SPINAGRAM_OFFLINE` | n |
| Layout of imported diagrams | Re-laid out by spinagram's engines (layout direction carried over); keeping the source tool's coordinates is P2 | Clean, themed result is the migration goal; positions from another renderer rarely fit the 1920×1080 canvas | y (2026-10-12) |
| Shapes spinagram cannot draw (cylinder, person, cloud, circle, hexagon, queue…) | Native shape kinds are part of the MVP (IMP-27, P1): cylinder, ellipse, hexagon, cloud, person, document in the model and every backend; shapes outside that list fall back to a box with a warning | User chose fidelity over a smaller MVP | y (2026-10-12) |
| Delivery order | D2 frontend and the shared pipeline (shapes, codegen, report, CLI, direct render) first; PlantUML second | D2.js gives structured JSON and the closest model; builds the pipeline PlantUML reuses | y (2026-10-12) |
| Per-element colours from the source | Ignored with a warning in P1; mapped to node fill/stroke overrides in P2 | The model has no per-node fill/stroke today; themes own colour | n |
| Generated code style | Python using the builder and operators (`d.box`, `with d.group`, `a >> b`, `a.to(b, "label")`), ids kept from the source | Matches the Python-first direction; source ids keep the file diffable against the original | n |
| Identifier mapping | Source keys become node ids after slugging (`aws.api` → `api`, deduplicated with the parent prefix on collision) and Python variable names (`snake_case`, keywords suffixed `_`) | Generated code must run; readable names matter for hand-editing after migration | n |
| D2 multi-board files (layers, scenarios, steps) | One spinagram diagram per board, ids suffixed with the board name | Maps naturally onto "one slide per diagram" in PowerPoint | n |
| Markdown / rich labels (`\|md …\|`, PlantUML creole) | Converted to plain text; bold/italic markup removed; line breaks kept | spinagram text is plain with wrapping | n |

**Open questions:** none - all resolved or logged above (required before the spec is confirmed). Rows marked `n` are agent defaults the user did not discuss (see `context.md`).

---

## User Stories

### P1: Convert a D2 file to a spinagram Python spec ⭐ MVP

**User Story**: As an engineer migrating from D2, I want `spinagram import arch.d2 -o arch.py` so that I get an editable spinagram Python spec of my diagram.

**Why P1**: D2 is the closest tool to spinagram (same icon sheet, containers, directions); it is the cheapest, highest-fidelity migration path.

**Acceptance Criteria**:

1. WHEN the user runs `spinagram import FILE.d2 -o OUT.py` THEN the system SHALL write a Python file that defines `diagram` and renders without error via `spinagram render OUT.py`.  <!-- IMP-01 -->
2. WHEN a D2 shape is not a container THEN the system SHALL emit one spinagram node whose title is the D2 label.  <!-- IMP-02 -->
3. WHEN a D2 shape contains other shapes THEN the system SHALL emit a spinagram group containing the converted children in source order.  <!-- IMP-03 -->
4. WHEN a D2 connection uses `->`, `<-`, `<->` or `--` THEN the system SHALL emit an edge with arrow `end`, `end` (endpoints swapped), `both` or `none` respectively, carrying the connection label.  <!-- IMP-04 -->
5. WHEN the D2 diagram sets `direction: right|down|left|up` THEN the system SHALL set the spinagram layout direction to `right` for right/left and `down` for down/up.  <!-- IMP-05 -->
6. WHEN a D2 shape's icon URL is a path on `icons.terrastruct.com` THEN the system SHALL set the node icon to the matching `terrastruct:` pack name.  <!-- IMP-06 -->
7. WHEN a D2 connection has `style.stroke-dash` greater than 0 THEN the system SHALL mark the edge `dashed`.  <!-- IMP-07 -->
8. IF bun and node are both missing THEN the system SHALL exit with status 1 and print a message naming bun and node as requirements for D2 import.  <!-- IMP-08 -->
9. IF the D2 source fails to compile THEN the system SHALL exit with status 1 and print the D2 compiler error with its line number.  <!-- IMP-09 -->

**Independent Test**: Import a fixture with a container, an icon URL, a dashed labelled edge and `direction: right`; render the generated `.py` and compare the model (nodes, groups, edges, icon names, direction) to the expected values.

---

### P1: Convert a PlantUML component, deployment or C4 diagram ⭐ MVP

**User Story**: As an engineer migrating from PlantUML, I want `spinagram import arch.puml -o arch.py` so that my component, deployment and C4 diagrams become spinagram specs.

**Why P1**: PlantUML is the most widely used diagrams-as-code tool for architecture; C4-PlantUML is the common enterprise case.

**Acceptance Criteria**:

1. WHEN a PlantUML element is declared (`component`, `node`, `database`, `actor`, `rectangle`, `cloud`, `queue`, `storage`, `artifact`, `interface`, `usecase`, `package`, `frame`, `folder`) THEN the system SHALL emit one node whose id is the `as` alias (or the slugged label without an alias) and whose title is the label.  <!-- IMP-10 -->
2. WHEN an element declares a `{ … }` block THEN the system SHALL emit a group containing the elements declared inside it.  <!-- IMP-11 -->
3. WHEN a relation is declared with `-->`, `->`, `..>`, `<--`, `<-->` or `--` (any length, with optional direction hints such as `-up->`) THEN the system SHALL emit an edge with the matching arrow ends, `dashed` for dotted forms, and the text after `:` as its label.  <!-- IMP-12 -->
4. WHEN an element carries a stereotype (`<<FastAPI>>`) THEN the system SHALL put the stereotype text in the node's body text.  <!-- IMP-13 -->
5. WHERE Java and the PlantUML jar are available the system SHALL parse the `--preproc` output so that `!include`, `!define` and C4-PlantUML macros (`Person`, `Container`, `ContainerDb`, `System_Boundary`, `Rel`) are converted.  <!-- IMP-14 -->
6. IF Java is unavailable AND the file contains `!include` THEN the system SHALL exit with status 1 and print a message that Java is required for included files.  <!-- IMP-15 -->
7. WHEN the file says `left to right direction` THEN the system SHALL set the layout direction to `right`, otherwise to `down`.  <!-- IMP-16 -->
8. IF the file is a sequence, class, activity, state, timing, Gantt or mind-map diagram THEN the system SHALL exit with status 1 and print the detected diagram type and the list of supported types.  <!-- IMP-17 -->

**Independent Test**: Import the component fixture without Java and the C4 fixture with Java; assert nodes, groups, edges, labels and stereotypes against expected models.

---

### P1: Render D2 and PlantUML files directly ⭐ MVP

**User Story**: As a user trying spinagram, I want `spinagram render arch.d2 -f pptx` to work so that I can see my existing diagrams in spinagram's outputs before converting anything.

**Why P1**: Zero-commitment evaluation is the strongest migration hook; it reuses the same converter.

**Acceptance Criteria**:

1. WHEN `render`, `check`, `facts`, `layout` or `serve` receives a `.d2` or `.puml` path, or a folder containing them, THEN the system SHALL load it through the importer exactly as `import` does.  <!-- IMP-18 -->
2. WHEN `spinagram.load(path)` is called on a `.d2` or `.puml` file THEN the system SHALL return the converted `Diagram` objects.  <!-- IMP-19 -->
3. WHILE `spinagram serve` watches a `.d2` or `.puml` file the system SHALL re-render it on save.  <!-- IMP-20 -->

**Independent Test**: `spinagram render fixture.d2 fixture.puml -f svg,pptx -o out/` produces one SVG per diagram and one slide per diagram.

---

### P1: Native shapes ⭐ MVP

**User Story**: As a migrating user, I want cylinders, people, clouds, circles, hexagons and documents preserved so that converted diagrams keep their meaning.

**Why P1**: Chosen by the user (2026-10-12): approximating shapes as boxes loses the meaning migrated diagrams carry. Native shapes also benefit hand-written spinagram diagrams.

**Acceptance Criteria**:

1. WHEN a source shape is a cylinder, circle or oval, hexagon, cloud, person or document THEN the system SHALL emit a node of the matching spinagram kind (`cylinder`, `ellipse`, `hexagon`, `cloud`, `person`, `document`).  <!-- IMP-27 -->
2. WHEN a node of a new kind is rendered to SVG THEN the system SHALL draw that geometry with the node's style fill and stroke, and place the title and body inside the shape's text area.  <!-- IMP-37 -->
3. WHEN a node of a new kind is rendered to PowerPoint THEN the system SHALL emit the matching preset geometry (`can`, `ellipse`, `hexagon`, `cloud`, a person glyph, `flowChartDocument`) with the text inside the shape.  <!-- IMP-38 -->
4. WHEN a node of a new kind is rendered to Figma or FigJam THEN the system SHALL draw that geometry as an editable vector with the text inside.  <!-- IMP-39 -->
5. The Python and YAML front-ends SHALL accept the new kinds (`d.add("cylinder", ...)`, `kind: cylinder`), and Python SHALL offer `d.cylinder()`, `d.ellipse()`, `d.hexagon()`, `d.cloud()`, `d.person()`, `d.document()`.  <!-- IMP-40 -->
6. IF a source shape is outside the supported list (queue, step, callout, stored_data, parallelogram…) THEN the system SHALL emit a box and a warning naming the shape.  <!-- IMP-41 -->

**Independent Test**: Render a fixture with one node of each new kind to SVG, PPTX and Figma JS; assert the SVG path geometry, the PPTX `prstGeom` values and the Figma vector calls, and that `spinagram check` reports no text overflow.

---

### P2: Colour overrides

**User Story**: As a migrating user, I want per-element fill and stroke colours preserved where they carry meaning.

**Why P2**: Themes own colour in spinagram; overrides are useful but not required to migrate.

**Acceptance Criteria**:

1. WHEN a source element sets a fill or stroke colour THEN the system SHALL set the node's fill and stroke overrides to those colours.  <!-- IMP-28 -->

**Independent Test**: Import a fixture with `style.fill`; assert the rendered shape's fill.

---

### P1: Conversion report ⭐ MVP

**User Story**: As a migrating engineer, I want to know what did not convert so that I can fix it by hand instead of discovering losses later.

**Why P1**: Silent loss destroys trust in a migration tool.

**Acceptance Criteria**:

1. WHEN a source construct is approximated or ignored (unsupported shape, colour, tooltip, link, note, sprite, markdown) THEN the system SHALL print one warning per construct with the source file, line and construct name.  <!-- IMP-21 -->
2. WHERE `--strict` is given the system SHALL exit with status 1 if any warning was emitted, after printing all warnings.  <!-- IMP-22 -->
3. WHEN the import finishes THEN the system SHALL print a summary line with counts of nodes, groups, edges and warnings.  <!-- IMP-23 -->
4. The generated Python file SHALL start with a comment naming the source file and listing every warning.  <!-- IMP-24 -->

**Independent Test**: Import a fixture with a tooltip, a fill colour and a `queue` shape; assert three warnings with lines and a non-zero exit under `--strict`.

---

### P2: Emit YAML instead of Python

**User Story**: As a team that keeps specs as data, I want `spinagram import arch.d2 --to yaml` so that I get a YAML spec.

**Why P2**: Python is the primary target; YAML suits generated pipelines.

**Acceptance Criteria**:

1. WHEN `--to yaml` is given THEN the system SHALL write a YAML spec with `groups`, `nodes` and `edges` (no frozen coordinates) that loads to the same model as the Python output.  <!-- IMP-25 -->

**Independent Test**: Import one fixture to both formats and assert both load to equal node, group and edge sets.

---

### P2: Keep the source tool's layout

**User Story**: As a user with carefully arranged diagrams, I want `--keep-layout` so that positions from D2 or PlantUML are preserved.

**Why P2**: Re-layout is the better default, but some diagrams encode meaning in placement.

**Acceptance Criteria**:

1. WHERE `--keep-layout` is given the system SHALL place nodes and groups at the source tool's computed positions, scaled uniformly to fit the layout area while keeping the aspect ratio.  <!-- IMP-26 -->

**Independent Test**: Import with `--keep-layout`; assert relative order of node centres on both axes matches the source layout.

---

### P3: More diagram families

**User Story**: As a PlantUML user, I want activity and use-case flows and D2 grid layouts converted so that more of my corpus migrates.

**Why P3**: Lower frequency in architecture corpora; activity diagrams need branch/merge semantics.

**Acceptance Criteria**:

1. WHEN a PlantUML activity diagram (new syntax) is imported THEN the system SHALL emit boxes for actions, diamonds for `if`/`switch`, and edges labelled with branch conditions.  <!-- IMP-29 -->
2. WHEN a D2 container sets `grid-columns` THEN the system SHALL set the group's `columns` hint to that value.  <!-- IMP-30 -->

---

## Edge Cases

- IF two source elements slug to the same id THEN the system SHALL suffix the later one with `-2`, `-3` … and keep both.  <!-- IMP-31 -->
- IF a label or id is a Python keyword or starts with a digit THEN the system SHALL generate a valid variable name (`class_`, `n_3tier`).  <!-- IMP-32 -->
- IF an edge references an element that was not declared THEN the system SHALL create that element as a node (PlantUML semantics) and warn.  <!-- IMP-33 -->
- WHEN the source file is empty or contains only directives THEN the system SHALL exit with status 1 and print "no elements found in FILE".  <!-- IMP-34 -->
- IF the D2.js or PlantUML subprocess runs longer than 60 seconds THEN the system SHALL stop it and exit with status 1 naming the timeout.  <!-- IMP-35 -->
- IF a remote icon URL is not on `icons.terrastruct.com` THEN the system SHALL drop the icon and warn with the URL (no network fetch in P1).  <!-- IMP-36 -->

---

## Implicit-Requirement Dimensions

| Dimension | Coverage |
| --------- | -------- |
| Input validation & bounds | IMP-09, IMP-17, IMP-34 (invalid source, unsupported family, empty file) |
| Failure / partial-failure states | IMP-21/22 (partial conversion reported, `--strict`); output file written only after a successful conversion |
| Idempotency / retry / duplicate handling | Importing the same file twice produces byte-identical output (deterministic id and ordering); IMP-31 for duplicate ids |
| Auth boundaries & rate limits | N/A because import is a local CLI with no auth surface |
| Concurrency / ordering | Toolchain installs reuse the ELK install lock pattern so parallel imports do not corrupt the cache |
| Data lifecycle / expiry | Pinned D2.js and jar versions live in the cache until the pinned version changes |
| Observability | IMP-23 summary line; warnings carry file and line |
| External-dependency failure | IMP-08, IMP-15, IMP-35 (missing runtime, missing Java, timeout); offline mode refuses downloads with a clear message |
| State-transition integrity | N/A because conversion is a stateless pure function of the source file |

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| IMP-01 | P1: D2 → Python | Design | Pending |
| IMP-02 | P1: D2 → Python | Design | Pending |
| IMP-03 | P1: D2 → Python | Design | Pending |
| IMP-04 | P1: D2 → Python | Design | Pending |
| IMP-05 | P1: D2 → Python | Design | Pending |
| IMP-06 | P1: D2 → Python | Design | Pending |
| IMP-07 | P1: D2 → Python | Design | Pending |
| IMP-08 | P1: D2 → Python | Design | Pending |
| IMP-09 | P1: D2 → Python | Design | Pending |
| IMP-10 | P1: PlantUML | Design | Pending |
| IMP-11 | P1: PlantUML | Design | Pending |
| IMP-12 | P1: PlantUML | Design | Pending |
| IMP-13 | P1: PlantUML | Design | Pending |
| IMP-14 | P1: PlantUML | Design | Pending |
| IMP-15 | P1: PlantUML | Design | Pending |
| IMP-16 | P1: PlantUML | Design | Pending |
| IMP-17 | P1: PlantUML | Design | Pending |
| IMP-18 | P1: Render directly | Design | Pending |
| IMP-19 | P1: Render directly | Design | Pending |
| IMP-20 | P1: Render directly | Design | Pending |
| IMP-21 | P1: Report | Design | Pending |
| IMP-22 | P1: Report | Design | Pending |
| IMP-23 | P1: Report | Design | Pending |
| IMP-24 | P1: Report | Design | Pending |
| IMP-25 | P2: YAML output | - | Pending |
| IMP-26 | P2: Keep layout | - | Pending |
| IMP-27 | P1: Native shapes | Design | Pending |
| IMP-28 | P2: Colour overrides | - | Pending |
| IMP-29 | P3: Activity diagrams | - | Pending |
| IMP-30 | P3: D2 grids | - | Pending |
| IMP-31 | Edge cases | Design | Pending |
| IMP-32 | Edge cases | Design | Pending |
| IMP-33 | Edge cases | Design | Pending |
| IMP-34 | Edge cases | Design | Pending |
| IMP-35 | Edge cases | Design | Pending |
| IMP-36 | Edge cases | Design | Pending |
| IMP-37 | P1: Native shapes | Design | Pending |
| IMP-38 | P1: Native shapes | Design | Pending |
| IMP-39 | P1: Native shapes | Design | Pending |
| IMP-40 | P1: Native shapes | Design | Pending |
| IMP-41 | P1: Native shapes | Design | Pending |

**ID format:** `IMP-NN`

**Coverage:** 41 total, 0 mapped to tasks, 41 unmapped ⚠️ (tasks not yet created)

---

## Success Criteria

- [ ] The migration corpus (at least 5 D2 and 5 PlantUML/C4 files covering every P1 construct) converts with zero errors, and every source element and connection is present in the output model.
- [ ] Generated Python files pass `ruff check` and render with `spinagram render` unchanged.
- [ ] Importing a file twice produces byte-identical output.

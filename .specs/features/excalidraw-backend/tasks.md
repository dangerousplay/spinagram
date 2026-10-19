# Excalidraw backend — Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: inline (one new backend module following `backends/svg.py` / `backends/figma.py`; no new pattern)
**Status**: In Progress

---

## Test Coverage Matrix

> Generated from codebase and spec. Guidelines found: `pyproject.toml` (pytest, ruff; no coverage threshold), `tests/test_engine.py` (backend tests build scenes from `Diagram`/`build_scene` and assert on output). Strong defaults applied.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
|---|---|---|---|---|
| `spinagram.backends.excalidraw` (scene → document) | unit | 1:1 to EXC-02..17 + every listed edge case | `tests/test_excalidraw.py` | `uv run --all-extras pytest -q tests/test_excalidraw.py` |
| Backend registry (`backends/__init__.py`, entry point) | unit | EXC-01: `available()` lists it, `render -f excalidraw` writes files | `tests/test_excalidraw.py` | same |
| Skill docs (`SKILL.md`) | none | build gate only | - | build gate |

## Gate Check Commands

| Gate Level | When to Use | Command |
|---|---|---|
| Quick | Tasks with unit tests | `uv run --all-extras pytest -q tests/test_excalidraw.py` |
| Build | Phase end, docs | `uv run ruff check src tests examples && uv run --all-extras pytest -q` |

---

## Execution Plan

### Phase 1: Backend

```
T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8
```

### Phase 2: Verifier fixes (validation.md, iteration 1)

```
T9 → T10 → T11 → T12
```

### Phase 3: Verifier fixes (validation.md, iteration 2)

```
T13 → T14
```

---

## Task Breakdown

### T1: Document skeleton, frame and shapes [x]

**What**: `to_excalidraw(scene) -> dict` with the top-level keys, the frame, rectangles/diamonds/pills (roundness, colours, transparent paints, dashes, opacity), deterministic ids/seeds, item order; `ExcalidrawBackend.render` writes `<slug>.excalidraw`.
**Where**: `src/spinagram/backends/excalidraw.py`
**Depends on**: None
**Reuses**: `backends/svg.py` (`SvgBackend.render` file loop)
**Requirement**: EXC-02, EXC-03, EXC-04, EXC-14, EXC-16, EXC-17

**Done when**:

- [x] Tests: top-level keys; frame first at 0,0 with scene size and `frameId` on the rest; rect/pill/diamond/radius mapping; transparent fill/stroke edge case; dashed/dotted; opacity; unique ids; byte-identical re-render; empty scene → only the frame
- [x] Quick gate passes

**Tests**: unit
**Gate**: quick
**Commit**: `feat(excalidraw): write scenes as excalidraw documents with native shapes`

---

### T2: Symbol parts as polygons [x]

**What**: Shapes with `parts` emit one `line` per part (`polygon: true`, Béziers flattened to 8 segments), grouped with the shape.
**Where**: `src/spinagram/backends/excalidraw.py`
**Depends on**: T1
**Reuses**: `spinagram.shapes.parse`
**Requirement**: EXC-05

**Done when**:

- [x] Test: a cylinder's lines' absolute points lie within 1 px of the flattened outline; all share the shape's group id

**Tests**: unit
**Gate**: quick
**Commit**: `feat(excalidraw): draw symbol shapes as grouped polygons`

---

### T3: Labels, free text and fonts [x]

**What**: One-block labels bind into the shape; multi-block labels become grouped free texts at `Label.place()`; `Text` items with anchor → `textAlign`; font family 2 / 3 (monospace), size, line height.
**Where**: `src/spinagram/backends/excalidraw.py`
**Depends on**: T2
**Requirement**: EXC-06, EXC-07, EXC-13 (Text), EXC-15

**Done when**:

- [x] Tests: bound text (`containerId` + `boundElements`), multi-block positions/sizes/colours, Text anchors start/middle/end, monospace → 3, size

**Tests**: unit
**Gate**: quick
**Commit**: `feat(excalidraw): add shape labels and text`

---

### T4: Arrows, bindings and edge labels [x]

**What**: Connectors → arrows with relative points, curve roundness, arrowheads, dash; bindings with `fixedPoint` and shape `boundElements`; label pill + text grouped with the arrow.
**Where**: `src/spinagram/backends/excalidraw.py`
**Depends on**: T3
**Requirement**: EXC-08, EXC-09, EXC-10

**Done when**:

- [x] Tests: points round-trip; every marker mapping; arrow none/both ends; binding fixed point; unbound end → `null`; shape lists the arrow; label grouped

**Tests**: unit
**Gate**: quick
**Commit**: `feat(excalidraw): add bound arrows with labels`

---

### T5: Icons and images [x]

**What**: Icons and `Image` items → `image` elements; `files` keyed by SHA-1 of the bytes with `dataURL` and `mimeType`; duplicates stored once; missing file raises like SVG.
**Where**: `src/spinagram/backends/excalidraw.py`
**Depends on**: T4
**Requirement**: EXC-11, EXC-12

**Done when**:

- [x] Tests: image box, dataURL decodes to the bytes, mime type, two icons one file, missing file → `FileNotFoundError`

**Tests**: unit
**Gate**: quick
**Commit**: `feat(excalidraw): embed icons and images`

---

### T6: Lines and tables [x]

**What**: `Line` → `line` element; `TableGrid` → grouped cell rectangles + texts.
**Where**: `src/spinagram/backends/excalidraw.py`
**Depends on**: T5
**Requirement**: EXC-13

**Done when**:

- [x] Tests: line endpoints; table cell count, positions, header fill, one group

**Tests**: unit
**Gate**: quick
**Commit**: `feat(excalidraw): add lines and tables`

---

### T7: Register the backend [x]

**What**: `excalidraw` in `_BUILTIN` and the `spinagram.backends` entry point; `render -f excalidraw` over `examples/` writes parseable files.
**Where**: `src/spinagram/backends/__init__.py`
**Depends on**: T6
**Requirement**: EXC-01

**Done when**:

- [x] Tests: `available()` has it; CLI render of every example → one `.excalidraw` per diagram that parses
- [x] Build gate passes

**Tests**: unit
**Gate**: build
**Commit**: `feat(excalidraw): register the excalidraw backend`

---

### T8: Document the output in the skill [x]

**What**: `## Outputs` gains an Excalidraw item.
**Where**: `src/spinagram/agent_skills/spinagram/SKILL.md`
**Depends on**: T7
**Requirement**: EXC-18

**Done when**:

- [x] Build gate passes

**Tests**: none
**Gate**: build
**Commit**: `docs(skills): describe the excalidraw output`

---

### T9: Multi-subpath parts and polygon closing (gaps 1, 2) [x]

**What**: Tests with `predefined` and `flow_final` (two open subpaths in one part) and `document`/`decision` (closed subpaths that do not end on their start) kill M16 and M08.
**Where**: `tests/test_excalidraw.py`
**Depends on**: None (Phase 1 done)
**Requirement**: EXC-05

**Done when**:

- [x] Dropping later subpaths or the closing point fails a test

**Tests**: unit
**Gate**: quick
**Commit**: `test(excalidraw): cover multi-subpath parts and polygon closing`

---

### T10: Pin payload fields (gaps 3, 4, 6, 7) [x]

**What**: Determinism across interpreter runs (`PYTHONHASHSEED` 1 vs 2); `version`/`updated` 1; binding `focus` 0, `gap` 1, `mode` "orbit"; opacity rounding (0.333 → 33, 0.336 → 34); file `created` 0.
**Where**: `tests/test_excalidraw.py`
**Depends on**: T9
**Requirement**: EXC-09, EXC-11, EXC-16

**Done when**:

- [x] Salted `hash()` seeds, `int()` opacity and each dropped field fail a test

**Tests**: unit
**Gate**: quick
**Commit**: `test(excalidraw): pin binding, file and determinism fields`

---

### T11: Centred multi-block labels (gap 5) [x]

**What**: EXC-07 states the reference point (Excalidraw `x` is the left edge: centre x − width / 2); test a centred multi-block label.
**Where**: `tests/test_excalidraw.py`
**Depends on**: T10
**Requirement**: EXC-07

**Done when**:

- [x] Using the centre x as `x` fails a test; `validate_spec.py` clean

**Tests**: unit
**Gate**: quick
**Commit**: `test(excalidraw): place centred multi-block labels by their left edge`

---

### T12: Entry point and help (gap 8) [x]

**What**: The installed `spinagram.backends` entry points include `excalidraw`; `render --help` lists it.
**Where**: `tests/test_excalidraw.py`
**Depends on**: T11
**Requirement**: EXC-01

**Done when**:

- [x] Deleting the entry point or the built-in fails a test
- [x] Build gate passes

**Tests**: unit
**Gate**: build
**Commit**: `test(excalidraw): require the backend entry point and help listing`

---

### T13: Bindings on a composed shape (gaps 1, 2) [x]

**What**: A shape with a one-block label and an icon: the arrow binds to the shape's own element and the shape keeps its bound text next to the arrow in `boundElements` (kills N13, N05).
**Where**: `tests/test_excalidraw.py`
**Depends on**: None (Phase 2 done)
**Requirement**: EXC-06, EXC-09

**Done when**:

- [ ] Binding to the shape's last element, or overwriting `boundElements`, fails a test

**Tests**: unit
**Gate**: quick
**Commit**: `test(excalidraw): bind arrows to labelled shapes with icons`

---

### T14: Swatch layer and monospace fallback (gaps 3, 4) [ ]

**What**: `swatch` shapes draw in the front layer; a family whose fallback is `monospace` maps to font 3 (kills N04, N01).
**Where**: `tests/test_excalidraw.py`
**Depends on**: T13
**Requirement**: EXC-15, EXC-17

**Done when**:

- [ ] Dropping `swatch` from the front layer, or reading only the family name, fails a test
- [ ] Build gate passes

**Tests**: unit
**Gate**: build
**Commit**: `test(excalidraw): cover swatch layering and monospace fallbacks`

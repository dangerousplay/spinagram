# CSS-like Styling Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec - confirmed by the user's "proceed" (2026-10-12). Guidelines found: none (no AGENTS.md / CONTRIBUTING.md) - strong defaults applied; style and location sampled from `tests/test_autolayout.py`, `tests/test_engine.py`, `tests/test_pptx_svg.py`.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Library logic (layout engines, builders, CSS cascade, model) | unit | All branches; 1:1 to MVP spec ACs; every listed edge case in MVP scope | `tests/test_*.py` | `uv run --all-extras pytest -q` |
| Backends (SVG, PPTX, Figma JS) | unit | Rendered output asserted per new kind/property (SVG attributes, DrawingML XML, Figma JS calls) | `tests/test_*.py` | `uv run pytest -q` |
| Examples / docs | none | build gate (render + ruff) | `examples/`, `docs/` | build gate |
| Dependency / packaging config | none | build gate only | `pyproject.toml`, `uv.lock` | build gate |

## Gate Check Commands

> Generated from `pyproject.toml` and `.github/workflows/ci.yml`.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | After tasks with unit tests only | `uv run --all-extras pytest -q` |
| Full | Same as quick (no integration suite) | `uv run --all-extras pytest -q` |
| Build | After phase completion | `uv run --all-extras ruff check src tests examples && uv run --all-extras pytest -q` |

---

**Design**: `.specs/features/css-styling/design.md`
**Status**: In Progress

**MVP scope**: CSS-01..07, CSS-08 (fill, stroke, stroke-width, stroke-dasharray, border-radius, opacity, box-shadow), CSS-09 (color, font-size, font-weight, font-style), CSS-10 (stroke, stroke-width, stroke-dasharray, opacity, marker-start/end), CSS-12..22, CSS-27, CSS-29, CSS-30. Deferred: CSS-11, CSS-23..26, CSS-28 and the remaining CSS-08..10 properties.

## Execution Plan

### Phase 1: Engine

```
T1 → T2 → T3 → T4
```

### Phase 2: Rendering

```
T5 → T6 → T7 → T8 → T9
```

## Task Breakdown

### T1: Add tinycss2 dependency

**What**: `tinycss2` in base dependencies and lockfile.
**Where**: `pyproject.toml`
**Depends on**: None
**Reuses**: none
**Requirement**: CSS-01

**Done when**:
- [x] `uv lock` updated; import works
- [x] Gate passes

**Tests**: none
**Gate**: build
**Status**: ✅ Complete


### T2: Stylesheet parser and selectors

**What**: `css.parse`, selector compiler, specificity, pseudo-elements, error collection with line/column.
**Where**: `src/spinagram/css.py`
**Depends on**: T1
**Reuses**: tinycss2
**Requirement**: CSS-02, CSS-21

**Done when**:
- [x] Every CSS-02 selector form matches/doesn't match as specified; syntax errors reported and skipped
- [x] Gate passes

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete


### T3: Cascade and computed styles

**What**: Element tree from a diagram, cascade (importance, specificity, order, inline), inheritance, `var()` and tokens, property parsing and validation.
**Where**: `src/spinagram/css.py`
**Depends on**: T2
**Reuses**: `Theme.color`
**Requirement**: CSS-01, CSS-03..07, CSS-14..16, CSS-22, CSS-30

**Done when**:
- [x] Competing-rules table resolved as specified; tokens across two themes; unknown property and negative values warned
- [x] Gate passes

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete


### T4: Classes and stylesheets in the model

**What**: `cls`/`css` fields, `class_=` keyword, `Diagram.stylesheet()`, `Diagram(css=)`, `style=` adds a class.
**Where**: `src/spinagram/model.py`
**Depends on**: T3
**Reuses**: `Diagram.add`, `edge`, `group`
**Requirement**: CSS-17, CSS-18, CSS-20

**Done when**:
- [x] Classes and sheets reach the cascade from Python
- [x] Build gate passes

**Tests**: unit
**Gate**: build
**Status**: ✅ Complete


### T5: YAML and theme stylesheets

**What**: YAML `class`, `css`, `stylesheets`; `_defaults.yaml` stylesheets; theme `theme.css`.
**Where**: `src/spinagram/yaml_io.py`
**Depends on**: None (runs after Phase 1 completes)
**Reuses**: `from_dict`, `_dir_defaults`
**Requirement**: CSS-19

**Done when**:
- [x] Same styled diagram in YAML and Python resolves identical computed styles
- [x] Gate passes

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete


### T6: Computed styles in the scene

**What**: `css.prepare` in `api.scenes`; build_scene applies fill/stroke/width/dash/radius/opacity/shadow/fonts/markers; Shape/Connector fields.
**Where**: `src/spinagram/layout.py`
**Depends on**: T5
**Reuses**: `_Builder`
**Requirement**: CSS-08, CSS-09, CSS-10, CSS-27, CSS-29

**Done when**:
- [x] Scene values match computed styles; examples render byte-identically without CSS
- [x] Gate passes

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete


### T7: SVG style properties

**What**: dash arrays, drop-shadow filter, marker types, italic text.
**Where**: `src/spinagram/backends/svg.py`
**Depends on**: T6
**Reuses**: `_Svg`
**Requirement**: CSS-12

**Done when**:
- [x] SVG attributes asserted per property
- [x] Gate passes

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete


### T8: PowerPoint style properties

**What**: prstDash mapping, outer shadow, arrowhead types, warnings for inexpressible values.
**Where**: `src/spinagram/backends/pptx.py`
**Depends on**: T7
**Reuses**: `_line`, `_arrows`
**Requirement**: CSS-12, CSS-13

**Done when**:
- [x] DrawingML asserted per property; one warning per inexpressible value
- [x] Gate passes

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete


### T9: Figma style properties

**What**: dashPattern, DROP_SHADOW effects, stroke caps per marker.
**Where**: `src/spinagram/backends/figma.py`
**Depends on**: T8
**Reuses**: `rect`/`vec` options
**Requirement**: CSS-12

**Done when**:
- [ ] Figma JS options asserted; script runs on the mock API
- [ ] Build gate passes

**Tests**: unit
**Gate**: build

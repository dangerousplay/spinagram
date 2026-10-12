# Behavior Diagrams Tasks

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

**Design**: `.specs/features/behavior-diagrams/design.md`
**Status**: Done

**MVP scope**: BHV-01..26, BHV-31..35. Deferred: BHV-27 (YAML regions), BHV-28..30 (P2/P3).
**Depends on feature**: `layered-layout` (all tasks).

## Execution Plan

### Phase 1: Shapes

```
T1 → T2 → T3 → T4 → T5 → T6
```

### Phase 2: Builders

```
T7 → T8 → T9 → T10 → T11
```

## Task Breakdown

### T1: Shape geometry library

**What**: `shapes.py` with geometry parts, text box, fixed sizes and PPTX preset per behavior kind.
**Where**: `src/spinagram/shapes.py`
**Depends on**: None
**Reuses**: none
**Requirement**: BHV-01, BHV-02, BHV-05

**Done when**:
- [x] Every BHV-01 kind has parts, a text box inside its bounds, and a preset or freeform plan
- [x] Gate passes

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete


### T2: Per-kind sizing

**What**: `auto_size` uses fixed sizes for pseudostates and text insets for text-bearing symbols.
**Where**: `src/spinagram/autolayout/sizing.py`
**Depends on**: T1
**Reuses**: `auto_size`
**Requirement**: BHV-05

**Done when**:
- [x] Untitled pseudostates get theme symbol sizes; titled symbols fit their text inside the text box
- [x] Gate passes

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete


### T3: Scene symbols

**What**: `_Builder.symbol` creates Shapes with `kind`, `parts` and label box for geometry kinds; anchors on circles use side midpoints.
**Where**: `src/spinagram/layout.py`
**Depends on**: T2
**Reuses**: `_Builder.box`, `block`
**Requirement**: BHV-02

**Done when**:
- [x] Scene shapes carry parts and label boxes; `check` sees no overflow for default-sized symbols
- [x] Gate passes

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete


### T4: SVG symbols

**What**: SVG backend draws geometry parts with paint rules.
**Where**: `src/spinagram/backends/svg.py`
**Depends on**: T3
**Reuses**: `_Svg.shape`
**Requirement**: BHV-02

**Done when**:
- [x] Each kind renders its path(s) with the specified paint
- [x] Gate passes

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete


### T5: PowerPoint symbols

**What**: PPTX backend uses preset geometry, grouped natives for multi-part symbols, freeform otherwise; text inside.
**Where**: `src/spinagram/backends/pptx.py`
**Depends on**: T4
**Reuses**: `_Slide.shape`
**Requirement**: BHV-03

**Done when**:
- [x] `prstGeom` per kind asserted; `final` is a group of two ovals; text frames present for titled symbols
- [x] Gate passes

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete


### T6: Figma symbols

**What**: Figma backend converts geometry parts to vector networks with text inside.
**Where**: `src/spinagram/backends/figma.py`
**Depends on**: T5
**Reuses**: `vec` helper
**Requirement**: BHV-04

**Done when**:
- [x] Every kind emits `vec(...)` networks; generated script runs on the mock Plugin API
- [x] Build gate passes

**Tests**: unit
**Gate**: build
**Status**: ✅ Complete


### T7: Flowchart builder and edge helpers

**What**: `Flowchart` class, flow verbs, `Node.yes/no/on`, layered default; final/initial edge validation.
**Where**: `src/spinagram/behavior.py`
**Depends on**: None (runs after Phase 1 completes)
**Reuses**: `Diagram`
**Requirement**: BHV-06, BHV-07, BHV-08, BHV-31, BHV-32

**Done when**:
- [x] Verbs create the right kinds; Yes/No labels; layered layout; ValueErrors for final/initial misuse
- [x] Gate passes

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete


### T8: State machine builder

**What**: `StateMachine` verbs: state (entry/do/exit), on, initial/final, composite, region, choice, history, self-transitions.
**Where**: `src/spinagram/behavior.py`
**Depends on**: T7
**Reuses**: flow verbs scope
**Requirement**: BHV-10..15, BHV-17

**Done when**:
- [x] Order lifecycle fixture builds with the expected kinds, labels and containment
- [x] Gate passes

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete


### T9: Activity builder

**What**: `Activity` verbs: action, decision, merge, start/end/flow_end, send/receive/object, parallel/branch, sequence, lanes.
**Where**: `src/spinagram/behavior.py`
**Depends on**: T8
**Reuses**: collector stack
**Requirement**: BHV-18..22, BHV-34

**Done when**:
- [x] Fulfilment fixture: lane membership, fork/join wiring, implicit sequence edges, empty lane drawn
- [x] Gate passes

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete


### T10: Typed regions in any diagram

**What**: `Diagram.flowchart/state_machine/activity` context managers; standalone equals embedded; duplicate region ids rejected.
**Where**: `src/spinagram/model.py`
**Depends on**: T9
**Reuses**: `Diagram.group`, behavior verbs
**Requirement**: BHV-23..26, BHV-35

**Done when**:
- [x] Mixed diagram renders both layouts and a crossing edge; standalone/embedded equivalence; duplicate id error
- [x] Gate passes

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete


### T11: Behavior checks

**What**: `check` reports decisions with < 2 branches, forks with 1 branch, regions without initial state.
**Where**: `src/spinagram/qa.py`
**Depends on**: T10
**Reuses**: `Issue`
**Requirement**: BHV-09, BHV-16, BHV-33

**Done when**:
- [x] Exact messages from the spec asserted
- [x] Build gate passes

**Tests**: unit
**Gate**: build
**Status**: ✅ Complete


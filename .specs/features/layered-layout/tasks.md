# Layered Layout Tasks

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

**Design**: `.specs/features/layered-layout/design.md`
**Status**: In Progress

**MVP scope**: LAY-01..17, LAY-20..22. Deferred: LAY-18, LAY-19 (P2).

## Execution Plan

### Phase 1: Engine

```
T1 → T2 → T3 → T4 → T5 → T6
```

## Task Breakdown

### T1: Layout graph carries self-loops and group layout hints

**What**: `LGraph.loops` (self-edges) and group hints `lanes`, `engine`, `direction` passed from the model to engines.
**Where**: `src/spinagram/autolayout/__init__.py`
**Depends on**: None
**Reuses**: `build_graph`
**Requirement**: LAY-09, LAY-16

**Done when**:
- [x] Self-edges appear in `graph.loops`, not in `graph.edges`; group hints include `lanes`/`engine`/`direction` when set
- [x] Gate passes

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete


### T2: Layered engine for flat graphs

**What**: `LayeredEngine` with cycle removal, ranking, dummies, barycentre ordering, isotonic coordinates, orthogonal dummy-channel routes, both directions; registered as `layered`.
**Where**: `src/spinagram/autolayout/engines/layered.py`
**Depends on**: T1
**Reuses**: engine protocol, `engines/__init__.py` registry
**Requirement**: LAY-01..07, LAY-10, LAY-11, LAY-13, LAY-21, LAY-22

**Done when**:
- [x] Rank order, gaps, no overlaps, determinism, no-edge row, cycles, axis-aligned routes, components side by side, bound warning tested
- [x] Gate passes

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete


### T3: Orthogonal obstacle router

**What**: `route(src_box, dst_box, obstacles)` grid A* router with bend penalty, plus self-loop routing helper.
**Where**: `src/spinagram/autolayout/route.py`
**Depends on**: T2
**Reuses**: none
**Requirement**: LAY-08, LAY-09, LAY-17

**Done when**:
- [x] Routes are axis-aligned, avoid every obstacle, end on the target box; loops leave and re-enter one side
- [x] Gate passes

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete


### T4: Groups and lanes in the layered engine

**What**: Recursive group levels, lane bands, back-edge and cross-block routing with the router, self-loops.
**Where**: `src/spinagram/autolayout/engines/layered.py`
**Depends on**: T3
**Reuses**: `route.py`
**Requirement**: LAY-08, LAY-09, LAY-15, LAY-16, LAY-17

**Done when**:
- [x] Containment of group members, lane bands full-span and disjoint, routes never cross node boxes
- [x] Gate passes

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete


### T5: Per-group engines in apply_layout

**What**: Groups with `engine`/`direction` hints are laid out by their own engine as blocks; crossing edges re-routed; self-loops bound as `via`.
**Where**: `src/spinagram/autolayout/__init__.py`
**Depends on**: T4
**Reuses**: `apply_layout`, `route.py`
**Requirement**: LAY-14, LAY-17

**Done when**:
- [x] A layered group inside a flex diagram lays out by rank; anchored edges untouched; crossing edge ends on both boxes
- [x] Gate passes

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete


### T6: Label placement avoids boxes

**What**: Routed edge labels placed at the first candidate on the route whose pill box intersects no node box.
**Where**: `src/spinagram/autolayout/__init__.py`
**Depends on**: T5
**Reuses**: `_label_point`
**Requirement**: LAY-12, LAY-20

**Done when**:
- [x] Label pills of the order-flow fixture intersect no node box; overflow still reported
- [x] Build gate passes

**Tests**: unit
**Gate**: build
**Status**: ✅ Complete


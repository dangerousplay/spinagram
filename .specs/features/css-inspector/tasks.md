# CSS Inspector, Live Reload and Backend Docs Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec - reused from css-styling (2026-10-12). Guidelines found: none (no AGENTS.md / CONTRIBUTING.md) - strong defaults applied; style and location sampled from `tests/test_autolayout.py`, `tests/test_engine.py`, `tests/test_pptx_svg.py`.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Library logic (layout engines, builders, CSS cascade, model) | unit | All branches; 1:1 to MVP spec ACs; every listed edge case in MVP scope | `tests/test_*.py` | `uv run --all-extras pytest -q` |
| Backends (SVG, PPTX, Figma JS) | unit | Rendered output asserted per new kind/property (SVG attributes, DrawingML XML, Figma JS calls) | `tests/test_*.py` | `uv run pytest -q` |
| Live UI server (Starlette, watcher) | unit | Endpoint payloads and watcher classification asserted | `tests/test_ui.py` | `uv run --all-extras pytest -q` |
| Web SPA (`web/`) | none | `bun run build` (tsc typecheck + vite) | `web/src/*.tsx` | `cd web && bun run build` |
| Examples / docs | none | build gate (render + ruff, docs build) | `examples/`, `docs/` | build gate |
| Dependency / packaging config | none | build gate only | `pyproject.toml`, `uv.lock` | build gate |

## Gate Check Commands

> Generated from `pyproject.toml` and `.github/workflows/ci.yml`.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | After tasks with unit tests only | `uv run --all-extras pytest -q` |
| Full | Same as quick (no integration suite) | `uv run --all-extras pytest -q` |
| Build | After phase completion | `uv run --all-extras ruff check src tests examples && uv run --all-extras pytest -q` |

---

**Spec**: `.specs/features/css-inspector/spec.md`
**Status**: In progress

## Execution Plan

### Phase 1: Engine and CLI

```
T1 → T2 → T3
T4
```

### Phase 2: Live UI

```
T5 → T6 → T7
```

### Phase 3: Docs

```
T8
```

## Task Breakdown

### T1: Cascade trace in `css.compute`

**What**: `compute(..., trace=)` records matched declarations with origin, selector, specificity, raw/resolved value and status, plus inherited values.
**Where**: `src/spinagram/css.py`
**Depends on**: None
**Reuses**: `compute`, `declared`
**Requirement**: INS-01, INS-02, INS-03, INS-17

**Done when**:
- [x] Statuses applied/overridden/invalid/unknown/inherited asserted on a competing-rules fixture; computed styles equal with and without trace
- [x] Gate passes

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete


### T2: `css.inspect` report

**What**: `inspect(d, theme)` → elements (key, type, kinds, id, classes, attrs, label), trace, sheets, warnings; `unused_selectors`; `select(d, selector)`.
**Where**: `src/spinagram/css.py`
**Depends on**: T1
**Reuses**: `tree`, `sheets_for`, `matches`
**Requirement**: INS-05, INS-08, INS-12, INS-16

**Done when**:
- [x] Report fields asserted; unused selectors only from the diagram's own sheets; selector filter
- [x] Gate passes

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete


### T3: `check --styles` CLI and pretty printer

**What**: `check --styles [--select] [--json] [--color]`; ANSI renderer with swatches and strike-through; unused selectors as info lines in `check`.
**Where**: `src/spinagram/cli.py`, `src/spinagram/inspect_fmt.py`
**Depends on**: T2
**Reuses**: `qa.check`
**Requirement**: INS-04, INS-05, INS-06, INS-07, INS-08, INS-16

**Done when**:
- [x] Plain and coloured output asserted; invalid selector exits 2; JSON parses; info lines not counted
- [x] Gate passes

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete


### T4: `fill-opacity` in every backend

**What**: Scene `Shape.fill_opacity`; SVG `fill-opacity`, PPTX fill alpha, Figma paint opacity.
**Where**: `src/spinagram/scene.py`, `src/spinagram/layout.py`, `src/spinagram/backends/*.py`
**Depends on**: None
**Reuses**: `_decorate`
**Requirement**: INS-15, INS-03

**Done when**:
- [x] Attribute/XML/JS asserted per backend; unstyled SVG unchanged
- [x] Gate passes

**Tests**: unit
**Gate**: quick
**Status**: ✅ Complete


### T5: Styles endpoint with geometry

**What**: `GET api/diagrams/<key>.styles` returns the inspect report plus scene geometry per element key.
**Where**: `src/spinagram/ui/workspace.py`, `src/spinagram/ui/server.py`
**Depends on**: None (Phase 1 complete)
**Reuses**: `Workspace.render`
**Requirement**: INS-12, INS-17

**Done when**:
- [ ] Payload keys, node box, edge polyline, group box asserted via TestClient
- [ ] Gate passes

**Tests**: unit
**Gate**: quick

### T6: Stylesheet live reload

**What**: Watcher classifies `.css` changes, maps them to diagrams via their cascade, watches external stylesheet folders and restarts when that set changes.
**Where**: `src/spinagram/ui/workspace.py`, `src/spinagram/ui/server.py`
**Depends on**: T5
**Reuses**: `apply_changes`, `watch_loop`
**Requirement**: INS-09, INS-10, INS-11, INS-18

**Done when**:
- [ ] Only diagrams using the saved sheet get events; external folder in targets; deleted sheet errors then recovers
- [ ] Gate passes

**Tests**: unit
**Gate**: quick

### T7: Inspector panel in the SPA

**What**: Inspect toggle (`i`), hover outline, click select (not on drag), side panel with classes, attrs, computed style, rules; refetch on live reload keeping selection; rebuild static bundle.
**Where**: `web/src/*.tsx`, `src/spinagram/ui/static/`
**Depends on**: T6
**Reuses**: `DiagramView`, `usePanZoom`
**Requirement**: INS-13, INS-14

**Done when**:
- [ ] `bun run build` passes; manual check in the browser
- [ ] Gate passes

**Tests**: none
**Gate**: build

### T8: Backend support docs and examples

**What**: Docs page: property × backend matrix, styling examples with rendered SVGs, `check --styles` colour output, live reload; README pointer.
**Where**: `docs/content/docs/`, `docs/public/assets/css/`, `examples/styling/`, `README.md`
**Depends on**: None (Phases 1-2 complete)
**Reuses**: `docs/content/docs/styling.mdx`
**Requirement**: DOC-01, DOC-02, DOC-03

**Done when**:
- [ ] Docs build passes; examples pass `spinagram check`
- [ ] Gate passes

**Tests**: none
**Gate**: build

# Catalog Previews Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: inline (reuses diagram-catalog patterns: `web/src/catalog.ts`, `DiagramsPage.tsx`, `ui/themes.py` previews)
**Status**: Done

---

## Test Coverage Matrix

> Same project guidelines as diagram-catalog (`pyproject.toml`, `web/package.json`); strong defaults.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Theme sample rendering (Python) | unit | PREV-04 | `tests/test_ui.py` | `uv run pytest tests/test_ui.py -q` |
| UI server API | integration | PREV-01..03 happy + error paths | `tests/test_ui.py` | `uv run pytest tests/test_ui.py -q` |
| UI pure logic (TS) | unit | PREV-06, 07, 10, section ordering | `web/src/*.test.ts` | `cd web && bun test` |
| UI components (TSX) | none | typecheck + build; browser walkthrough | - | `cd web && bun run build` |

## Gate Check Commands

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | Python unit tasks | `uv run pytest tests/test_ui.py -q` |
| Web | TS logic tasks | `cd web && bun test` |
| Full | Server integration | `uv run pytest -q` |
| Build | UI components, last task | `uv run ruff check src tests && uv run pytest -q && cd web && bun test && bun run build` |

---

## Execution Plan

### Phase 1: Previews

```
T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8 → T9
```

---

## Task Breakdown

### T1: Theme sample diagram

**What**: `theme_thumbnail(ref, active_ref)` renders a built-in sample diagram with the theme, using only node styles it defines.
**Where**: `src/spinagram/ui/themes.py`
**Depends on**: None
**Reuses**: `style_preview`, `build_scene`, `to_svg`
**Requirement**: PREV-04

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] a theme without `warning`/`alert` styles renders without them; the default theme uses all six
- [x] Gate check passes: `uv run pytest tests/test_ui.py -q`

**Tests**: unit
**Gate**: quick

---

### T2: Theme thumbnail endpoint

**What**: `GET /api/themes/{ref}/thumbnail.svg` with 404 for unknown refs and 422 for broken themes.
**Where**: `src/spinagram/ui/server.py`
**Depends on**: T1
**Reuses**: `theme_preview` handler pattern
**Requirement**: PREV-01, PREV-02, PREV-03

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] endpoint returns `image/svg+xml` with the theme's title; 404 and 422 paths tested
- [x] Gate check passes: `uv run pytest -q`

**Tests**: integration
**Gate**: full

---

### T3: Preview logic in TypeScript

**What**: `matchesTerms`, `sampleIcons` (evenly spread) and section builders for themes and packs.
**Where**: `web/src/catalog.ts`
**Depends on**: T2
**Reuses**: `matchesQuery` term splitting
**Requirement**: PREV-06, PREV-07, PREV-10

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] tests cover term matching on name/ref and name/title, 12-of-N spread incl. N ≤ 12, section order
- [x] Gate check passes: `cd web && bun test`

**Tests**: unit
**Gate**: web

---

### T4: Themes page

**What**: Searchable card grid of themes with thumbnails, sections Built-in / Custom, active badge, empty state.
**Where**: `web/src/ThemesPage.tsx`
**Depends on**: T3
**Reuses**: `DiagramsPage` card layout
**Requirement**: PREV-05, PREV-06, PREV-11, PREV-12

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] typechecks
- [x] Gate check passes: `cd web && bun test && bun run typecheck`

**Tests**: none
**Gate**: build

---

### T5: Icon packs page

**What**: Searchable card grid of packs with sample icon grids, sections Downloaded / Not downloaded, empty state.
**Where**: `web/src/PacksPage.tsx`
**Depends on**: T4
**Reuses**: `api.packIcons`, `api.icon`, `sampleIcons`
**Requirement**: PREV-07, PREV-08, PREV-09, PREV-10, PREV-11, PREV-12

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] typechecks
- [x] Gate check passes: `cd web && bun test && bun run typecheck`

**Tests**: none
**Gate**: build

---

### T6: Wire pages and rebuild

**What**: App uses ThemesPage and PacksPage (old list pages removed); rebuild the shipped bundle.
**Where**: `web/src/App.tsx`
**Depends on**: T5
**Reuses**: routes from diagram-catalog
**Requirement**: PREV-05, PREV-09

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] build gate passes; browser walkthrough of both pages

**Tests**: none
**Gate**: build

---

### T7: Documentation

**What**: Describe theme and pack cards in the live UI docs.
**Where**: `docs/content/docs/live-ui.mdx`
**Depends on**: T6
**Reuses**: existing page
**Requirement**: PREV-05, PREV-09

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] docs updated; Gate check passes: `uv run pytest -q`

**Tests**: none
**Gate**: build

---

### T8: Sorted pack sample in tested logic (Verifier gap 1, iteration 1)

**What**: `packSample` sorts by name then samples; PacksPage calls it.
**Where**: `web/src/catalog.ts`
**Depends on**: T7
**Reuses**: `sampleIcons`
**Requirement**: PREV-07

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] unsorted input yields the sample of the sorted list; caller's list untouched
- [x] Gate check passes: `cd web && bun test`

**Tests**: unit
**Gate**: web

---

### T9: Assert the 422 message (Verifier gap 2, iteration 1)

**What**: The broken-theme thumbnail test asserts the error text names the missing base theme.
**Where**: `tests/test_ui.py`
**Depends on**: T8
**Reuses**: `test_theme_thumbnail_endpoint`
**Requirement**: PREV-03

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] assertion on the message text; Gate check passes: `uv run pytest tests/test_ui.py -q`

**Tests**: unit
**Gate**: quick

---

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | start | ✅ |
| T2 | T1 | T1 → T2 | ✅ |
| T3 | T2 | T2 → T3 | ✅ |
| T4 | T3 | T3 → T4 | ✅ |
| T5 | T4 | T4 → T5 | ✅ |
| T6 | T5 | T5 → T6 | ✅ |
| T7 | T6 | T6 → T7 | ✅ |
| T8 | T7 | T7 → T8 | ✅ |
| T9 | T8 | T8 → T9 | ✅ |

## Test Co-location Validation

| Task | Code Layer | Matrix Requires | Task Says | Status |
| ---- | ---------- | --------------- | --------- | ------ |
| T1 | Theme sample | unit | unit | ✅ |
| T2 | UI server API | integration | integration | ✅ |
| T3 | UI pure logic | unit | unit | ✅ |
| T4 | UI component | none | none | ✅ |
| T5 | UI component | none | none | ✅ |
| T6 | UI component | none | none | ✅ |
| T7 | Docs | none | none | ✅ |
| T8 | UI pure logic | unit | unit | ✅ |
| T9 | UI server API | integration | unit | ✅ |

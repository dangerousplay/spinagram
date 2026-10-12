# Diagram Catalog Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/diagram-catalog/design.md`
**Status**: Approved

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec. Guidelines found: `pyproject.toml` (pytest, ruff), `web/package.json` (tsc typecheck, vite build) - no coverage thresholds; strong defaults applied.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Core model / loaders / metadata (Python) | unit | All branches; 1:1 to spec ACs; listed edge cases | `tests/test_metadata.py` | `uv run pytest tests/test_metadata.py -q` |
| CLI | integration | Each flag happy path + combined + no-match | `tests/test_metadata.py` | `uv run pytest tests/test_metadata.py -q` |
| UI server API | integration | New fields present and correct | `tests/test_ui.py` | `uv run pytest tests/test_ui.py -q` |
| UI pure logic (TS) | unit | 1:1 to META-14 grouping, 15, 16, 23, 25, 26, 27 | `web/src/*.test.ts` | `cd web && bun test` |
| UI components (TSX) | none | typecheck + build; interactive UAT | - | `cd web && bun run build` |

## Gate Check Commands

| Gate Level | When to Use | Command |
| ---------- | ----------- | ----------- |
| Quick | Python unit tasks | `uv run pytest tests/test_metadata.py -q` |
| Web | TS logic tasks | `cd web && bun test` |
| Full | Server/CLI integration | `uv run pytest -q` |
| Build | UI component tasks and phase ends | `uv run ruff check src tests && uv run pytest -q && cd web && bun test && bun run build` |

---

## Execution Plan

### Phase 1: Core metadata

```
T1 → T2 → T3 → T4
```

### Phase 2: Server and UI logic

```
T5 → T6 → T7
```

### Phase 3: UI

```
T8 → T9 → T10
```

---

## Task Breakdown

### T1: Diagram category and tags fields

**What**: Add `category` and `tags` to `Diagram` with tag normalisation and type validation.
**Where**: `src/spinagram/model.py`
**Depends on**: None
**Reuses**: dataclass defaults
**Requirement**: META-01, META-03, META-04, META-07

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `Diagram(..., category="Networking", tags=["aws", " Hub ", "AWS", ""])` reports `["aws", "hub"]`
- [x] single-string tags become a one-element list; non-string tags/category raise `ValueError` naming id and key
- [x] Gate check passes: `uv run pytest tests/test_metadata.py -q`

**Tests**: unit
**Gate**: quick

---

### T2: YAML keys and folder defaults

**What**: Load `category`/`tags` from YAML and merge `_defaults.yaml` category (fill) and tags (union) for YAML and Python specs.
**Where**: `src/spinagram/yaml_io.py`
**Depends on**: T1
**Reuses**: `merged()` and `load_python` folder-default handling
**Requirement**: META-02, META-03, META-05, META-06

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] YAML metadata matches META-01 result; invalid types fail with the id and key
- [ ] folder category fills an unset category; folder tags union with spec tags (YAML and Python)
- [ ] Gate check passes: `uv run pytest tests/test_metadata.py -q`

**Tests**: unit
**Gate**: quick

---

### T3: Effective metadata module

**What**: `metadata.py` with provider inference, effective tags/category and `matches`.
**Where**: `src/spinagram/metadata.py`
**Depends on**: T2
**Reuses**: model fields
**Requirement**: META-08, META-09, META-10, META-11, META-12

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] provider tags from node, group and zone icons and `aws-*` styles
- [ ] dominant category with alphabetical tie-break; declared category wins; empty when none
- [ ] the five showcase diagrams report AWS, AWS, Google Cloud, Kubernetes, Kubernetes
- [ ] Gate check passes: `uv run pytest tests/test_metadata.py -q`

**Tests**: unit
**Gate**: quick

---

### T4: CLI --tag and --category

**What**: Filter diagrams by effective metadata on render, check, facts and layout.
**Where**: `src/spinagram/cli.py`
**Depends on**: T3
**Reuses**: `_collect`, `--only`
**Requirement**: META-28, META-29, META-30, META-31

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `check examples/showcase --tag kubernetes` processes 2 diagrams; `--category aws` 2; combined with `--only` intersects; no match exits "no diagrams found"
- [ ] Gate check passes: `uv run pytest -q`

**Tests**: integration
**Gate**: full

---

### T5: Workspace API metadata fields

**What**: `/api/workspace` diagram entries gain `subtitle`, `category`, `tags`.
**Where**: `src/spinagram/ui/workspace.py`
**Depends on**: None (Phase 1 completes first)
**Reuses**: `Workspace.summary`, `metadata`
**Requirement**: META-13

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] API test asserts effective category and tags for a declared and an inferred diagram
- [ ] Gate check passes: `uv run pytest -q`

**Tests**: integration
**Gate**: full

---

### T6: Catalog logic in TypeScript

**What**: Pure functions for search, tag filter, category grouping, tag counts and recents storage, with `bun test` tests and a pytest wrapper.
**Where**: `web/src/catalog.ts`
**Depends on**: T5
**Reuses**: `DiagramRef` type from `web/src/api.ts`
**Requirement**: META-14, META-15, META-16, META-23, META-25, META-26

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] tests cover every term matching, AND tag chips, sort with Uncategorised last, recents cap/dedupe/order, stale removal, throwing storage
- [ ] Gate check passes: `cd web && bun test`

**Tests**: unit
**Gate**: web

---

### T7: Section routes

**What**: Routes for the Diagrams, Themes and Icon packs index pages; empty hash lands on Diagrams.
**Where**: `web/src/hooks.ts`
**Depends on**: T6
**Reuses**: existing hash parser
**Requirement**: META-27

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `parse`/`href` round-trip every route kind; `#/` and `""` parse to diagrams
- [ ] Gate check passes: `cd web && bun test`

**Tests**: unit
**Gate**: web

---

### T8: Diagrams page

**What**: Search box, tag chips, category sections of thumbnail cards, empty state, file errors.
**Where**: `web/src/DiagramsPage.tsx`
**Depends on**: None (Phase 2 completes first)
**Reuses**: `catalog.ts`, `api.diagram` URL, `Empty` styling
**Requirement**: META-14, META-15, META-16, META-17, META-18, META-19

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] component typechecks and builds
- [ ] Gate check passes: `cd web && bun test && bun run typecheck`

**Tests**: none
**Gate**: build

---

### T9: App shell with navbar and recents

**What**: Navbar (Diagrams, Themes, Icon packs, Docs ↗), recents sidebar, themes/packs index pages, recording recents; rebuild the static bundle.
**Where**: `web/src/App.tsx`
**Depends on**: T8
**Reuses**: `NavLink`, `Section`, `Empty`, `catalog.ts` recents
**Requirement**: META-20, META-21, META-22, META-23, META-24, META-25, META-26, META-27

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] build gate passes and `src/spinagram/ui/static` is rebuilt
- [ ] browser walkthrough: navbar sections, Docs opens the site, recents update newest first

**Tests**: none
**Gate**: build

---

### T10: Documentation

**What**: Document `category`/`tags`, inference, CLI flags and the new UI navigation.
**Where**: `docs/content/docs/python.mdx`
**Depends on**: T9
**Reuses**: existing docs pages (also `yaml.mdx`, `cli.mdx`, `live-ui.mdx`)
**Requirement**: META-01, META-02, META-28

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] docs describe metadata, inference table, CLI flags and the UI navigation
- [ ] Gate check passes: `uv run pytest -q`

**Tests**: none
**Gate**: build

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3

Phase 1:  T1 → T2 → T3 → T4
Phase 2:  T5 → T6 → T7
Phase 3:  T8 → T9 → T10
```

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | start | ✅ |
| T2 | T1 | T1 → T2 | ✅ |
| T3 | T2 | T2 → T3 | ✅ |
| T4 | T3 | T3 → T4 | ✅ |
| T5 | None (phase order) | Phase 1 → T5 | ✅ |
| T6 | T5 | T5 → T6 | ✅ |
| T7 | T6 | T6 → T7 | ✅ |
| T8 | None (phase order) | Phase 2 → T8 | ✅ |
| T9 | T8 | T8 → T9 | ✅ |
| T10 | T9 | T9 → T10 | ✅ |

## Test Co-location Validation

| Task | Code Layer | Matrix Requires | Task Says | Status |
| ---- | ---------- | --------------- | --------- | ------ |
| T1 | Core model | unit | unit | ✅ |
| T2 | Loaders | unit | unit | ✅ |
| T3 | Metadata | unit | unit | ✅ |
| T4 | CLI | integration | integration | ✅ |
| T5 | UI server API | integration | integration | ✅ |
| T6 | UI pure logic | unit | unit | ✅ |
| T7 | UI pure logic | unit | unit | ✅ |
| T8 | UI component | none | none | ✅ |
| T9 | UI component | none | none | ✅ |
| T10 | Docs | none | none | ✅ |

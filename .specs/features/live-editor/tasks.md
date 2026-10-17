# Live editor — Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/live-editor/design.md`
**Status**: Approved

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec. Guidelines found: `pyproject.toml` (pytest, ruff), `.github/workflows/ci.yml` (ruff, pytest 3.11–3.13, `bun run build` bundle check), `tests/test_web_unit.py` (runs `bun test`). No coverage thresholds documented — strong defaults applied.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
|---|---|---|---|---|
| Python workspace / file service (`src/spinagram/ui/*.py`) | unit | All branches; 1:1 to spec ACs (DIR, SRC); every listed edge case | `tests/test_ui_editor.py` | `uv run pytest -q tests/test_ui_editor.py` |
| HTTP routes (`server.py`) | integration (Starlette `TestClient`) | Every new route: happy + each error status (403/404/409/413/422) | `tests/test_ui_editor.py` | `uv run pytest -q tests/test_ui_editor.py` |
| SPA pure logic (`web/src/editor.ts`) | unit (`bun test`) | All transitions of the tab model; jumpLine match/no-match | `web/src/*.test.ts` | `cd web && bun test` |
| SPA components (`*.tsx`) | none | Build gate (typecheck + bundle); behaviour covered by the logic tests and the API tests | - | `cd web && bunx bun@1.4.2 run build` |

## Gate Check Commands

| Gate Level | When to Use | Command |
|---|---|---|
| Quick | Python tasks | `uv run pytest -q tests/test_ui_editor.py` |
| Quick-web | `editor.ts` / `api.ts` | `cd web && bun test` |
| Build | UI components, phase ends, bundle | `uv run ruff check src tests examples && uv run pytest -q && (cd web && bunx bun@1.4.2 install --frozen-lockfile && bunx bun@1.4.2 run build)` |

---

## Execution Plan

### Phase 1: Workspace and files (Python)

```
T1 → T2 → T3 → T4
```

### Phase 2: Server routes

```
T5 → T6
```

### Phase 3: SPA logic

```
T7 → T8
```

### Phase 4: Code panel

```
T9 → T10 → T11 → T12
```

### Phase 5: Open folder, bundle and docs

```
T13 → T14 → T15 → T16 → T17
```

---

## Task Breakdown

### T1: File helpers — skip list, spec counts, directory listing, source read

**What**: `files.py` with `SKIP_DIRS`, `MAX_SPECS`, `spec_count`, `list_dir`, `read_source` (LF-normalised text, SHA-256 version, newline style, language).
**Where**: `src/spinagram/ui/files.py`
**Depends on**: None
**Reuses**: `SPEC_EXTS` from `workspace.py`
**Requirement**: DIR-02, DIR-07, SRC-01, SRC-08

**Done when**:
- [x] `list_dir` lists subdirectories (hidden and skipped omitted) with spec counts; raises `NotADirectoryError` with "not a directory: <path>"
- [x] `read_source` returns text with LF newlines, the original newline style, version and language
- [x] Tests in `tests/test_ui_editor.py` pass

**Tests**: unit
**Gate**: quick

---

### T2: Recursive workspace scan, `contains`, `open`

**What**: `Workspace.scan` walks directory roots recursively with the skip list and the 2,000 cap (`truncated`), `contains(path)`, and `open(path)` swapping the root.
**Where**: `src/spinagram/ui/workspace.py`
**Depends on**: T1
**Reuses**: `rescan`, `rel`, `key`
**Requirement**: DIR-03, DIR-05, DIR-06, DIR-07, DIR-08, DIR-09

**Done when**:
- [x] Nested specs load with keys like `sub/file.py#ID`; skipped dirs ignored; cap sets `truncated` in `summary()`
- [x] `open` on a non-directory raises and leaves the workspace unchanged
- [x] Tests pass

**Tests**: unit
**Gate**: quick

---

### T3: Diagram source listing

**What**: `Workspace.source(key)` returns the spec file then the existing stylesheet files of the diagram's cascade, de-duplicated, with display paths.
**Where**: `src/spinagram/ui/workspace.py`
**Depends on**: T2
**Reuses**: stylesheet resolution from `stylesheet_users`
**Requirement**: SRC-01, EDIT-01

**Done when**:
- [x] Order is spec, folder `_defaults` sheets, diagram sheets; CSS text and missing files excluded
- [x] Spec with a load error still lists its spec file
- [x] Tests pass

**Tests**: unit
**Gate**: quick

---

### T4: Safe file write

**What**: `Workspace.write(path, text, version)` with the allow-list, version check, size/encoding checks, newline preservation and atomic replace.
**Where**: `src/spinagram/ui/workspace.py`
**Depends on**: T3
**Reuses**: `files.read_source`
**Requirement**: SRC-02, SRC-03, SRC-04, SRC-07, SRC-08

**Done when**:
- [x] Unlisted path → `PermissionError`; stale version → `VersionConflict` carrying the current version; file untouched in both
- [x] CRLF file stays CRLF; a failing replace leaves the original intact
- [x] Tests pass

**Tests**: unit
**Gate**: quick

---

### T5: Source and file routes with the header guard

**What**: `GET /api/diagrams/{key}.source`, `PUT /api/files`, and the `X-Spinagram` guard.
**Where**: `src/spinagram/ui/server.py`
**Depends on**: None (previous phase complete)
**Reuses**: `_err`, `NO_STORE`, threadpool pattern
**Requirement**: SRC-01, SRC-02, SRC-03, SRC-04, SRC-05, SRC-06

**Done when**:
- [x] 200/403/404/409/413/422 paths each covered by a `TestClient` test
- [x] Tests pass

**Tests**: integration
**Gate**: quick

---

### T6: Folder routes, recursive watching and retarget

**What**: `GET /api/fs`, `POST /api/workspace/open` (publishes `workspace`), `classify` using `ws.contains`, and a retarget event that restarts the watcher on the new root.
**Where**: `src/spinagram/ui/server.py`
**Depends on**: T5
**Reuses**: `watch_loop`, `apply_changes`, `EventBus`
**Requirement**: DIR-02, DIR-03, DIR-04, DIR-05

**Done when**:
- [x] Bad path → 404 and the workspace keeps its files; good path → summary of the new root
- [x] A save to a nested spec is classified as a spec change; after `open`, the watcher targets the new root
- [x] Tests pass

**Tests**: integration
**Gate**: quick

---

### T7: Editor tab model and jumpLine

**What**: `editor.ts` with `Tab`, `fromSource`, `edit`, `saved`, `disk`, `reload`, `keepMine`, `jumpLine`, `languageOf`, plus `editor.test.ts`.
**Where**: `web/src/editor.ts`
**Depends on**: None (previous phase complete)
**Reuses**: none (pure)
**Requirement**: EDIT-03, EDIT-07, EDIT-08, EDIT-09, JUMP-01, JUMP-02

**Done when**:
- [x] Clean tab follows disk; dirty tab + disk change → conflict; reload and keep-mine resolve it
- [x] `jumpLine` finds the first line with the title as a string literal, `null` otherwise
- [x] `bun test` passes

**Tests**: unit
**Gate**: quick-web

---

### T8: API client for source, save, folders

**What**: `api.source`, `api.save`, `api.listDir`, `api.open` sending `X-Spinagram: 1`, and their types.
**Where**: `web/src/api.ts`
**Depends on**: T7
**Reuses**: `check`, `json`, `ApiError`
**Requirement**: SRC-06, DIR-03

**Done when**:
- [x] Types match the server payloads; `ApiError` carries the 409 version
- [x] `bun test` and typecheck pass

**Tests**: none
**Gate**: build

---

### T9: CodeMirror module (lazy chunk)

**What**: `codemirror.ts` creating an editor view with basicSetup, Python/CSS/YAML modes, light/dark theme, change and save callbacks, `setText`, `jumpTo`.
**Where**: `web/src/codemirror.ts`
**Depends on**: None (previous phase complete)
**Reuses**: none
**Requirement**: EDIT-02, EDIT-04

**Done when**:
- [x] Only module importing `@codemirror/*`; build emits it as a separate chunk
- [x] Build gate passes

**Tests**: none
**Gate**: build

---

### T10: Code panel

**What**: `CodePanel.tsx`: tabs with modified dot, editor, Save button and Cmd/Ctrl+S, refetch on `rev`, "file removed" state.
**Where**: `web/src/CodePanel.tsx`
**Depends on**: T9
**Reuses**: `editor.ts`, `api.ts`
**Requirement**: EDIT-01, EDIT-03, EDIT-04, EDIT-05, EDIT-06, EDIT-07

**Done when**:
- [x] Saving writes, clears the dot, and the diagram re-renders through the live event
- [x] Build gate passes

**Tests**: none
**Gate**: build

---

### T11: Conflicts and leave guard

**What**: Conflict banner (Reload from disk / Keep mine) for disk changes and 409s, `beforeunload` and hash-change confirmation while dirty.
**Where**: `web/src/CodePanel.tsx`
**Depends on**: T10
**Reuses**: `editor.ts` transitions
**Requirement**: EDIT-08, EDIT-09, EDIT-10

**Done when**:
- [x] Keep mine re-saves with the current version; Reload replaces the buffer
- [x] Build gate passes

**Tests**: none
**Gate**: build

---

### T12: Code toggle and click-to-jump in the diagram view

**What**: "Code" button and `e` key in `DiagramView`; with the panel open, clicking a node (outside inspect mode) jumps the spec tab to its line.
**Where**: `web/src/DiagramView.tsx`
**Depends on**: T11
**Reuses**: `hitTest`, styles report
**Requirement**: EDIT-01, JUMP-01, JUMP-02

**Done when**:
- [x] Panel opens next to the canvas; inspector still works
- [x] Build gate passes

**Tests**: none
**Gate**: build

---

### T13: Open-folder dialog

**What**: `OpenFolder.tsx` with path box, parent entry, directory list with spec counts, trust notice, Open and error display.
**Where**: `web/src/OpenFolder.tsx`
**Depends on**: None (previous phase complete)
**Reuses**: `api.listDir`, `api.open`
**Requirement**: DIR-01, DIR-02, DIR-03, DIR-05, DIR-10

**Done when**:
- [x] Navigating and opening work against the API; bad path shows "not a directory: <path>"
- [x] Build gate passes

**Tests**: none
**Gate**: build

---

### T14: Header entry for Open folder

**What**: "Open folder" button with the current root name in the `App` header; after opening, go to the catalog and reload the workspace.
**Where**: `web/src/App.tsx`
**Depends on**: T13
**Reuses**: `loadWs`, `useRoute`
**Requirement**: DIR-01, DIR-03

**Done when**:
- [x] Build gate passes

**Tests**: none
**Gate**: build

---

### T15: Catalog paths and notices

**What**: Cards show the spec's relative path; truncation notice; "no diagrams in <path>".
**Where**: `web/src/DiagramsPage.tsx`
**Depends on**: T14
**Reuses**: existing card layout
**Requirement**: DIR-06, DIR-08

**Done when**:
- [x] Build gate passes

**Tests**: none
**Gate**: build

---

### T16: Rebuild the shipped bundle

**What**: `bun run build` with the CI-pinned bun so `src/spinagram/ui/static` matches `web/`.
**Where**: `src/spinagram/ui/static/index.html`
**Depends on**: T15
**Reuses**: CI build steps
**Requirement**: EDIT-01, DIR-01

**Done when**:
- [x] Rebuilding twice gives no diff; wheel test still finds `static/index.html`
- [x] Build gate passes

**Tests**: none
**Gate**: build

---

### T17: Document the editor and Open folder

**What**: Live UI docs page section for the code panel, saving, conflicts, Open folder and the security model.
**Where**: `docs/content/docs/tools/live-ui.mdx`
**Depends on**: T16
**Reuses**: existing page structure
**Requirement**: EDIT-01, DIR-01

**Done when**:
- [ ] Docs site builds with 0 broken links

**Tests**: none
**Gate**: build

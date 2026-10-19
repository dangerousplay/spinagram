# Inspector declarations — Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: inline (no new patterns; extends `features/css-inspector/` and `features/live-editor/`)
**Status**: In Progress

---

## Test Coverage Matrix

> Generated from codebase and project guidelines: `pyproject.toml` (pytest, ruff), `tests/test_web_unit.py` (runs `bun test`), `.specs/features/live-editor/tasks.md` (same layers). No coverage thresholds documented — strong defaults applied.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
|---|---|---|---|---|
| `spinagram.css.inspect` | unit | ELI-01/02 1:1 | `tests/test_css.py` | `uv run pytest -q tests/test_css.py` |
| `spinagram.ui.declare` | unit | DECL-01..05 1:1 + listed edge cases | `tests/test_ui_declare.py` | `uv run pytest -q tests/test_ui_declare.py` |
| Styles endpoint (`workspace.py`, `server.py`) | integration (Starlette `TestClient`) | ELI-03, DECL-06, unreadable-file edge case | `tests/test_ui.py` | `uv run pytest -q tests/test_ui.py` |
| SPA pure logic (`web/src/inspect.ts`) | unit (`bun test`) | HIL-02..04 1:1 | `web/src/*.test.ts` | `cd web && bun test` |
| SPA components (`*.tsx`) | none | Build gate (typecheck + bundle) + browser check of the AC | - | `cd web && bunx bun@1.4.2 run build` |

## Gate Check Commands

| Gate Level | When to Use | Command |
|---|---|---|
| Quick | Python tasks | `uv run --extra ui pytest -q tests/test_css.py tests/test_ui_declare.py tests/test_ui.py` |
| Quick-web | `inspect.ts` | `cd web && bun test` |
| Build | UI components, phase ends | `uv run ruff check src tests examples && uv run --extra ui pytest -q && (cd web && bun test && bunx bun@1.4.2 run build)` |

---

## Execution Plan

### Phase 1: Report (Python)

```
T1 → T2 → T3
```

### Phase 2: UI

```
T4 → T5 → T6 → T7 → T8 → T10 → T9
```

### Phase 3: Verifier fixes (validation.md, iteration 1)

```
T11 → T12 → T13
```

---

## Task Breakdown

### T1: `css.inspect(all_elements=True)` lists the tree of unstyled diagrams [x]

**What**: Keyword flag on `inspect` that skips the unstyled early return and emits elements with empty `styles`/`trace`.
**Where**: `src/spinagram/css.py`
**Depends on**: None
**Requirement**: ELI-01, ELI-02

**Done when**:

- [ ] Unstyled + flag → elements for diagram, groups, nodes, edges; `styled` false; empty styles/trace
- [ ] Unstyled without flag → `elements == []`

**Tests**: unit
**Gate**: quick
**Commit**: `feat(css): list elements of unstyled diagrams on request`

---

### T2: `spinagram.ui.declare.locate` [x]

**What**: Pure function `locate(text, suffix, element) -> int | None` implementing DECL-01..05 and the diagram element of DECL-06.
**Where**: `src/spinagram/ui/declare.py`
**Depends on**: T1
**Requirement**: DECL-01, DECL-02, DECL-03, DECL-04, DECL-05

**Done when**:

- [ ] Every DECL-01..05 AC and the regex/list-title edge cases have a test

**Tests**: unit
**Gate**: quick
**Commit**: `feat(ui): locate element declarations in spec source`

---

### T3: Styles endpoint carries `declaration` and the full tree [x]

**What**: `Workspace.styles` calls `inspect(all_elements=True)` and adds `declaration` per element from the spec text.
**Where**: `src/spinagram/ui/workspace.py`
**Depends on**: T2
**Requirement**: ELI-03, DECL-06

**Done when**:

- [ ] Unstyled report keys equal the styled copy's keys
- [ ] Declarations `{file, line, text}` for YAML and Python specs; `null` when not found; unreadable file → all `null`, 200

**Tests**: integration
**Gate**: build
**Commit**: `feat(ui): add declarations and unstyled elements to the styles report`

---

### T4: Code panel fills its column [x]

**What**: The wrapper in `DiagramView` carries the column width; the `aside` fills it.
**Where**: `web/src/DiagramView.tsx`, `web/src/CodePanel.tsx`
**Depends on**: None
**Requirement**: LAYOUT-01, LAYOUT-02

**Done when**:

- [ ] Browser: `aside[aria-label=Code]` width == wrapper width; wrapper == max(44 % of row, 420 px)

**Tests**: none
**Gate**: build
**Commit**: `fix(ui): let the code panel fill its column`

---

### T5: Hover chip logic [x]

**What**: Pure `chip(report, key)` → `{text, x, y, below}` for the overlay label.
**Where**: `web/src/inspect.ts`
**Depends on**: T4
**Requirement**: HIL-02, HIL-03, HIL-04

**Done when**:

- [ ] Node/group text `label W × H`, edge text without size, `below` when above the top edge

**Tests**: unit
**Gate**: quick-web
**Commit**: `feat(ui): compute the inspector hover label`

---

### T6: Overlay draws the tinted highlight and chip [x]

**What**: `Overlay` fills the hovered box, solid outline, renders the chip from T5; `elementLabel` moves to `inspect.ts`.
**Where**: `web/src/Inspector.tsx`
**Depends on**: T5
**Requirement**: HIL-01, HIL-02

**Done when**:

- [ ] Browser: hover shows tint + chip

**Tests**: none
**Gate**: build
**Commit**: `feat(ui): highlight the element under the pointer like devtools`

---

### T7: Panel shows details and the declaration for any diagram [x]

**What**: `InspectorPanel` lists elements for unstyled diagrams, shows a Declaration section (`file:line`, source line, Show in code) or the not-found message; `api.ts` gains the type.
**Where**: `web/src/Inspector.tsx`
**Depends on**: T6
**Requirement**: ELI-04, DECL-07, DECL-08

**Done when**:

- [ ] Browser: unstyled diagram → list + details + `aws_layout.yaml:22`

**Tests**: none
**Gate**: build
**Commit**: `feat(ui): show element declarations in the inspector`

---

### T8: Jump to the declaration line [x]

**What**: `jump` carries a line; Show in code opens the panel and selects it; click-to-line in code mode uses the declaration; `jumpLine` removed with its test; bundle rebuilt.
**Where**: `web/src/DiagramView.tsx`
**Depends on**: T7
**Requirement**: DECL-09, DECL-10

**Done when**:

- [ ] Browser: Show in code selects line 22 of `aws_layout.yaml`; code-mode click on "ALB" selects line 23

**Tests**: none
**Gate**: build
**Commit**: `feat(ui): jump from an element to its declaration line`

---

### T9: Collapsible Recent sidebar [x]

**What**: `Recents` folds to a 32 px rail via `«`, the rail or `[`; state in `localStorage["spinagram.sidebar"]`.
**Where**: `web/src/App.tsx`
**Depends on**: T10
**Requirement**: SIDE-01, SIDE-02, SIDE-03

**Done when**:

- [ ] Browser: `«` → rail 32 px; reload keeps it; `[` restores 256 px

**Tests**: none
**Gate**: build
**Commit**: `feat(ui): let the recent sidebar collapse to a rail`

---

### T10: Single-key shortcuts ignore editable targets [x]

**What**: `typingIn(target)` (input, textarea, select or contenteditable) guards `useKey`.
**Where**: `web/src/hooks.ts`
**Depends on**: T8
**Requirement**: KEY-01

**Done when**:

- [ ] Unit: contenteditable, input and textarea targets count as typing; a plain div does not
- [ ] Browser: typing `e` in the code editor inserts it; the panel stays open

**Tests**: unit
**Gate**: quick-web
**Commit**: `fix(ui): keep single-key shortcuts out of the code editor`

---

### T11: Declarations of mixed-quote YAML edges; first-match, literal and boundary tests [x]

**What**: `_yaml`/`_quoted` match `"v"`, `'v'` or bare `v` without numbered backreferences (gap D1); tests kill M2 (escape), M3 (edge left boundary), M4 (first match).
**Where**: `src/spinagram/ui/declare.py`
**Depends on**: None
**Requirement**: DECL-01, DECL-02, DECL-03

**Done when**:

- [ ] `{from: a, to: "b"}` and `{from: "a", to: b}` are found
- [ ] A missing `re.escape`, a missing edge left boundary or a last-match search each fail a test

**Tests**: unit
**Gate**: quick
**Commit**: `fix(ui): find YAML edges whose ends are quoted differently`

---

### T12: HIL-04 boundary test [ ]

**What**: A box whose top is within chip height + gap of the scene top gets the chip below; exactly at the threshold it stays above (kills M14).
**Where**: `web/src/inspect.test.ts`
**Depends on**: T11
**Requirement**: HIL-04

**Done when**:

- [ ] Ignoring the gap in the below test fails a test

**Tests**: unit
**Gate**: quick-web
**Commit**: `test(ui): pin the hover label's below threshold`

---

### T13: Spec wording and gates [ ]

**What**: DECL-01 terminators match the code (`,`, `}`, `#` or end of line); the list-title limit for Python is logged; gates run with the `ui` extra.
**Where**: `.specs/features/inspector-declarations/spec.md`
**Depends on**: T12
**Requirement**: DECL-01

**Done when**:

- [ ] `validate_spec.py` clean

**Tests**: none
**Gate**: build
**Commit**: `docs(specs): align DECL-01 with the locator and log its limits`

# Legend CSS Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `inline (extends annotate.py; see spec assumptions)`
**Status**: Done

---

## Test Coverage Matrix

> Guidelines: `pyproject.toml` (pytest, ruff); no coverage thresholds - strong defaults.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Model / loaders / annotate / qa | unit | 1:1 to spec ACs and edge cases | `tests/test_legend_css.py` | `uv run pytest tests/test_legend_css.py -q` |
| Builder integration / backends | integration | Annotated render per backend + unannotated unchanged | `tests/test_legend_css.py` | `uv run pytest -q` |
| Theme config, showcase, docs | none | build gate; PNG review | - | build gate |

## Gate Check Commands

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | Unit tasks | `uv run pytest tests/test_legend_css.py -q` |
| Full | Integration tasks | `uv run pytest -q` |
| Build | Config, showcase, docs, phase ends | `uv run ruff check src tests && uv run pytest -q && uv run spinagram check examples/showcase` |

---

## Execution Plan

### Phase 1: CSS and engine

```
T1 → T2 → T3 → T4
```

### Phase 2: Docs and showcase

```
T5 → T6 → T7
```

---

## Task Breakdown

### T1: Legend CSS properties

**What**: Parse `placement`, `width`, `columns`, `gap`, `padding`, `swatch-width`, `swatch-height`, `display`.
**Where**: `src/spinagram/css.py`
**Depends on**: None
**Reuses**: `PROPS`, `_keyword`, `_length`
**Requirement**: LCSS-05, LCSS-07, LCSS-08, LCSS-09, LCSS-10, LCSS-11, LCSS-13

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] computed values for every property; invalid placement / columns warn with the allowed values
- [x] Gate check passes: `uv run pytest tests/test_legend_css.py -q`

**Tests**: unit
**Gate**: quick

---

### T2: Explicit position stays optional

**What**: `add_legend(position=None)` defers to CSS; YAML keeps an explicit `position`.
**Where**: `src/spinagram/model.py`
**Depends on**: T1
**Reuses**: `add_legend`
**Requirement**: LCSS-04

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] default position is None; explicit values validated and kept
- [x] Gate check passes: `uv run pytest tests/test_legend_css.py -q`

**Tests**: unit
**Gate**: quick

---

### T3: Annotator reads the legend style

**What**: Placement (explicit > CSS > right), band size, columns, gap, padding, swatch size, label size, display none; left and top bands.
**Where**: `src/spinagram/annotate.py`
**Depends on**: T2
**Reuses**: `band`, `panels`, `legend_rows`
**Requirement**: LCSS-01, LCSS-02, LCSS-03, LCSS-07, LCSS-08, LCSS-09, LCSS-10, LCSS-11, LCSS-12, LCSS-13

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] each property changes the drawn card as specified; left/top cards start at the area edge
- [x] Gate check passes: `uv run pytest tests/test_legend_css.py -q`

**Tests**: unit
**Gate**: quick

---

### T4: Layout area after a left or top band

**What**: `_area` moves the content start past a left or top band.
**Where**: `src/spinagram/autolayout/__init__.py`
**Depends on**: T3
**Reuses**: `_area`
**Requirement**: LCSS-06

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] laid-out nodes start after the band
- [x] Gate check passes: `uv run pytest tests/test_legend_css.py -q`

**Tests**: unit
**Gate**: quick

---

### T5: Documentation

**What**: Legend properties table in the annotations page, CSS styling row, skill hint.
**Where**: `docs/content/docs/annotations.mdx`
**Depends on**: None (previous phase completes first)
**Reuses**: docs
**Requirement**: LCSS-14

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] docs build
- [x] Gate check passes: `build gate`

**Tests**: none
**Gate**: build

---

### T6: Showcase legend placed by CSS

**What**: One showcase moves its legend from its stylesheet; skill examples synced.
**Where**: `examples/showcase/campus.css`
**Depends on**: T5
**Reuses**: showcase
**Requirement**: LCSS-15

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `check examples/showcase` 0 issues; PNG reviewed
- [x] Gate check passes: `build gate`

**Tests**: none
**Gate**: build

---

### T7: Close verifier test gaps (iteration 1)

**What**: Tests for columns on top/bottom bands, explicit columns beating the automatic two columns, the YAML path leaving position unset, manual overlap on left/top bands, and an invalid placement keeping the default side.
**Where**: `tests/test_legend_css.py`
**Depends on**: T6
**Reuses**: existing helpers
**Requirement**: LCSS-04, LCSS-05, LCSS-08

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] each surviving mutant (M12, M13, M15, M20, M21, M30) has a test that fails on it
- [x] Gate check passes: `uv run pytest tests/test_legend_css.py -q`

**Tests**: unit
**Gate**: quick

---

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | start of phase | ✅ |
| T2 | T1 | T1 → T2 | ✅ |
| T3 | T2 | T2 → T3 | ✅ |
| T4 | T3 | T3 → T4 | ✅ |
| T5 | None | start of phase | ✅ |
| T6 | T5 | T5 → T6 | ✅ |
| T7 | T6 | T6 → T7 | ✅ |

## Test Co-location Validation

| Task | Code Layer | Matrix Requires | Task Says | Status |
| ---- | ---------- | --------------- | --------- | ------ |
| T1 | Model/annotate/qa | unit | unit | ✅ |
| T2 | Model/annotate/qa | unit | unit | ✅ |
| T3 | Model/annotate/qa | unit | unit | ✅ |
| T4 | Model/annotate/qa | unit | unit | ✅ |
| T5 | Config/showcase/docs | none | none | ✅ |
| T6 | Config/showcase/docs | none | none | ✅ |
| T7 | Model/annotate/qa | unit | unit | ✅ |

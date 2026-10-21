# Layout Engine Improvements Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/layout-engine/design.md`
**Status**: In Progress

---

## Test Coverage Matrix

> Guidelines found: `pyproject.toml` (pytest, ruff); no coverage thresholds. Strong defaults applied, plus the user's DDT rule: every requirement is exercised through a `pytest.mark.parametrize` scenario table with readable `ids=`.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Engine helpers (`engine/*.py`, `text.py`, `qa.py`) | unit | 1:1 to spec ACs, every listed edge case, DDT scenario tables | `tests/test_engine_<area>.py` | `uv run pytest tests/test_engine_<area>.py -q` |
| Builder / model / YAML / CSS integration | integration | Scene-level DDT per AC; YAML parity row per Python API; golden changes pinned by intent tests | `tests/test_engine_<area>.py` | `uv run pytest -q` |
| Backends (svg, pptx, png, figma) | integration | SVG + PPTX XML asserts per feature; PNG when playwright is installed | `tests/test_engine_parity.py`, area files | `uv run pytest -q` |
| CLI (`check`, `render`, `icons report`) | integration | Happy path + error path per flag via `cli.main([...])` | `tests/test_engine_check.py`, `tests/test_engine_output.py` | `uv run pytest -q` |
| Docs, showcase | none | build gate | - | build gate |

## Gate Check Commands

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | Unit-only tasks | `uv run pytest tests/test_engine_<area>.py -q` |
| Full | Integration tasks | `uv run pytest -q` |
| Build | Phase ends, docs, fixtures | `uv run ruff check src tests && uv run pytest -q` |

Baseline before T1: 516 passed, 3 skipped.

---

## Execution Plan

Phases run sequentially; tasks run in order. The first task of each phase depends on the last task of the previous phase.

### Phase 1: Foundation (no behaviour change)

```
T1 → T2 → T3
```

### Phase 2: Text fitting (T1)

```
T4 → T5 → T6 → T7 → T8 → T9
```

### Phase 3: Zone outlines and headers (Z1, Z2)

```
T10 → T11 → T12 → T13 → T14
```

### Phase 4: Edges: zone targets and label placement (E1, E2)

```
T15 → T16 → T17 → T18 → T19 → T20
```

### Phase 5: Diagnostics and check --fix (C1)

```
T21 → T22 → T23 → T24 → T25 → T26 → T27 → T28
```

### Phase 6: Icons and glyphs (I1, I2, T2)

```
T29 → T30 → T31 → T32 → T33 → T34 → T35
```

### Phase 7: Sizing: boxes, rows and zones (B1, I4, Z3)

```
T36 → T37 → T38 → T39 → T40 → T41
```

### Phase 8: Routing and legend (E3, E4, L1)

```
T42 → T43 → T44 → T45 → T46 → T47
```

### Phase 9: Grid, anchors and labels (G1, E5, I3, T3)

```
T48 → T49 → T50 → T51 → T52 → T53 → T54
```

### Phase 10: CSS, parity and output (S1, S2, O1)

```
T55 → T56 → T57 → T58 → T59 → T60
```

---

## Task Breakdown

### T1: Engine package and endpoint extraction

**What**: Engine package and endpoint extraction.
**Where**: `src/spinagram/engine/endpoints.py`
**Depends on**: None
**Reuses**: `_Builder.endpoint/_center` (layout.py:246-271)
**Requirement**: EDG-07 (prep)

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `engine/__init__.py` created; `_Builder.endpoint` delegates to `engine.endpoints.resolve`; DDT table of node anchors (auto side × 4 directions, `side@frac`, absolute point) asserts identical points to 0.3; golden SVG hash unchanged
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_endpoints.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `refactor(engine): move endpoint resolution into engine package`

---

### T2: Issue fix and severity fields, check --json

**What**: Issue fix and severity fields, check --json.
**Where**: `src/spinagram/qa.py`
**Depends on**: T1
**Reuses**: `Issue`, `cli._check`
**Requirement**: CHK-02, CHK-03

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `Issue` gains `fix: dict | None` and `severity`; `str(issue)` unchanged; `check --json` prints a JSON list of issues with `fix`; DDT over issue kinds asserts JSON keys
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_check.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(check): issue fixes, severity and JSON output`

---

### T3: Zone model fields and YAML parity

**What**: Zone model fields and YAML parity.
**Where**: `src/spinagram/model.py`
**Depends on**: T2
**Reuses**: `Zone`, `yaml_io.load` zones loop, dump `_Z`
**Requirement**: ZON-10, ZON-11 (model)

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `Zone` gains id, dash, stroke, stroke_width, fill, header, fit, padding, equalize, children, meaning, cls; `d.zone(...)` accepts them; auto id `z<index>`; YAML load/dump round-trip DDT; existing zones unchanged
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_zones.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(model): zone ids, outline and header fields in Python and YAML`

---

### T4: Token break points with CIDR protection

**What**: Token break points with CIDR protection.
**Where**: `src/spinagram/engine/textfit.py`
**Depends on**: None
**Reuses**: `text.measure`
**Requirement**: TXT-02, TXT-03

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `break_token` splits after `break_on` chars with no hyphen; IPv4/CIDR atomic; DDT: 12 tokens (hostnames, `runner-*-x-*`, `10.0.0.0/22 · 10.0.8.0/21`, URLs, paths) × widths
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_textfit.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest tests/test_engine_textfit.py -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(text): break long tokens at safe points`

---

### T5: Wrap spaces then tokens

**What**: Wrap spaces then tokens.
**Where**: `src/spinagram/engine/textfit.py`
**Depends on**: T4
**Reuses**: `text.wrap`
**Requirement**: TXT-01

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `wrap_fit` wraps at spaces first, then breaks over-wide tokens; DDT: lengths 10–60 chars in 166 px; every line ≤ width unless an atomic token
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_textfit.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest tests/test_engine_textfit.py -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(text): wrap at spaces then safe token breaks`

---

### T6: Fit loop: shrink and grow

**What**: Fit loop: shrink and grow.
**Where**: `src/spinagram/engine/textfit.py`
**Depends on**: T5
**Reuses**: `TextBlock`
**Requirement**: TXT-04, TXT-05, TXT-06

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `fit_blocks` modes `none|shrink|grow|shrink-then-grow`; 1 px steps to `min_scale`; returns strategy and height needed; DDT matrix mode × text length × box size; empty text no-op; narrow box terminates
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_textfit.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest tests/test_engine_textfit.py -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(text): shrink and grow fitting strategies`

---

### T7: Wire fitting into boxes, symbols and diamonds

**What**: Wire fitting into boxes, symbols and diamonds.
**Where**: `src/spinagram/layout.py`
**Depends on**: T6
**Reuses**: `_Builder.box/symbol/diamond`
**Requirement**: TXT-08, TXT-01..06 (integration)

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] node `fit/min_scale/break_on` via kwargs, YAML and `defaults.node`; default `shrink` (+grow only when `fit` says so); scene DDT: no rendered line exceeds label box; golden SVG regenerated with an intent test listing changed node ids
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_textfit.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(layout): fit node text to its box by default`

---

### T8: Overflow detail names the strategy

**What**: Overflow detail names the strategy.
**Where**: `src/spinagram/qa.py`
**Depends on**: T7
**Reuses**: `check` overflow branch
**Requirement**: TXT-07

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `overflow-x/y` detail ends with `after <strategy> to <n>px`; DDT over modes; no overflow reported when fit succeeded
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_textfit.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest tests/test_engine_textfit.py -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(check): report the fitting strategy that failed`

---

### T9: Letter-spaced zone label measurement

**What**: Letter-spaced zone label measurement.
**Where**: `src/spinagram/layout.py`
**Depends on**: T8
**Reuses**: `_Builder.text` letter_spacing
**Requirement**: TXT-09

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] uppercase zone labels measured with letter spacing (theme `defaults.zone.label_tracking`, default 0); DDT tracking × label length → Text.width
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_textfit.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest tests/test_engine_textfit.py -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `fix(layout): measure zone labels with letter spacing`

---

### T10: Outline resolution: dash, stroke, fill none

**What**: Outline resolution: dash, stroke, fill none.
**Where**: `src/spinagram/engine/zones.py`
**Depends on**: None
**Reuses**: `Theme.zone_style`, `_decorate`
**Requirement**: ZON-09, ZON-10

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `solid|dashed(8 6)|dotted(2 6, round caps)|[list]` on styles and zones; `fill: none`; Shape gains `cap`; SVG emits `stroke-linecap=round` for dotted; DDT dash × source (style/zone/css)
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_zones.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(zones): dashed, dotted and custom outline patterns`

---

### T11: PPTX zone dash parity

**What**: PPTX zone dash parity.
**Where**: `src/spinagram/backends/pptx.py`
**Depends on**: T10
**Reuses**: `_line` custDash
**Requirement**: ZON-12

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] zone dash patterns emit `a:custDash` with matching ratios and round cap for dotted; DDT over patterns asserts SVG dasharray and PPTX XML
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_zones.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(pptx): zone dash patterns and round caps`

---

### T12: CSS zone element and fill none

**What**: CSS zone element and fill none.
**Where**: `src/spinagram/css.py`
**Depends on**: T11
**Reuses**: `tree`, colour parsing
**Requirement**: ZON-11, ZON-13, STY-01

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] zones in CSS tree as `zone` keyed `zone:<id>` with style class; `fill|stroke|color: none` accepted → None; DDT selectors `zone#id`, `zone.az`, `#id`, `group:<gid>` still works
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_zones.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(css): zone elements and none colours`

---

### T13: Zone header: inset icon and centred label

**What**: Zone header: inset icon and centred label.
**Where**: `src/spinagram/engine/zones.py`
**Depends on**: T12
**Reuses**: zone loop layout.py:345-369
**Requirement**: ZON-01, ZON-02, ZON-03, ZON-07, ZON-08

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] icon ≥ padding inside outline, equal header icon size, label centre ±1 px of icon centre, `header.upper`, `inset:false` keeps 0.3 flush; DDT (dash × icon × label × inset); golden updated with intent test
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_zones.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(zones): inset header with centred label`

---

### T14: Header chips, strip and content_top

**What**: Header chips, strip and content_top.
**Where**: `src/spinagram/engine/zones.py`
**Depends on**: T13
**Reuses**: header layout from previous task
**Requirement**: ZON-04, ZON-05, ZON-06

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] icon list → chips left to right; `header.strip` 5 px accent bar; `Zone.content_top` exposed after build; DDT chip count 1–3 × strip
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_zones.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(zones): header chips, accent strip and content top`

---

### T15: Zone endpoints

**What**: Zone endpoints.
**Where**: `src/spinagram/engine/endpoints.py`
**Depends on**: None
**Reuses**: auto-side logic
**Requirement**: EDG-07, EDG-08, EDG-12

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `Zone`, `zone:<id>`, `zone:<id>.<side>[@f]` endpoints; facing side; closest point clamped 24 px from corners; inner face when source inside; KeyError on unknown; DDT 8 source positions
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_endpoints.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(edges): zones as edge endpoints`

---

### T16: PPTX zone binding and through-box exclusion

**What**: PPTX zone binding and through-box exclusion.
**Where**: `src/spinagram/backends/pptx.py`
**Depends on**: T15
**Reuses**: connector binding
**Requirement**: EDG-10, EDG-11

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] connector bound to zone shape; Binding target kind recorded; edges ending on a zone border excluded from edge-through-box for that zone; DDT
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_endpoints.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(pptx): bind connectors to zone targets`

---

### T17: Bus fan into zones

**What**: Bus fan into zones.
**Where**: `src/spinagram/engine/endpoints.py`
**Depends on**: T16
**Reuses**: zone endpoint
**Requirement**: EDG-09

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `fan="bus"` draws a bar 10 px inside the side spanning direct children; arrowhead at border; DDT side × child count
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_endpoints.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(edges): bus fan-in to zones`

---

### T18: Label candidate generator

**What**: Label candidate generator.
**Where**: `src/spinagram/engine/labels.py`
**Depends on**: T17
**Reuses**: `annotate._candidate` pattern
**Requirement**: EDG-01

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] candidates in spec order for straight, poly and curve routes; DDT route kind × orientation asserts order and offsets
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_labels.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest tests/test_engine_labels.py -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(labels): edge label candidates`

---

### T19: Label placement pass

**What**: Label placement pass.
**Where**: `src/spinagram/engine/labels.py`
**Depends on**: T18
**Reuses**: `annotate._overlaps`, `_Builder.pill`
**Requirement**: EDG-02, EDG-03, EDG-04, EDG-05

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] obstacles: nodes, zone headers, placed labels, last 14 px, canvas margin; first free wins; least overlap fallback + `label-collision` issue with count; `label_at` unchanged; wired after edges in build; golden updated with intent test
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_labels.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(labels): place edge labels clear of boxes, headers and arrowheads`

---

### T20: Label placement determinism and random property test

**What**: Label placement determinism and random property test.
**Where**: `tests/test_engine_labels.py`
**Depends on**: T19
**Reuses**: LAY-05 hash-seed pattern (test_layered.py:408)
**Requirement**: EDG-06

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] 200 seeded random short edges: no intersection when a free candidate exists; identical hash across PYTHONHASHSEED 0-4
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_labels.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `test(labels): random edges and hash-seed determinism`

---

### T21: Icon and header diagnostics

**What**: Icon and header diagnostics.
**Where**: `src/spinagram/qa.py`
**Depends on**: None
**Reuses**: scene geometry
**Requirement**: CHK-01

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `icon-touches-border`, `icon-overflows-box`, `header-overlap`; DDT fixtures one per kind + clean control
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_check.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest tests/test_engine_check.py -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(check): icon and header diagnostics`

---

### T22: Safe-area and contrast diagnostics

**What**: Safe-area and contrast diagnostics.
**Where**: `src/spinagram/qa.py`
**Depends on**: T21
**Reuses**: `canvas.margin`
**Requirement**: CHK-01

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `outside-safe-area`, `low-contrast` (WCAG < 3.0 title/icon, < 4.5 body); DDT colour pairs incl. boundary ratios
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_check.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest tests/test_engine_check.py -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(check): safe-area and contrast diagnostics`

---

### T23: Attach fixes to issues

**What**: Attach fixes to issues.
**Where**: `src/spinagram/qa.py`
**Depends on**: T22
**Reuses**: `Issue.fix`
**Requirement**: CHK-02

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] move-label, resize, nudge, shrink-font fixes with concrete values; DDT issue kind → fix op and payload
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_check.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest tests/test_engine_check.py -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(check): machine-readable fixes`

---

### T24: Apply fixes to the model

**What**: Apply fixes to the model.
**Where**: `src/spinagram/engine/fix.py`
**Depends on**: T23
**Reuses**: `copy.deepcopy`
**Requirement**: CHK-07, CHK-08

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `apply_to_diagram` applies safe fixes, skips ones leaving the safe area; re-check shows zero fixed kinds; DDT per op
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_check.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest tests/test_engine_check.py -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(fix): apply safe fixes to a diagram`

---

### T25: check --fix for YAML

**What**: check --fix for YAML.
**Where**: `src/spinagram/cli.py`
**Depends on**: T24
**Reuses**: `yaml_io` dumper
**Requirement**: CHK-04

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] writes `<stem>.fixed.yaml`, source unchanged, no file when nothing fixable; DDT over fixture specs
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_check.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(cli): check --fix writes a fixed YAML copy`

---

### T26: check --fix for Python

**What**: check --fix for Python.
**Where**: `src/spinagram/cli.py`
**Depends on**: T25
**Reuses**: `fix.suggest_python`
**Requirement**: CHK-05

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] prints `<element>: key=value` per fix; no file written; exit 1 while P0 remains; DDT
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_check.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(cli): suggest fixes for Python specs`

---

### T27: render --relayout

**What**: render --relayout.
**Where**: `src/spinagram/cli.py`
**Depends on**: T26
**Reuses**: `api.render`
**Requirement**: CHK-06

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] applies safe fixes in memory before rendering; DDT asserts output geometry equals fixed spec render
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_check.py` asserting spec outcomes
- [x] Gate check passes: `uv run pytest -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(cli): render --relayout applies fixes in memory`

---

### T28: D2-like end-to-end fixture

**What**: D2-like end-to-end fixture.
**Where**: `tests/fixtures/layout_engine/d2_first_iteration.yaml`
**Depends on**: T27
**Reuses**: roadmap Appendix workarounds
**Requirement**: CHK-07

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] fixture reproduces D2 first-iteration problems; `check --fix` → zero P0 diagnostics
- [x] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_check.py` asserting spec outcomes
- [x] Gate check passes: `uv run ruff check src tests && uv run pytest -q`
- [x] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: build

**Commit**: `test(check): D2-like spec converges with check --fix`

---

### T29: Icon aspect ratio and fit by height

**What**: Icon aspect ratio and fit by height.
**Where**: `src/spinagram/engine/icons.py`
**Depends on**: None
**Reuses**: `scene.Icon`, backends icon()
**Requirement**: ICN-01, ICN-02, ICN-03, ICN-05

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `aspect()` from viewBox/size; `Icon.w/h`; svg/pptx/figma/png read w/h; 1:4 wordmark in 40 px header ≥ 24 px tall; centred icon-only boxes; DDT aspect × slot
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_icons.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(icons): keep intrinsic aspect ratio`

---

### T30: Icon variants

**What**: Icon variants.
**Where**: `src/spinagram/engine/icons.py`
**Depends on**: T29
**Reuses**: `Theme.icon` alias
**Requirement**: ICN-04

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `variant=` resolves `<icon>-wordmark|-symbol` alias, else plain; DDT
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_icons.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest tests/test_engine_icons.py -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(icons): wordmark and symbol variants`

---

### T31: Badges

**What**: Badges.
**Where**: `src/spinagram/engine/icons.py`
**Depends on**: T30
**Reuses**: `_Builder.box` icon slot
**Requirement**: ICN-06, ICN-07, ICN-08, ICN-09, ICN-10

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] ≤ 3 badges, 40 % size min 14, halo +3, top-right stacking inset 6, text width reduced, ValueError > 3; YAML; DDT count × box size
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_icons.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(icons): corner badges on boxes`

---

### T32: Per-character fallback runs and bundled symbol font

**What**: Per-character fallback runs and bundled symbol font.
**Where**: `src/spinagram/engine/textfit.py`
**Depends on**: T31
**Reuses**: `text._cmap`
**Requirement**: TXT-10, TXT-11, TXT-15

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] bundle NotoSansSymbols2 + OFL in `src/spinagram/fonts/` and wheel; `runs()` chain role→body→symbols; measure uses fallback metrics (heuristic removed); DDT `× → ⚠ ✓ ·` × roles
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_glyphs.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest tests/test_engine_glyphs.py -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(text): per-character glyph fallback with bundled symbol font`

---

### T33: SVG fallback runs

**What**: SVG fallback runs.
**Where**: `src/spinagram/backends/svg.py`
**Depends on**: T32
**Reuses**: `text_lines`, @font-face
**Requirement**: TXT-12

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] fallback chars in tspans with fallback family, font embedded; DDT
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_glyphs.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(svg): render glyph fallback runs`

---

### T34: PPTX fallback runs

**What**: PPTX fallback runs.
**Where**: `src/spinagram/backends/pptx.py`
**Depends on**: T33
**Reuses**: text frame runs
**Requirement**: TXT-13

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] separate `a:r` runs with fallback `a:latin`/`a:sym`; DDT
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_glyphs.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(pptx): render glyph fallback runs`

---

### T35: glyph-missing diagnostic

**What**: glyph-missing diagnostic.
**Where**: `src/spinagram/qa.py`
**Depends on**: T34
**Reuses**: `Scene.fallbacks`
**Requirement**: TXT-14, CHK-01

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] one issue per (char, role) with exact message format; DDT
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_glyphs.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest tests/test_engine_glyphs.py -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(check): report glyph fallbacks`

---

### T36: Content-sized boxes

**What**: Content-sized boxes.
**Where**: `src/spinagram/engine/model_passes.py`
**Depends on**: None
**Reuses**: `autolayout.sizing`
**Requirement**: BOX-01

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] fixed diagrams: box with w=h=0 sized to content; auto diagrams unchanged; DDT icon × title × body
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_sizing.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(layout): size boxes to their content`

---

### T37: Row and column containers with same_size

**What**: Row and column containers with same_size.
**Where**: `src/spinagram/model.py`
**Depends on**: T36
**Reuses**: `Diagram._seq`
**Requirement**: BOX-02, BOX-03, BOX-04, BOX-05

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `with d.row(x=,y=,gap=,same_size=,max_width=)` / column; legacy function form unchanged; ValueError naming widest; YAML `row:`/`column:` blocks; DDT
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_sizing.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(dsl): row and column containers with equal sizes`

---

### T38: same_icon_size and icon-size-mismatch

**What**: same_icon_size and icon-size-mismatch.
**Where**: `src/spinagram/engine/model_passes.py`
**Depends on**: T37
**Reuses**: container pass
**Requirement**: BOX-06

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] smallest member icon size applied; check reports mismatch in explicit rows otherwise; DDT
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_sizing.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(layout): uniform icon size per row`

---

### T39: Zone context manager

**What**: Zone context manager.
**Where**: `src/spinagram/model.py`
**Depends on**: T38
**Reuses**: `Diagram.group` pattern
**Requirement**: ZON-18

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `with d.zone(...) as z:` collects nodes and nested zones as children; YAML `children:`; DDT nesting depth 1–4
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_sizing.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest tests/test_engine_sizing.py -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(dsl): zones as containers`

---

### T40: Zones fit children and equalize siblings

**What**: Zones fit children and equalize siblings.
**Where**: `src/spinagram/engine/zones.py`
**Depends on**: T39
**Reuses**: `model_passes`
**Requirement**: ZON-14, ZON-15, ZON-16

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] bbox + padding + header; innermost first; `equalize="siblings"`; DDT nesting × padding × equalize
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_sizing.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(zones): fit zones to children`

---

### T41: Zone clip and underuse diagnostics

**What**: Zone clip and underuse diagnostics.
**Where**: `src/spinagram/qa.py`
**Depends on**: T40
**Reuses**: zone children
**Requirement**: ZON-17, CHK-01

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `zone-clips-child` (children or geometric), `zone-underused` < 0.35; DDT incl. single-AZ blank sibling
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_sizing.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest tests/test_engine_sizing.py -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(check): zone clipping and underuse`

---

### T42: Router crossing penalty hook

**What**: Router crossing penalty hook.
**Where**: `src/spinagram/autolayout/route.py`
**Depends on**: None
**Reuses**: `route`, `_search`
**Requirement**: EDG-18

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] optional `penalty_fn` (default None = identical routes, layered golden unchanged); DDT crossing vs detour
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_route.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest tests/test_engine_route.py -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(route): crossing penalty in the obstacle router`

---

### T43: Ortho routing pass

**What**: Ortho routing pass.
**Where**: `src/spinagram/engine/route.py`
**Depends on**: T42
**Reuses**: obstacle router
**Requirement**: EDG-17, EDG-19, EDG-21

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `route="ortho"` per edge or `defaults.edge.route`; declaration order; via/curve kept; hash-seed determinism; DDT layouts
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_route.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(edges): crossing-aware orthogonal routing`

---

### T44: edge-crossings diagnostic

**What**: edge-crossings diagnostic.
**Where**: `src/spinagram/qa.py`
**Depends on**: T43
**Reuses**: `engine.route.crossings`
**Requirement**: EDG-20, CHK-01

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] reported when n > 0 with count; DDT 0/1/4 crossings
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_route.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest tests/test_engine_route.py -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(check): count edge crossings`

---

### T45: Bundles and shared trunks

**What**: Bundles and shared trunks.
**Where**: `src/spinagram/engine/route.py`
**Depends on**: T44
**Reuses**: ortho pass
**Requirement**: EDG-13, EDG-14, EDG-15, EDG-16

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `d.bundle([...], trunk=)` and `fan_in=True`; shared trunk line; one arrowhead; ValueError on mixed targets; YAML; DDT trunk side × source count
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_route.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(edges): bundled edges share a trunk`

---

### T46: meaning= and legend collection

**What**: meaning= and legend collection.
**Where**: `src/spinagram/engine/legend.py`
**Depends on**: T45
**Reuses**: `annotate.legend_entries`
**Requirement**: LEG-01, LEG-02, LEG-03

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `meaning` on edges/zones (Python, YAML); one row per distinct style with meaning; removal drops row; DDT
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_legend.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest tests/test_engine_legend.py -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(legend): collect rows from meanings`

---

### T47: Legend drawing and placement

**What**: Legend drawing and placement.
**Where**: `src/spinagram/engine/legend.py`
**Depends on**: T46
**Reuses**: `annotate._swatch`, band
**Requirement**: LEG-04, LEG-05

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] edge rows = line with dash/colour; zone rows = mini rect; `place="band"|(x,y,w,h)`; card fitted; `d.legend(...)`; DDT
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_legend.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(legend): automatic legend card`

---

### T48: Grid cells

**What**: Grid cells.
**Where**: `src/spinagram/engine/model_passes.py`
**Depends on**: None
**Reuses**: model pass
**Requirement**: GRD-01

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `d.grid(cols, rows, gutter)`; `g[c, r]`; `cell=` on nodes/zones; YAML `grid:`; DDT
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_grid.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest tests/test_engine_grid.py -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(dsl): named grid cells`

---

### T49: Alignment helpers

**What**: Alignment helpers.
**Where**: `src/spinagram/engine/model_passes.py`
**Depends on**: T48
**Reuses**: grid pass
**Requirement**: GRD-02

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `align_x`, `align_y`, `center_on` applied before build; DDT
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_grid.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest tests/test_engine_grid.py -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(dsl): alignment helpers`

---

### T50: Straight edges and not-straight check

**What**: Straight edges and not-straight check.
**Where**: `src/spinagram/engine/endpoints.py`
**Depends on**: T49
**Reuses**: `straight_anchors`
**Requirement**: GRD-03, GRD-04

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] anchors at shared-span midpoint; axis-aligned; `not-straight` issue when no overlap; DDT overlaps
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_grid.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(edges): straight edges between aligned boxes`

---

### T51: Anchor methods

**What**: Anchor methods.
**Where**: `src/spinagram/model.py`
**Depends on**: T50
**Reuses**: `Node.at`
**Requirement**: GRD-05

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `at_left/at_right/at_top/at_bottom(frac)` return anchor strings; properties unchanged; DDT
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_grid.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest tests/test_engine_grid.py -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(dsl): anchor helper methods`

---

### T52: Icon fallback chain and source record

**What**: Icon fallback chain and source record.
**Where**: `src/spinagram/engine/icons.py`
**Depends on**: T51
**Reuses**: `Theme.icon`
**Requirement**: ICN-11, ICN-12

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `icons.fallback` concepts; `concept:<name>`; source official/theme/fallback:n recorded on scene; DDT
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_icons.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest tests/test_engine_icons.py -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(icons): declared fallback chains`

---

### T53: icons report CLI

**What**: icons report CLI.
**Where**: `src/spinagram/cli.py`
**Depends on**: T52
**Reuses**: `_icons`
**Requirement**: ICN-13

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `spinagram icons report <paths>` prints diagram, icon, resolved ref, source; DDT
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_icons.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(cli): icons report`

---

### T54: Free label size, roles and wrapping

**What**: Free label size, roles and wrapping.
**Where**: `src/spinagram/model.py`
**Depends on**: T53
**Reuses**: `Diagram.label`, `_Builder.node` text
**Requirement**: TXT-16, TXT-17, TXT-18

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `size=`, `role=zone-label|caption|footnote`, `max_width` wrap; DDT
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_textfit.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(dsl): free label roles, size and wrapping`

---

### T55: CSS label and chip elements, icon-only defaults

**What**: CSS label and chip elements, icon-only defaults.
**Where**: `src/spinagram/css.py`
**Depends on**: None
**Reuses**: `tree`
**Requirement**: STY-02, STY-03

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `label`, `chip` element types; icon-only boxes no shadow/stroke unless styled; DDT selectors
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_style.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(css): label and chip elements`

---

### T56: Backend parity goldens

**What**: Backend parity goldens.
**Where**: `tests/test_engine_parity.py`
**Depends on**: T55
**Reuses**: backends
**Requirement**: STY-04

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] DDT feature × backend (svg, png when playwright, pptx): dash, icon-only, classed label, absolute point edge, zone target, fallback glyph
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_parity.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `test(backends): parity goldens for new scene features`

---

### T57: Stable output names

**What**: Stable output names.
**Where**: `src/spinagram/api.py`
**Depends on**: T56
**Reuses**: `Scene.slug`, backends render
**Requirement**: OUT-01, OUT-02

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `output=`/YAML `output:`; `render --name-from id|file|slug`; DDT
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_output.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: integration
**Gate**: full

**Commit**: `feat(render): stable output names`

---

### T58: requires version check

**What**: requires version check.
**Where**: `src/spinagram/yaml_io.py`
**Depends on**: T57
**Reuses**: `importlib.metadata`
**Requirement**: OUT-03

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `requires` in Python and YAML; warning + `version-mismatch` issue; DDT specifiers
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_output.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest tests/test_engine_output.py -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(spec): warn on unsatisfied requires`

---

### T59: SVG metadata content hash

**What**: SVG metadata content hash.
**Where**: `src/spinagram/backends/svg.py`
**Depends on**: T58
**Reuses**: `to_svg`
**Requirement**: OUT-04

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `<metadata>` sha256 of scene; identical for identical input, differs on change; DDT
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/test_engine_output.py` asserting spec outcomes
- [ ] Gate check passes: `uv run pytest tests/test_engine_output.py -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: unit
**Gate**: quick

**Commit**: `feat(svg): content hash metadata`

---

### T60: Docs, skill and changelog

**What**: Docs, skill and changelog.
**Where**: `docs/content/docs/layout-engine.mdx`
**Depends on**: T59
**Reuses**: existing docs pages, agent skill
**Requirement**: all (docs)

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] doc page per area; spinagram SKILL.md workarounds replaced by new APIs; examples/layout-engine showcase renders with `check` clean
- [ ] DDT scenario table (`pytest.mark.parametrize` with `ids=`) in `tests/n/a` asserting spec outcomes
- [ ] Gate check passes: `uv run ruff check src tests && uv run pytest -q`
- [ ] Test count: previous total + new scenarios pass (no silent deletions)

**Tests**: none
**Gate**: build

**Commit**: `docs: layout engine improvements`

---

# Annotations Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/annotations/design.md`
**Status**: Done

---

## Test Coverage Matrix

> Guidelines: `pyproject.toml` (pytest, ruff); no coverage thresholds - strong defaults.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Model / loaders / annotate / qa | unit | 1:1 to spec ACs and edge cases | `tests/test_annotations.py` | `uv run pytest tests/test_annotations.py -q` |
| Builder integration / backends | integration | Annotated render per backend + unannotated unchanged | `tests/test_annotations.py` | `uv run pytest -q` |
| Theme config, showcase, docs | none | build gate; PNG review | - | build gate |

## Gate Check Commands

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | Unit tasks | `uv run pytest tests/test_annotations.py -q` |
| Full | Integration tasks | `uv run pytest -q` |
| Build | Config, showcase, docs, phase ends | `uv run ruff check src tests && uv run pytest -q && uv run spinagram check examples/showcase` |

---

## Execution Plan

### Phase 1: Model and loaders

```
T1 → T2
```

### Phase 2: Theme and CSS

```
T3 → T4
```

### Phase 3: Layout engine

```
T5 → T6 → T7 → T8 → T9 → T10 → T11 → T12
```

### Phase 4: Backends

```
T13
```

### Phase 5: Showcase and docs

```
T14 → T15 → T16 → T17
```

---

## Task Breakdown

### T1: Annotation model and builders

**What**: `Annotations`, `LegendSpec`, `Step`, `Callout`; `add_legend`, `step` (edge/node/pair/id, numbering), `Edge.step`, `callout`, note `variant` with validation.
**Where**: `src/spinagram/model.py`
**Depends on**: None
**Reuses**: `Diagram.add`, `_endpoint`
**Requirement**: ANN-02, ANN-13, ANN-14, ANN-15, ANN-25, ANN-29

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] steps number in call order; explicit n kept; `on` accepts edge, node, id and (src, dst)
- [x] unknown callout kind / note variant raise naming allowed values; foreign callout target raises
- [x] Gate check passes: `uv run pytest tests/test_annotations.py -q`

**Tests**: unit
**Gate**: quick

---

### T2: YAML annotations

**What**: Parse and dump `annotations:` (legend, steps, callouts) and note `variant`; resolve `on` references.
**Where**: `src/spinagram/yaml_io.py`
**Depends on**: T1
**Reuses**: `from_dict`, `dump`
**Requirement**: ANN-19, ANN-29

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `on: "a -> b"` attaches to the first a→b edge; unknown reference fails naming it
- [x] round-trip through `dump` keeps annotations
- [x] Gate check passes: `uv run pytest tests/test_annotations.py -q`

**Tests**: unit
**Gate**: quick

---

### T3: Theme tokens and defaults

**What**: Add `success*` colours and `defaults.annotations` to the default theme.
**Where**: `src/spinagram/themes/default/theme.yaml`
**Depends on**: None (previous phase completes first)
**Reuses**: theme defaults
**Requirement**: ANN-21

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] theme loads; `t.color('success')` resolves; existing golden tests unchanged
- [x] Gate check passes: `build gate`

**Tests**: none
**Gate**: build

---

### T4: CSS elements for annotations

**What**: Style tree gains `legend`, `step`, `callout` elements and note variant classes.
**Where**: `src/spinagram/css.py`
**Depends on**: T3
**Reuses**: `tree`, `compute`
**Requirement**: ANN-31, ANN-32, ANN-33, ANN-34, ANN-35

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] selectors `legend`, `step::label`, `callout.warning`, `note.card` match; computed under `legend`, `step:<n>`, `callout:<i>`
- [x] `check --styles --select legend` lists the legend
- [x] Gate check passes: `uv run pytest tests/test_annotations.py -q`

**Tests**: unit
**Gate**: quick

---

### T5: Legend entries and band size

**What**: `legend_entries` (auto/explicit, labels, first-use element) and `band` (side, thickness).
**Where**: `src/spinagram/annotate.py`
**Depends on**: None (previous phase completes first)
**Reuses**: css computed keys
**Requirement**: ANN-01, ANN-02, ANN-03, ANN-10

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] auto entries: classes and non-default styles once, first-use order, humanised labels
- [x] explicit items keep order and labels; unused keys flagged
- [x] right band 360 + 32; bottom band height from content
- [x] Gate check passes: `uv run pytest tests/test_annotations.py -q`

**Tests**: unit
**Gate**: quick

---

### T6: Layout area minus the band

**What**: Automatic layout places content in the area minus the reserved band.
**Where**: `src/spinagram/autolayout/__init__.py`
**Depends on**: T5
**Reuses**: `_area`
**Requirement**: ANN-08, ANN-09

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] right: area width shrinks by band; bottom: height shrinks; no annotations: area unchanged
- [x] Gate check passes: `uv run pytest tests/test_annotations.py -q`

**Tests**: unit
**Gate**: quick

---

### T7: Legend and steps panels

**What**: Annotator draws the legend card (node swatches with computed style, edge samples, icons) and the steps panel.
**Where**: `src/spinagram/annotate.py`
**Depends on**: T6
**Reuses**: `_Builder.pill`, `_decorate`, `Connector`
**Requirement**: ANN-04, ANN-05, ANN-06, ANN-07, ANN-17

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] node swatch copies fill/stroke/width/dash/radius of the first matching node; edge sample copies colour/width/dash/markers
- [x] steps listed ascending with badges identical to the diagram's
- [x] Gate check passes: `uv run pytest tests/test_annotations.py -q`

**Tests**: unit
**Gate**: quick

---

### T8: Step badges

**What**: Numbered circular badges on edges (beside the label) and node corners.
**Where**: `src/spinagram/annotate.py`
**Depends on**: T7
**Reuses**: connector geometry
**Requirement**: ANN-13, ANN-14, ANN-18

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] edge badge at the label's right edge + gap, or the path midpoint; node badge centred on the top-left corner
- [x] badge never overlaps the edge label
- [x] Gate check passes: `uv run pytest tests/test_annotations.py -q`

**Tests**: unit
**Gate**: quick

---

### T9: Callouts

**What**: Bubble with title/text/glyph in the kind colour, leader line, auto side placement.
**Where**: `src/spinagram/annotate.py`
**Depends on**: T8
**Reuses**: rect overlap helpers
**Requirement**: ANN-20, ANN-21, ANN-22, ANN-23, ANN-24

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] auto side: first of top/right/bottom/left that fits and avoids nodes, zones, panels, callouts
- [x] explicit side honoured; no side fits → first side + overlap flagged
- [x] Gate check passes: `uv run pytest tests/test_annotations.py -q`

**Tests**: unit
**Gate**: quick

---

### T10: Builder integration

**What**: `_Builder.build` calls the annotator at fixed points; scene carries annotation issues.
**Where**: `src/spinagram/layout.py`
**Depends on**: T9
**Reuses**: `build`, `build_scene`
**Requirement**: ANN-07, ANN-13, ANN-20

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] annotated diagram renders badges, panels and callouts; unannotated output byte-identical
- [x] Gate check passes: `uv run pytest -q`

**Tests**: integration
**Gate**: full

---

### T11: Note variants

**What**: Render `card` (accent bar) and `quote` (quote mark, italic body); `sticky` unchanged; icons.
**Where**: `src/spinagram/layout.py`
**Depends on**: T10
**Reuses**: `box`
**Requirement**: ANN-26, ANN-27, ANN-28, ANN-30

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] card has a 6 px primary bar on the left; quote has a quote glyph and italic body; sticky identical to before
- [x] Gate check passes: `uv run pytest tests/test_annotations.py -q`

**Tests**: unit
**Gate**: quick

---

### T12: Annotation checks

**What**: `check` reports legend unused, duplicate steps, band overflow/overlap, callout overlap.
**Where**: `src/spinagram/qa.py`
**Depends on**: T11
**Reuses**: `check`, `Issue`
**Requirement**: ANN-03, ANN-11, ANN-12, ANN-16, ANN-24

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] each issue kind reported with the spec wording; clean annotated diagram has 0 issues
- [x] Gate check passes: `uv run pytest tests/test_annotations.py -q`

**Tests**: unit
**Gate**: quick

---

### T13: Native output in every backend

**What**: Integration tests: SVG, PPTX and Figma output carry badges, panels, bubbles as native shapes with text.
**Where**: `tests/test_annotations.py`
**Depends on**: None (previous phase completes first)
**Reuses**: backends
**Requirement**: ANN-13, ANN-20, ANN-07

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] PPTX shapes for badge (circle), legend card and callout with editable text; Figma script creates them
- [x] Gate check passes: `uv run pytest -q`

**Tests**: integration
**Gate**: full

---

### T14: Showcase: AWS legends and steps

**What**: AWS01 and AWS02 get an automatic legend and numbered steps.
**Where**: `examples/showcase/aws_three_tier.py`
**Depends on**: None (previous phase completes first)
**Reuses**: showcase css
**Requirement**: ANN-36

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `check` 0 issues; PNG reviewed
- [x] Gate check passes: `build gate`

**Tests**: none
**Gate**: build

---

### T15: Showcase: callouts on K8s and GCP

**What**: K8S01, K8S02 and GCP01 get legends and callouts.
**Where**: `examples/showcase/k8s_platform.py`
**Depends on**: T14
**Reuses**: showcase css
**Requirement**: ANN-37

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `check` 0 issues; PNG reviewed
- [x] Gate check passes: `build gate`

**Tests**: none
**Gate**: build

---

### T16: Showcase: notes slide

**What**: A new showcase diagram with the three note variants; skill examples synced.
**Where**: `examples/showcase/notes.py`
**Depends on**: T15
**Reuses**: notes
**Requirement**: ANN-38, ANN-39

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `check examples/showcase` 0 issues; skill examples identical
- [x] Gate check passes: `build gate`

**Tests**: none
**Gate**: build

---

### T17: Documentation

**What**: Annotations docs page, CSS reference rows, skill guidance.
**Where**: `docs/content/docs/annotations.mdx`
**Depends on**: T16
**Reuses**: docs
**Requirement**: ANN-01, ANN-13, ANN-20, ANN-26, ANN-31

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] docs build; skill mentions annotations
- [x] Gate check passes: `build gate`

**Tests**: none
**Gate**: build

---

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | start of phase | ✅ |
| T2 | T1 | T1 → T2 | ✅ |
| T3 | None | start of phase | ✅ |
| T4 | T3 | T3 → T4 | ✅ |
| T5 | None | start of phase | ✅ |
| T6 | T5 | T5 → T6 | ✅ |
| T7 | T6 | T6 → T7 | ✅ |
| T8 | T7 | T7 → T8 | ✅ |
| T9 | T8 | T8 → T9 | ✅ |
| T10 | T9 | T9 → T10 | ✅ |
| T11 | T10 | T10 → T11 | ✅ |
| T12 | T11 | T11 → T12 | ✅ |
| T13 | None | start of phase | ✅ |
| T14 | None | start of phase | ✅ |
| T15 | T14 | T14 → T15 | ✅ |
| T16 | T15 | T15 → T16 | ✅ |
| T17 | T16 | T16 → T17 | ✅ |

## Test Co-location Validation

| Task | Code Layer | Matrix Requires | Task Says | Status |
| ---- | ---------- | --------------- | --------- | ------ |
| T1 | Model/annotate/qa | unit | unit | ✅ |
| T2 | Model/annotate/qa | unit | unit | ✅ |
| T3 | Config/showcase/docs | none | none | ✅ |
| T4 | Model/annotate/qa | unit | unit | ✅ |
| T5 | Model/annotate/qa | unit | unit | ✅ |
| T6 | Model/annotate/qa | unit | unit | ✅ |
| T7 | Model/annotate/qa | unit | unit | ✅ |
| T8 | Model/annotate/qa | unit | unit | ✅ |
| T9 | Model/annotate/qa | unit | unit | ✅ |
| T10 | Integration | integration | integration | ✅ |
| T11 | Model/annotate/qa | unit | unit | ✅ |
| T12 | Model/annotate/qa | unit | unit | ✅ |
| T13 | Integration | integration | integration | ✅ |
| T14 | Config/showcase/docs | none | none | ✅ |
| T15 | Config/showcase/docs | none | none | ✅ |
| T16 | Config/showcase/docs | none | none | ✅ |
| T17 | Config/showcase/docs | none | none | ✅ |

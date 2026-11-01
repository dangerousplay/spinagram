# Rust core: CSS selector matching and cascade Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Spec**: `.specs/features/rust-core-css/spec.md`
**Design**: inline (spec Assumptions table). Boundary: Python → JSON (tree + rules) → Rust → per element/pseudo matched declarations in cascade order with resolved values → Python typing/warnings/trace.
**Status**: In Progress

---

## Test Coverage Matrix

> Guidelines found: `pyproject.toml`, `.github/workflows/ci.yml`, `.specs/LESSONS.md` (L-001, L-014, L-020: every selector feature and every pseudo-element in every consumer). Strong defaults.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Rust core (`css.rs`) | unit | every selector feature, specificity rule, cascade level, `var()` form; expected values from Python | `#[cfg(test)]` | `cd rust && cargo test -p spinagram-core` |
| Python `css.py` dispatch + binding | integration | Rust vs Python equality per AC; dispatch; colour error | `tests/test_rust_css.py` (`importorskip` for binding cases) | quick command after the Wheel gate |
| Bench | none | - | `rust/bench/css_parity.py` | listed per task |

## Gate Check Commands

Same as `rust-core-svg-png/tasks.md` (Quick, Rust, Wheel, Full, Build). Build adds `rust/bench/css_parity.py` (from T7 on).

Baseline before T1: **2709 passed, 3 skipped, 1 deselected** in both modes. Always `--no-sync`. Before trusting any Rust-mode run, confirm `import spinagram_core` works (macOS linker workaround, see `rust/README.md`): a failed import silently falls back to Python.

---

## Execution Plan

### Phase 1: Selectors and matching in Rust

```
T1 → T2 → T3
```

### Phase 2: Cascade and integration

```
T4 → T5 → T6
```

### Phase 3: Parity and CI

```
T7 → T8
```

---

## Task Breakdown

### T1: Parse selectors in Rust

**What**: `css.rs`: port of `_TOKEN`, `_split_top`, `_parse_one`, `parse_selectors` and `specificity` for accepted selectors.
**Where**: `rust/spinagram-core/src/css.rs`
**Depends on**: None
**Reuses**: `regex`
**Requirement**: CSS-02

**Done when**:

- [x] Rust tests: structure + specificity equal Python's (expected values taken from Python) for each supported feature incl. nested `:not`, `::label` alone, selector lists (L-020)
- [x] Rust gate passes

**Tests**: unit (Rust)
**Gate**: rust
**Commit**: `feat(rust): parse css selectors`

---

### T2: Match selectors in Rust

**What**: Element tree type (parent, children, type, kinds, id, classes, attrs) and right-to-left `matches` with `_match_compound` semantics.
**Where**: `rust/spinagram-core/src/css.rs`
**Depends on**: T1
**Reuses**: T1 types
**Requirement**: CSS-03

**Done when**:

- [x] Rust tests: one per selector feature and edge case (root element siblings, `:root`, `:not(list)`, attr presence vs value, quoted/unquoted) with expected match sets from Python
- [x] Rust gate passes

**Tests**: unit (Rust)
**Gate**: rust
**Commit**: `feat(rust): match css selectors against the style tree`

---

### T3: Cascade order and var() in Rust

**What**: `cascade(tree, rules)`: per element and pseudo-element the declared list sorted by `(important, specificity, order, index)` with inline levels 1/3; custom-property scope; `substitute()` port; output entries `(rule, selector, decl, resolved|None)`.
**Where**: `rust/spinagram-core/src/css.rs`
**Depends on**: T2
**Reuses**: T1, T2
**Requirement**: CSS-04, CSS-05

**Done when**:

- [x] Rust tests: each cascade level ordering (normal < inline < important < inline important), specificity ties broken by order then index (CSS-04)
- [x] Rust tests: `var()` nested, fallback with `rgb(1, 2, 3)`, unknown → token name, 9-level nesting stops after 8 (CSS-05)
- [x] Rust gate passes

**Tests**: unit (Rust)
**Gate**: rust
**Commit**: `feat(rust): order the css cascade and substitute var()`

---

### T4: Expose the cascade to Python

**What**: Binding `css_cascade(tree_json, rules_json) -> json` and `css_select(tree_json, selector_texts) -> [indices]`.
**Where**: `rust/spinagram-core-py/src/lib.rs` (+ `__init__.py`, `tests/test_rust_css.py`)
**Depends on**: None (Phase 1 complete)
**Reuses**: binding patterns
**Requirement**: CSS-02, CSS-03

**Done when**:

- [x] Test (importorskip): for a fixture tree and every selector feature, binding match sets equal Python `matches` (CSS-03)
- [x] Wheel + quick gate pass

**Tests**: integration
**Gate**: quick
**Commit**: `feat(rust): expose the css cascade to python`

---

### T5: Use the Rust cascade in compute()

**What**: `css.compute()` builds the JSON once, calls the core when active, and runs the existing typing/warnings/trace loop over the returned entries; custom-property entries skipped as before; `CssValueError` unchanged.
**Where**: `src/spinagram/css.py` (+ `tests/test_rust_css.py`)
**Depends on**: T4
**Reuses**: `resolve()` body
**Requirement**: CSS-01, CSS-08, CSS-09

**Done when**:

- [ ] Test: for every example diagram and every fixture in `tests/test_css*.py`, `compute` values, warnings and trace equal across modes (CSS-01)
- [ ] Test: core inactive → core never called (CSS-08)
- [ ] Test: unresolvable colour raises the same message in both modes (CSS-09)
- [ ] Build gate passes (both modes, SVGs byte-identical)

**Tests**: integration
**Gate**: build
**Commit**: `feat(css): compute the cascade in the rust core when enabled`

---

### T6: Use the Rust matcher in select() and inspect()

**What**: `select()` and `inspect()`'s unused-selector scan use the core when active.
**Where**: `src/spinagram/css.py` (+ `tests/test_rust_css.py`)
**Depends on**: T5
**Reuses**: T4 binding
**Requirement**: CSS-06, CSS-07

**Done when**:

- [ ] Test: `select()` keys equal across modes for every selector feature (CSS-06)
- [ ] Test: `inspect()` report equal across modes for every example (CSS-07)
- [ ] Build gate passes

**Tests**: integration
**Gate**: build
**Commit**: `feat(css): select and inspect through the rust matcher`

---

### T7: CSS parity and speed harness

**What**: `css_parity.py`: `inspect()` equality across modes for every example and ≥ 1,000 seeded random (tree, stylesheet) pairs covering every selector feature and `var()` form; timing on the 500-node/200-rule benchmark; exit 1 on difference.
**Where**: `rust/bench/css_parity.py`
**Depends on**: None (Phase 2 complete)
**Reuses**: other bench scripts
**Requirement**: PAR-21

**Done when**:

- [ ] Run: N/N identical, timing table, exit 0; ≥ 5x on the benchmark (recorded)
- [ ] A one-token fault in `css.rs` (scratch) makes it exit 1
- [ ] Build gate passes

**Tests**: none
**Gate**: build
**Commit**: `test(bench): add css parity and speed harness`

---

### T8: CI and docs

**What**: CI `rust` job runs `css_parity.py`; README documents the CSS slice and numbers.
**Where**: `.github/workflows/ci.yml` (+ `rust/README.md`)
**Depends on**: T7
**Reuses**: existing job
**Requirement**: PAR-22

**Done when**:

- [ ] Workflow parses; step present; other jobs unchanged (PAR-22)
- [ ] Build gate passes

**Tests**: none
**Gate**: build
**Commit**: `ci: check css parity and document the css slice`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3

Phase 1:  T1 ------→ T2 ------→ T3
Phase 2:  T4 ------→ T5 ------→ T6
Phase 3:  T7 ------→ T8
```

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1 | selector parser | ✅ |
| T2 | matcher | ✅ |
| T3 | cascade + substitute | ⚠️ cohesive |
| T4 | 2 bindings | ✅ |
| T5 | 1 function | ✅ |
| T6 | 2 call sites | ✅ |
| T7 | 1 script | ✅ |
| T8 | CI step + doc | ⚠️ cohesive |

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | start of Phase 1 | ✅ |
| T2 | T1 | T1 → T2 | ✅ |
| T3 | T2 | T2 → T3 | ✅ |
| T4 | None (Phase 1 complete) | start of Phase 2 | ✅ |
| T5 | T4 | T4 → T5 | ✅ |
| T6 | T5 | T5 → T6 | ✅ |
| T7 | None (Phase 2 complete) | start of Phase 3 | ✅ |
| T8 | T7 | T7 → T8 | ✅ |

## Test Co-location Validation

| Task | Code Layer | Matrix Requires | Task Says | Status |
| ---- | ---------- | --------------- | --------- | ------ |
| T1 | Rust core | unit | unit (Rust) | ✅ |
| T2 | Rust core | unit | unit (Rust) | ✅ |
| T3 | Rust core | unit | unit (Rust) | ✅ |
| T4 | binding | integration | integration | ✅ |
| T5 | dispatch | integration | integration | ✅ |
| T6 | dispatch | integration | integration | ✅ |
| T7 | bench | none | none | ✅ |
| T8 | CI + docs | none | none | ✅ |

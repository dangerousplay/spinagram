# Rust core: scene model, SVG drawing and PNG Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Spec**: `.specs/features/rust-core-svg-png/spec.md`
**Design**: inline (Assumptions table of the spec + notes per task); the routing slice's patterns apply (`src/spinagram/rust.py`, import-time switch, data across the boundary, `py.detach`).
**Status**: In Progress

---

## Test Coverage Matrix

> Guidelines found: `pyproject.toml` (pytest, ruff), `.github/workflows/ci.yml`, `.specs/LESSONS.md` confirmed lessons L-001 (hash across PYTHONHASHSEED), L-014 (one assertion per clause), L-020 (cover every enum value in every consumer: every `Item` type, every marker kind, every `Part.paint`). No coverage threshold - strong defaults.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Python modules (`scene_json`, `backends/svg`, `backends/png`) | unit | 1:1 to spec ACs, every edge case, one assertion per clause | `tests/test_*.py` | `uv run --all-extras --no-sync pytest -q -p no:cacheprovider <files>` |
| Rust core (`scene.rs`, `pyfmt.rs`, `svg.rs`, `png.rs`) | unit | every branch; every Item type, marker kind, `Part.paint` value; Python-derived expected strings | `#[cfg(test)]` in each file | `cd rust && cargo test -p spinagram-core` |
| PyO3 bindings + dispatch | integration | Rust vs Python byte identity per AC; dispatch rules | `tests/test_rust_svg.py`, `tests/test_rust_png.py` (`importorskip("spinagram_core")` for binding cases) | quick command after the Wheel gate |
| Bench / schema | none (scripts are the parity check) | - | `rust/bench/*`, `rust/schema/*` | listed per task |

## Gate Check Commands

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | Python unit tests of the task | `uv run --all-extras --no-sync pytest -q -p no:cacheprovider <test files>` |
| Rust | Rust-only tasks | `cd rust && cargo test && cargo clippy --all-targets -- -D warnings` |
| Wheel | Before tests importing `spinagram_core` | `cd rust/spinagram-core-py && uvx maturin build --release -o ../target/wheels && cd ../.. && uv pip install --reinstall rust/target/wheels/spinagram_core-*.whl` |
| Full | Integration tasks | Wheel gate; `uv run --all-extras --no-sync ruff check src tests examples`; pytest `-q -p no:cacheprovider --deselect tests/test_web_unit.py::test_web_unit_tests_pass` pure Python **and** with `SPINAGRAM_RUST=1` |
| Build | Last task of a phase, config/doc tasks | Full + Rust gates + `bash rust/bench/render_all.sh` in both modes equal to a baseline rendered at the feature's start commit |

Baseline before T1: **2666 passed, 3 skipped, 1 deselected** in both modes. Always `--no-sync`.

---

## Execution Plan

### Phase 1: Scene model

```
T1 → T2 → T3 → T4
```

### Phase 2: SVG drawing in Rust

```
T5 → T6 → T7 → T8
```

### Phase 3: PNG and parity

```
T9 → T10 → T11 → T12
```

---

## Task Breakdown

### T1: Serialize scenes to versioned JSON

**What**: `spinagram/scene_json.py` with `dumps(scene) -> str` and `to_dict(scene)`: `"version": 1`, every field `to_svg`/`Scene.fonts()` read, items tagged by type (`shape`, `connector`, `text`, `line`, `image`, `table`), nested `Label`/`TextBlock`/`Run`/`FontRef`/`Icon`/`Part`/`Cell`/`Binding`, paths as absolute strings, tuples as arrays.
**Where**: `src/spinagram/scene_json.py` (+ `tests/test_scene_json.py`)
**Depends on**: None
**Reuses**: `scene.py` dataclasses, `shapes.Part`
**Requirement**: SCN-01

**Done when**:

- [x] Test: `version == 1` and each of the 6 item types appears with its tag and fields for a scene built to contain all of them (L-020) (SCN-01)
- [x] Test: width, height, background, title, sources, item_facts, meta_tooltips present with their values (SCN-01, one assertion each, L-014)
- [x] Baseline for the Build gate rendered: `render_all.sh` at the commit before T1 into the scratchpad (pure Python, `fonts` default)
- [x] Quick gate passes

**Tests**: unit
**Gate**: quick
**Commit**: `feat(scene): serialize scenes to versioned json`

---

### T2: Rust scene types with serde

**What**: `scene.rs`: serde structs/enums mirroring the JSON (`#[serde(tag = "type")]` items), `parse(json) -> Result<Scene, String>` rejecting `version != 1` with "scene version X is not supported (expected 1)", and `to_json`.
**Where**: `rust/spinagram-core/src/scene.rs` (+ `serde`, `serde_json` deps, `pub mod scene;`)
**Depends on**: T1
**Reuses**: none
**Requirement**: SCN-02, SCN-05

**Done when**:

- [x] Rust tests: a JSON fixture with every item type round-trips to an equal `serde_json::Value` (SCN-02)
- [x] Rust test: `version: 2` errors with the exact message naming 2 and 1 (SCN-05)
- [x] Rust gate passes

**Tests**: unit (Rust)
**Gate**: rust
**Commit**: `feat(rust): add scene types to spinagram-core`

---

### T3: Generate and commit the scene JSON Schema

**What**: `schemars` derives on the scene types; a `scene-schema` binary (or `#[test]` writer) emits `rust/schema/scene.schema.json`; a Rust test compares the committed file with a fresh generation.
**Where**: `rust/schema/scene.schema.json` (+ derive attributes in `scene.rs`, generator)
**Depends on**: T2
**Reuses**: none
**Requirement**: SCN-03

**Done when**:

- [x] Committed schema exists; the freshness test fails when a field is added without regenerating (checked in scratch) (SCN-03)
- [x] Rust gate passes

**Tests**: unit (Rust)
**Gate**: rust
**Commit**: `feat(rust): publish the scene json schema`

---

### T4: Round-trip and validate every example scene

**What**: Binding `scene_roundtrip(json) -> json` exported from `spinagram_core`; pytest over every example scene: round-trip equal (SCN-02) and `jsonschema` validation against the committed schema (SCN-04); version error surfaces as `ValueError` (SCN-05).
**Where**: `rust/spinagram-core-py/src/lib.rs` (+ `__init__.py` export, `tests/test_scene_json.py`)
**Depends on**: T3
**Reuses**: example discovery from `rust/bench/route_parity.py`
**Requirement**: SCN-02, SCN-04, SCN-05

**Done when**:

- [x] Test: every example scene round-trips equal (count asserted > 40 scenes) (SCN-02)
- [x] Test: every example scene validates against `rust/schema/scene.schema.json` (SCN-04)
- [x] Test: `version: 2` raises `ValueError` with the Rust message (SCN-05)
- [x] Build gate passes (`jsonschema` importable under `uv sync --all-extras`; if not, add it to the `dev` dependency group in this task)

**Tests**: integration
**Gate**: build
**Commit**: `test(scene): round-trip and validate every example scene`

---

### T5: Split the Python SVG writer into draw and assemble

**What**: Refactor `_Svg.render` into `_draw()` (items → `defs/back/mid/front/chars`) and `_assemble(defs, back, mid, front, chars)` (faces, head, metadata, hash). No behaviour change.
**Where**: `src/spinagram/backends/svg.py`
**Depends on**: None (Phase 1 complete)
**Reuses**: existing code
**Requirement**: SVG-07

**Done when**:

- [x] Existing SVG/font tests pass unchanged (`tests/test_cd_fonts.py`, `tests/test_css*.py`, backend tests)
- [x] `render_all.sh` equals the T1 baseline (pure Python) (SVG-07)
- [x] Quick gate on the SVG-related test files passes

**Tests**: unit (existing; refactor only)
**Gate**: quick
**Commit**: `refactor(svg): split drawing from assembly`

---

### T6: Python number formatting and escaping in Rust

**What**: `pyfmt.rs`: `f1(x)` = `format(x, ".1f")`, `g(x)` = `format(x, "g")` (precision 6, Python's exponent and trailing-zero rules), `esc(s)` / `attr(s)` = `html.escape` with `quote=False` / `True`.
**Where**: `rust/spinagram-core/src/pyfmt.rs`
**Depends on**: T5
**Reuses**: none
**Requirement**: SVG-02, SVG-03

**Done when**:

- [ ] Rust tests with expected strings taken from Python for every value listed in SVG-02, for both formats (one assertion per value) (SVG-02)
- [ ] Rust tests for `& < > " '` and non-ASCII in both escape modes (SVG-03)
- [ ] Rust gate passes

**Tests**: unit (Rust)
**Gate**: rust
**Commit**: `feat(rust): match python number formatting and html escaping`

---

### T7: Draw scene items in Rust

**What**: `svg.rs`: port `_Svg` drawing (text_lines with runs/fallback tspans, label placement, image data URIs, markers, shadow filters, tooltips, shapes incl. parts/diamond/rect, connectors incl. curve, table and cells, Text/Line/Image items, layer rules) returning `(defs, back, mid, front, chars)`.
**Where**: `rust/spinagram-core/src/svg.rs` (+ `base64` dep)
**Depends on**: T6
**Reuses**: `pyfmt`, `scene`
**Requirement**: SVG-04, SVG-05, SVG-06, SVG-08

**Done when**:

- [ ] Rust tests: one per item type, per marker kind (`arrow`, `open-arrow`, `diamond`, `open-diamond`, `circle`, `bar`), per `Part.paint` (`solid`, `stroke`, default) with expected fragments taken from the Python writer (L-020)
- [ ] Rust tests: image data URI (SVG-04), marker/filter id and order (SVG-05), tooltip (SVG-06), chars per face incl. the empty-line no-break space (SVG-08)
- [ ] Missing image path returns an error naming the path (edge case)
- [ ] Rust gate passes

**Tests**: unit (Rust)
**Gate**: rust
**Commit**: `feat(rust): draw scene items as svg`

---

### T8: Expose SVG drawing and dispatch to_svg

**What**: Binding `svg_draw(scene_json) -> (defs, back, mid, front, chars)`; `to_svg` uses it when the core is active, then `_assemble`; missing image → `FileNotFoundError`.
**Where**: `src/spinagram/backends/svg.py` (+ binding in `lib.rs`, `tests/test_rust_svg.py`)
**Depends on**: T7
**Reuses**: `scene_json.dumps`, `rust.core()`
**Requirement**: SVG-01, SVG-07, SVG-08

**Done when**:

- [ ] Test: for every example scene and each `fonts` mode, Rust-mode `to_svg` == Python-mode `to_svg` (SVG-01, one parametrized assertion per mode)
- [ ] Test: core inactive → Python path used (spy) (SVG-07)
- [ ] Test: `chars` from Rust equal Python's per face for a scene with fallback runs and empty lines (SVG-08)
- [ ] Build gate passes (both modes; `render_all.sh` both modes == T1 baseline)

**Tests**: integration
**Gate**: build
**Commit**: `feat(svg): draw svg in the rust core when enabled`

---

### T9: Render PNG with resvg in Rust

**What**: `png.rs`: `render_png(svg, width, height, scale, font_files) -> Vec<u8>` with `resvg`/`usvg`/`tiny-skia`, fontdb loaded with the given font files, then system fonts; output `round(W*s)` × `round(H*s)`.
**Where**: `rust/spinagram-core/src/png.rs` (+ `resvg` dep)
**Depends on**: None (Phase 2 complete)
**Reuses**: none
**Requirement**: PNG-03, PNG-04

**Done when**:

- [ ] Rust test: a 300×200 SVG at scale 1.5 gives a 450×300 PNG (decode header) (PNG-03)
- [ ] Rust test: text rendered with a given font file differs from the same text with a different font file (pixel comparison), proving the file is used (PNG-04)
- [ ] Rust gate passes

**Tests**: unit (Rust)
**Gate**: rust
**Commit**: `feat(rust): render png with resvg`

---

### T10: Use resvg in the PNG backend

**What**: Binding `render_png`; `PngBackend` picks resvg when the core is active and `SPINAGRAM_PNG` is unset/`resvg`, Playwright when `SPINAGRAM_PNG=chromium` or no core; passes `Scene.fonts()` files + bundled fonts.
**Where**: `src/spinagram/backends/png.py` (+ binding, `tests/test_rust_png.py`)
**Depends on**: T9
**Reuses**: `text.BUNDLED`, `to_svg`
**Requirement**: PNG-01, PNG-02, PNG-06

**Done when**:

- [ ] Test: core active, Playwright import blocked (`sys.modules["playwright"] = None`), PNG written with the right size (PNG-01, PNG-03)
- [ ] Test: `SPINAGRAM_PNG=chromium` calls the Playwright path (spy) (PNG-02)
- [ ] Test: core inactive and Playwright missing → the existing RuntimeError text (PNG-06)
- [ ] Build gate passes

**Tests**: integration
**Gate**: build
**Commit**: `feat(png): render png with resvg when the rust core is enabled`

---

### T11: SVG and PNG parity harness

**What**: `svg_png_parity.py`: SVG byte identity per font mode over every example; PNG similarity vs Chromium at scale 1 (mean |Δ| ≤ 8, > 64 share ≤ 2 %) when Chromium is available; timings (SVG Python vs Rust, PNG Chromium vs resvg); exit 1 on any SVG difference or similarity breach; `--svg-only` flag for CI.
**Where**: `rust/bench/svg_png_parity.py`
**Depends on**: T10
**Reuses**: `rust/bench/route_parity.py` structure
**Requirement**: PAR-11, PNG-05

**Done when**:

- [ ] Run reports N/N identical per font mode, per-example PNG similarity within bounds, timing table; exit 0 (PAR-11, PNG-05)
- [ ] A one-character fault in `pyfmt.rs` makes it exit 1 (scratch, discarded)
- [ ] SVG identity holds under `PYTHONHASHSEED` 0, 1, 2 (L-001)
- [ ] Build gate passes

**Tests**: none
**Gate**: build
**Commit**: `test(bench): add svg and png parity harness`

---

### T12: CI and docs

**What**: CI `rust` job runs `svg_png_parity.py --svg-only` and the schema freshness test (already in `cargo test`); `rust/README.md` documents the scene JSON, schema, SVG/PNG slices, `SPINAGRAM_PNG`, and measured numbers.
**Where**: `.github/workflows/ci.yml` (+ `rust/README.md`)
**Depends on**: T11
**Reuses**: existing `rust` job
**Requirement**: PAR-12

**Done when**:

- [ ] Workflow parses; new step present; other jobs unchanged (PAR-12)
- [ ] README updated with numbers from T11
- [ ] Build gate passes

**Tests**: none
**Gate**: build
**Commit**: `ci: check svg parity and document the scene and png slices`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3

Phase 1:  T1 ------→ T2 ------→ T3 ------→ T4
Phase 2:  T5 ------→ T6 ------→ T7 ------→ T8
Phase 3:  T9 ------→ T10 -----→ T11 -----→ T12
```

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1 | 1 module | ✅ |
| T2 | 1 Rust module | ✅ |
| T3 | schema + generator | ⚠️ cohesive |
| T4 | 1 binding + tests | ✅ |
| T5 | 1 refactor | ✅ |
| T6 | 1 Rust module | ✅ |
| T7 | 1 Rust module (port of the drawing half of 1 Python module) | ⚠️ cohesive: one writer |
| T8 | 1 binding + dispatch | ✅ |
| T9 | 1 Rust module | ✅ |
| T10 | 1 backend change | ✅ |
| T11 | 1 script | ✅ |
| T12 | CI step + doc | ⚠️ cohesive |

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | start of Phase 1 | ✅ |
| T2 | T1 | T1 → T2 | ✅ |
| T3 | T2 | T2 → T3 | ✅ |
| T4 | T3 | T3 → T4 | ✅ |
| T5 | None (Phase 1 complete) | start of Phase 2 | ✅ |
| T6 | T5 | T5 → T6 | ✅ |
| T7 | T6 | T6 → T7 | ✅ |
| T8 | T7 | T7 → T8 | ✅ |
| T9 | None (Phase 2 complete) | start of Phase 3 | ✅ |
| T10 | T9 | T9 → T10 | ✅ |
| T11 | T10 | T10 → T11 | ✅ |
| T12 | T11 | T11 → T12 | ✅ |

## Test Co-location Validation

| Task | Code Layer | Matrix Requires | Task Says | Status |
| ---- | ---------- | --------------- | --------- | ------ |
| T1 | Python module | unit | unit | ✅ |
| T2 | Rust core | unit | unit (Rust) | ✅ |
| T3 | Rust core | unit | unit (Rust) | ✅ |
| T4 | binding | integration | integration | ✅ |
| T5 | Python module | unit | unit (existing) | ✅ |
| T6 | Rust core | unit | unit (Rust) | ✅ |
| T7 | Rust core | unit | unit (Rust) | ✅ |
| T8 | binding + dispatch | integration | integration | ✅ |
| T9 | Rust core | unit | unit (Rust) | ✅ |
| T10 | binding + backend | integration | integration | ✅ |
| T11 | bench | none | none | ✅ |
| T12 | CI + docs | none | none | ✅ |

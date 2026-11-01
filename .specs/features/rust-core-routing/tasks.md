# Rust core routing + YAML loading Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Spec**: `.specs/features/rust-core-routing/spec.md`
**Design**: `.specs/features/rust-core-routing/design.md`
**Status**: In Progress

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec. Guidelines found: `pyproject.toml` (pytest, ruff), `.github/workflows/ci.yml`, `.specs/LESSONS.md` (confirmed lessons L-001, L-014). No coverage threshold configured - strong defaults applied.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Python engine modules (yamlload, icons, theme, yaml_io, engine/route, autolayout/route) | unit | All branches; 1:1 to spec ACs; every listed edge case; one assertion per clause (L-014) | `tests/test_*.py` | `uv run --all-extras --no-sync pytest -q -p no:cacheprovider tests/<file>` |
| Rust core (`rust/spinagram-core/src/*.rs`) | unit | Every ported branch of `_search`/`route`/`_simplify`, including round-half ties and the elbow fallback | `#[cfg(test)] mod tests` in the same file | `cd rust && cargo test -p spinagram-core` |
| PyO3 bindings + dispatch | integration | Python vs Rust identical on hand cases for ROUTE-05..10; dispatch rules ROUTE-01..03 | `tests/test_rust_route.py` (uses `pytest.importorskip("spinagram_core")` for the binding cases) | quick command on that file, after rebuilding the wheel |
| Bench / parity scripts | none (they are the parity check; run them in the gate) | - | `rust/bench/*` | listed in the task |
| CI config | none | build gate only | `.github/workflows/ci.yml` | YAML parse check + run the job's commands locally |

## Gate Check Commands

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | After tasks with Python unit tests only | `uv run --all-extras --no-sync pytest -q -p no:cacheprovider <test files of the task>` |
| Rust | After Rust-only tasks | `cd rust && cargo test && cargo clippy --all-targets -- -D warnings` |
| Wheel | Before any test that imports `spinagram_core` | `cd rust/spinagram-core-py && uvx maturin build --release -o ../target/wheels && cd ../.. && uv pip install --reinstall rust/target/wheels/spinagram_core-*.whl` |
| Full | After integration tasks | Wheel gate, then `uv run --all-extras --no-sync ruff check src tests examples` and `uv run --all-extras --no-sync pytest -q -p no:cacheprovider --deselect tests/test_web_unit.py::test_web_unit_tests_pass` and the same pytest with `SPINAGRAM_RUST=1` |
| Build | Last task of a phase, config-only tasks | Full gate + Rust gate |

Baseline before T1: **2630 passed, 3 skipped, 1 deselected** in both modes. Never use plain `uv run` without
`--no-sync`: it uninstalls the locally built wheel.

---

## Execution Plan

### Phase 1: Fast YAML in pure Python

```
T1 → T2 → T3 → T4 → T5
```

### Phase 2: Edge routing in Rust

```
T6 → T7 → T8 → T9
```

### Phase 3: Parity and CI

```
T10 → T11 → T12
```

---

## Task Breakdown

### T1: Add the render-all script for byte-identity checks

**What**: A script that renders every example folder, every top-level example file and `docs/diagrams/` to SVG in a target directory.
**Where**: `rust/bench/render_all.sh`
**Depends on**: None
**Reuses**: the loop used in the spike (`spinagram render <path> -f svg --no-gallery -o <out>/<name>`)
**Requirement**: YAML-08

**Done when**:

- [x] `bash rust/bench/render_all.sh OUT` renders 40 SVGs from the repo root
- [x] Running it twice into two directories gives `diff -r` with no output
- [x] Baseline captured: render at commit `5f33d46` (a `git worktree` under the session scratchpad) into a baseline directory for T5

**Tests**: none
**Gate**: build (ruff + the script run twice)
**Commit**: `chore(bench): add script to render every example to svg`

---

### T2: Add the yamlload module (libyaml parser + file cache)

**What**: `parse(text)` using `yaml.CSafeLoader` when `yaml.__with_libyaml__` else `yaml.SafeLoader`; `load_file(path)` cached on (absolute path, `st_mtime_ns`, `st_size`), returning a deep copy, guarded by a lock.
**Where**: `src/spinagram/yamlload.py` (+ `tests/test_yamlload.py`)
**Depends on**: T1
**Reuses**: none
**Requirement**: YAML-01, YAML-02, YAML-03, YAML-04, YAML-05

**Done when**:

- [x] Test: with libyaml present, the loader class used is `yaml.CSafeLoader` (YAML-01)
- [x] Test: with `yaml.__with_libyaml__` patched False, `SafeLoader` is used and data equals `yaml.safe_load` on a sample with booleans (`yes`/`on`), nulls, nested maps (YAML-02)
- [x] Test: two `load_file` calls on an unchanged file parse once (parser spied) (YAML-03)
- [x] Test: changing the file's content and size, and separately only its mtime, re-parses (YAML-04, both clauses)
- [x] Test: mutating the returned dict does not affect the next result (YAML-05)
- [x] Test: empty file returns None; missing file raises `FileNotFoundError` (edge cases)
- [x] Quick gate passes

**Tests**: unit
**Gate**: quick
**Commit**: `perf(yaml): add libyaml parser and stat-keyed file cache`

---

### T3: Cache icon registries

**What**: `icons._load_file` reads through `yamlload.load_file`; `registry()` caches its result keyed by every registry file's stat key (built-ins, user, project, env), the cwd and `$SPINAGRAM_ICON_PACKS`; callers get packs equal to a fresh build.
**Where**: `src/spinagram/icons.py` (+ `tests/test_icons_registry_cache.py`)
**Depends on**: T2
**Reuses**: `yamlload.load_file`
**Requirement**: YAML-03, YAML-06, YAML-07

**Done when**:

- [x] Test: second `registry()` with nothing changed reads no file (spy on `yamlload.load_file` / `_load_file`) and returns packs equal to the first (YAML-06)
- [x] Test: changing `$SPINAGRAM_ICON_PACKS` rebuilds (YAML-07 clause 1)
- [x] Test: changing cwd rebuilds (YAML-07 clause 2)
- [x] Test: editing a project registry file rebuilds and includes the new pack (YAML-07 clause 3)
- [x] `register()`/`unregister()` writes are seen by the next `registry()` (stat key changes)
- [x] Existing icon tests pass (`tests/test_icons*.py`)
- [x] Quick gate passes

**Tests**: unit
**Gate**: quick
**Commit**: `perf(icons): cache icon registries until their files change`

---

### T4: Load themes through the file cache

**What**: `theme._load_raw` reads `theme.yaml` (and parents) through `yamlload.load_file`.
**Where**: `src/spinagram/theme.py` (+ a test in `tests/test_yamlload.py`)
**Depends on**: T3
**Reuses**: `yamlload.load_file`
**Requirement**: YAML-03, YAML-05

**Done when**:

- [x] Test: `Theme.load("default")` twice parses `theme.yaml` once (YAML-03)
- [x] Test: mutating `Theme.load(...).data` does not change the next `Theme.load(...).data` (YAML-05)
- [x] Existing theme tests pass
- [x] Quick gate passes

**Tests**: unit
**Gate**: quick
**Commit**: `perf(theme): load theme files through the yaml cache`

---

### T5: Pin spec parsing to the strict loader ~~Parse spec files with libyaml~~

**What**: Dropped the libyaml switch for spec files (SPEC_DEVIATION, see spec Assumptions: libyaml accepts `title: Why?` in a flow mapping, SafeLoader rejects it). Instead, add a test that `yaml_io` still parses spec files with `yaml.SafeLoader` (the second clause of YAML-01), and confirm byte identity and the speed measurement.
**Where**: `tests/test_yamlload.py`
**Depends on**: T4
**Reuses**: existing `tests/test_engine.py::test_yaml_pitfalls_are_reported` (must keep passing, untouched)
**Requirement**: YAML-01, YAML-08

**Done when**:

- [x] Test: loading a spec file through `yaml_io` uses `yaml.SafeLoader`, not `CSafeLoader` (spy), even with libyaml available (YAML-01 clause 2)
- [x] `src/spinagram/yaml_io.py` unchanged; `test_yaml_pitfalls_are_reported` passes
- [x] `bash rust/bench/render_all.sh` output equals the T1 baseline (`diff -r` empty) (YAML-08)
- [x] Speed measured and recorded in the commit body: 1545 ms at `5f33d46` → after T4 (best of 3, warm)
- [x] Build gate passes (full pytest, pure Python)

**Tests**: unit
**Gate**: build
**Commit**: `test(yaml): pin spec files to the strict yaml loader`

---

### T6: Port the router to Rust

**What**: `route.rs` in spinagram-core: `ports`, `inside`, A* `search` with Python-identical ordering and cost sums, `simplify` with Python `round(x, 2)` semantics, `route` with side-pair loop, busy cost, crossing penalty as data, guides, fracs and the elbow fallback.
**Where**: `rust/spinagram-core/src/route.rs` (+ `pub mod route;` in `lib.rs`)
**Depends on**: None (Phase 1 complete)
**Reuses**: `src/spinagram/autolayout/route.py` (line-by-line), `engine/route.py::crosses`
**Requirement**: ROUTE-04, ROUTE-05, ROUTE-06, ROUTE-07, ROUTE-08, ROUTE-09, ROUTE-10

**Done when**:

- [x] Rust unit tests: `round2` of 0.125 → 0.12, 0.375 → 0.38, 2.675 → 2.67, 1.005 → 1.0, -0.125 → -0.12 (values from Python `round`) (ROUTE-10)
- [x] Rust unit test: boxed-in endpoints return the 4-point elbow from `src` bottom-middle to `dst` top-middle (ROUTE-05)
- [x] Rust unit test: a stub inside an obstacle rejects that side pair (ROUTE-06)
- [x] Rust unit test: busy side of `src` makes the route pick another side when one is free (ROUTE-07)
- [x] Rust unit test: a drawn segment across the straight path with a crossing cost makes the route go around (ROUTE-08)
- [x] Rust unit test: `fracs=(0.2, None)` starts the route at 20 % of the chosen side (ROUTE-09)
- [x] Rust gate passes (test + clippy `-D warnings`)

**Tests**: unit (Rust)
**Gate**: rust
**Commit**: `feat(rust): port orthogonal edge router to spinagram-core`

---

### T7: Make the crossing penalty a Crossings object

**What**: `Crossings(cost, drawn)` in `engine/route.py`, callable `(p, q) → cost * strict crossings`; `route_ortho` passes it instead of the closure.
**Where**: `src/spinagram/engine/route.py` (+ tests in `tests/test_engine_route.py`)
**Depends on**: T6
**Reuses**: `crosses`
**Requirement**: ROUTE-11

**Done when**:

- [x] Test: `Crossings(120, drawn)(p, q)` equals `120 * sum(crosses(p, q, *s) for s in drawn)` for crossing, touching and parallel segments (ROUTE-11)
- [x] Test: `route_ortho` passes a `Crossings` with its `penalty` and the drawn segments (spy on `route`)
- [x] Existing `tests/test_engine_route.py` and `tests/test_cd_route.py` pass unchanged
- [x] Quick gate passes

**Tests**: unit
**Gate**: quick
**Commit**: `refactor(route): pass the crossing penalty as data`

---

### T8: Expose the router in the Python bindings

**What**: `route(src, dst, obstacles, margin, sides, busy_src, busy_dst, crossing, guides, fracs) -> list[tuple[float, float]]` in the PyO3 module and `spinagram_core/__init__.py`.
**Where**: `rust/spinagram-core-py/src/lib.rs` (+ `__init__.py` export, + `tests/test_rust_route.py`)
**Depends on**: T7
**Reuses**: binding patterns from the text slice (`py.detach`)
**Requirement**: ROUTE-04, ROUTE-05, ROUTE-06, ROUTE-07, ROUTE-08, ROUTE-09

**Done when**:

- [ ] `tests/test_rust_route.py` (importorskip `spinagram_core`): the binding equals the Python router (called with the core disabled) on one case per AC ROUTE-05..09 plus fixed `sides`, empty `guides`, and obstacles containing `src`/`dst` (edge cases)
- [ ] Wheel gate + quick gate on that file pass

**Tests**: integration
**Gate**: quick (after wheel gate)
**Commit**: `feat(rust): expose the edge router to python`

---

### T9: Dispatch route() to the Rust core

**What**: `autolayout.route.route()` calls the core when `rust.core()` is active and `penalty` is None or a `Crossings`; otherwise the Python path. Busy sides are looked up for `src`/`dst` before the call.
**Where**: `src/spinagram/autolayout/route.py` (+ tests in `tests/test_rust_route.py`)
**Depends on**: T8
**Reuses**: `rust.core()`, the text slice's import-time switch
**Requirement**: ROUTE-01, ROUTE-02, ROUTE-03

**Done when**:

- [ ] Test: with the core active and `penalty=None`, the core's `route` is called (spy) and its result returned (ROUTE-01, clause None)
- [ ] Test: with the core active and a `Crossings` penalty, the core is called with `(cost, drawn)` (ROUTE-01, clause Crossings)
- [ ] Test: with the core active and a plain lambda penalty, the core is not called and the Python result is returned (ROUTE-02)
- [ ] Test: with the core inactive, the core is never called (ROUTE-03)
- [ ] Build gate passes: full suite in both modes = baseline counts (+ new tests); `render_all.sh` with `SPINAGRAM_RUST=1` equals the T1 baseline (ROUTE-04)

**Tests**: integration
**Gate**: build
**Commit**: `feat(route): run edge routing in the rust core when enabled`

---

### T10: Add the routing parity and speed harness

**What**: `route_parity.py` records every `route()` call made while building all examples (monkeypatch), adds ≥ 2,000 seeded random scenarios (boxes, sides, busy, guides, fracs, crossings), compares Python vs Rust point lists, times both on the recorded corpus (best of 3), exits 1 on any difference.
**Where**: `rust/bench/route_parity.py`
**Depends on**: None (Phase 2 complete)
**Reuses**: `rust/bench/parity.py` structure
**Requirement**: PAR-01, PAR-02

**Done when**:

- [ ] Run prints `N of N identical` for recorded calls and for random scenarios, and a timing table; exit code 0 (PAR-01, PAR-02)
- [ ] A deliberate one-character fault in `route.rs` (e.g. `BEND` 60 → 61) makes it exit 1 (checked in a scratch copy, then discarded)
- [ ] Byte identity holds under `PYTHONHASHSEED` 0, 1 and 2 with `SPINAGRAM_RUST=1` (L-001)
- [ ] Rust is ≥ 10x faster than Python on the recorded corpus (number recorded in the commit body)

**Tests**: none (the script is the parity check)
**Gate**: build
**Commit**: `test(bench): add routing parity and speed harness`

---

### T11: Run the Rust core in CI

**What**: A `rust` job in CI: checkout, Rust toolchain, `cargo test`, `cargo clippy --all-targets -- -D warnings`, build the wheel with maturin, `uv sync --locked --all-extras`, install the wheel, `SPINAGRAM_RUST=1 uv run --no-sync pytest -q`, and `route_parity.py` + `parity.py`. Existing jobs untouched.
**Where**: `.github/workflows/ci.yml`
**Depends on**: T10
**Reuses**: the `test` job's uv setup
**Requirement**: PAR-03, PAR-04, PAR-05

**Done when**:

- [ ] The workflow parses as YAML and the new job lists the steps above (PAR-03, PAR-04)
- [ ] The `test` job is unchanged (PAR-05) - `git diff` shows only additions under a new job
- [ ] Every command of the new job runs green locally in sequence
- [ ] Build gate passes

**Tests**: none
**Gate**: build
**Commit**: `ci: build the rust core and run the suite against it`

---

### T12: Document the routing slice

**What**: `rust/README.md` lists the routing slice, the `Crossings` rule, the two bench scripts and the measured numbers; spec traceability set to Implementing for all IDs.
**Where**: `rust/README.md`
**Depends on**: T11
**Reuses**: existing README layout
**Requirement**: PAR-01, PAR-02

**Done when**:

- [ ] README covers what is ported, how to run both harnesses, and the measured speed-ups from T5 and T10
- [ ] Build gate passes

**Tests**: none
**Gate**: build
**Commit**: `docs(rust): document the routing slice and parity harnesses`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3

Phase 1:  T1 ------→ T2 ------→ T3 ------→ T4 ------→ T5
Phase 2:  T6 ------→ T7 ------→ T8 ------→ T9
Phase 3:  T10 -----→ T11 -----→ T12
```

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1 | 1 script | ✅ |
| T2 | 1 module (2 functions) | ✅ |
| T3 | 1 module change | ✅ |
| T4 | 1 function change | ✅ |
| T5 | 2 call sites in 1 file | ✅ |
| T6 | 1 Rust module (port of 1 Python module) | ⚠️ cohesive: one algorithm |
| T7 | 1 class + 1 call site | ✅ |
| T8 | 1 binding function | ✅ |
| T9 | 1 function change | ✅ |
| T10 | 1 script | ✅ |
| T11 | 1 CI job | ✅ |
| T12 | 1 doc | ✅ |

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | start of Phase 1 | ✅ |
| T2 | T1 | T1 → T2 | ✅ |
| T3 | T2 | T2 → T3 | ✅ |
| T4 | T3 | T3 → T4 | ✅ |
| T5 | T4 | T4 → T5 | ✅ |
| T6 | None (Phase 1 complete) | start of Phase 2 | ✅ |
| T7 | T6 | T6 → T7 | ✅ |
| T8 | T7 | T7 → T8 | ✅ |
| T9 | T8 | T8 → T9 | ✅ |
| T10 | None (Phase 2 complete) | start of Phase 3 | ✅ |
| T11 | T10 | T10 → T11 | ✅ |
| T12 | T11 | T11 → T12 | ✅ |

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T1 | bench script | none | none | ✅ |
| T2 | Python engine module | unit | unit | ✅ |
| T3 | Python engine module | unit | unit | ✅ |
| T4 | Python engine module | unit | unit | ✅ |
| T5 | Python engine module | unit | unit | ✅ |
| T6 | Rust core | unit | unit (Rust) | ✅ |
| T7 | Python engine module | unit | unit | ✅ |
| T8 | PyO3 binding | integration | integration | ✅ |
| T9 | dispatch | integration | integration | ✅ |
| T10 | bench script | none | none | ✅ |
| T11 | CI config | none | none | ✅ |
| T12 | docs | none | none | ✅ |

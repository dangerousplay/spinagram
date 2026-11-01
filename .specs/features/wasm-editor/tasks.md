# Rich editor MVP (Rust edit operations + live edges in WASM) Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the per-task cycle.

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Spec**: `.specs/features/wasm-editor/spec.md`
**Status**: Ready

**MVP scope (decided by the orchestrator, 2026-11-01).** The full YAML → scene port is months of work and stays
out of this MVP. The MVP proves the architecture end to end with the Rust pieces that exist plus one new one:

- **New:** edit operations in Rust that patch YAML text minimally (OPS-01..04), plus a YAML source map (CTR-03).
  Shared with Python through PyO3 (OPS-05 partial) and with the browser through WASM.
- **Live edges in WASM:** while a node is dragged, the browser moves it in the scene and re-routes the edges that
  touch it, using the same Rust routing and SVG drawing code as the server (LRF-01 partial: edges only, no zone
  reflow; HST-03 partial: the draw stage is shared).
- **On release:** the Rust Move operation patches the YAML, the existing save path writes it, and the server
  re-renders the authoritative picture. Layout stays in Python for now (WSM-* pending).
- **Canvas basics:** select, drag, Delete, and highlighting the YAML range of the selection (SYN-01).

Out of this MVP: icon palette, grouping and zones from the canvas (they belong to `canvas-editor`), browser-only
mode, scene diffs (DIF-*), live QA, AI edits.

---

## Test Coverage Matrix

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Rust core (`rust/spinagram-core/src/*.rs`) | unit | Every operation, every rejection reason, byte preservation on commented fixtures | `#[cfg(test)] mod tests` + `rust/spinagram-core/tests/data/` | `cd rust && cargo test -p spinagram-core` |
| WASM crate (`rust/spinagram-wasm`) | integration | Every export, called from JS; outputs equal the PyO3 outputs on golden files | `rust/spinagram-wasm/tests/*.test.ts` (bun, nodejs target) | `cd rust/spinagram-wasm && bun test` |
| PyO3 bindings + server | integration | Patched YAML loads through `yaml_io` and renders; new endpoint returns valid scene JSON | `tests/test_rust_edit.py`, `tests/test_ui_*.py` | `uv run --all-extras pytest -q <files>` |
| Web canvas logic | unit | Pure logic (hit-test, drag state, op building, range highlight) | `web/src/*.test.ts` | `cd web && bun test` |
| CI config | none | build gate only | `.github/workflows/ci.yml` | YAML parse + run the job's commands locally |

## Gate Check Commands

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Rust | Rust-only tasks | `cd rust && cargo test && cargo clippy --all-targets -- -D warnings && cargo deny check` |
| WASM | Tasks touching the WASM crate | Rust gate, then `cargo build -p spinagram-wasm --target wasm32-unknown-unknown --release`, the wasm-bindgen step, and `bun test` in `rust/spinagram-wasm` |
| Quick | Python-only tasks | `uv run --all-extras pytest -q <test files>` |
| Full | Integration tasks | `uv sync --all-extras`, then `uv run --all-extras ruff check src tests examples` and `uv run --all-extras pytest -q --deselect tests/test_web_unit.py::test_web_unit_tests_pass`, plus the same pytest with `SPINAGRAM_RUST=0` |
| Web | Frontend tasks | `cd web && bun test && bun run build` |

Baseline before T1: 2800 tests per mode, all passing except none (record the actual numbers before starting).
`uv sync` rebuilds `src/spinagram/_core.abi3.so` from `rust/` (maturin); always pass `--all-extras`.

---

## Execution Plan

### Phase 1: Rust edit operations

```
T1 → T2 → T3
```

### Phase 2: WASM and live edges

```
T3 → T4 → T5 → T6
```

### Phase 3: Canvas and delivery

```
T6 → T7 → T8
```

---

## Task Breakdown

### T1: Make spinagram-core build for wasm32

**What**: Put file-system font loading behind a cfg or feature so fonts can also be registered from bytes; `spinagram-core` builds for `wasm32-unknown-unknown` with no change to native behaviour.
**Where**: `rust/spinagram-core/src/font.rs`, `text.rs`, `png.rs`, `Cargo.toml`
**Depends on**: None
**Reuses**: existing `Font`/`Measurer` types
**Requirement**: HST-03 (partial)

**Done when**:

- [x] `cargo build -p spinagram-core --target wasm32-unknown-unknown --release` succeeds
- [x] Test: measuring with a font registered from bytes equals measuring with the same font loaded from its path
- [x] Native `cargo test`, clippy and the existing parity scripts are unchanged

**Tests**: unit
**Gate**: rust
**Commit**: `build(rust): let spinagram-core compile for wasm32`

**Notes**: wasm32 already compiled before the change (vstd and the verified kernel are fine on wasm); the real work was `font::register` (fonts from bytes), a cfg for fs reads on wasm32, and a default `png` feature so the wasm build can drop resvg. Parity scripts run in the T3 full gate.

---

### T2: Edit operations and YAML source map in Rust

**What**: Module `edit` in spinagram-core. `srcmap(yaml) -> {id: [start, end]}` for nodes, zones and edges, and `apply_ops(yaml, ops) -> {yaml} | {error}`, with these operations:
- Move and Resize: writes the node's `at` list or `x`/`y`/`w`/`h` keys, whichever form the entry uses; zones use `x`/`y`/`w`/`h`.
- Rename: `title`.
- Delete: removes the node, every edge touching it, and its id from `children` lists and from `rows`/`columns` `nodes`.
- AddNode, Connect (`"src -> dst"` string form, `: label` optional), Disconnect.

Patches are byte ranges taken from parser spans. Pick a crate per `rust/DEPENDENCIES.md` policy (saphyr spans, or `yaml-edit`) and record the pick there.
**Where**: `rust/spinagram-core/src/edit.rs`, `rust/spinagram-core/tests/data/*.yaml`, `rust/DEPENDENCIES.md`
**Depends on**: T1
**Reuses**: YAML shapes accepted by `src/spinagram/yaml_io.py` (block and flow entries, `at: [x, y, w, h]`, string edges)
**Requirement**: OPS-01 (listed ops), OPS-02, OPS-03, OPS-04, CTR-03

**Done when**:

- [x] Test per operation on a commented fixture with both block and flow entries: the result equals a hand-written expected file, so every byte outside the patch is unchanged (OPS-02)
- [x] Test: unknown id, duplicate id on AddNode and Connect to a missing node are each rejected with a reason, and the input is returned unchanged (OPS-03)
- [x] Test: a batch with one invalid op changes nothing (OPS-04)
- [x] Test: every patched output re-parses as YAML; a patch that would not re-parse is rejected
- [x] Test: srcmap ranges slice exactly the entry text of each node, zone and edge
- [x] Rust gate passes

**Tests**: unit
**Gate**: rust
**Commit**: `feat(rust): yaml edit operations with byte-range patches`

**Notes**: Crate pick: `saphyr-parser` 0.3 event spans (see rust/DEPENDENCIES.md). Spans count characters, converted to bytes; a flow collection's end span runs over a trailing comment, so the end is found from the last child. Srcmap keys: node and zone ids, and `e0`, `e1`... for edges (the scene connector ids); ranges are byte offsets. Ops in JSON: move, resize, rename, delete, add_node, connect, disconnect. Delete removes entry lines only (a blank line or comment next to it stays).

---

### T3: Expose edit operations to Python

**What**: `_core.apply_ops(yaml, ops_json)` and `_core.yaml_srcmap(yaml)` through PyO3, plus a thin Python wrapper `spinagram.edit` (`apply_ops`, `srcmap`, `EditError`).
**Where**: `rust/spinagram-core-py/src/lib.rs`, `src/spinagram/edit.py`, `tests/test_rust_edit.py`
**Depends on**: T2
**Reuses**: `spinagram.rust.core()` loading pattern
**Requirement**: OPS-05 (Python part)

**Done when**:

- [ ] Test: Move on `examples/aws_layout.yaml` text, loaded with `yaml_io`, gives the node the new coordinates and leaves every other node equal
- [ ] Test: Delete of a node removes it and its edges in the loaded diagram, and the diagram renders without error
- [ ] Test: an invalid op raises `EditError` with the Rust reason
- [ ] Full gate passes

**Tests**: integration
**Gate**: full
**Commit**: `feat: expose yaml edit operations to python`

---

### T4: Scene re-routing for moved nodes

**What**: Rust `reroute(scene_json, moves_json) -> scene_json`, where `moves` maps node id to `[dx, dy]` (or a new box). It translates the node's shape and its own items (title, text, icon), then re-routes every connector touching a moved node with `route.rs`, against the other shapes as obstacles. If the scene JSON lacks what this needs (edge source and target ids, sides, bindings), extend `scene_json.py`, `rust/schema/scene.schema.json` and `scene.rs` together, and keep the existing schema tests green.
**Where**: `rust/spinagram-core/src/reroute.rs`, `scene.rs`, `src/spinagram/scene_json.py`, `rust/schema/scene.schema.json`
**Depends on**: T3
**Reuses**: `route.rs`, `scene.rs`, the Python orchestration in `layout.py` `_Builder.route_edges`/`edge`
**Requirement**: LRF-01 (edges part)

**Done when**:

- [ ] Test: an empty move map returns a scene equal to the input
- [ ] Test: after moving a node, every touching connector starts or ends on that node's boundary and no other connector changes
- [ ] Test: for straight two-node cases from `examples/`, the rerouted connector equals the connector from a full Python render of the moved YAML (record any tolerance and why in the test)
- [ ] Rust gate and full gate pass

**Tests**: unit
**Gate**: full
**Commit**: `feat(rust): reroute edges of moved nodes in a scene`

---

### T5: spinagram-wasm crate

**What**: New crate `rust/spinagram-wasm` (wasm-bindgen) that exports:
- `registerFont(name, bytes)`;
- `renderSvg(sceneJson) -> string`: the same drawing code the server uses (`svg.rs`). Fonts are referenced by URL instead of embedded subsets in the browser; byte-identity applies to the drawn body;
- `reroute(sceneJson, movesJson)`, `applyOps(yaml, opsJson)` and `srcmap(yaml)`.

Add a build script that produces `web/src/wasm/` (gitignored). Add the crate to the workspace and `cargo deny`.
**Where**: `rust/spinagram-wasm/`, `rust/Cargo.toml`, `web/.gitignore`, a build script (e.g. `rust/spinagram-wasm/build.sh`)
**Depends on**: T4
**Reuses**: `spinagram-core` modules; the PyO3 crate as the binding template
**Requirement**: HST-03 (partial), OPS-05 (browser part)

**Done when**:

- [ ] Golden files generated by a Python script from 3 examples (scene JSON, drawn SVG body, an op batch and its YAML result)
- [ ] bun test (nodejs target): `renderSvg` body, `applyOps` and `srcmap` equal the golden files byte-for-byte
- [ ] bun test: `reroute` then `renderSvg` on `software_architecture.yaml`'s scene; record the median ms per call in the test output and in this task's notes
- [ ] WASM gate passes; gzip size of the `.wasm` recorded in notes

**Tests**: integration
**Gate**: wasm
**Commit**: `feat(wasm): add spinagram-wasm with render, reroute and edit exports`

---

### T6: Scene endpoint in serve

**What**: `GET /api/diagrams/{key}.scene` returns the scene JSON (`scene_json.dumps`) of a diagram, with the same caching and error handling as `.svg`; it also says whether the diagram is canvas-editable (YAML spec, no layout engine). Add a font route if the browser's `renderSvg` needs font URLs.
**Where**: `src/spinagram/ui/server.py`, `src/spinagram/ui/workspace.py`, `web/src/api.ts`, a UI test file
**Depends on**: T5
**Reuses**: the `.svg` and `.source` handlers
**Requirement**: CTR-02 (partial)

**Done when**:

- [ ] Test: the endpoint returns JSON that validates against `rust/schema/scene.schema.json` for a YAML example
- [ ] Test: `editable` is false for a Python spec and for an engine-laid-out YAML, and true for a hand-placed YAML
- [ ] Test: an unknown key gives 404
- [ ] Full gate passes

**Tests**: integration
**Gate**: full
**Commit**: `feat(ui): serve scene json for the canvas`

---

### T7: Canvas mode in the diagram view

**What**: For editable diagrams, a Web Worker loads `spinagram-wasm`. The canvas works like this:
- Click selects a node by hit-testing the scene geometry, and the code panel highlights its YAML range from `srcmap` (SYN-01).
- Dragging calls `reroute` + `renderSvg` once per animation frame, so the edges follow live.
- Release calls `applyOps` Move with x/y snapped to 10 px, saves through `PUT /api/files` with the version check, and the server render replaces the preview.
- Delete/Backspace calls `applyOps` Delete and saves.

A 409 reloads and shows "File changed on disk; edit not applied". Non-editable diagrams show "Canvas editing needs a hand-placed YAML spec" and keep today's view.
**Where**: `web/src/DiagramView.tsx`, new `web/src/canvas/*.ts(x)`, `web/src/CodePanel.tsx`
**Depends on**: T6
**Reuses**: existing hooks, `api.ts`, CodeMirror setup
**Requirement**: SYN-01, LRF-01 (edges part), OPS-05 (browser part)

**Done when**:

- [ ] bun tests for pure logic: hit-test picks the topmost node, snapping, the ops built for move and delete, srcmap → editor range
- [ ] Manual check in `spinagram serve examples/aws_layout.yaml` (Chrome): drag a node, see the edges follow during the drag, release, then the YAML diff shows only that node's coordinates; Delete removes the node and its edges. Record the result in notes
- [ ] Web gate and full gate pass

**Tests**: unit
**Gate**: web
**Commit**: `feat(web): canvas mode with live edges and rust edit operations`

---

### T8: Build, CI and docs

**What**:
- The wheel's UI bundle includes the `.wasm`, and `spinagram serve` serves it with `application/wasm`.
- A CI job builds the WASM crate (with the wasm32 target and wasm-bindgen) and runs its bun tests.
- The UI bundle job builds the WASM before `bun run build`.
- Docs: `rust/README.md` and `docs/content/docs/reference/development.mdx` cover the WASM build.
- Spec traceability is updated for the requirements this MVP covers.
**Where**: `.github/workflows/ci.yml`, `rust/README.md`, `docs/content/docs/reference/development.mdx`, `.specs/features/wasm-editor/spec.md`
**Depends on**: T7
**Reuses**: existing UI bundle and rust jobs
**Requirement**: HST-01 (partial)

**Done when**:

- [ ] `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` passes, and the new job's commands run locally
- [ ] A wheel built locally contains the `.wasm`, and serve returns it with `content-type: application/wasm`
- [ ] Full gate, Rust gate and web gate pass

**Tests**: none
**Gate**: full
**Commit**: `ci: build and test spinagram-wasm and ship it in the ui bundle`

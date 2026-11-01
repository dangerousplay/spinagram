# Rich editor MVP (Rust edit operations + live edges in WASM) Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the per-task cycle.

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Spec**: `.specs/features/wasm-editor/spec.md`
**Status**: MVP done (T1–T8, validation PASS); second iteration (T9–T17) done; polish iteration (T18–T23) done; toolbar iteration (T24–T29) ready

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

### Phase 4: Editing model (Rust)

```
T8 → T9 → T10 → T11
```

### Phase 5: Canvas interactions

```
T11 → T12 → T13 → T14 → T15
```

### Phase 6: Showcase and delivery

```
T15 → T16 → T17
```

### Phase 7: Polish

```
T17 → T18 → T19 → T20 → T21 → T22 → T23
```

### Phase 8: Toolbar and smooth updates

```
T23 → T24 → T25 → T26 → T27 → T28 → T29
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

- [x] Test: Move on `examples/aws_layout.yaml` text, loaded with `yaml_io`, gives the node the new coordinates and leaves every other node equal
- [x] Test: Delete of a node removes it and its edges in the loaded diagram, and the diagram renders without error
- [x] Test: an invalid op raises `EditError` with the Rust reason
- [x] Full gate passes

**Tests**: integration
**Gate**: full
**Commit**: `feat: expose yaml edit operations to python`

**Notes**: `spinagram.edit` loads the core with `rust._load()` (not `rust.core()`) because edit ops have no pure-Python twin, so `SPINAGRAM_RUST=0` does not switch them off. `srcmap` ranges are UTF-8 byte offsets. Baseline was 2799 passed, 3 skipped per mode; now 2815 (16 new).

---

### T4: Scene re-routing for moved nodes

**What**: Rust `reroute(scene_json, moves_json) -> scene_json`, where `moves` maps node id to `[dx, dy]` (or a new box). It translates the node's shape and its own items (title, text, icon), then re-routes every connector touching a moved node with `route.rs`, against the other shapes as obstacles. If the scene JSON lacks what this needs (edge source and target ids, sides, bindings), extend `scene_json.py`, `rust/schema/scene.schema.json` and `scene.rs` together, and keep the existing schema tests green.
**Where**: `rust/spinagram-core/src/reroute.rs`, `scene.rs`, `src/spinagram/scene_json.py`, `rust/schema/scene.schema.json`
**Depends on**: T3
**Reuses**: `route.rs`, `scene.rs`, the Python orchestration in `layout.py` `_Builder.route_edges`/`edge`
**Requirement**: LRF-01 (edges part)

**Done when**:

- [x] Test: an empty move map returns a scene equal to the input
- [x] Test: after moving a node, every touching connector starts or ends on that node's boundary and no other connector changes
- [x] Test: for straight two-node cases from `examples/`, the rerouted connector equals the connector from a full Python render of the moved YAML (record any tolerance and why in the test)
- [x] Rust gate and full gate pass

**Tests**: unit
**Gate**: full
**Commit**: `feat(rust): reroute edges of moved nodes in a scene`

**Notes**: Scene JSON gained `explicit` on bindings (written only when true; schema regenerated). `_core.reroute` was added to the PyO3 crate so Python can test it end to end. Tolerance in the parity tests: 1e-9 px (same router; only last-bit float order in anchors). Limits, each recorded in the module docs of reroute.rs: zone header rects are not obstacles; connectors with a free end, bundles and bus bars are left alone; every `poly` connector is routed by the ortho router (the scene does not say elbow vs via vs ortho); `straight` connectors re-resolve facing sides but do not re-run `straight_refs`. Reroute only touches connectors whose end is on a moved shape (an obstacle moving does not reroute others). SPEC_DEVIATION: examples/software_architecture.yaml and aws_layout.yaml are engine-laid-out, so the hand-placed fixtures here and the T7 manual check use examples/decision.yaml and rust/spinagram-core/tests/data/reroute/ortho.yaml. Also added a Move-on-aws_layout test to tests/test_rust_edit.py (T3's done-when named that file).

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

- [x] Golden files generated by a Python script from 3 examples (scene JSON, drawn SVG body, an op batch and its YAML result)
- [x] bun test (nodejs target): `renderSvg` body, `applyOps` and `srcmap` equal the golden files byte-for-byte
- [x] bun test: `reroute` then `renderSvg` on `software_architecture.yaml`'s scene; record the median ms per call in the test output and in this task's notes
- [x] WASM gate passes; gzip size of the `.wasm` recorded in notes

**Tests**: integration
**Gate**: wasm
**Commit**: `feat(wasm): add spinagram-wasm with render, reroute and edit exports`

**Notes**: wasm 1,957,125 bytes raw, 632,569 bytes gzipped (opt-level s or z with fat LTO gave 591-605 KB gz, so the default release profile is kept; wasm-opt is not installed). reroute + renderSvg median 0.53-0.73 ms per call on software_architecture.yaml's scene (23 items, p95 about 1 ms), 100 calls after warm-up, nodejs target. Goldens: drawn bodies from the pure-Python writer (SPINAGRAM_RUST=0), patched YAML and source maps from PyO3, reroute output from PyO3; icons are copied into golden/icons so nothing depends on the machine's icon cache. Added to spinagram-core: `svg::register_file` (icons from bytes), `svg::document` (browser document: fonts as @font-face by URL, no sources metadata or content hash) and `svg::scene_fonts`. Extra exports beyond the list: registerFile, renderBody (the byte-identical layers), measureText (to test registerFont). wasm-bindgen-cli 0.2.130 installed with cargo install --locked.

---

### T6: Scene endpoint in serve

**What**: `GET /api/diagrams/{key}.scene` returns the scene JSON (`scene_json.dumps`) of a diagram, with the same caching and error handling as `.svg`; it also says whether the diagram is canvas-editable (YAML spec, no layout engine). Add a font route if the browser's `renderSvg` needs font URLs.
**Where**: `src/spinagram/ui/server.py`, `src/spinagram/ui/workspace.py`, `web/src/api.ts`, a UI test file
**Depends on**: T5
**Reuses**: the `.svg` and `.source` handlers
**Requirement**: CTR-02 (partial)

**Done when**:

- [x] Test: the endpoint returns JSON that validates against `rust/schema/scene.schema.json` for a YAML example
- [x] Test: `editable` is false for a Python spec and for an engine-laid-out YAML, and true for a hand-placed YAML
- [x] Test: an unknown key gives 404
- [x] Full gate passes

**Tests**: integration
**Gate**: full
**Commit**: `feat(ui): serve scene json for the canvas`

**Notes**: Response shape: {scene, editable, files}; `files` maps each icon or image path in the scene to base64 (the browser has no file system, so `renderSvg` needs the bytes: registerFile). `GET /api/fonts/{file name}` serves only fonts a rendered scene uses (404 otherwise). editable = YAML spec, alone in its file, not engine-laid-out (`d.auto`), no rows/columns/snakes. A spec that fails to load gives the same status as `.svg` (no diagrams: 404). Tests in tests/test_ui.py (6 new).

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

- [x] bun tests for pure logic: hit-test picks the topmost node, snapping, the ops built for move and delete, srcmap → editor range
- [x] Manual check in `spinagram serve examples/aws_layout.yaml` (Chrome): drag a node, see the edges follow during the drag, release, then the YAML diff shows only that node's coordinates; Delete removes the node and its edges. Record the result in notes
- [x] Web gate and full gate pass

**Tests**: unit
**Gate**: web
**Commit**: `feat(web): canvas mode with live edges and rust edit operations`

**Notes**: Manual Chrome check done (claude-in-chrome) on a copy of examples/decision.yaml served by `spinagram serve` (examples/aws_layout.yaml is engine-laid-out, so not canvas-editable: SPEC_DEVIATION, decision.yaml is the hand-placed example): Canvas on, dragged the Standard path node; edges followed during the drag; on release the YAML diff was only that node's `at` (900,220 -> 1050,320, snapped to 10); Delete removed the node entry and the `known.right -> std.left` edge, nothing else. Notes: the Canvas toggle (key c) is a new toolbar button; the code panel highlights the selected node's range when it is open (a collapsed panel highlights when opened); edits read the spec fresh from the server (api.source) and save with its version, so unsaved code-panel edits turn into the usual conflict prompt. The wasm keeps a fixed file name in the bundle (assets/spinagram_wasm_bg.wasm) so the JS does not change with the wasm bytes. The committed static bundle was rebuilt and now includes the wasm (1.96 MB, 653 KB gzip).

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

- [x] `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` passes, and the new job's commands run locally
- [x] A wheel built locally contains the `.wasm`, and serve returns it with `content-type: application/wasm`
- [x] Full gate, Rust gate and web gate pass

**Tests**: none
**Gate**: full
**Commit**: `ci: build and test spinagram-wasm and ship it in the ui bundle`

**Notes**: Wheel built with uv build contains spinagram/ui/static/assets/spinagram_wasm_bg.wasm; the sdist's workspace manifest is rewritten by maturin to drop spinagram-wasm and `cargo metadata` passes on it. serve returns application/wasm (explicit mimetypes.add_type, tested). CI: new `wasm` job; the `web` job builds the wasm first and does not compare the .wasm in the stale check (it is built per toolchain; its file name is fixed so the JS does not change). The workflow YAML parses and its commands ran locally; the taiki-e/install-action step for wasm-bindgen is not exercised until CI runs. Also restored web/.gitignore lines (node_modules/, *.tsbuildinfo) that the T5 commit had overwritten, adding src/wasm/.


---

## Second iteration scope (orchestrator, 2026-11-01)

The user asked for the next features: an editable showcase, dragging (zones, palette drop) and grouping. Behaviour
follows the untracked `.specs/features/canvas-editor/spec.md` (ZON-*, GRP-*, PAL-*, SEL-01/09). **That file belongs
to the user and is read-only: cite its IDs, never edit it.** Layout stays in Python. Live previews in the browser
use `reroute` (moves of several shapes); container reflow shows after release.

---

### T9: Reach the re-parse guard through apply_ops

**What**: Close the surviving mutant M3 (validation.md). Add a test that drives `apply_ops` into a patch that fails to re-parse, through a test-only seam if no real input can. If none exists and the guard is provably unreachable, document why in a comment and keep a seam test that asserts `apply_ops` calls the guard.
**Where**: `rust/spinagram-core/src/edit.rs`
**Depends on**: T8
**Reuses**: `checked`, the existing test helpers
**Requirement**: OPS-02, OPS-03

**Done when**:

- [x] Test: removing the `checked(...)` call in `apply_ops` makes a test fail (re-run mutant M3 in a scratch worktree, never `git stash`)
- [x] Rust gate passes

**Tests**: unit
**Gate**: rust
**Commit**: `test(rust): reach the yaml re-parse guard through apply_ops`

**Notes**: No real operation produces a non-re-parsing patch (scalars are quoted, removals take whole entries), so the guard is reached through a test seam: `apply_with(yaml, ops, patcher)`, which `apply_ops` calls with `op_patches`. Mutant M3 (checked call removed) re-run in a scratch worktree: killed. Rust tests 186 -> 187.

---

### T10: Zone and container operations in Rust

**What**: New operations in `edit.rs`, with the same byte-preserving patch rules:
- AddZone (`label`, `x`, `y`, `w`, `h`; unique id).
- Reparent (node or zone into a zone, or out to top level). It updates the zone `children` list or the node's `in:` key, whichever form the file uses; a zone cannot become its own ancestor (ZON-05).
- MoveZone, which moves the zone and every child node and child zone by the same offset in one patch set (ZON-04).
- Group (`axis` row or column, member ids ordered by x or y, `gap` 20, at the selection's top-left; appends to `rows:` or `columns:`) (GRP-01).
- Ungroup (removes the container; each member gets its rendered `x`/`y`/`w`/`h` passed in the op) (GRP-04).
- AddToContainer (at an index) and RemoveFromContainer. A container left with fewer than 2 members dissolves as in Ungroup (GRP-02, GRP-03, GRP-05).
- SetContainer (`gap`, `align`) (GRP-06).

Ops JSON shapes are documented in `src/spinagram/edit.py`.
**Where**: `rust/spinagram-core/src/edit.rs`, `rust/spinagram-core/tests/data/edit/`, `src/spinagram/edit.py`, `tests/test_rust_edit.py`
**Depends on**: T9
**Reuses**: `set_keys`, `remove_items`, `append_item`, fixtures
**Requirement**: OPS-01 (zone and group ops), canvas-editor ZON-04, ZON-05, GRP-01..06

**Done when**:

- [x] Test per operation on commented block and flow fixtures: the output equals a hand-written expected file
- [x] Test: Reparent into a descendant zone is rejected with "A zone cannot contain itself"
- [x] Test: removing the second-to-last member dissolves the container and writes the members' boxes
- [x] Python test: every patched fixture loads through `yaml_io` and the diagram has the expected zone children and containers
- [x] Rust gate and full gate pass

**Tests**: unit
**Gate**: full
**Commit**: `feat(rust): zone and row/column edit operations`

**Notes**: Ops JSON in `src/spinagram/edit.py`: `add_zone`, `reparent` (`parent` null = top level), `move_zone` (new x/y; children shift by the same offset, a container holding the zone's children shifts too), `group`, `ungroup` (`boxes`), `add_to_container` (`index`), `remove_from_container` (`boxes`), `set_container`. Container ids are positional like the scene's (`row0`, `column1`: every `rows` entry then every `columns` entry), and `srcmap` now lists them. SPEC_DEVIATION: a node's `in:` names a group, not a zone, so Reparent only edits zones' `children` lists and rejects a node that has `in:` ("placed by a group"). `align` is rejected for a container without `zone:` (the loader refuses it). Inline container members (mappings under `nodes:`) become flow-style top-level nodes on ungroup/remove. Outside `Where`: `yaml_io.py` now treats `children:` with an empty value as no children (the last removal from a block `children` list leaves it that way). Fixtures `zones_block/flow`, `groups_block/flow`; the expected text is hand-written in the tests as replacements of the fixture, each required to match once.

---

### T11: Make container diagrams canvas-editable

**What**: `canvas_editable` accepts diagrams with row/column containers. The scene JSON carries what the canvas needs: each container's id, axis, member ids and box, and each zone's id and child ids (extend `scene_json.py`, the schema and `scene.rs` together). Container members cannot be free-moved: dragging one inside its container reorders it, dragging it out removes it.
**Where**: `src/spinagram/ui/workspace.py`, `src/spinagram/scene_json.py`, `rust/schema/scene.schema.json`, `rust/spinagram-core/src/scene.rs`, `tests/test_ui.py`, `tests/test_scene_json.py`
**Depends on**: T10
**Reuses**: `scene.rows`, `scene.zone_children` (already on `Scene`)
**Requirement**: CTR-02 (partial), canvas-editor GRP-02/03

**Done when**:

- [x] Test: a hand-placed YAML with a row is editable; Python and engine layouts still are not
- [x] Test: scene JSON lists containers (id, axis, members, box) and zone children, and validates against the schema
- [x] Rust `scene_roundtrip` still round-trips every example scene byte-for-byte
- [x] Full gate passes

**Tests**: integration
**Gate**: full
**Commit**: `feat: canvas editing for diagrams with rows and columns`

**Notes**: Scene JSON gained `zones` (`{id: declared id, shape_id: z0.., children: declared ids}`) and `containers` (`{id: row0/column1.., axis, members, box}`), each written only when non-empty so older scenes still round-trip equal; Rust `scene.rs` has `ZoneInfo`/`ContainerInfo` (serde default), the schema is regenerated, and `Scene.zone_ids` (python) carries the declared zone ids. A container's box is the union of its member shapes. The test `rows.yaml#RW` in tests/test_ui.py flipped from not editable to editable (the new requirement); a new `rowsauto.yaml` (rows plus `layout: {engine: flex}`) stays not editable. 2842 passed, 3 skipped per mode; cargo 202.

---

### T12: Zone dragging on the canvas

**What**:
- Dragging a zone moves its children live (one `reroute` move map holding the zone, its child shapes and their text and icon items), and release sends MoveZone.
- While a node or zone is dragged, the innermost zone under its centre is highlighted as the drop target (ZON-06). On release a change of zone sends Reparent together with the Move in one batch (ZON-02, ZON-03, ZON-05 message).
- Double-clicking a zone header edits its label inline (ZON-07); double-clicking a node edits its title (SEL-05).
**Where**: `web/src/canvas/*.ts(x)`, `web/src/canvas/canvas.test.ts`
**Depends on**: T11
**Reuses**: `useCanvas`, `drag.ts`, `ops.ts`, `reroute`
**Requirement**: canvas-editor ZON-02..07, SEL-05; LRF-02 (zone part)

**Done when**:

- [x] bun tests: drop-target selection (innermost zone, none outside); the batch for a reparenting move; the zone move map includes child items; refusal when dropping a zone into its own descendant
- [x] Web gate passes

**Tests**: unit
**Gate**: web
**Commit**: `feat(web): drag zones and drop nodes into zones`

**Notes**: Pure logic is in `scene.ts` (zone boxes by declared id, `hitZone`, `descendants`, `zoneMoveShapes`) and `ops.ts` (`dropTarget`, `planDrop`, `renameOps`, `CYCLE_MESSAGE`); `useCanvas` selects nodes and zones, highlights the drop zone, shows the refusal as a notice, and opens the inline editor on double-click (the current title is read from the entry text through the source map: `entryField`). A zone is grabbed by its 56 px header band or 8 px outline (a node under the pointer wins). Outside `Where`: `rust/spinagram-core/src/reroute.rs` now also carries a moved zone's `z<k>-label` text and `z<k>-icon*`/`z<k>-strip` shapes (without it a zone's label stayed behind), with a new fixture pair (`zone`, `zone_moved`, generated by `rust/bench/reroute_fixtures.py`) and 2 Rust tests; the regenerated scene fixtures now include `zones`. Double-click edits the title only (the inline `text` editor of SEL-05 is not built). bun 62 -> 74; cargo 204. The web build rewrites the tracked static bundle; it is restored here and rebuilt once in T17.

---

### T13: Multi-select and grouping on the canvas

**What**:
- Shift+click toggles a node in the selection, and dragging on empty canvas rubber-band selects (SEL-01).
- A selection moves together (one batch) and deletes together.
- With ≥ 2 nodes selected, "Group as row" (Ctrl/Cmd+G) and "Group as column" send Group.
- With a container selected, "Ungroup" and a small property bar for `gap` and `align` (GRP-06).
- Dragging a node onto a container inserts it at the gap its centre falls in, and dragging a member out removes it (GRP-02, GRP-03).
**Where**: `web/src/canvas/*.ts(x)`, `web/src/DiagramView.tsx`, `web/src/canvas/canvas.test.ts`
**Depends on**: T12
**Reuses**: T12 drag code, the T10 ops
**Requirement**: canvas-editor SEL-01, SEL-02 (move part), SEL-06, GRP-01..06

**Done when**:

- [x] bun tests: rubber-band hit set; members ordered by x (row) or y (column); insertion index from the drop point; a multi-move batch; Ungroup op carries the rendered boxes
- [x] Web gate passes

**Tests**: unit
**Gate**: web
**Commit**: `feat(web): multi-select and row/column grouping on the canvas`

**Notes**: Logic in `scene.ts` (`rubberBand`, container lookup, `insertionIndex`) and `ops.ts` (`groupOps`, `ungroupOps`, `setContainerOps`, `planMultiDrop`, container-aware `planDrop`); UI in `useCanvas.ts`, the new `CanvasBar.tsx` (Group as row/column, Ungroup, gap, and align for containers placed in a zone) and `DiagramView.tsx`. With the canvas on, a press on empty canvas draws the selection box, so panning moves to Alt+drag (wheel still zooms). A free node dropped on a container's box joins it without a Reparent; a member dropped inside its container is reordered. Outside `Where`: Rust `add_to_container` on a node that already belongs to that same container now reorders it (`index` counts the other members; no other op can reorder), with tests in edit.rs and tests/test_rust_edit.py; `src/spinagram/edit.py` docs. Dragging a container itself only selects it (no container-move op). bun 74 -> 89; cargo 205.

---

### T14: Icon palette with search and drop

**What**: A palette panel on the canvas.
- Fuzzy search over the icons of every cached pack (names, aliases, pack name), the built-in shapes and the items Zone, Row and Column. Pick a small fuzzy library (uFuzzy or Fuse.js) for the web app.
- `/` or Ctrl/Cmd+K focuses it, ↑/↓ move, and Enter adds at the canvas centre (PAL-03).
- Dropping an icon adds a node with `icon: <pack>:<name>`, the title as the display name, `w: 220, h: 96`, centred on the drop point and snapped (PAL-04). Dropping a shape adds a node of that kind (PAL-05), and Zone adds a zone (ZON-01).
- Uncached packs are listed under "Not downloaded" with a Fetch action, never fetched automatically (PAL-06). No match shows "No icons match '<query>'" (PAL-07).
- New ids are kebab-case titles with `-2`, `-3` … suffixes.
**Where**: `web/src/canvas/palette*.ts(x)`, `web/src/canvas/canvas.test.ts`, `web/package.json`
**Depends on**: T13
**Reuses**: `/api/packs`, `/api/packs/{name}/icons`, `PackView` icon rendering
**Requirement**: canvas-editor PAL-01..07, ZON-01

**Done when**:

- [x] bun tests: "postgress" ranks `postgres` first; one typo tolerated for queries of ≥ 4 characters; the id scheme; AddNode op from a drop; the no-match message
- [x] bun benchmark test: search over a 10,000-icon synthetic corpus, p95 ≤ 100 ms (PAL-01)
- [x] Web gate passes

**Tests**: unit
**Gate**: web
**Commit**: `feat(web): icon palette with fuzzy search and drop`

**Notes**: Search library: uFuzzy (`@leeoniya/ufuzzy` 1.0.19, `intraMode: 1`, no dependencies, 7 KB). Pure logic in `canvas/palette.ts` (corpus, `search`, `newId`, `dropOps`), panel in `canvas/PalettePanel.tsx` (drag to the canvas, `/` or Ctrl/Cmd+K to focus, arrows and Enter add at the canvas centre, "Not downloaded" with Fetch that polls while a pack downloads). Benchmark over a 10,018-item synthetic corpus (16 queries x 8 rounds): p50 2.0 ms, p95 10.8 ms, max 11.8 ms (limit 100). Row and Column items add two boxes and group them (a container cannot be empty); a node dropped with its centre in a zone also gets a Reparent. Outside `Where`: Rust `AddNode` gained an optional `icon` (edit.rs test, tests/test_rust_edit.py, edit.py docs). `web/bun.lock` was edited by hand (3 lines: the local bun 1.3.14 rewrites the whole lockfile and cannot verify `--frozen-lockfile` even on the committed lock, so CI's bun 1.4.2 is the check). bun 89 -> 104; cargo 206.

---

### T15: Undo and redo

**What**: Ctrl/Cmd+Z and Shift+Ctrl/Cmd+Z undo and redo canvas edits of this page session, 50 steps, each as a new save through the version-checked save path. A 409 clears the stack and reloads (SEL-09).
**Where**: `web/src/canvas/history.ts`, `web/src/canvas/useCanvas.ts`, `web/src/canvas/canvas.test.ts`
**Depends on**: T14
**Reuses**: the save path in `useCanvas`
**Requirement**: canvas-editor SEL-09

**Done when**:

- [x] bun tests: the 50-step cap; redo cleared after a new edit; undo restores the exact prior text
- [x] Web gate passes

**Tests**: unit
**Gate**: web
**Commit**: `feat(web): undo and redo for canvas edits`

**Notes**: `history.ts` keeps whole-file before/after texts (50 steps); `useCanvas.travel` saves the earlier or later text through `api.save` with the current version, after checking the file still holds the text the edit produced or left (otherwise, like a 409, the history is cleared, the notice "File changed on disk; edit not applied" shows and the diagram reloads). Ctrl/Cmd+Z, Shift+Ctrl/Cmd+Z and Ctrl+Y work while the canvas is on and focus is not in a field or the code editor. bun 104 -> 108.

---

### T16: Editable showcase example

**What**: A hand-placed, canvas-editable showcase in YAML that looks like the other showcase diagrams:
- 2–3 nested zones;
- at least one row and one column;
- about 10 icon nodes from cached-by-default packs;
- labelled edges and a stylesheet.

Add it to the examples index and docs gallery the way other showcase files are, and make sure it renders in every backend test that renders examples.
**Where**: `examples/showcase/editable_platform.yaml` (+ `.css` if needed), docs gallery entry, `tests/test_ui.py`
**Depends on**: T15
**Reuses**: `examples/showcase/*.css` styles, `rust/bench/render_all.sh`
**Requirement**: canvas-editor goal (10-node, 2-zone, 6-edge build)

**Done when**:

- [x] Test: the scene endpoint reports it editable
- [x] `spinagram check` reports no errors on it
- [x] Manual check in Chrome with `spinagram serve` on a scratch copy covers: drag a node between zones; drag a zone (children follow); group two nodes as a row and ungroup; drop a palette icon; undo; delete. Each step's YAML diff touches only the expected lines. Record the result in notes
- [x] Full gate and web gate pass

**Tests**: integration
**Gate**: full
**Commit**: `feat(examples): editable platform showcase for the canvas`

**Notes**: `examples/showcase/editable_platform.yaml` (+ `.css`; id EDIT01): zones region > vpc > app/data (3 levels), a row (users, cdn), a column (alb, api, worker), 10 icon nodes from aws/network packs, 9 labelled `route: ortho` edges; `spinagram check` reports 0 issues (a `layout:` key would make it an engine layout, so edges are routed per edge instead). The edges still share trunks in places (ortho routing of hand-placed boxes). Docs: gallery view `edit01` in `docs/lib/showcase.ts`, a section in `examples/architecture.mdx`, asset `docs/public/assets/gallery/edit01.svg`. Outside `Where`: the tests that enumerate the showcase folder were updated for the new file (tests/test_metadata.py: EDIT01 is category AWS, 3 diagrams in `--category aws`), the css skill's bundled examples mirror it (`agent_skills/spinagram-css/examples/`, required by `test_css_examples_match_the_repository_showcase`), and the source-map example tests skip container keys (`row0`, `column1` have no id). The palette gained a hide/show button (`PalettePanel.tsx`) after the manual check showed it covers a small viewport. 2847 passed, 3 skipped per mode.

Manual check (Chrome via claude-in-chrome, `spinagram serve` on a git-tracked scratch copy, port 8794, diffs read with `git diff` after each step): (1) dragging Orders DB onto the column container made it join the column (`nodes: [alb, api, db, worker]`, only that line changed), and Ctrl/Cmd+Z restored the file exactly; (2) dragging Session cache from the data tier into the region left the data tier: `children: [db, cache]` -> `[db]`, region `children` gained `cache`, and `cache`'s `at` changed, nothing else; (3) dragging the Data tier header moved the zone x 500 -> 610 and Orders DB x 540 -> 650 (children follow), nothing else; (4) shift-click Order events and Reports then Ctrl/Cmd+G added `- {x: 960, y: 570, gap: 20, nodes: [queue, bucket]}` to `rows`; (5) selecting that row (click in the gap) showed the Ungroup / Gap bar and Ungroup removed it, writing `bucket`'s box (`at: [1200, 570, 220, 96]`); (6) the palette (search "termin", Enter) appended `{id: terminal, title: "Terminal", icon: "selfhosted:terminal", x: 850, y: 490, w: 220, h: 96}` and added `terminal` to region `children`; (7) Ctrl/Cmd+Z removed both; (8) Delete on Monitoring removed the node, its edge and its id in region `children`. Not exercised by hand: inline rename (double-click), the rubber band, the zone-into-descendant refusal (bun-tested), the container property bar's gap field, and palette drag and drop (synthetic drags do not drive HTML5 drag events; Enter is covered).

---

### T17: Bundle, docs and traceability

**What**:
- Rebuild the committed UI bundle.
- Document canvas editing (what is editable, shortcuts, palette, grouping, undo) in the docs live-editor page.
- Update `rust/README.md` for the new ops.
- Update `spec.md` traceability for the wasm-editor IDs covered.
**Where**: `src/spinagram/ui/static/`, `docs/content/docs/` (live editor page), `rust/README.md`, `.specs/features/wasm-editor/spec.md`
**Depends on**: T16
**Reuses**: the T8 bundle steps
**Requirement**: HST-01 (partial)

**Done when**:

- [x] The rebuilt bundle is committed and CI's stale-bundle check passes locally
- [x] Full gate, Rust gate, WASM gate and web gate pass

**Tests**: none
**Gate**: full
**Commit**: `docs: canvas editing guide and rebuilt ui bundle`

**Notes**: Bundle rebuilt with `bash rust/spinagram-wasm/build.sh` then `bun run build` in web/ (a second build gives the same file names, so CI's stale check holds; the .wasm is 663 KB gzipped). Docs: new "Edit on the canvas" section in `docs/content/docs/tools/live-ui.mdx` (the live editor page: what is editable, shortcuts, palette, grouping, undo); `rust/README.md` has an "Edit operations" section; `spec.md` traceability updated (CTR-02, CTR-03, OPS-01, LRF-01, LRF-02, HST-01, coverage line). Gates: Rust 206 tests, clippy and deny clean; WASM build and bun 21; web bun 108 and build; pytest 2847 passed, 3 skipped per mode, ruff clean. The `taiki-e/install-action` wasm-bindgen step and `bun install --frozen-lockfile` with the hand-edited `web/bun.lock` run only in CI.

---

## Polish iteration scope (orchestrator, 2026-11-01)

Fixes the UX findings of the second validation (`validation.md`, "UX findings") and polishes the editor so it feels
finished. The behaviour reference stays the read-only `.specs/features/canvas-editor/spec.md`.

---

### T18: Palette visibility and layout

**What**: The palette starts collapsed, as a "Palette" tab. It opens with the tab, `/` or Ctrl/Cmd+K, and Esc closes it. Its open/closed state survives re-renders and saves (finding 2) and is remembered per browser in `localStorage`, wrapped in try/catch. When open it sits beside the diagram rather than over it, or at least never covers the selection (finding 1). Kind badges get a fixed width that fits "COLUMN" without overflow (finding 3).
**Where**: `web/src/canvas/PalettePanel.tsx`, `web/src/DiagramView.tsx`, `web/src/canvas/canvas.test.ts`
**Depends on**: T17
**Reuses**: the existing palette, the `useCanvas` state
**Requirement**: canvas-editor PAL-03; validation UX findings 1–3

**Done when**:

- [x] bun tests: the open state persists across a save (state is kept outside the re-rendered subtree, or a test of the stored flag); storage that throws falls back to collapsed
- [x] Browser check: collapse, make an edit, and the palette stays collapsed; the "COLUMN" badge fits
- [x] Web gate passes

**Tests**: unit
**Gate**: web
**Commit**: `fix(web): palette starts collapsed and keeps its state`

**Notes**: Open state lives in `DiagramView` (initialised from `localStorage` through `canvas/paletteState.ts`, try/catch, collapsed on any failure), so a save that re-renders the canvas cannot reset it; `PalettePanel` is rendered only while open, as a flex column beside the diagram (never over it); the collapsed "Palette" tab sits in the corner. Esc in the search box closes it. Kind badges and the icon cell are `w-14` (fits "COLUMN"). bun 109 -> 113. Browser check (port 8796, scratch copy of showcase): palette collapsed on first Canvas-on; `/` opened it beside the diagram with the COLUMN badge intact; Esc closed it; after renaming Monitoring (double-click) the palette stayed collapsed. Observed, not in scope: the rename input does not always receive focus right after a double-click (typed keys then hit canvas shortcuts); T21 pointer polish should look at it.

---

### T19: Plain YAML scalars where safe

**What**: Rename, AddNode, Connect labels and AddZone write a plain scalar when YAML would read it back as the same string. They quote only when needed: leading or trailing spaces, `: `, ` #`, a leading indicator character, YAML 1.1 booleans and nulls (`yes`, `no`, `on`, `off`, `null`, `~`), anything that would read as a number, or flow-context characters `,[]{}` inside flow entries (finding 4).
**Where**: `rust/spinagram-core/src/edit.rs`, `rust/spinagram-core/tests/data/edit/`
**Depends on**: T18
**Reuses**: `scalar`, `quoted`
**Requirement**: OPS-02; validation UX finding 4

**Done when**:

- [x] Test: "Report store" is written plain; each quoting trigger above is written quoted, and every output re-parses to the exact input string (round-trip table)
- [x] Existing fixtures updated only where the new rule changes output
- [x] Rust gate and full gate pass

**Tests**: unit
**Gate**: full
**Commit**: `fix(rust): write plain yaml scalars when quoting is not needed`

**Notes**: New `text_scalar(s, flow)` / `plain_safe` in edit.rs for titles, labels, icon refs and edge strings (ids keep the stricter `scalar`). Rename of a plain entry stays plain when safe; flow-ness comes from the entry. Quoting triggers: leading/trailing space, `: `, ` #`, leading indicator, trailing `:`, control characters, YAML 1.1 bool/null words, numbers (decimal, `.inf`/`.nan`, 0x, 0o, `1_000`, `1e5`, `1:30`), and `,[]{}` in flow entries. A labelled edge always contains `: ` so it stays quoted; an unlabelled edge is plain. The round-trip table test found one bug in the first draft (`.inf` written plain). Fixtures changed only where the rule changes output (6 expected files + 5 inline strings). Outside `Where`: `rust/spinagram-wasm/tests/golden/decision.patched.yaml` regenerated (`SPINAGRAM_RUST=0 ... gen_golden.py`; the scene goldens it also rewrites were left alone, they are unrelated drift). cargo 206 -> 209; pytest 2847 passed, 3 skipped per mode; bun wasm 21.

---

### T20: Clear render errors on gallery cards

**What**: When a diagram cannot render, the gallery card shows the short error (e.g. "No such file: showcase.css") instead of "preview unavailable". The full message is in a tooltip (finding 5).
**Where**: `web/src/DiagramsPage.tsx` (or the card component), `web/src/previews.test.ts`
**Depends on**: T19
**Reuses**: the error body the `.svg` endpoint already returns
**Requirement**: validation UX finding 5

**Done when**:

- [x] bun test: a failed preview shows the server's first error line, truncated to one line
- [x] Web gate passes

**Tests**: unit
**Gate**: web
**Commit**: `fix(web): show the render error on a gallery card`

**Notes**: `errorLine` in `catalog.ts` (first non-empty line, 90 chars, ellipsis); the card fetches the `.svg` URL once its `<img>` failed and shows the `ApiError` message, full text in the `title` tooltip; `failed` resets on a live reload. Checked in Chrome with `showcase.css` removed from the scratch copy: cards show "[Errno 2] No such file or directory: 'showcase.css'" in red. bun 113 -> 116.

---

### T21: Keyboard and pointer polish

**What**:
- Esc clears the selection, and cancels a drag in progress, restoring the preview.
- Arrow keys nudge the selection 1 px, and Shift+arrow 10 px. One batch per key-up burst, so holding a key makes one save and one undo step.
- Pointer cursors: `grab`/`grabbing` on nodes and zone headers, `crosshair` on empty canvas, `copy` over a valid drop target.
- Selection gets a clear outline with handles. Multi-selection shows one bounding box with a count badge.
- `?` opens a small shortcuts sheet listing every canvas shortcut.
- Errors from the Rust ops (e.g. "A zone cannot contain itself") show as a toast near the pointer for 3 s.
**Where**: `web/src/canvas/*.ts(x)`, `web/src/canvas/canvas.test.ts`
**Depends on**: T20
**Reuses**: `useCanvas`, `ops.ts`, `History`
**Requirement**: canvas-editor SEL-01..03 (polish), ZON-05 message

**Done when**:

- [x] bun tests: nudge op batching (a burst of 5 presses → one Move per node with the summed offset); Esc restores the pre-drag scene; the shortcuts list includes every bound key (derived from one keymap table that the handlers also use)
- [x] Web gate passes

**Tests**: unit
**Gate**: web
**Commit**: `feat(web): keyboard nudge, escape, cursors and shortcut sheet`

**Notes**: New `canvas/interaction.ts` holds the keymap table (`KEYMAP`; `matchKey` and the `?` sheet rows both read it, and `DiagramView` has one canvas keydown handler that switches on `matchKey`, replacing the separate Delete, Backspace, Ctrl+G, undo/redo, `/`, Ctrl+K and Esc handlers), `escapeStep` (sheet, drag, nudge, selection, palette), burst nudging (`nudgeOps` reuses `planMultiDrop` with a 1 px grid, so a burst is one Move per node and still reparents/reorders like a drop), `cursorFor`, `selectionFrame` (bounding box and count). Taps of an arrow key within 350 ms after a key-up join one burst (a held key is one burst); keys pressed while the scene reloads are ignored. Selection: 2 px outline with 8 visual handles (resizing stays in the YAML), several nodes get thin outlines plus one dashed bounding box with a count badge. Op errors (Rust refusals and the zone-cycle message) show as a red toast at the pointer for 3 s (`TOAST_MS`); 409 and network errors keep the old bottom-left notice. New `InlineEdit.tsx` takes focus on mount and re-takes it once (fixes the T18 observation that typing right after a double-click hit the shortcuts) and `ShortcutSheet.tsx`. bun 116 -> 126. Browser check (port 8796): click Monitoring then ArrowRight x3, ArrowDown, Shift+ArrowDown gave one save, `at: [960, 900, ...]` -> `[963, 911, ...]`; selection outline with handles shown; `?` opened the sheet and Esc closed it; dragging the region header onto the VPC showed "A zone cannot contain itself" at the pointer and left the file untouched. Not exercised by hand: Esc in the middle of a pointer drag (the browser tool drags atomically; covered by the `escapeStep` test and the cancel path is the same code as a refused drop), grab/crosshair/copy cursors (unit-tested mapping only).

---

### T22: Showcase layout polish

**What**: Rework `examples/showcase/editable_platform.yaml` coordinates and edge sides so that:
- no two edges share a trunk segment;
- labels don't overlap edges or nodes;
- zones have even padding.

Keep it canvas-editable with the same features (nested zones, a row, a column, icons). Regenerate the docs gallery SVG.
**Where**: `examples/showcase/editable_platform.yaml`, `examples/showcase/editable_platform.css`, `docs/public/assets/gallery/edit01.svg`
**Depends on**: T21
**Reuses**: `spinagram check` (label collisions, overlaps)
**Requirement**: showcase quality

**Done when**:

- [x] `spinagram check` reports 0 issues and 0 label collisions
- [x] Visual review of the rendered PNG: no shared trunks, even spacing (record a short note)
- [x] Full gate passes (example tests, css-skill mirror test)

**Tests**: integration
**Gate**: full
**Commit**: `style(examples): tidy the editable showcase layout`

**Notes**: Same features (3 nested zones, one row, one column, 10 icon nodes) with 8 edges instead of 9. The old trunk (publish, consume, reports and metrics all ran along one vertical) is gone: nodes sit on three shared rows (y centres 524, 676, 828) so five of the edges are straight horizontals (sessions, SQL, export, metrics, consume) and `origin` leaves CloudFront at the bottom and enters the load balancer at the top (`cdn.bottom -> alb.top`). Column members render 266 px wide, so the app tier is 346 px wide (the first draft clipped `worker`, which `spinagram check` caught); the column gap is 56 px so `forward` fits. Zone padding: 40 px at the sides and bottom, 60 px under the header. `spinagram check`: 0 issues (label collisions and zone clips included). Visual review of the rendered PNG: no shared trunk, no label on a node or another edge, even zone padding; the right side of the region is wider than the content by about 120 px. Dropped the unused `edge.metrics` rule from the css. Outside `Where`: the css skill mirror in `src/spinagram/agent_skills/spinagram-css/examples/` and `tests/test_ui.py` (connector count 9 -> 8). Gate: pytest 2847 passed, 3 skipped per mode, ruff clean.

---

### T23: Bundle, docs and browser pass

**What**:
- Rebuild and commit the UI bundle.
- Update the live-ui docs with the new shortcuts.
- Do a final browser pass on a scratch copy of the whole `examples/showcase/` folder: palette collapse persists; rename writes plain; arrow nudge and undo; Esc; the `?` sheet; a refused zone drop shows the toast; the gallery card error with a missing CSS.

Record the results in notes.
**Where**: `src/spinagram/ui/static/`, `docs/content/docs/tools/live-ui.mdx`, this file
**Depends on**: T22
**Reuses**: T17 steps
**Requirement**: HST-01 (partial)

**Done when**:

- [x] The browser pass is recorded, with each step's YAML diff where it applies
- [x] Full, Rust, WASM and web gates pass

**Tests**: none
**Gate**: full
**Commit**: `docs: canvas polish shortcuts and rebuilt ui bundle`

**Notes**: Bundle rebuilt (`bash rust/spinagram-wasm/build.sh`, then `bun run build`; a second build gives the same file names; wasm 665 KB gzipped). `live-ui.mdx` gained the palette behaviour, nudge, Esc, `?`, the refusal toast and plain-scalar notes. Gates: cargo 209, clippy and deny clean; wasm bun 21; web bun 126 and build; pytest 2847 passed, 3 skipped per mode; `test_web_unit` passes; ruff clean.

Browser pass (Chrome, `spinagram serve` on a git-tracked scratch copy of the whole `examples/showcase/`, port 8796; diffs from `git diff`):
1. Palette: collapsed on first Canvas-on; stays collapsed through saves (T18 check; still collapsed after the edits below).
2. Rename: double-click Reports, type "Report store", Enter: `title: Reports` -> `title: Report store` (plain, no quotes); the typed text went into the field (focus fix).
3. Arrow nudge: ArrowDown x3 and Shift+ArrowRight sent together: one save, `at: [1380, 628, ...]` -> `[1390, 631, ...]`. Ctrl/Cmd+Z restored `[1380, 628, ...]`, leaving the rename.
4. Esc cleared the selection; `?` opened the shortcut sheet listing every row of the keymap; Esc closed it.
5. Refused zone drop: dragging the region header into the VPC showed "A zone cannot contain itself" at the pointer and left the file unchanged.
6. Gallery card error: with `aws.css` removed from the scratch copy the three AWS cards show "[Errno 2] No such file or directory: 'aws.css'" (full text in the tooltip).
Not exercised by hand: Esc in the middle of a pointer drag (the tool drags atomically; unit-tested through `escapeStep`), and the cursors.

---

## Toolbar iteration scope (orchestrator, 2026-11-01)

User feedback on PR #8:
1. **The diagram redraws while dragging an item from the palette.** Likely cause: every save replaces the whole
   diagram's `innerHTML` (`web/src/DiagramView.tsx`, `dangerouslySetInnerHTML={{ __html: canvas.preview ?? svg }}`),
   first with the WASM preview and then with the server SVG. That re-parses embedded fonts and images, so the
   diagram flashes.
2. **Add a toolbar with icons:** select/drag mode, pan, text and the other tools.
3. **Give the palette items icons** (zone, box…) and group them into categories.

Tools go through the existing Rust ops (AddNode, AddZone, Connect, Group). No new ops unless one is missing. The
browser checks use their own `spinagram serve` port (8799) and their own tab. **Never touch the user's open tab or
the server on port 8798**, nor the one on 8791.

---

### T24: Find and fix the redraw on palette drag and on saves

**What**: Reproduce the flash first. Use HTML5 drag events dispatched with `new DataTransfer()` from the Chrome
`javascript_tool`, plus a `MutationObserver` on the SVG host that counts subtree replacements and records frames
where the host is empty or the old SVG was removed before the new one was ready. Then fix it:
- No DOM change to the diagram during `dragover`.
- A drop shows an immediate ghost at the drop point.
- Updates after a save patch the existing SVG in place, morphing by element `id` or `data-id` with a small DOM-morph
  library such as idiomorph or morphdom (record the pick). Swapping only after the new SVG is parsed is acceptable
  if morphing is not.
- No blank or unstyled frame at any point. Embedded fonts and images that did not change are not re-created.
- The preview → server-render hand-off makes at most one visible update per edit.
**Where**: `web/src/DiagramView.tsx`, `web/src/canvas/useCanvas.ts`, new `web/src/canvas/svgHost.ts(x)`, `web/src/canvas/canvas.test.ts`, `web/package.json`
**Depends on**: T23
**Reuses**: `canvas.preview`, the existing render hooks
**Requirement**: DIF-02, DIF-04 (in spirit), user feedback 1

**Done when**:

- [x] Before/after numbers recorded in notes (observer counts of host replacements and empty frames, for one palette drag-and-drop and one node drag)
- [x] bun tests for the host updater (jsdom or happy-dom): an update keeps unchanged nodes as the same DOM objects (identity check), changes the changed ones, and never leaves the host empty
- [x] Browser check after the fix: 0 empty frames, 0 full-host replacements during dragover, and at most 1 update batch per committed edit
- [x] Web gate passes

**Tests**: unit
**Gate**: web
**Commit**: `fix(web): update the diagram in place instead of redrawing it`

**Notes**: Pick: **morphdom 2.7.8** (small, no dependencies, keyed morphing); `happy-dom` 21.0.4 is a dev dependency for the host tests (it drops the content of `<style>` inside `<svg>`, so the tests stand a `<defs>` in for the font style; Chrome parses it correctly). Installed with bun 1.4.2.
Cause confirmed by the observer (`MutationObserver` on the SVG host, plus a per-frame empty-host check; `spinagram serve` on a scratch copy of `examples/showcase/`, port 8799, `editable_platform`):
| Case | Before (innerHTML) | After (`SvgHost` + `patchSvg`) |
| --- | --- | --- |
| Palette drag, 6 dragover events | 0 mutations | 0 mutations |
| Palette drop of a Box | 1 full host replacement, 1 `<style>` and 10 `<image>` re-created | 0 replacements, 125 of 128 elements kept (3 new), the 10 images the same objects, a ghost shown for 2 frames, 1 update batch |
| Node drag (down, move, up) | 3 full replacements, 3 `<style>`, 30 `<image>` re-created | 0 replacements, 112 of 131 elements kept (19 re-created: the moved node and its edges), the same 10 image objects, 3 batches (live preview, snapped release preview, server render) |
| Empty or unstyled frames | 0 (innerHTML is atomic within a task, but every embedded image was decoded again) | 0 |
What it took beyond a plain morph: rendered elements have no ids, so one new box shifted every later element and morphdom re-created them. `patchSvg` keys each element by tag, attributes and its place among identical ones (an `<image>` by its href only), and first removes old elements with no counterpart so matched ones are not moved past them. The preview (WASM) and the server render order an icon and its text differently, so on a hand-off the images are moved (same objects, same task, no repaint) rather than re-created. `useCanvas` gained `ghost` (`ghostOf(ops)` in `palette.ts`): a dashed placeholder at the dropped box at once, cleared when the render arrives or fails.
SPEC_DEVIATION: a node drag after release makes two batches (the snapped preview, then the server render) rather than one. The first is a visible snap from the unsnapped live drag; the second changes the DOM order of image and text siblings only, no pixels. Dropping the release preview would make the node jump back until the save finished.
Gate: bun test 139 pass (was 127; +9 host tests, +3 ghost tests), `bun run build` ok, bundle not committed here (T29).

---

### T25: Icon set for the editor

**What**: Add an icon library (lucide-react, ISC, tree-shaken imports) and one `EditorIcon` mapping: select,
hand/pan, box, text, zone, row, column, connect, note, diamond, pill, undo, redo, palette, group, ungroup, delete,
and each built-in shape kind. Record it in the web dependencies notes. Keep `web/bun.lock` consistent with the
installed bun; do not hand-edit it.
**Where**: `web/src/canvas/icons.tsx`, `web/package.json`, `web/bun.lock`
**Depends on**: T24
**Reuses**: none
**Requirement**: user feedback 2, 3

**Done when**:

- [x] bun test: every palette item kind and every toolbar tool has an icon (derived from the same tables the palette and toolbar use)
- [x] Web gate passes

**Tests**: unit
**Gate**: web
**Commit**: `feat(web): icon set for canvas tools and palette items`

**Notes**: `lucide-react` 1.66.0 (ISC), each icon imported by name, added with `bunx bun@1.4.2 add`. `tools.ts` was created here (the tool and action tables: ids, labels, keys) so the icon test can derive from the table T26's toolbar uses; T26 builds on it. `icons.tsx` maps tools, actions, containers and every `SHAPE_KINDS` entry; `iconNameOf(item)` gives a palette item's icon name (null for an icon-pack item, which shows its pack image). Heads-up for T26: the Connect key `c` is today the global Canvas on/off key in `DiagramView`. Gate: bun test 143 pass (+4), build ok.

---

### T26: Canvas toolbar with tool modes

**What**: A vertical toolbar on the canvas's left edge, with icon buttons, tooltips naming the tool and its key,
and an active state. Tools:
- **Select/drag (V):** today's behaviour.
- **Hand/pan (H):** plain drag pans; holding Space pans temporarily in any tool.
- **Box (B), Text (T), Zone (Z):** a click places the default size centred on the point; a drag draws the rectangle
  (snapped). Text creates a `kind: text` node and opens the inline editor right away.
- **Connect (C):** drag from one node to another sends Connect, with a live straight preview line. A release on
  empty space, the same node or a zone adds nothing (canvas-editor EDG-02/03).
- **Actions:** Group row, Group column, Ungroup, Undo, Redo, Palette toggle, `?`.

After placing an item the tool returns to Select, unless the user held Shift to keep it. The tools join the single
keymap table, so the `?` sheet lists them.
**Where**: `web/src/canvas/Toolbar.tsx`, `web/src/canvas/tools.ts`, `web/src/canvas/useCanvas.ts`, `web/src/canvas/interaction.ts`, `web/src/DiagramView.tsx`, `web/src/canvas/canvas.test.ts`
**Depends on**: T25
**Reuses**: `ops.ts`, `palette.ts` `newId`/`dropOps`, `History`, the keymap table
**Requirement**: user feedback 2; canvas-editor EDG-01..03

**Done when**:

- [x] bun tests: a click places the default box at the point and a drag places the drawn rectangle (snapped); a Text placement yields AddNode kind text and opens the editor; Connect rejects empty space, the same node and a zone; the tool falls back to Select unless Shift is held; the keymap holds every tool key
- [x] Web gate passes

**Tests**: unit
**Gate**: web
**Commit**: `feat(web): canvas toolbar with select, pan, box, text, zone and connect tools`

**Notes**: `tools.ts` holds the pure logic (`placeOps`, `connectOps`, `toolAfterUse`, `CLICK_SLOP` 8 px); `useCanvas` gained `tool`, `setTool`, `beginTool`, `drawing` and `connecting` (the live rectangle and the straight dashed line, with the target node highlighted); `move` and `end` route to them, and `end(shift)` takes the Shift state at release (Shift at the press also keeps the tool). A new `connect` op type in `ops.ts` (the Rust `Op::Connect` already existed). A placed Text opens the inline editor once the scene with the new node arrives. Connect released on nothing keeps the tool for another try. Space held pans in any tool (`DiagramView`); Hand pans with a plain drag. Esc order: sheet, drag/drawing, nudge, selection, tool back to Select, palette. Key `c`: with the canvas off it still turns it on; with it active it is the Connect tool (the global handler steps aside), and the Canvas button turns it off; the `?` footer says so. The floating "Palette" button is replaced by the toolbar's Palette action. Group, Ungroup and Delete are disabled without a matching selection. Tool keys V H B T Z C and the new pointer rows are in the keymap table and the `?` sheet. Tests +13 (placement, rectangle, minimum size, click slop, zone join, text edit flag, id uniqueness, connect accept and the four refusals, tool fallback, keymap), six mutants checked in a scratch worktree (removed afterwards) and all killed. Quick browser check on port 8799: Box tool click placed `new-box`, Connect drag db to bucket added `db -> bucket`. Gate: bun test 156 pass, build ok.

---

### T27: Palette categories with item icons

**What**: When the search box is empty, the palette shows collapsible categories, each with a header and count:
- **Basics:** Box, Text, Zone, Row, Column, Note.
- **Shapes:** every other built-in shape kind.
- **Icons**, one category per cached pack.
- **Not downloaded:** with Fetch.

Every item shows its icon: `EditorIcon` for basics and shapes, the pack image for icons. With a query, results stay
one ranked list, each row tagged with its category. Collapsed state is remembered like the palette open state.
**Where**: `web/src/canvas/PalettePanel.tsx`, `web/src/canvas/palette.ts`, `web/src/canvas/canvas.test.ts`
**Depends on**: T26
**Reuses**: `buildCorpus`, `search`, `paletteState.ts`
**Requirement**: user feedback 3; canvas-editor PAL-01, PAL-06

**Done when**:

- [x] bun tests: category assignment (Zone/Box/Text in Basics, the shape kinds in Shapes, icons under their pack); search results keep their category tag; the collapsed state round-trips through storage and falls back when storage throws
- [x] Web gate passes

**Tests**: unit
**Gate**: web
**Commit**: `feat(web): palette categories with item icons`

**Notes**: `palette.ts` gained `categoryOf`, `categorize`, `paletteRows` and `defaultCollapsed`; `paletteState.ts` gained `readCollapsed`/`writeCollapsed` (an object of category id to collapsed, storage failures or foreign content give `{}`). Basics are Box, Text, Zone, Row, Column, Note in that order; packs start collapsed (they can hold thousands of items), Basics and Shapes open; "Not downloaded" is a collapsible footer section with the count and the Fetch buttons. The list is virtualized with `@tanstack/react-virtual` (headers and items as rows) and the arrow keys and Enter walk the items in view. A query gives one ranked list, each row tagged with its category title. Items draw `EditorIcon` (basics and shapes) or the pack image. Tests +7, six mutants checked in a scratch worktree (removed afterwards) and all killed. Gate: bun test 163 pass, build ok; checked in the browser (Basics 6, Shapes 12, packs below).

---

### T28: Browser pass

**What**: On a scratch copy of the whole `examples/showcase/` (port 8799, git-initialised for diffs), check each
of the following and record the result and YAML diff in notes:
- palette drag-and-drop of a Box and an icon, with dispatched DragEvents and the observer showing no flash;
- each toolbar tool: Box click and drag, Text, Zone, Connect, and the Hand tool and Space-pan;
- the category view, collapsing a category, and search.
**Where**: this file (notes)
**Depends on**: T27
**Reuses**: T24 observer script
**Requirement**: user feedback 1–3

**Done when**:

- [ ] Every step recorded with its diff; no flash recorded by the observer
- [ ] Any bug found is fixed in this task with a test

**Tests**: unit
**Gate**: web
**Commit**: `test(web): toolbar and palette browser pass fixes`

---

### T29: Bundle and docs

**What**: Rebuild and commit the UI bundle. Update `docs/content/docs/tools/live-ui.mdx` with the toolbar, the
tools and their keys, and the palette categories.
**Where**: `src/spinagram/ui/static/`, `docs/content/docs/tools/live-ui.mdx`
**Depends on**: T28
**Reuses**: T23 steps
**Requirement**: HST-01 (partial)

**Done when**:

- [ ] The rebuilt bundle is committed; full, Rust, WASM and web gates pass

**Tests**: none
**Gate**: full
**Commit**: `docs: canvas toolbar guide and rebuilt ui bundle`

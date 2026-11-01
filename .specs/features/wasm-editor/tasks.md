# Rich editor MVP (Rust edit operations + live edges in WASM) Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the per-task cycle.

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Spec**: `.specs/features/wasm-editor/spec.md`
**Status**: MVP done (T1–T8, validation PASS); second iteration (T9–T17) ready

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

- [ ] bun tests: rubber-band hit set; members ordered by x (row) or y (column); insertion index from the drop point; a multi-move batch; Ungroup op carries the rendered boxes
- [ ] Web gate passes

**Tests**: unit
**Gate**: web
**Commit**: `feat(web): multi-select and row/column grouping on the canvas`

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

- [ ] bun tests: "postgress" ranks `postgres` first; one typo tolerated for queries of ≥ 4 characters; the id scheme; AddNode op from a drop; the no-match message
- [ ] bun benchmark test: search over a 10,000-icon synthetic corpus, p95 ≤ 100 ms (PAL-01)
- [ ] Web gate passes

**Tests**: unit
**Gate**: web
**Commit**: `feat(web): icon palette with fuzzy search and drop`

---

### T15: Undo and redo

**What**: Ctrl/Cmd+Z and Shift+Ctrl/Cmd+Z undo and redo canvas edits of this page session, 50 steps, each as a new save through the version-checked save path. A 409 clears the stack and reloads (SEL-09).
**Where**: `web/src/canvas/history.ts`, `web/src/canvas/useCanvas.ts`, `web/src/canvas/canvas.test.ts`
**Depends on**: T14
**Reuses**: the save path in `useCanvas`
**Requirement**: canvas-editor SEL-09

**Done when**:

- [ ] bun tests: the 50-step cap; redo cleared after a new edit; undo restores the exact prior text
- [ ] Web gate passes

**Tests**: unit
**Gate**: web
**Commit**: `feat(web): undo and redo for canvas edits`

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

- [ ] Test: the scene endpoint reports it editable
- [ ] `spinagram check` reports no errors on it
- [ ] Manual check in Chrome with `spinagram serve` on a scratch copy covers: drag a node between zones; drag a zone (children follow); group two nodes as a row and ungroup; drop a palette icon; undo; delete. Each step's YAML diff touches only the expected lines. Record the result in notes
- [ ] Full gate and web gate pass

**Tests**: integration
**Gate**: full
**Commit**: `feat(examples): editable platform showcase for the canvas`

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

- [ ] The rebuilt bundle is committed and CI's stale-bundle check passes locally
- [ ] Full gate, Rust gate, WASM gate and web gate pass

**Tests**: none
**Gate**: full
**Commit**: `docs: canvas editing guide and rebuilt ui bundle`

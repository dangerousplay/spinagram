# Validation: wasm-editor MVP (T1–T8)

**Result**: PASS, with 1 low-severity gap (a surviving mutant on a defensive guard).
**Verifier:** orchestrator session. The author was a separate Sonnet sub-agent (author ≠ verifier).
**Diff range:** `ff6f02a..353853d` on `feat/wasm-editor-mvp`, 8 commits, one per task.
**Date:** 2026-11-01

## Gates (re-run independently)

| Gate | Result |
|---|---|
| `cargo test` (workspace) | 186 passed, 0 failed |
| `cargo clippy --all-targets -- -D warnings` | clean |
| `cargo deny check` | advisories, bans, licenses, sources ok |
| `ruff check src tests examples` | clean |
| pytest, Rust core default | 2831 passed, 3 skipped |
| pytest, `SPINAGRAM_RUST=0` | 2831 passed, 3 skipped |
| `rust/spinagram-wasm/build.sh` + `bun test` | build ok, 21 pass |
| `web` `bun test` + `bun run build` | 62 pass, build ok; the rebuilt bundle equals the committed `src/spinagram/ui/static` (clean `git status`) |

The baseline before T1 was 2799 passed per mode. The suite grew by 32 Python tests, 27 Rust tests and 34 bun tests.

## Per-requirement evidence (MVP scope only)

| Req | Evidence | Status |
|---|---|---|
| OPS-01 (listed ops) | `rust/spinagram-core/src/edit.rs:487` `op_patches` (move, resize, rename, delete, add_node, connect, disconnect); fixtures `rust/spinagram-core/tests/data/edit/*.yaml` | Covered |
| OPS-02 (bytes outside the patch unchanged) | The `check()` helper `edit.rs:647` compares the whole output with a hand-written expected file, for block and flow fixtures. Browser run: `diff` shows only the `std` line changed | Covered |
| OPS-03 (reject invalid, input unchanged) | `edit.rs:714` `invalid_operations_are_rejected_with_a_reason`, `edit.rs:732` | Covered |
| OPS-04 (batch all or none) | `edit.rs:741` `a_batch_with_one_invalid_op_changes_nothing`; `apply_ops` works on a copy (`edit.rs:604`) | Covered |
| OPS-05 (Python + browser part) | `src/spinagram/edit.py`, `tests/test_rust_edit.py`; wasm `applyOps` golden test `rust/spinagram-wasm/tests/wasm.test.ts` | Partial (CLI and MCP not in the MVP) |
| CTR-03 (srcmap) | `edit.rs:817` `srcmap_ranges_slice_exactly_the_entry_text`, `edit.rs:839` (byte offsets with non-ASCII text) | Covered |
| CTR-02 (scene endpoint, partial) | `tests/test_ui.py:483`, `:507` (editable flag), `:522` (404/422) | Partial (as scoped) |
| LRF-01 (edges follow during drag, partial) | `tests/test_rust_reroute.py:40` (reroute equals a full Python render of the moved YAML), `:54` (untouched connectors unchanged). Browser: the `yes` edge followed the dragged node | Partial (no zone reflow, as scoped) |
| HST-03 (shared draw code, partial) | The wasm `renderSvg` body equals the PyO3 golden body byte-for-byte (`wasm.test.ts`) | Partial (draw stage only) |
| SYN-01 (selection highlights YAML) | bun test srcmap → editor range (`web/src/canvas/canvas.test.ts`) | Covered (unit); not exercised in the browser run |
| HST-01 (bundle ships the wasm, partial) | `tests/test_ui.py` wasm mime test (T8); a wheel built locally contains the `.wasm` (author report) | Partial |

## Browser check (independent of the author's)

`spinagram serve` ran on a scratch copy of `examples/decision.yaml`, in Chrome:
1. **Canvas mode:** turned on, then "Standard path" dragged down by about 300 screen px. The `yes` edge was
   re-routed to the moved node. After release, the file diff was only
   `at: [900, 220, …]` → `at: [900, 690, …]`, snapped to the 10 px grid.
2. **Delete:** selected the node and pressed Delete. The diff removed the node line and its one edge
   `"known.right -> std.left: yes"`, nothing else.

## Discrimination sensor

The mutants ran in a scratch `git worktree` with a separate cargo target. Afterwards the worktree was removed
and the porcelain matches the pre-sensor baseline.

| Mutant | Target | Result |
|---|---|---|
| M1 delete keeps touching edges | `edit.rs` delete | killed |
| M2 delete keeps ids in children/nodes lists | `edit.rs` delete | killed |
| M3 `apply_ops` skips the re-parse guard | `edit.rs:611` | **survived** |
| M4 reroute leaves connector points unchanged | `reroute.rs` poly branch | killed |
| M5 hit-test picks the bottom-most node | `web/src/canvas/scene.ts` | killed |
| M6 snap floors instead of rounding | `scene.ts` | killed |
| M7 a click counts as a drag | `web/src/canvas/drag.ts` | killed |
| M8 every diagram is canvas-editable | `src/spinagram/ui/workspace.py` | killed |
| M9 diagrams with containers are editable | `workspace.py` | killed |

8 of 9 killed.

**M3:** `checked()` is unit-tested directly (`edit.rs:753`), but no test drives `apply_ops` into a patch that fails
to re-parse. Quoting (`edit.rs:760`) probably makes the guard unreachable, so the mutant may be equivalent. Fix
task (low): add a test that reaches the guard through `apply_ops`, or document it as unreachable defence. Lesson
L-077 recorded.

## Spec-precision notes

- **No editable examples:** `aws_layout.yaml` and `software_architecture.yaml` are engine-laid-out, so the canvas
  correctly refuses them. The canvas-editable examples are `decision.yaml` and the new `ortho.yaml` fixture. Worth
  adding a hand-placed showcase example.
- **Zone membership:** a node dragged out of its zone keeps it. That is expected in the MVP: Reparent is
  canvas-editor ZON-02/03.
- **Diagrams with row/column containers** are not canvas-editable yet (`workspace.py:485`).
- **Deviations documented in tasks.md:**
  - the `explicit` binding flag in scene JSON;
  - the endpoint shape `{scene, editable, files}`;
  - reroute limits: zone headers are not obstacles, bundles and edges with a free end are skipped;
  - edit operations ignore `SPINAGRAM_RUST=0`.

---

# Validation, second iteration (T9–T17)

**Result**: PASS. 2 surviving mutants found; fixed by the verifier's test commit on this branch (`test(web): cover overlapping zone headers…`).
**Verifier:** orchestrator session. The author was a separate Sonnet sub-agent.
**Diff range:** `857ec70..b99a21a`, 9 commits, one per task, plus the verifier's test commit.

## Gates (re-run independently)

| Gate | Result |
|---|---|
| `cargo test` | 206 passed |
| clippy `-D warnings`, `cargo deny` | clean |
| ruff | clean |
| pytest, Rust default / `SPINAGRAM_RUST=0` | 2848 passed, 3 skipped / 2848 passed, 3 skipped |
| wasm build + `bun test` | 21 pass |
| web `bun test` + build | 108 pass (109 after the verifier's tests); the rebuilt bundle equals the committed one |
| `bun install --frozen-lockfile` | Fails locally on this branch **and on `main`** with local bun 1.3.14, so the cause is the local version, not the hand edit of `web/bun.lock`. CI's pinned bun is the real check |

## Evidence (behaviour, from tests)

- **Reparent, zone cycles:** `rust/spinagram-core/src/edit.rs:1366`, `:1399` ("A zone cannot contain itself").
- **MoveZone:** `edit.rs:1415`, and `:1439` for a container inside the zone.
- **Group:** `edit.rs:1446`, `:1468`.
- **Remove from container, dissolve:** `edit.rs:1526`, `:1537`.
- **Canvas logic:** `web/src/canvas/canvas.test.ts` (drop target, zone move map, rubber band, grouping order,
  insertion index, palette ranking and ids, history cap and redo).

## Discrimination sensor

The mutants ran in a scratch worktree, which was removed afterwards; the porcelain is unchanged.

| Mutant | Result |
|---|---|
| N1 cycle check only refuses the zone itself | killed |
| N2 container dissolves at 1 member instead of 2 | killed |
| N3 Group does not order members | killed |
| N4 MoveZone leaves children in place | killed |
| N5 history has no 50-step cap | killed |
| N6 redo survives a new edit | killed |
| N7 new id never suffixed | killed |
| N8 `hitZone` picks the outermost zone | **survived**, then killed after the verifier's test (overlapping header bands) |
| N9 rubber band ignores the far-side bounds | **survived**, then killed after the verifier's test (band below and right of every node) |
| M3 (iteration 1) re-parse guard skipped | killed by T9 |

## Browser check (independent; scratch git copy of `examples/showcase/editable_platform.yaml`)

| Step | YAML diff |
|---|---|
| Double-click rename "Reports" → "Report store" | the `title` of `bucket` only |
| Rubber band over three nodes, then Group as column | one new `columns:` entry, `{x: 960, y: 570, gap: 20, nodes: [queue, bucket, monitor]}`, flow style like its neighbours |
| Cmd+Z twice | the file is byte-identical to the original |

## UX findings (not blocking, for the next iteration)

1. **Palette open by default:** it covers about a third of the diagram at 68 % zoom.
2. **Palette reopens itself:** after collapsing it, it opens again after the next canvas save (its collapsed state
   is lost on re-render).
3. **Badge overflow:** the "COLUMN" badge text overflows its chip in the palette list.
4. **Unneeded quotes:** a rename writes a quoted scalar (`"Report store"`) where a plain one would do. Valid, but
   it adds a diff character.
5. **Fragile example:** the example loads `showcase.css` and `aws.css` from its folder, so a copy without them
   fails with "No such file". That's expected, but the gallery card says only "preview unavailable".

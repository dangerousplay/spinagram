# Excalidraw backend Validation

**Date**: 2026-10-19
**Spec**: `.specs/features/excalidraw-backend/spec.md`
**Diff range**: `9a55725..HEAD` (`e589230`..`8e98b59`, 8 commits on `feat/excalidraw-mcp`)
**Verifier**: independent sub-agent (author ≠ verifier)
**Verdict**: FAIL

All 18 ACs have `file:line` evidence and both gates pass. The verdict is FAIL because the discrimination sensor left 9 of 23 mutants alive: they sit in contract rows the spec makes explicit (subpaths, polygon closing, binding fields, determinism across processes, multi-block centre placement, opacity rounding).

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 shapes, frame, ids | ✅ Done | marked `[x]`; "Done when" boxes left unticked in tasks.md |
| T2 symbol parts | ⚠️ Partial | multi-subpath parts and polygon closing are not discriminated (M08, M16) |
| T3 labels, text, fonts | ⚠️ Partial | multi-block `center` placement untested (M17) |
| T4 arrows, bindings | ⚠️ Partial | binding `focus`/`gap`/`mode` unasserted (M12, M13) |
| T5 icons/images | ✅ Done | `created: 0` unasserted (M22, minor) |
| T6 lines/tables | ✅ Done | - |
| T7 registry | ✅ Done | entry point in `pyproject.toml:56` is not asserted on its own (see gap 8) |
| T8 docs | ✅ Done | `SKILL.md` Outputs section |

Note: the feature commits also edited `spec.md` (EXC-05 rewritten to "one `line` per subpath, `polygon` true when closed"; EXC-17 rewritten to the SVG layer order; Kinds row gained the part-paint rule). This report checks against the amended spec at HEAD. The traceability footer still says "18 total, 0 mapped to tasks", which is stale.

---

## Spec-Anchored Acceptance Criteria

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| EXC-01 | backend `excalidraw` built-in + entry point, listed by `render --help` | `tests/test_excalidraw.py:380` `available()["excalidraw"] == "spinagram.backends.excalidraw:ExcalidrawBackend"`; `:381` `isinstance(get_backend("excalidraw"), ExcalidrawBackend)`; `:392` CLI `main([... "-f","excalidraw" ...]) == 0`. `--help` builds its list from `available()` (`src/spinagram/cli.py:64`) | ✅ PASS (entry point only covered indirectly, gap 8) |
| EXC-02 | `<out>/<slug>.excalidraw`, UTF-8 JSON, keys `type, version, source, elements, appState, files` | `:30` `list(doc) == ["type","version","source","elements","appState","files"]`; `:31-32` type/version/source values; `:38` `paths == [tmp_path / "d1.excalidraw"]`; `:39` `json.loads(read_text(encoding="utf-8"))` | ✅ PASS |
| EXC-03 | `roughness` 0 everywhere, `fillStyle` "solid" on filled shapes | `:58` `all(e["roughness"] == 0 ...)`; `:59` `all(e["fillStyle"] == "solid" ...)` | ✅ PASS |
| EXC-04 | x/y/w/h, fill→`backgroundColor`, stroke→`strokeColor`/`strokeWidth`, Kinds row type+roundness | `:66` geometry `(100,200,300,120)`; `:67` `("#112233","#FF0000",2.5)`; `:68` `roundness is None`; `:73` `{"type":3,"value":12}`; `:74` pill `{"type":3,"value":20}` (h/2 of 40); `:75` `"diamond"` | ✅ PASS |
| EXC-05 | one `line` per **subpath** of each part, `polygon` true when closed, points within 1 px of the 8-segment flattening, grouped; part paint `solid`/`stroke` | `:136` `len(lines) == 2`; `:137` `[True, False]`; `:140` shared group; `:147-148` length + ≤1 px per point; `:157-158` ring/dot paints; `:159-160` paint "shape" uses fill | ⚠️ Partial: every part in the fixture (`data`) has one subpath, and its closed body already ends on its start point. Tests stay green when only the first subpath is kept (M16) and when the closing point is not appended (M08). Real kinds hit by both: `predefined`, `flow_final` (2 subpaths per part); `document`, `predefined`, `decision`, `choice`, `merge` (closed subpath not ending on its start) |
| EXC-06 | text with `containerId` = shape id, in shape `boundElements`, `textAlign`/`verticalAlign` from label | `:177` `containerId == "a"`; `:178` `boundElements == [{"type":"text","id":t["id"]}]`; `:180` `("center","middle")`; `:190` `("left","top")`; `:182` geometry | ✅ PASS |
| EXC-07 | one text per block at `Label.place()` position, block font size + colour, grouped | `:203` `(t["x"], t["y"], t["fontSize"], t["strokeColor"]) == (x, top, b.font.size, b.color)`; `:200` `containerId is None`; `:206` shared group | ⚠️ Spec-precision gap + survivor M17: `place()` returns the block's centre x for `align="center"` (`scene.py:48`), but Excalidraw's `x` is the left edge, and the code shifts it (`excalidraw.py:116`). The spec does not say which x is meant, and only `align="left"` is tested |
| EXC-08 | `x + points[i]` = connector points (curve: 3 points), Arrowheads row, `strokeStyle` from dash | `:244` points round-trip; `:245` `"dashed"`, opacity 50; `:243` `elbowed is False`, `roundness is None`; `:251-252` curve 3 points + `{"type": 2}`; `:256-260` full marker map; `:262`, `:264` `None` | ✅ PASS |
| EXC-09 | binding `{elementId, focus: 0, gap: 1, fixedPoint, mode: "orbit"}`; shape `boundElements` lists the arrow | `:274` elementIds; `:275` `fixedPoint == [1, 0.5]`; `:276` `[0, 0.25]`; `:277-278` `boundElements == [{"type":"arrow","id":"e"}]` | ⚠️ Partial: the Bindings row's `focus: 0`, `gap: 1`, `mode: "orbit"` are never asserted (M12, M13 survive) |
| EXC-10 | label pill + text at the scene position, sharing a group with the arrow | `:295` rect geometry; `:296` text; `:297-298` non-empty shared group | ✅ PASS |
| EXC-11 | `image` at its box, `fileId` in `files`, `dataURL` decodes to the bytes, `mimeType` | `:315-316` boxes; `:319` `f["id"] == el["fileId"] and f["mimeType"] == mime`; `:321` `b64decode(data) == raw` | ✅ PASS (`created: 0` unasserted, M22) |
| EXC-12 | same bytes → one `files` entry | `:332` `len(els(doc,"image")) == 2 and len(doc["files"]) == 1` | ✅ PASS |
| EXC-13 | free texts with `textAlign` from anchor; `line` elements; per-cell rect + text grouped by table | `:216` `["left","center","right"]`; `:217` x shifts; `:353-355` line type/points/paint; `:367-368` cell boxes + fills; `:370` texts; `:373` single group `("g:t",)` | ✅ PASS |
| EXC-14 | `frame` `spinagram:<id>` at 0,0 with scene size; every other element's `frameId`; `viewBackgroundColor` | `:45` `name == "spinagram:D1"`; `:46` `(0,0,1920,1080)`; `:47` all `frameId == frame["id"]`; `:49` `"#101010"` | ✅ PASS |
| EXC-15 | `fontFamily` 2, or 3 for monospace; `fontSize` = block size | `:227` `(2, 18)`; `:228` `== 3`; `:229` lineHeight/autoResize (Text row) | ✅ PASS |
| EXC-16 | unique ids; same scene renders to byte-identical files | `:96` `len(ids) == len(set(ids))`; `:99` `one == two` | ⚠️ Partial: both renders run in the same process, so seeds taken from the salted built-in `hash()` (M14) pass. I confirmed the mutant writes different `seed` values under `PYTHONHASHSEED=1` and `2` (1362815603 vs 1142756797). The Determinism row's `version: 1` / `updated: 1` are also unasserted (M23) |
| EXC-17 | frame, then `zone`/`chrome`, then other items, then `pill`/`swatch`; scene order within layer; texts/icons right after the item | `:104` `ids[1:] == ["z","c","n","pill"]` | ✅ PASS |
| EXC-18 | SKILL.md `## Outputs` describes `-f excalidraw` (native elements, clean style, Excalidraw fonts, what is dropped) | `src/spinagram/agent_skills/spinagram/SKILL.md:237-240`: native editable elements, "no hand-drawn roughness", "Helvetica, or Cascadia", "Drop shadows are not drawn" | ✅ PASS (doc review; build gate) |

**Assumption rows checked**: Dashes `:85` (`["solid","dashed","dashed","dotted"]`, the ≤ 2 px threshold is discriminated); Opacity `:90` (`[50, 25, 100]`, product discriminated, but "rounded" is not: M15); Transparent `:80`; Text row `:179`, `:229`; Kinds/part paints `:157-160`.

**Status**: ❌ Gaps present: 1 spec-precision gap (EXC-07), 3 partially discriminated ACs (EXC-05, EXC-09, EXC-16)

---

## Edge Cases

- [x] Empty scene → only the frame: `tests/test_excalidraw.py:53` `[...types] == ["frame"]`
- [x] Missing icon → same error as SVG: `:342-345` `pytest.raises(FileNotFoundError)` for both `to_svg` and `to_excalidraw`
- [x] Unbound end → `null`: `:285` `endBinding is None and startBinding is not None`
- [x] Fill `None` + no stroke → both `"transparent"`, `strokeWidth` 1: `:80`

---

## Gate Check

- **Lint**: `uv run ruff check src tests examples` → `All checks passed!` (exit 0)
- **Build gate**: `uv run --all-extras pytest -q` → **659 passed, 3 skipped, 0 failed** (exit 0)
- **Quick gate**: `uv run --all-extras pytest -q tests/test_excalidraw.py` → 32 passed
- **Delta**: +32 tests (new file `tests/test_excalidraw.py`); no existing tests were removed or weakened
- **Skipped** (environmental, not part of this feature): `tests/test_autolayout.py:155`, `:165` (dot runtime not installed); `tests/test_pptx_svg.py:129` (soffice not installed)

---

## Discrimination Sensor

Scratch: `git worktree add --detach .../scratchpad/verify-exc HEAD`. I confirmed the worktree's venv imports the scratch `excalidraw.py`. Each mutant is a literal replacement in the scratch copy, then `uv run --all-extras pytest -q tests/test_excalidraw.py`, then the file is restored. The worktree was removed with `git worktree remove --force`. `git status --porcelain` on the real tree was empty both before and after.

| # | `src/spinagram/backends/excalidraw.py` | Mutation | Result |
| - | -------------------------------------- | -------- | ------ |
| M01 | :22 | arrowhead map swap `arrow`↔`open-arrow` | ✅ Killed (`test_arrowheads`) |
| M02 | :176 | `fixedPoint` axes swapped | ✅ Killed (`test_bindings`) |
| M03 | :241 | `frameId` left `None` | ✅ Killed (`test_frame_first_holds_everything`) |
| M04 | :61 | dotted threshold `<= 2` → `< 2` | ✅ Killed (`test_dashes`) |
| M05 | :195 | opacity ignores `fill_opacity` | ✅ Killed (`test_opacity`) |
| M06 | :112 | bound text `containerId` → `None` | ✅ Killed (`test_one_block_label_binds_into_the_shape`) |
| M07 | :125 | file id from path, not bytes (dedupe broken) | ✅ Killed (`test_same_bytes_stored_once`) |
| M08 | :49-50 | closed polygon not ended on its first point | ❌ **Survived** |
| M09 | :225 | layer sort removed (scene order) | ✅ Killed (`test_layer_order`) |
| M10 | :56 | monospace `fontFamily` 3 → 1 | ✅ Killed (`test_fonts`) |
| M11 | :154 | curve `roundness` → `null` | ✅ Killed (`test_curve_keeps_three_points_and_rounds`) |
| M12 | :176 | binding `mode` `"orbit"` → `"inside"` | ❌ **Survived** |
| M13 | :175 | binding `focus` 0 → 0.5, `gap` 1 → 0 | ❌ **Survived** |
| M14 | :32 | seed from built-in `hash()` (process-salted) | ❌ **Survived** (output differs across processes) |
| M15 | :195 | opacity `round()` → `int()` | ❌ **Survived** |
| M16 | :207 | only the first subpath of each part | ❌ **Survived** |
| M17 | :116 | multi-block centre x not shifted to the left edge | ❌ **Survived** |
| M18 | :44-45 | Bézier flattened to 4 segments | ✅ Killed (`test_symbol_parts_become_grouped_polygons`) |
| M19 | :213 | pill radius h/2 → h/4 | ✅ Killed (`test_kinds_and_roundness`) |
| M20 | :177 | shape does not list the bound arrow | ✅ Killed (`test_bindings`) |
| M21 | :164 | arrow left out of the edge-label group | ✅ Killed (`test_edge_label_grouped_with_arrow`) |
| M22 | :127 | file `created` 0 → 1 | ❌ **Survived** |
| M23 | :87 | `version` 1 → 2 | ❌ **Survived** |

**Sensor depth**: expanded (23 manual mutants; the orchestrator asked for ≥ 8)
**Result**: 14/23 killed, 9 survived → **FAIL ❌**

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code | ✅ one 261-line module, reusing `svg._mime`, `shapes.parse`, `text.measure` |
| Surgical changes | ✅ registry +1 line, entry point +1 line, SKILL.md +4 lines |
| No scope creep | ✅ |
| Matches patterns | ✅ follows the `SvgBackend.render` file loop |
| Spec-anchored outcome check | ⚠️ EXC-07 x semantics undefined; binding constants and determinism constants unasserted |
| Per-layer Coverage Expectation (1:1 EXC-02..17 + edge cases) | ⚠️ every AC has a test, but EXC-05, EXC-09 and EXC-16 are only partly discriminated |
| Every test maps to a spec requirement | ✅ each test is tagged with its EXC id, row or edge case |
| Documented guidelines followed | ✅ `pyproject.toml` (pytest, ruff); strong defaults applied |

---

## Ranked Gaps / Fix Plans

1. **[Major] EXC-05: multi-subpath parts untested (M16).** `predefined` and `flow_final` parts have 2 subpaths. Fix task: add a test on `predefined` that asserts the line count equals the total number of subpaths, and the points of each line against that subpath's own flattening. `tests/test_excalidraw.py:130-148`.
2. **[Major] EXC-05: polygon closing not discriminated (M08).** The `data` body already ends on its start point. Fix task: add a test with a closed subpath that does not return to its start (`decision` or `document`), and assert `points[-1] == points[0]` and `polygon is True`.
3. **[Major] EXC-16 / Determinism row: cross-process byte identity (M14).** Fix task: render the same scene in two subprocesses with different `PYTHONHASHSEED` values and compare bytes, or assert `seed == int.from_bytes(sha1(id)[:4]) % 2e9` for a known id. Also assert `version == 1` and `updated == 1` (M23). `tests/test_excalidraw.py:93-99`.
4. **[Major] EXC-09 / Bindings row: `focus`/`gap`/`mode` unasserted (M12, M13).** Fix task: assert the whole binding dict `== {"elementId":"a","focus":0,"gap":1,"fixedPoint":[1,0.5],"mode":"orbit"}`. `tests/test_excalidraw.py:274-276`.
5. **[Minor] EXC-07 spec-precision gap + M17.** Fix task: amend EXC-07 to say the text's `x` is the left edge of the label box (place() x − w/2 when centred), and add an `align="center"` multi-block test.
6. **[Minor] Opacity row "rounded" (M15).** Fix task: add a case where truncation and rounding differ (e.g. `opacity=0.29` → 29).
7. **[Minor] Icons row `created: 0` (M22).** Fix task: assert `f["created"] == 0`.
8. **[Minor] EXC-01 entry point.** `available()` is satisfied by `_BUILTIN` alone, so deleting `pyproject.toml:56` would still pass. Fix task: assert `excalidraw` in `importlib.metadata.entry_points(group="spinagram.backends")` names, and assert `excalidraw` in `render --help` output.
9. **[Cosmetic] spec.md traceability footer stale** ("0 mapped to tasks"); tasks.md "Done when" boxes unticked.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| EXC-01..04, EXC-06, EXC-08, EXC-10..15, EXC-17, EXC-18 | Implementing | ✅ Verified |
| EXC-05 | Implementing | ❌ Needs Fix (M08, M16) |
| EXC-07 | Implementing | ❌ Needs Fix (spec-precision gap, M17) |
| EXC-09 | Implementing | ❌ Needs Fix (M12, M13) |
| EXC-16 | Implementing | ❌ Needs Fix (M14, M23) |

(The Verifier does not edit spec.md; the orchestrator applies these statuses.)

---

## Summary

**Overall**: ❌ Not Ready

**Spec-anchored check**: 18/18 ACs have evidence; 14 fully match the spec outcome, 3 are partly discriminated (EXC-05, EXC-09, EXC-16), and 1 has a spec-precision gap (EXC-07)
**Sensor**: 23 mutants, 14 killed, 9 survived
**Gate**: ruff clean; 659 passed, 0 failed, 3 skipped (environmental)

**What works**: document skeleton, frame and frameId, clean style, native kinds and roundness, dashes and dotted threshold, opacity product, bound one-block labels, multi-block left-aligned labels, arrow points, curve roundness, arrowhead map, fixedPoint, boundElements, edge-label grouping, image embedding, dedupe, lines, tables, fonts, layer order, registry, docs.

**State check**: `python3 <skill-dir>/scripts/validate_state.py excalidraw-backend` exited 1 with `ERROR excalidraw-backend: validation.md verdict is FAIL - route the ranked gaps to fix tasks, then re-verify (feature is not done)`. That is the expected result for a FAIL verdict.

**Lessons recorded** (`scripts/lessons.py add`): L-001 (M14, now confirmed), L-014 (M12/M13/M22/M23, now confirmed), L-017 (M17, now confirmed), L-037 (M08/M16), L-038 (M15), L-039 (EXC-07 spec-precision gap).

**Next steps**: route gaps 1-8 to an implementer as test-strengthening fix tasks (plus the EXC-07 spec amendment), then re-verify (iteration 1 of 3).

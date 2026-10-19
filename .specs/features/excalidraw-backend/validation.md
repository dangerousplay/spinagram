# Excalidraw backend Validation

**Date**: 2026-10-19
**Spec**: `.specs/features/excalidraw-backend/spec.md`
**Diff range**: `9a55725..HEAD` (`e589230`..`b79feec`, 13 commits on `feat/excalidraw-mcp`; iteration-1 fixes `9b316bb..b79feec` changed only `tests/test_excalidraw.py`, `spec.md` and `tasks.md`; `excalidraw.py` is unchanged since iteration 1)
**Verifier**: independent sub-agent (author ≠ verifier), iteration 2 of 3
**Verdict**: FAIL

All 18 ACs have `file:line` evidence, both gates pass, and all 11 iteration-1 targets (M08, M12–M17, M22, M23, plus the entry point and built-in of gap 8) are now killed. The verdict is FAIL because 4 of 16 fresh mutants survived. Two of them are Major: a shape that has both a bound label and a bound arrow is never tested. That combination is the normal case in real diagrams, and it is where the arrow's `elementId` and the shape's `boundElements` can go wrong without any test failing.

---

## Iteration 1 (history)

FAIL: 9 of 23 mutants survived (M08, M12–M17, M22, M23), plus gap 8 (the entry point was not asserted on its own) and a spec-precision gap on EXC-07. Fix tasks T9–T12 added 10 tests, and EXC-07 was sharpened to name the left edge as the reference point. All of those targets are re-checked below.

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1–T8 | ✅ Done | Phase 1. Behaviour as in iteration 1 |
| T9 multi-subpath + closing | ✅ Done | M16, M08 killed |
| T10 payload fields | ✅ Done | M12, M13, M14, M15, M22, M23 killed |
| T11 centred multi-block | ✅ Done | M17 killed; EXC-07 now names the left edge |
| T12 entry point + help | ✅ Done | entry point (`pyproject.toml`) and `_BUILTIN` each killed on their own |

The "Done when" checkboxes in tasks.md (T9–T12) are still unticked (cosmetic).

---

## Spec-Anchored Acceptance Criteria

All test references are to `tests/test_excalidraw.py`.

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| EXC-01 | built-in + `spinagram.backends` entry point, listed by `render --help` | `:490` `_BUILTIN["excalidraw"] == target`; `:492` pyproject `entry-points["spinagram.backends"]["excalidraw"] == target`; `:500-502` `main(["render","--help"])` output contains `excalidraw`; `:380-381` `available()` / `get_backend` | ✅ PASS |
| EXC-02 | `<out>/<slug>.excalidraw`, UTF-8 JSON, keys in order | `:30` key list; `:31-32` values; `:38` `paths == [tmp_path / "d1.excalidraw"]`; `:39` utf-8 parse; `:392-397` every example | ✅ PASS |
| EXC-03 | `roughness` 0, `fillStyle` solid | `:58`, `:59` | ✅ PASS |
| EXC-04 | geometry, paints, Kinds-row type + roundness | `:66-68`, `:73-75` | ✅ PASS |
| EXC-05 | one `line` per subpath, `polygon` iff closed, ≤1 px of 8-seg flattening, grouped | `:136-148` (`data`); `:415` `len(lines) == len(subs) == 3` for `predefined`/`flow_final`; `:417` each line starts on its subpath; `:426-428` `document`/`decision`: `pts[-1] == pts[0]` | ✅ PASS |
| EXC-06 | `containerId`, in `boundElements`, align/valign | `:177-182`, `:190` | ✅ PASS for a shape with only a label. Not tested together with a bound arrow (N05, see gaps) |
| EXC-07 | one text per block, `width` = box width, `y` = place() top, `x` = left edge (x − w/2 when centred), block size + colour, grouped | `:203` left-aligned `(x, top, size, color)`; `:478-479` centred `(t["x"], t["y"], t["width"], t["textAlign"]) == (110, top, 280, "center")`; `:206` group | ✅ PASS |
| EXC-08 | `x + points[i]` = connector points, curve 3 pts, arrowheads, dash | `:243-246`, `:251-252`, `:256-264` | ✅ PASS |
| EXC-09 | binding `{elementId = shape's element id, focus 0, gap 1, fixedPoint, mode orbit}`; shape `boundElements` lists the arrow | `:274-278`; `:455` `(focus, gap, mode) == (0, 1, "orbit")` | ⚠️ Partial: only shapes with a single element (no label, no icon) are bound in tests. Binding to the shape's last element (N13) and dropping the label text from `boundElements` (N05) both survive |
| EXC-10 | pill + text at the scene position, grouped with the arrow | `:295-298` | ✅ PASS |
| EXC-11 | image at its box, `fileId` in files, dataURL bytes, mimeType; `created: 0` | `:315-321`; `:468` `created == [0]` | ✅ PASS |
| EXC-12 | same bytes → one file | `:332` | ✅ PASS |
| EXC-13 | free texts by anchor, lines, per-cell rect + text grouped | `:216-218`, `:353-355`, `:367-373` | ✅ PASS |
| EXC-14 | frame `spinagram:<id>` 0,0 scene size, `frameId`, viewBackgroundColor | `:45-49` | ✅ PASS |
| EXC-15 | `fontFamily` 2 / 3 monospace, `fontSize` | `:227-229` | ✅ PASS (mono only via the family name; fallback-only detection is unasserted, N01) |
| EXC-16 | unique ids; byte-identical re-render | `:96`, `:99`; `:440-442` subprocess `PYTHONHASHSEED` 1 vs 2 identical; `:447` `version`/`updated` 1 | ✅ PASS |
| EXC-17 | frame, `zone`/`chrome`, others, `pill`/`swatch` | `:104` `["z","c","n","pill"]` | ⚠️ Partial: the `swatch` role is never used in tests (N04 survives); real legends emit `role="swatch"` (`src/spinagram/annotate.py:270`, `src/spinagram/layout.py:391`) |
| EXC-18 | SKILL.md Outputs describes excalidraw | `src/spinagram/agent_skills/spinagram/SKILL.md:237-240` | ✅ PASS (doc review) |

**Assumption rows**: Dashes `:85`; Opacity `:90`, `:460` (rounding); Transparent `:80`; Text `:179`, `:229`; Part paints `:157-160`; Bindings `:455`; Determinism `:440-447`; Icons `:468`.

**Status**: ❌ Gaps present: EXC-09 and EXC-17 are only partly discriminated. No spec-precision gaps remain.

---

## Edge Cases

- [x] Empty scene → only the frame: `:53`
- [x] Missing icon → same error as SVG: `:342-345` (`FileNotFoundError` from both backends)
- [x] Unbound end → `null`: `:285`
- [x] Fill `None` and no stroke → `"transparent"` for both, `strokeWidth` 1: `:80`

---

## Gate Check

- **Lint**: `uv run ruff check src tests examples` → `All checks passed!` (exit 0)
- **Build gate**: `uv run --all-extras pytest -q` → **669 passed, 3 skipped, 0 failed**
- **Quick gate**: `tests/test_excalidraw.py` → 42 passed
- **Delta**: +10 tests since iteration 1 (659 → 669). No tests were removed or weakened.
- **Skipped** (environmental, unchanged): `tests/test_autolayout.py:155`, `:165` (dot not installed); `tests/test_pptx_svg.py:129` (soffice not installed)

---

## Discrimination Sensor

Scratch: `git worktree add --detach <scratchpad>/verify-exc2 HEAD`, with its own venv. I confirmed `spinagram.backends.excalidraw.__file__` resolves into the worktree, and ran with `PYTHONPATH=<worktree>/src` (the subprocess test inherits it). Each mutant is one literal replacement, followed by `uv run --all-extras pytest -q -x tests/test_excalidraw.py` and then `git checkout -- <file>`. The worktree was removed with `git worktree remove --force`. Real-tree `git status --porcelain` was empty before and after (diff identical).

### Iteration-1 survivors (re-run)

| # | Location | Mutation | Result |
| - | -------- | -------- | ------ |
| M08 | `excalidraw.py:49-50` | closing point not appended | ✅ Killed (`test_closed_subpath_ends_on_its_start`) |
| M12 | `:176` | `mode` "orbit" → "inside" | ✅ Killed (`test_binding_fields`) |
| M13 | `:175` | `focus` 0.5, `gap` 0 | ✅ Killed (`test_binding_fields`) |
| M14 | `:32` | seed from salted `hash()` | ✅ Killed (`test_same_bytes_across_interpreter_runs`) |
| M15 | `:195` | opacity `round` → `int` | ✅ Killed (`test_opacity_is_rounded`) |
| M16 | `:207` | only the first subpath | ✅ Killed (`test_every_subpath_of_a_part_is_drawn`) |
| M17 | `:116` | centred x not shifted | ✅ Killed (`test_centred_multi_block_label_uses_the_left_edge`) |
| M22 | `:127` | `created` 1 | ✅ Killed (`test_file_created_is_zero`) |
| M23 | `:87` | `version` 2 | ✅ Killed (`test_fixed_version_fields`, re-run without `-x`) |
| G8a | `pyproject.toml:56` | entry point deleted | ✅ Killed (`test_entry_point_and_builtin`) |
| G8b | `backends/__init__.py:21` | built-in deleted | ✅ Killed (`test_entry_point_and_builtin`) |

### Fresh mutants (not used in iteration 1)

| # | `excalidraw.py` | Mutation | Result |
| - | --------------- | -------- | ------ |
| N01 | :56 | monospace detected from the family name only (fallback ignored) | ❌ **Survived** |
| N02 | :203 | part paint `solid` prefers fill over stroke | ✅ Killed (`test_part_paints`) |
| N03 | :206 | part paint `stroke` keeps the fill | ✅ Killed (`test_part_paints`) |
| N04 | :21 | `swatch` removed from the front layer | ❌ **Survived** |
| N05 | :177 | bind overwrites `boundElements` (bound label text dropped) | ❌ **Survived** |
| N06 | :120 | `end` anchor shifts by w/2 | ✅ Killed (`test_free_text_anchor_alignment`) |
| N07 | :142 | table cell text not vertically centred | ✅ Killed (`test_table_cells_grouped`) |
| N08 | :208 | `polygon` always true | ✅ Killed (`test_symbol_parts_become_grouped_polygons`) |
| N09 | :116 | every multi-block text uses the first block | ✅ Killed (`test_multi_block_label_is_grouped_free_text`) |
| N10 | :79 | uid does not record ids (duplicate ids) | ✅ Killed (`test_unique_ids_and_deterministic`) |
| N11 | :154 | `poly` routes get curve roundness | ✅ Killed (`test_arrow_points_and_paint`) |
| N12 | :166 | label pill keeps its own group instead of joining the arrow's | ✅ Killed (`test_edge_label_grouped_with_arrow`) |
| N13 | :182 | binding target = shape's last element (its text/icon) | ❌ **Survived** |
| N14 | :243 | `viewBackgroundColor` hard-coded | ✅ Killed (`test_frame_first_holds_everything`) |
| N15 | :61 | dotted threshold reads the gap, not the dash | ✅ Killed (`test_dashes`) |
| N16 | :105 | `lineHeight` fixed at 1.25 | ✅ Killed (`test_fonts`) |

(A first draft of N10, `out = key`, made `uid` loop forever. I replaced it with the non-hanging variant above.)

**Sensor depth**: expanded (11 re-runs + 16 fresh = 27 mutants)
**Result**: 23/27 killed. Re-runs 11/11 killed; fresh 12/16 killed, 4 survived → **FAIL ❌**

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / surgical / no scope creep / matches patterns | ✅ (unchanged since iteration 1) |
| Spec-anchored outcome check | ✅ every asserted value matches the spec; EXC-07 precision gap closed |
| Per-layer Coverage Expectation | ⚠️ EXC-09 (label + arrow on one shape) and EXC-17 (`swatch`) are only partly discriminated |
| Every test maps to a spec requirement | ✅ each test is tagged with its EXC id, row or edge case |
| Documented guidelines followed | ✅ `pyproject.toml` (pytest, ruff); strong defaults applied |

---

## Ranked Gaps / Fix Plans

1. **[Major] EXC-09: binding a labelled shape (N13).** If `by_shape` held the shape's last element (its bound text or icon), arrows would bind to the label, and no test would fail. Fix task: in a binding test, give the bound shape a one-block label (and an icon), then assert `startBinding["elementId"] == "a"` (the rectangle) and that the text id is not the target. Where: `tests/test_excalidraw.py` next to `:267-278`.
2. **[Major] EXC-06 + EXC-09 conjunction: `boundElements` keeps both (N05).** Fix task: same fixture. Assert the shape's `boundElements == [{"type":"text","id":<text id>}, {"type":"arrow","id":"e"}]`.
3. **[Minor] EXC-17: `swatch` layer (N04).** Fix task: add `box("s", role="swatch")` to `test_layer_order` (`:103-104`) and assert it comes after the other items, alongside `pill`.
4. **[Minor] EXC-15: monospace by fallback (N01).** Fix task: assert `fontFamily == 3` for `family="Courier New", fallback="monospace"`.
5. **[Cosmetic]** The tasks.md T9–T12 "Done when" boxes are unticked.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| EXC-01..05, EXC-07, EXC-08, EXC-10..14, EXC-16, EXC-18 | Implementing / Needs Fix | ✅ Verified |
| EXC-06 | Implementing | ❌ Needs Fix (N05, together with EXC-09) |
| EXC-09 | Needs Fix | ❌ Needs Fix (N05, N13) |
| EXC-15 | Implementing | ❌ Needs Fix (N01, minor) |
| EXC-17 | Implementing | ❌ Needs Fix (N04, minor) |

(The Verifier does not edit spec.md; the orchestrator applies these statuses.)

---

## Summary

**Overall**: ❌ Not Ready (iteration 2 of 3)

**Spec-anchored check**: 18/18 ACs have evidence and match the spec outcome; 0 spec-precision gaps; EXC-09 and EXC-17 partly discriminated
**Sensor**: 27 mutants, 23 killed, 4 survived (N01, N04, N05, N13)
**Gate**: ruff clean; 669 passed, 0 failed, 3 skipped (environmental)

**What works**: every iteration-1 gap is closed (subpaths, polygon closing, binding constants, cross-process determinism, opacity rounding, centred multi-block x, file `created`, `version`/`updated`, entry point, built-in, help listing), plus everything verified in iteration 1.

**State check**: `python3 <skill-dir>/scripts/validate_state.py excalidraw-backend` exits 1 (verdict FAIL). That is the expected result for a FAIL.

**Lessons recorded** (`scripts/lessons.py add`): L-040 (N05/N13), L-020 (N04, recurred; promoted to confirmed), L-041 (N01).

**Next steps**: route gaps 1–4 as test-only fix tasks, then re-verify (iteration 3 of 3).

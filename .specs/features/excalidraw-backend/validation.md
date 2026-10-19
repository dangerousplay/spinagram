# Excalidraw backend Validation

**Date**: 2026-10-19
**Spec**: `.specs/features/excalidraw-backend/spec.md`
**Diff range**: `9a55725..HEAD` (`e589230`..`5315694`, 16 commits on `feat/excalidraw-mcp`; iteration-2 fixes `4160102..5315694` changed only `tests/test_excalidraw.py` (+26 lines) and `tasks.md`; `excalidraw.py` is unchanged since iteration 1)
**Verifier**: independent sub-agent (author ≠ verifier), iteration 3 of 3
**Verdict**: FAIL

All 18 ACs have `file:line` evidence, both gates pass, and the four iteration-2 survivors (N01, N04, N05, N13) are now killed. The verdict is FAIL because 4 of 19 fresh mutants survived in spec-stated rules. One of them is Major: no test binds an arrow to a symbol shape (one with `parts`, such as a cylinder). If the binding pointed at the shape's last subpath line instead of its first element, no test would fail. Six other survivors are equivalent or have no spec rule, and are not gaps (see the sensor table). This is the last iteration, so the gaps go to the user.

---

## History

- **Iteration 1**: FAIL. 9 of 23 mutants survived (M08, M12–M17, M22, M23), plus gap 8 (entry point) and a spec-precision gap on EXC-07. Fixed by T9–T12.
- **Iteration 2**: FAIL. Re-runs 11/11 killed; 4 of 16 fresh mutants survived (N01 mono fallback, N04 `swatch` layer, N05 `boundElements` overwrite, N13 binding to the shape's last element). Fixed by T13–T14.

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1–T12 | ✅ Done | As verified in iterations 1–2 |
| T13 bindings on a composed shape | ✅ Done | N05 and N13 killed (`test_binding_on_a_labelled_shape_with_an_icon`) |
| T14 swatch + mono fallback | ✅ Done | N04 and N01 killed |

The T13/T14 "Done when" boxes in tasks.md are unticked (cosmetic).

---

## Spec-Anchored Acceptance Criteria

All test references are to `tests/test_excalidraw.py`.

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| EXC-01 | built-in + entry point, listed by `render --help` | `:490` `_BUILTIN[...] == target`; `:492` pyproject entry point; `:500-502` help output; `:380-381` | ✅ PASS |
| EXC-02 | `<out>/<slug>.excalidraw`, UTF-8 JSON, the six keys | `:30-33`; `:38-39`; `:392-397` | ✅ PASS |
| EXC-03 | `roughness` 0, `fillStyle` solid | `:58-59` | ✅ PASS |
| EXC-04 | geometry, paints, Kinds-row type + roundness | `:66-68`, `:73-75` | ✅ PASS |
| EXC-05 | one `line` per subpath, `polygon` iff closed, ≤1 px, grouped | `:136-148`, `:415-417`, `:426-428` | ✅ PASS |
| EXC-06 | `containerId`, in `boundElements`, align/valign | `:177-182`, `:190`; with an arrow on the same shape `:515` `boundElements == [text, arrow]` | ✅ PASS |
| EXC-07 | one text per block, width, place() top, left edge, size + colour, grouped | `:203`, `:478-479`, `:206` | ✅ PASS |
| EXC-08 | `x + points[i]`, curve 3 points, arrowheads, dash | `:243-246`, `:251-252`, `:256-264` | ✅ PASS |
| EXC-09 | binding `elementId` = the shape's element id, fixedPoint, constants; shape lists the arrow | `:274-278`, `:455`, `:514` `elementId == "a"` on a labelled shape with an icon | ⚠️ Partial: never bound to a symbol shape with `parts`, whose element id sits on its first `line` (N13b survives) |
| EXC-10 | pill + text at the scene position, grouped with the arrow | `:295-298` | ✅ PASS |
| EXC-11 | image at its box, fileId, dataURL bytes, mimeType, `created` 0 | `:315-321`, `:468` | ✅ PASS |
| EXC-12 | same bytes → one file | `:332` | ✅ PASS |
| EXC-13 | free texts by anchor, lines, per-cell rect + text grouped | `:216-218`, `:353-355`, `:367-373` | ✅ PASS |
| EXC-14 | frame `spinagram:<id>` at 0,0, scene size, frameId, background | `:45-49` | ✅ PASS |
| EXC-15 | `fontFamily` 2 / 3 for monospace, `fontSize` = block size | `:227-229`, `:528` (mono by fallback) | ⚠️ Partial: only integer sizes are tested, so a truncated `fontSize` survives (P10). Monospace is only tested with a `monospace` fallback, so a family named "… Mono" with another fallback is not discriminated (P16) |
| EXC-16 | unique ids; byte-identical | `:96`, `:99`, `:440-442`, `:447` | ✅ PASS |
| EXC-17 | frame, `zone`/`chrome`, others, `pill`/`swatch` | `:104`, `:521` `["z","n","sw"]` | ✅ PASS |
| EXC-18 | SKILL.md Outputs describes excalidraw | `src/spinagram/agent_skills/spinagram/SKILL.md:237-240` | ✅ PASS (doc review) |

**Assumption rows**: Dashes `:85`; Opacity `:90`, `:460`; Transparent `:80` (only `stroke=None` is tested; the case of a stroke colour with width 0 is not, P17); Text `:179`, `:229`; Part paints `:157-160`; Bindings `:455`; Determinism `:440-447`; Icons `:468`.

**Status**: ❌ Gaps present: EXC-09, EXC-15 and the Transparent row are only partly discriminated. No spec-precision gaps.

---

## Edge Cases

- [x] Empty scene → only the frame: `:53`
- [x] Missing icon → same error as SVG: `:342-345`
- [x] Unbound end → `null`: `:285`
- [x] Fill `None` and no stroke → `"transparent"` for both: `:80`

---

## Gate Check

- **Lint**: `uv run ruff check src tests examples` → `All checks passed!` (exit 0)
- **Build gate**: `uv run --all-extras pytest -q` (with `set -o pipefail`) → **672 passed, 3 skipped, 0 failed** (exit 0)
- **Quick gate**: `tests/test_excalidraw.py` → 45 passed
- **Delta**: +3 tests since iteration 2 (669 → 672). None removed or weakened.
- **Skipped** (environmental, unchanged): `tests/test_autolayout.py:155`, `:165` (dot not installed); `tests/test_pptx_svg.py:129` (soffice not installed)

---

## Discrimination Sensor

Scratch: `git worktree add --detach <scratchpad>/verify-exc3 HEAD`. Tests ran with the project venv's Python and `PYTHONPATH=<worktree>/src`. I confirmed `spinagram.backends.excalidraw.__file__` resolves into the worktree, and the subprocess test inherits that path. Each mutant is one literal replacement (pattern count checked as 1), followed by `pytest -q tests/test_excalidraw.py` and a restore. The file was confirmed restored at the end. The worktree was removed with `git worktree remove --force`, and the real tree's `git status --porcelain` was empty before and after (identical to the baseline).

### Iteration-2 survivors (re-run)

| # | Mutation | Result |
| - | -------- | ------ |
| N01 | monospace read from the family name only | ✅ Killed (`test_monospace_from_the_fallback`) |
| N04 | `swatch` removed from the front layer | ✅ Killed (`test_swatch_draws_in_front`) |
| N05 | bind overwrites `boundElements` | ✅ Killed (`test_binding_on_a_labelled_shape_with_an_icon`) |
| N13 | `by_shape` = the shape's last element after its icon and label | ✅ Killed (same test) |

Note: my first N13 draft replaced `:182` in place with `self.by_shape[s.id] = self.elements[-1]`. At that line only the outline exists, so that draft does not change rectangles, and it survived. For a symbol shape, though, it does change the output (elementId `db~2` instead of `db`). That case is recorded as N13b below. The faithful N13 moves the assignment after the icon and label are added, and it is killed.

### Fresh mutants (not used in iterations 1–2)

| # | `excalidraw.py` | Mutation | Result | Classification |
| - | --------------- | -------- | ------ | -------------- |
| N13b | :182 | binding target = last outline element (a symbol shape's last subpath `line`) | ❌ **Survived** | **Gap (Major)**, EXC-09: `elementId` must be the shape's element id (`db`); the probe gives `db~2` |
| P01 | :120 | `middle` anchor not shifted | ✅ Killed (`test_free_text_anchor_alignment`) | |
| P02 | :137 | cell fill always transparent | ✅ Killed (`test_table_cells_grouped`) | |
| P03 | :142 | cell text ignores `pad_left` | ✅ Killed (`test_table_cells_grouped`) | |
| P04 | :144 | row rules on row 0 instead of rows ≥ 1 | ❌ Survived | **Not a gap**: no spec rule covers row rules (the Tables row says rectangle + text per cell only) |
| P05 | :219 | frame named by slug | ✅ Killed (`test_frame_first_holds_everything`) | |
| P06 | :189 | group only when > 2 elements | ✅ Killed (`test_icon_and_image_become_image_elements`) | |
| P07 | :127 | `files.setdefault` → plain assignment | ❌ Survived | **Equivalent**: the same bytes give the same sha1 key and an identical entry, and dict position is kept on reassignment, so the document is identical |
| P08 | :152 | arrow `strokeWidth` fixed at 1 | ✅ Killed (`test_arrow_points_and_paint`) | |
| P09 | :155 | start arrowhead ignores `arrow_start` | ✅ Killed (`test_arrowheads`) | |
| P10 | :103 | `fontSize` = `int(size)` | ❌ **Survived** | **Gap (Minor)**, EXC-15: `fontSize` = the block's size. 13.5 would become 13. Every fixture size is an integer |
| P11 | :174 | anchor `frac` ignored (0.5) | ✅ Killed (`test_bindings`) | |
| P12 | :203-204 | solid part keeps the shape's `strokeWidth` | ❌ Survived | **Not a gap**: the stroke is already `"transparent"`, so nothing is drawn. The Kinds row only fixes the fill, and the Transparent row is about shapes without a stroke |
| P13 | :259 | `ensure_ascii=True` | ❌ Survived | **Equivalent**: the parsed JSON is identical, still valid UTF-8 and still deterministic. Only the escaping of non-ASCII characters changes |
| P14 | :121 | `end` anchor → `left` | ✅ Killed (`test_free_text_anchor_alignment`) | |
| P15 | :166 | label parts lose their own group (replaced by the arrow's) | ❌ Survived | **Not a gap**: EXC-10 only requires a group id shared with the arrow, which still holds |
| P16 | :56 | mono detected only by the token `monospace` | ❌ **Survived** | **Gap (Minor)**, EXC-15: a monospace family such as `Roboto Mono` with a non-generic fallback falls back to 2 |
| P17 | :196 | stroke kept when `stroke_width` is 0 | ❌ **Survived** | **Gap (Minor)**, Transparent row: no stroke → `"transparent"`, width 1. The SVG backend treats width 0 as no stroke (`backends/svg.py:130`), but the mutant writes the colour with width 0 |
| P18 | :172 | zero-size guard removed | ❌ Survived | **Not a gap**: no spec rule; it only matters for zero-size shapes (division by zero) |

**Sensor depth**: expanded (4 re-runs + 19 fresh = 23 mutants, plus the discarded no-op N13 draft)
**Result**: 13/23 killed. Re-runs 4/4 killed. Fresh: 9 killed, 10 survived. Of the 10 survivors, 2 are equivalent (P07, P13), 3 have no spec rule (P04, P15, P18) and are not gaps, P12 is visually equivalent and has no spec rule, and **4 are gaps** (N13b, P10, P16, P17) → **FAIL ❌**

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / surgical / no scope creep / matches patterns | ✅ (source unchanged since iteration 1) |
| Spec-anchored outcome check | ✅ every asserted value matches the spec |
| Per-layer Coverage Expectation | ⚠️ EXC-09 (symbol shapes), EXC-15 (fractional sizes, mono by name) and the Transparent row (stroke width 0) are only partly discriminated |
| Every test maps to a spec requirement | ✅ each test is tagged with its EXC id, row or edge case |
| Documented guidelines followed | ✅ `pyproject.toml` (pytest, ruff); strong defaults applied |

---

## Ranked Gaps / Fix Plans

1. **[Major] EXC-09: binding to a symbol shape (N13b).** Fix task: bind a connector to `Shape(kind="data", parts=shapes.parts(...))`. Assert `endBinding["elementId"] == "db"` (the first `line`) and that `by_id(doc, "db")["boundElements"]` lists the arrow. Where: `tests/test_excalidraw.py`, next to `:506`.
2. **[Minor] EXC-15: fractional `fontSize` (P10).** Fix task: a text with `size=13.5` asserts `fontSize == 13.5`.
3. **[Minor] EXC-15: monospace family name (P16).** Fix task: `family="Roboto Mono", fallback="sans-serif"` gives `fontFamily == 3`.
4. **[Minor] Transparent row: a stroke colour with width 0 (P17).** Fix task: `box(stroke="#333333", stroke_width=0)` gives `(strokeColor, strokeWidth) == ("transparent", 1)`.
5. **[Cosmetic]** The T13/T14 "Done when" boxes in tasks.md are unticked.

All four are test-only fixes; the code already behaves as the spec says. This is iteration 3 of 3, so the gaps go to the user, who decides between a fourth round and accepting them.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| EXC-01..08, EXC-10..14, EXC-16..18 | Verified / Needs Fix | ✅ Verified |
| EXC-09 | Needs Fix | ❌ Needs Fix (N13b, symbol shapes) |
| EXC-15 | Needs Fix | ❌ Needs Fix (P10, P16, minor) |

(The Verifier does not edit spec.md; the orchestrator applies these statuses.)

---

## Summary

**Overall**: ❌ Not Ready (iteration 3 of 3, escalate)

**Spec-anchored check**: 18/18 ACs have evidence and match the spec outcome; 0 spec-precision gaps; EXC-09, EXC-15 and the Transparent row are only partly discriminated
**Sensor**: 23 mutants, 13 killed, 10 survived (4 gaps: N13b, P10, P16, P17; 6 equivalent or with no spec rule: P04, P07, P12, P13, P15, P18)
**Gate**: ruff clean; 672 passed, 0 failed, 3 skipped (environmental)

**What works**: every iteration-1 and iteration-2 gap is closed, including the labelled + icon shape binding, `boundElements` keeping text and arrow, the `swatch` layer and mono by fallback.

**State check**: `python3 <skill-dir>/scripts/validate_state.py excalidraw-backend` exits 1 (verdict FAIL). That is the expected result for a FAIL.

**Lessons recorded** (`scripts/lessons.py add`): L-042 (N13b), L-043 (P10), L-041 (P16, same feature, recurrence unchanged), L-044 (P17).

**Next steps**: escalate the 4 gaps to the user (iteration bound reached). The fixes are test-only, about 4 short tests.

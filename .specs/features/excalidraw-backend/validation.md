# Excalidraw backend Validation

**Date**: 2026-10-19
**Spec**: `.specs/features/excalidraw-backend/spec.md`
**Diff range**: `9a55725..HEAD` (`e589230`..`26bd1ad`, 18 commits on `feat/excalidraw-mcp`; the iteration-3 fix `26bd1ad` changed only `tests/test_excalidraw.py` (+29 lines) and `tasks.md`; `excalidraw.py` is unchanged since iteration 1)
**Verifier**: independent sub-agent (author ≠ verifier), iteration 4 (the user approved a 4th pass after iteration 3 escalated)
**Verdict**: FAIL

All 18 ACs have `file:line` evidence, both gates pass, and the four iteration-3 gaps (N13b, P10, P16, P17) are now killed. The verdict is FAIL because 8 of 12 fresh mutants survived, and each one breaks a rule the spec states. They share one cause: the cross-cutting rules (Dashes, Opacity, EXC-03 style, the Arrowheads `none` entry, EXC-17 child order, pill radius) are tested only on the plainest element (a native rectangle, the start arrowhead, a shape with no children). The same rule on symbol polygons, arrows, texts, the end arrowhead or a labelled shape is untested. The code is correct in every one of these cases (probed below), so all the fixes are test-only.

---

## History

- **Iteration 1**: FAIL. 9 of 23 mutants survived (M08, M12–M17, M22, M23), plus gap 8 (entry point) and a spec-precision gap on EXC-07. Fixed by T9–T12.
- **Iteration 2**: FAIL. Re-runs 11/11 killed; 4 of 16 fresh mutants survived (N01 mono fallback, N04 `swatch` layer, N05 `boundElements` overwrite, N13 binding to the last element). Fixed by T13–T14.
- **Iteration 3**: FAIL. Re-runs 4/4 killed; 4 of 19 fresh mutants were gaps (N13b symbol-shape binding, P10 truncated `fontSize`, P16 mono by family name, P17 stroke at width 0). Six survivors were judged not gaps: P04 (row rules, no spec rule), P07 (`setdefault` → assignment, equivalent), P12 (solid part `strokeWidth`, nothing drawn), P13 (`ensure_ascii`, equivalent JSON), P15 (label keeps own group, EXC-10 still holds), P18 (zero-size guard, no rule). Escalated, then fixed by T15.

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1–T14 | ✅ Done | As verified in iterations 1–3 |
| T15 symbol bindings, font size, mono family, zero-width stroke | ✅ Done | N13b, P10, P16, P17 killed (`:532-557`) |

The T15 "Done when" boxes in tasks.md are unticked (cosmetic).

---

## Spec-Anchored Acceptance Criteria

All test references are to `tests/test_excalidraw.py`.

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| EXC-01 | built-in + entry point, listed by `render --help` | `:490` `_BUILTIN["excalidraw"] == target`; `:492` pyproject entry point; `:502` help output; `:380-381` | ✅ PASS |
| EXC-02 | `<out>/<slug>.excalidraw`, UTF-8 JSON, the six keys | `:30-33`; `:38-39`; `:392-397` | ✅ PASS |
| EXC-03 | `roughness` 0 on every element, `fillStyle` solid on every filled shape | `:58-59` (rectangle + diamond only) | ⚠️ Partial: texts and symbol polygons are never checked (Q06, Q07 survive) |
| EXC-04 | geometry, paints, Kinds-row type + roundness | `:66-68`, `:73-75`, `:557` | ⚠️ Partial: no pill carries its own radius, so "pill → h/2" is indistinguishable from "use the radius" (Q03) |
| EXC-05 | one `line` per subpath, `polygon` iff closed, ≤1 px, grouped | `:136-148`, `:415-417`, `:426-428` | ✅ PASS |
| EXC-06 | `containerId`, in `boundElements`, align/valign | `:177-182`, `:190`, `:515` | ✅ PASS |
| EXC-07 | one text per block, width, place() top, left edge, size + colour, grouped | `:203`, `:478-479`, `:206` | ✅ PASS |
| EXC-08 | `x + points[i]`, curve 3 points, arrowheads, `strokeStyle` from its dash | `:243-246`, `:251-252`, `:256-264` | ⚠️ Partial: only `dashed=True` is tested; a `dash` pattern on an arrow is ignored without failing (Q01); `marker_end="none"` is untested (Q02) |
| EXC-09 | binding `elementId` = the shape's element id, fixedPoint, constants; shape lists the arrow | `:274-278`, `:455`, `:514`, `:538-539` (symbol shape `db`) | ✅ PASS |
| EXC-10 | pill + text at the scene position, grouped with the arrow | `:295-298` | ✅ PASS |
| EXC-11 | image at its box, fileId, dataURL bytes, mimeType, `created` 0 | `:315-321`, `:468` | ✅ PASS |
| EXC-12 | same bytes → one file | `:332` | ✅ PASS |
| EXC-13 | free texts by anchor, lines, per-cell rect + text grouped | `:216-218`, `:353-355`, `:367-373` | ✅ PASS |
| EXC-14 | frame `spinagram:<id>` at 0,0, scene size, frameId, background | `:45-49` | ✅ PASS |
| EXC-15 | `fontFamily` 2 / 3 for monospace, `fontSize` = block size | `:227-229`, `:528`, `:545` (13.5), `:552` (Roboto Mono + sans) | ✅ PASS |
| EXC-16 | unique ids; byte-identical | `:96`, `:99`, `:440-442`, `:447` | ✅ PASS |
| EXC-17 | frame, `zone`/`chrome`, others, `pill`/`swatch`; each item's texts and icons right after it | `:104`, `:521` | ⚠️ Partial: no order test has a labelled shape, so moving every text to the end survives (Q09) |
| EXC-18 | SKILL.md Outputs describes excalidraw | `src/spinagram/agent_skills/spinagram/SKILL.md:237-240` | ✅ PASS (doc review) |

**Assumption rows**: Dashes `:85` (native shapes only; arrows Q01, polygons Q05 not discriminated); Opacity `:90`, `:460` (native shapes and arrows; polygons Q04 not discriminated); Transparent `:80`, `:557`; Text `:179`, `:229`; Part paints `:157-160`; Bindings `:455`; Determinism `:440-447`; Icons `:468`; Arrowheads `:256-264` (end `none` Q02 not discriminated).

**Status**: ❌ Gaps present: EXC-03, EXC-04, EXC-08, EXC-17 and the Dashes / Opacity / Arrowheads rows are only partly discriminated. No spec-precision gaps.

---

## Edge Cases

- [x] Empty scene → only the frame: `:53`
- [x] Missing icon → same error as SVG: `:342-345`
- [x] Unbound end → `null`: `:285`
- [x] Fill `None` and no stroke → `"transparent"` for both: `:80`

---

## Gate Check

- **Lint**: `uv run ruff check src tests examples` → `All checks passed!` (exit 0)
- **Build gate**: `uv run --all-extras pytest -q` (with `set -o pipefail`) → **676 passed, 3 skipped, 0 failed** (exit 0)
- **Quick gate**: `tests/test_excalidraw.py` → 49 passed
- **Delta**: +4 tests since iteration 3 (672 → 676). None removed or weakened.
- **Skipped** (environmental, unchanged): `tests/test_autolayout.py:155`, `:165` (dot not installed); `tests/test_pptx_svg.py:129` (soffice not installed)

---

## Discrimination Sensor

Scratch: `git worktree add --detach <scratchpad>/verify-exc4 HEAD`. Tests ran with the project venv's Python and `PYTHONPATH=<worktree>/src`; `spinagram.backends.excalidraw.__file__` resolved into the worktree, and the unmutated quick gate passed there (49). Each mutant is a literal replacement whose pattern count was checked as 1, followed by `pytest -q tests/test_excalidraw.py` and a restore (file confirmed identical at the end). For every survivor, a probe script printed the unmutated output (correct per spec) and the mutated output (wrong), so none is equivalent. The worktree was removed with `git worktree remove --force` (no prune). The real tree's `git status --porcelain` was empty before and after, identical to the baseline.

### Iteration-3 gaps (faithful re-runs)

| # | Mutation | Result |
| - | -------- | ------ |
| N13b | `by_shape` = `self.elements[-1]` right after the outline (a `parts` shape's last subpath line) | ✅ Killed (`test_binding_on_a_symbol_shape`) |
| P10 | `fontSize=int(block.font.size)` | ✅ Killed (`test_fractional_font_size`) |
| P16 | mono only if `"monospace"` appears in family + fallback | ✅ Killed (`test_monospace_from_the_family`) |
| P17 | `if s.stroke:` (colour kept at width 0) | ✅ Killed (`test_zero_width_stroke_is_transparent`) |

### Fresh mutants (not used in iterations 1–3)

| # | `excalidraw.py` | Mutation | Probe: correct → mutant | Result | Classification |
| - | --------------- | -------- | ----------------------- | ------ | -------------- |
| Q01 | :153 | arrow `strokeStyle` ignores the `dash` pattern | `dash=[2,3]`: `dotted` → `solid` | ❌ **Survived** | **Gap**, EXC-08 "strokeStyle from its dash" + Dashes row |
| Q02 | :156 | end arrowhead defaults to `triangle` for an unmapped marker | `marker_end="none"`: `null` → `triangle` | ❌ **Survived** | **Gap**, Arrowheads row (`none` → `null`) |
| Q03 | :213 | `radius = s.radius or (h/2 if pill)` | pill h=40 radius=8: 20 → 8 | ❌ **Survived** | **Gap**, Kinds row (pill → `h/2`) |
| Q04 | :201 | part lines get `opacity` 100 | symbol at opacity 0.5: 50 → 100 | ❌ **Survived** | **Gap**, Opacity row |
| Q05 | :201 | part lines always `strokeStyle` solid | dashed symbol: `dashed` → `solid` | ❌ **Survived** | **Gap**, Dashes row |
| Q06 | :105 | texts get `roughness` 1 | free text: 0 → 1 | ❌ **Survived** | **Gap**, EXC-03 (every element roughness 0) |
| Q07 | :201 | part lines get `fillStyle` `hachure` | filled polygon: `solid` → `hachure` | ❌ **Survived** | **Gap**, EXC-03 (every filled shape solid) |
| Q08 | :259 | file written as cp1252 | — | ✅ Killed (`test_render_examples_with_the_cli`) | |
| Q09 | :239 | every text moved to the end of `elements` | `[a, a:text, b]` → `[a, b, a:text]` | ❌ **Survived** | **Gap**, EXC-17 (texts right after their item) |
| Q10 | :165 | only the label pill joins the arrow's group | — | ✅ Killed (`test_edge_label_grouped_with_arrow`) | |
| Q11 | :119 | free text width always measured (`it.width` ignored) | — | ✅ Killed (`test_free_text_anchor_alignment`) | |
| Q12 | :210 | diamond only when it has a radius | — | ✅ Killed (`test_kinds_and_roundness`) | |

The iteration-3 non-gap survivors (P04, P07, P12, P13, P15, P18) were not re-run; their classification still holds because `excalidraw.py` is unchanged.

**Sensor depth**: expanded (4 re-runs + 12 fresh = 16 mutants)
**Result**: 8/16 killed. Re-runs 4/4 killed. Fresh: 4 killed, **8 survived, all gaps** (Q01–Q07, Q09) → **FAIL ❌**

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / surgical / no scope creep / matches patterns | ✅ (source unchanged since iteration 1) |
| Spec-anchored outcome check | ✅ every asserted value matches the spec |
| Per-layer Coverage Expectation | ⚠️ cross-cutting style rules are tested on native shapes only (see gaps) |
| Every test maps to a spec requirement | ✅ each test is tagged with its EXC id, row or edge case |
| Documented guidelines followed | ✅ `pyproject.toml` (pytest, ruff); strong defaults applied |

---

## Ranked Gaps / Fix Plans

All fixes go in `tests/test_excalidraw.py`; the code already behaves as the spec says (see the probe column).

1. **[Minor] EXC-08 / Dashes: arrow dash pattern (Q01).** `conn(dash=[2, 3])` → `strokeStyle == "dotted"`; `conn(dash=[8, 4])` → `"dashed"`.
2. **[Minor] Arrowheads: `none` at the end (Q02).** `conn(arrow_end=True, marker_end="none")` → `endArrowhead is None`.
3. **[Minor] Dashes + Opacity on symbol polygons (Q04, Q05).** A `data` symbol with `dashed=True, opacity=0.5` → every `line` has `strokeStyle == "dashed"` and `opacity == 50`.
4. **[Minor] EXC-03 on texts and polygons (Q06, Q07).** Extend `test_clean_style` with a free text, a labelled shape and a symbol: every element `roughness == 0`, every element with a non-transparent `backgroundColor` has `fillStyle == "solid"`.
5. **[Minor] EXC-17 child order (Q09).** `scene(box("a", label=one-block), box("b", x=600))` → ids after the frame are `["a", "a:text", "b"]`.
6. **[Minor] Kinds: pill ignores its radius (Q03).** `box("p", kind="pill", h=40, radius=8)` → `roundness == {"type": 3, "value": 20}`.
7. **[Cosmetic]** T15 "Done when" boxes in tasks.md are unticked.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| EXC-01, 02, 05–07, 09–16, 18 | Verified / Needs Fix | ✅ Verified |
| EXC-03 | Verified | ❌ Needs Fix (Q06, Q07) |
| EXC-04 | Verified | ❌ Needs Fix (Q03) |
| EXC-08 | Verified | ❌ Needs Fix (Q01, Q02) |
| EXC-17 | Verified | ❌ Needs Fix (Q09) |

(The Verifier does not edit spec.md; the orchestrator applies these statuses.)

---

## Summary

**Overall**: ❌ Not Ready (iteration 4, beyond the 3-iteration bound; escalate)

**Spec-anchored check**: 18/18 ACs have evidence and match the spec outcome; 0 spec-precision gaps; EXC-03, EXC-04, EXC-08, EXC-17 and the Dashes / Opacity / Arrowheads rows are only partly discriminated
**Sensor**: 16 mutants, 8 killed, 8 survived (all gaps: Q01–Q07, Q09)
**Gate**: ruff clean; 676 passed, 0 failed, 3 skipped (environmental)

**What works**: every iteration-1 to iteration-3 gap is closed. The output is correct per spec in every survivor scenario (probed).

**State check**: `python3 <skill-dir>/scripts/validate_state.py excalidraw-backend` exits 1 (verdict FAIL), as expected for a FAIL.

**Lessons recorded** (`scripts/lessons.py add`): L-045 (Q01, Q04–Q07: cross-cutting style rules on every element kind), L-046 (Q02: null mapping entry at every position), L-047 (Q09: order with children), L-048 (Q03: override rule against a conflicting input).

**Next steps**: the user decides between a 5th round (about 6 short tests, no code change) and accepting the 8 minor gaps, since the code is correct in each probed case.

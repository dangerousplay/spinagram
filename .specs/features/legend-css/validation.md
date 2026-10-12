# Legend CSS Validation

**Date**: 2026-10-12
**Spec**: `.specs/features/legend-css/spec.md`
**Diff range**: `7f54ff0^..HEAD` (7f54ff0..4f6abe5, branch `feat/legend-css`; includes unrelated fix f2504ed)
**Iteration**: 3 of 3 (iter 1 FAIL: 6 spec-relevant survivors; iter 2 FAIL: M12; T7 ad0669f and 4f6abe5 added tests only)
**Verifier**: independent sub-agent (author ≠ verifier)

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 | ✅ Done | 219b73a - `PROPS` + `_count` in `src/spinagram/css.py:367-398` |
| T2 | ✅ Done | 5213d66 - `add_legend(position=None)` `src/spinagram/model.py:464`; YAML `src/spinagram/yaml_io.py:140,155` |
| T3 | ✅ Done | d3c3289 - `legend_style` `src/spinagram/annotate.py:108`, `band`, `panels`, overlap rect `:525` |
| T4 | ✅ Done | 9c05324 - `_area` left/top `src/spinagram/autolayout/__init__.py:258-266` |
| T5 | ✅ Done | 70c0cb5 - `docs/content/docs/annotations.mdx:43-62`, `styling.mdx:47`; defaults match `themes/default/theme.yaml:103` |
| T6 | ✅ Done | 2f777dd - `examples/showcase/campus.css:15-19` + skill copy (identical) |
| T7 | ✅ Done | ad0669f + 4f6abe5 - 9 new test cases (iteration 1 gaps 1-5, iteration 2 M12), no source changes |
| (fix) | ✅ Done | f2504ed - dump `cls`→`class`, drop `laid_out`; `tests/test_metadata.py:263-276` |

---

## Spec-Anchored Acceptance Criteria

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| LCSS-01 placement left | band on left edge; card starts at area left | `tests/test_legend_css.py:86` - `(card.x, card.y, card.w) == (ax, ay, 360)`; band reserved: `:185` `area(...) == (ax + thick, ay, aw - thick, ah)` | ✅ PASS |
| LCSS-02 placement top | band at top; card at area top | `tests/test_legend_css.py:93` - `(card.x, card.y, card.w) == (ax, ay, aw)`; `:185` `(ax, ay + thick, aw, ah - thick)` | ✅ PASS |
| LCSS-03 bottom/right same as position= | identical card geometry | `tests/test_legend_css.py:99` - `(by_css.x, .y, .w, .h) == (by_arg.x, ...)` for right and bottom | ✅ PASS |
| LCSS-04 explicit wins | `position="right"` beats `placement: left`; without it CSS decides (Python and YAML) | `tests/test_legend_css.py:105` - `legend.x == ax + aw - 360`; `:50` `position is None`; YAML: `:246` `position is None`, `:248` `legend.x == ax` | ✅ PASS (M30 killed) |
| LCSS-05 invalid placement | warning naming allowed values; default side kept | `tests/test_legend_css.py:43` - `len(warnings) == 1 and all(w in warnings[0] ...)` with right/left/top/bottom; `:42` value dropped; clause 2: `:269` - `legend.x == ax + aw - 360` | ✅ PASS |
| LCSS-06 content after left/top band | area = area minus band, starting after it | `tests/test_legend_css.py:185` - exact area tuple; `:189`/`:191` - `min(n.x) >= card.x + card.w` / `min(n.y) >= card.y + card.h` | ✅ PASS (expected thickness reuses `band()`, but band thickness is pinned independently by `:116` and `tests/test_annotations.py:277`) |
| LCSS-07 width 300 | band 300 + gap, card 300 | `tests/test_legend_css.py:115` - `(card.x, card.w) == (ax + aw - 300, 300)`; `:116` `band(...) == ("right", 332)` | ✅ PASS (right band only; left shares the code path) |
| LCSS-08 columns 3 | three entries per row, on every band side; band sized to hold them | right: `tests/test_legend_css.py:124`; top/bottom: `:202` `sw[0].y == sw[1].y == sw[2].y < sw[3].y`, `:204` spacing `== approx((card.w - 44) / 3)`; reserved band: `:218` `band(...) == (side, 58 + 68 + 22 + 32)`, `:220` `card.h == 58 + 68 + 22`, fit `:223`/`:225`; forces over auto rule: `:234` `== 2`, `:237` `== 1` | ✅ PASS (M12, M13, M15 killed) |
| LCSS-09 gap 20 | rows 20 px apart | `tests/test_legend_css.py:133` - `swatch1.y - swatch0.y == 30 + 20` | ✅ PASS |
| LCSS-10 padding 30 | title and first swatch inset 30 | `tests/test_legend_css.py:141` - `title.x == card.x + 30 and swatch0.x == card.x + 30` | ✅ PASS (x inset only) |
| LCSS-11 swatch 60×20 | every swatch 60 × 20 | `tests/test_legend_css.py:148` - `(sw.w, sw.h) == (60, 20)` | ✅ PASS |
| LCSS-12 label font 20 | labels 20 px | `tests/test_legend_css.py:154` - `label.block.font.size == 20` | ✅ PASS |
| LCSS-13 display none | no card; no band without steps | `tests/test_legend_css.py:164` `"legend" not in scene`; `:165` `band(...) is None` | ✅ PASS |
| Edge: columns not positive int | warning; default layout | `tests/test_legend_css.py:43` (`columns: 0`, `columns: 2.5`) | ✅ PASS |
| Edge: display none + steps | steps take the band alone | `tests/test_legend_css.py:169` - `steps.(x, y) == (ax + aw - 360, ay)` | ✅ PASS (right band) |
| LCSS-14 docs | every property, values, default | `docs/content/docs/annotations.mdx:52-59` - all 8 properties + `legend::body font-size`, defaults match `settings()` `src/spinagram/annotate.py:97` | ✅ PASS |
| LCSS-15 showcase | legend placed by its stylesheet; check 0 issues | `examples/showcase/campus.css:16` `placement: bottom; columns: 7`; `spinagram check examples/showcase` → `9 diagram(s), 0 issue(s)`; PNG: bottom band, 7 entries in one row | ✅ PASS |
| f2504ed dump fix | `class` key, no `laid_out` | `tests/test_metadata.py:272-276` - `out["nodes"][0]["class"] == "web" and "cls" not in ...`; `not {"laid_out","layout_area"} & set(meta)` | ✅ PASS |

**Status**: ✅ All ACs covered with exact spec outcomes (iteration 3).

Not required by the spec, so not flagged as gaps: `placement` from a theme/folder stylesheet (covered behaviourally by the showcase render, which uses `d.stylesheet("campus.css")`); the steps panel following a left/top band (stated in Goals/Out of Scope, no AC); `display:none` with steps on a top band.

---

## Discrimination Sensor (iteration 3)

Fresh isolated `git worktree` at HEAD 4f6abe5 (removed and pruned afterwards); `uv sync --all-extras`; `PYTHONDONTWRITEBYTECODE=1`, `__pycache__` cleared per mutant, scratch `SPINAGRAM_CACHE`/`XDG_CONFIG_HOME`; import confirmed from the worktree `src`. The same 33 mutants as iteration 1. Runner: full `pytest -q -x` minus `tests/test_web_unit.py` (needs `web/node_modules`, absent in a fresh worktree; unrelated). Survivors also run against `spinagram check examples/showcase` (0 issues).

| # | File:line | Description | Killed? |
| - | --------- | ----------- | ------- |
| M01 | `src/spinagram/annotate.py:116` | CSS `placement` beats explicit position | ✅ `test_explicit_position_beats_css` |
| M02 | `src/spinagram/annotate.py:116` | CSS placement ignored | ✅ `test_placement_left_...` |
| M03 | `src/spinagram/annotate.py:119` | `width`→band mapping dropped | ✅ `test_width_sets_the_side_band` |
| M04 | `src/spinagram/annotate.py:119` | `gap` mapped to band gap, not row_gap | ✅ `test_gap_spaces_the_rows` |
| M05 | `src/spinagram/annotate.py:119` | `padding` mapping dropped | ✅ `test_padding_insets_...` |
| M06 | `src/spinagram/annotate.py:119` | `swatch-width` mapped to swatch_h | ✅ `test_swatch_size` |
| M07 | `src/spinagram/annotate.py:118` | label size ignores `legend::body` | ✅ `test_body_font_size_...` |
| M08 | `src/spinagram/annotate.py:177` | `display:none` ignored in `band()` | ✅ `test_display_none_...` |
| M09 | `src/spinagram/annotate.py:346` | `display:none` ignored in `panels()` | ✅ `test_display_none_...` |
| M10 | `src/spinagram/annotate.py:182` | side band thickness without gap | ✅ `test_band_reserves_the_right_or_bottom_edge` |
| M11 | `src/spinagram/annotate.py:191` | top/bottom thickness without gap | ✅ `test_bottom_band_is_legend_height_plus_gap_...` |
| M12 | `src/spinagram/annotate.py:187` | `band()` ignores `columns` on top/bottom (reserves 140 px for one flowed row while the card draws two rows, 180 px) | ✅ `test_columns_on_a_top_or_bottom_band_reserve_their_rows[top]` (survived in iter 1 and 2) |
| M13 | `src/spinagram/annotate.py:370` | `panels()` ignores `columns` on top/bottom | ✅ `test_columns_on_a_top_or_bottom_band[top]` (survived in iter 1) |
| M14 | `src/spinagram/annotate.py:353` | side band ignores `columns` | ✅ `test_columns_lay_entries_out_per_row` |
| M15 | `src/spinagram/annotate.py:354` | explicit `columns` still auto-switches to 2 on a tall band | ✅ `test_explicit_columns_beat_the_automatic_two_columns` (survived in iter 1) |
| M16 | `src/spinagram/annotate.py:351` | left card drawn at right edge | ✅ `test_placement_left_...` |
| M17 | `src/spinagram/annotate.py:366` | top card drawn at bottom | ✅ `test_placement_top_...` |
| M18 | `src/spinagram/annotate.py:191` | top band reported as bottom | ✅ `test_placement_top_...` |
| M19 | `src/spinagram/annotate.py:373` | steps on a top/bottom band at left edge | ✅ `test_bottom_band_shares_the_width_with_steps` |
| M20 | `src/spinagram/annotate.py:525` | overlap rect for left band uses right edge | ✅ `test_manual_layout_overlap_on_left_and_top_bands[left]` (survived in iter 1) |
| M21 | `src/spinagram/annotate.py:526` | overlap rect for top band uses bottom | ✅ `test_manual_layout_overlap_on_left_and_top_bands[top]` (survived in iter 1) |
| M22 | `src/spinagram/autolayout/__init__.py:262` | `_area` left keeps x | ✅ `test_content_starts_...[left]` |
| M23 | `src/spinagram/autolayout/__init__.py:264` | `_area` top keeps y | ✅ `test_content_starts_...[top]` |
| M24 | `src/spinagram/autolayout/__init__.py:262` | `_area` left does not shrink w | ✅ `test_content_starts_...[left]` |
| M25 | `src/spinagram/css.py:369` | `_count` accepts 0 | ✅ `test_invalid_legend_values_warn[columns: 0]` |
| M26 | `src/spinagram/css.py:369` | `_count` accepts fractions | ✅ `test_invalid_legend_values_warn[columns: 2.5]` |
| M27 | `src/spinagram/css.py:391` | `placement` keyword set lacks `top` | ✅ `test_invalid_legend_values_warn[placement]` |
| M28 | `src/spinagram/yaml_io.py:294` | dump keeps `cls` key | ✅ `test_position_defaults_...` / metadata test |
| M29 | `src/spinagram/yaml_io.py:288` | dump keeps `laid_out` | ✅ `test_frozen_spec_round_trips_...` |
| M30 | `src/spinagram/yaml_io.py:140` | YAML legend without `position:` defaults to right (CSS ignored) | ✅ `test_yaml_legend_without_position_follows_the_stylesheet` (survived in iter 1) |
| M31 | `src/spinagram/yaml_io.py:155` | dump always writes `position` | ✅ `test_position_defaults_...` |
| M32 | `src/spinagram/model.py:465` | `add_legend` default `"right"` | ✅ `test_position_defaults_...` |
| M33 | `src/spinagram/annotate.py:301` | label vertical centring uses theme text size | ❌ Survived - outside spec (LCSS-12 fixes the label size, not its vertical alignment); no fix task |

**Sensor depth**: expanded (33 mutants)
**Result**: 32/33 killed (iter 1: 26/33, iter 2: 31/33). The one survivor, M33, is outside the spec: LCSS-12 fixes the label font size (asserted at `tests/test_legend_css.py:154`), not the label's vertical centring. No fix task. PASS ✅

Isolation: worktree removed and pruned; real-tree `git status --porcelain` identical to the pre-sensor baseline (only the verifier's `.specs` files).

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code | ✅ |
| Surgical changes | ✅ (f2504ed is an unrelated fix with its own commit and test; T7 is tests only) |
| No scope creep | ✅ |
| Matches patterns | ✅ |
| Spec-anchored outcome check (asserted values match spec) | ✅ exact values; band size derived independently from theme defaults (L-011) |
| Per-layer Coverage Expectation met (domain 1:1 ACs) | ✅ |
| Every test maps to a spec requirement - no unclaimed tests | ✅ (metadata test → f2504ed; overlap test → ANN-12 for the new sides) |
| Documented guidelines followed: `pyproject.toml` (pytest, ruff); `.specs/LESSONS.md` | ✅ |

---

## Edge Cases

- [x] `columns` not a positive integer → warning, default layout (`tests/test_legend_css.py:43`)
- [x] `display: none` with steps → steps take the band alone (`tests/test_legend_css.py:169`, right band)

---

## Gate Check

- **Gate command**: `set -o pipefail; uv run ruff check src tests && uv run pytest -q && uv run spinagram check examples/showcase`
- **Result**: ruff clean; 516 passed, 0 failed, 3 skipped; check `9 diagram(s), 0 issue(s)`
- **Test count before feature**: 486
- **Test count after feature**: 516
- **Delta**: +30 (29 in `tests/test_legend_css.py`, 1 in `tests/test_metadata.py`); one existing test changed `position="left"`→`"middle"` because left is now valid (not a weakening)
- **Skipped tests**: 3, pre-existing optional extras (`pptx`, vector) - environmental
- **Failures**: none

---

## Fix Plans

None open. Iteration 1 gaps (M12, M13, M15, M20, M21, M30, LCSS-05 clause 2) and the iteration 2 gap (M12) were closed with tests only.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| LCSS-01..15 | Implementing | ✅ Verified |

---

## Summary

**Overall**: ✅ Ready

**Verdict**: PASS

**Spec-anchored check**: 15/15 ACs matched spec outcome; 0 spec-precision gaps
**Sensor**: 32/33 mutations killed (sole survivor M33 is out of spec)
**Gate**: 516 passed, 0 failed

**What works**: all eight properties parse and validate; placement precedence via both the Python API and YAML; left/top bands, layout area and overlap check; display none; columns drawn and reserved on every side and forced over the auto rule; docs; showcase (bottom band, 7 entries in one row); the dump fix.

**Issues found**: none open.

**Next steps**: feature done; update spec.md traceability to Verified.

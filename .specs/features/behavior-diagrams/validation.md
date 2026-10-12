# Behavior Diagrams Validation (iteration 2)

**Date**: 2026-10-12
**Spec**: `.specs/features/behavior-diagrams/spec.md` (BHV-05, BHV-12, BHV-26 reworded in 7ee7f55)
**Diff range**: iteration 1 surface (841afcd..ab96222, feature commits only) plus the fix commits **2ef6c98** (lane members inside embedded activities) and **7ee7f55** (spanning fork/join bars, region `layout=`, gap tests, spec rewording). Verified at 7ee7f55. Other commits on `feat/behavior-css-mvp` (3a3d07b, 5d5e09c, 71d5f4f, 70e01e6, c9e6b74, 99549c5, 46d7696) belong to css-styling or layered-layout. They do not break the behavior tests.
**Verifier**: independent sub-agent (author ≠ verifier)
**MVP scope**: BHV-01..26, BHV-31..35. BHV-27 and BHV-28..30 are deferred and were not judged.

**Verdict**: ✅ PASS. All 31 in-scope ACs have exact evidence. Gaps G1-G9 are closed. All 4 survivors from iteration 1 (M7, M11, M13, M15) are now killed. BHV-14 is still a documented, accepted SPEC_DEVIATION, and the dashed rendering is now asserted. Two defensive branches of the new bar code are not exercised by any test (N6, N9). Neither guards a spec-defined outcome, so they are advisory and do not block.

---

## Task Completion

T1-T11 are all ✅ Done. In tasks.md, the T6-T10 partials from iteration 1 were closed by the tests added in 7ee7f55. The feature header still reads "In Progress" (`tasks.md:35`). The orchestrator should flip it after this PASS.

---

## Gap closure (iteration 1 → 2)

| Gap | How closed | Evidence |
| --- | ---------- | -------- |
| G1 BHV-02 bars do not span | `layered.py:491-508` stretches fork/join bars across their neighbours' positions (±24 px, clamped to row neighbours). `layered.py:641-649` sets bar ports at the other end's column | `tests/test_behavior.py:662-667`: `bar.x <= min(centres) and bar.x + bar.w >= max(centres)`, `bar.h == 8`, and fork edges have `e.via is None or len(e.via) == 0` |
| G2 BHV-24 region layout | `behavior.py:265-277` accepts `layout={engine, direction, gap, columns, align, padding}` | `:675` `g.engine == "flex" and g.direction == "right" and g.gap == 30`. `:678` laid out as a flex row 30 px apart. `:681` `direction=` override |
| G3 BHV-31 flow_final | test only | `:687` `pytest.raises(ValueError, match=f"final node {ff.id} cannot have outgoing edges")` |
| G4 BHV-04 Figma text | test only | `:695-700`: titles present in the JS, and the `text(...)` call for "State" is placed inside `state.label.box` |
| G5 BHV-20 lane re-entry | test only | `:712` `[g.label ...] == ["Ops","Dev"] and lanes[0].children == [x.id, z.id]` |
| G6 BHV-14 dashing | test only | `:718-720` two dashed region zones, and `to_svg(sc).count("stroke-dasharray") >= 2` |
| G7 BHV-05 themability | AC reworded to "built-in symbol sizes of the shape table (`spinagram.shapes`)" | `:78` `auto_size(...) == shapes.fixed_size(kind)` now matches the AC literally |
| G8 BHV-26 "exactly" | AC reworded to "same sizes and relative positions… the region adds only its own box" | `:575` relative `(dx, dy, w, h)` equality matches the AC literally |
| G9 BHV-01 note, BHV-12 clause | `note` test added. BHV-12 reworded to "one per scope, same node on every later access" | `:727-728` `note.kind == "rect" and ...lines == ["Remember"]`. `:363` `count("final") == 1` while `sm.final` is accessed twice in the fixture (`:340-341`) |

Regression from 2ef6c98: `_scope` no longer re-pushes the region group when a lane is open (`behavior.py:36`). Covered by `:643-645`: `lanes["Ops"].children == [x.id, z.id]` and `region.children == [lanes["Ops"].id, lanes["Dev"].id]`.

---

## Spec-Anchored Acceptance Criteria

All references are to `tests/test_behavior.py` at 7ee7f55 unless another file is named. Lines 1-630 are unchanged from iteration 1, because the new tests are appended at the end of the file.

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| BHV-01 | 23 kinds incl. `note` | `:21-30` 22 kinds in `shapes.KINDS` with parts and text box. `:727-728` note renders | ✅ PASS |
| BHV-02 | Shape-table geometry; fork is an 8 px bar spanning its edges | `:34-49` paints, `fixed_size`. `:130-171` scene and SVG parts. `:662-667` bars span the branch centres, `h == 8`, straight edges | ✅ PASS |
| BHV-03 | Native preset (group for final), text inside | `:190-213` `geom.get("prst") == PRST[kind]`, final group of 2 ovals, texts | ✅ PASS |
| BHV-04 | Editable vectors with text inside | `:235-262` vectors, mock run `returncode == 0`. `:695-700` label text inside the label box | ✅ PASS |
| BHV-05 | Built-in shape-table sizes, not text | `:78` `== shapes.fixed_size(kind)`. `:83` `(8, 140)` | ✅ PASS |
| BHV-06 | Flowchart kinds | `:274` exact kind list | ✅ PASS |
| BHV-07 | Yes/No/custom labels on distinct sides | `:285` labels, `:288` 3 distinct ports | ✅ PASS |
| BHV-08 | layered, down | `:293` `fc.layout == {"engine":"layered","direction":"down"}` | ✅ PASS |
| BHV-09 | "decision X has N outgoing edges (expected ≥ 2)" | `:603` exact list equality | ✅ PASS |
| BHV-10 | entry/do/exit lines | `:350-351` exact lines | ✅ PASS |
| BHV-11 | `event [guard] / action` | `:317`, `:357` exact labels | ✅ PASS |
| BHV-12 | One initial/final per scope, same node on reuse | `:363-365` `count("final") == 1` (accessed twice), `count("initial") == 3`, edge `initial → created` | ✅ PASS |
| BHV-13 | Composite state box containing substates | `:371-375`, `:391-393` | ✅ PASS |
| BHV-14 | Dashed dividers between regions | `:373` region styles. `:718-720` dashed zones plus `stroke-dasharray` | ⚠️ PASS with documented SPEC_DEVIATION (dashed nested boxes, `design.md:92`, `behavior.py:108`). Accepted for the MVP |
| BHV-15 | choice, H / H* | `:380-385` | ✅ PASS |
| BHV-16 | "region X has no initial state" | `:613` exact messages | ✅ PASS |
| BHV-17 | Self-transition loop | `:395` | ✅ PASS |
| BHV-18 | Activity kinds | `:446-449` | ✅ PASS |
| BHV-19 | fork/join wiring | `:455-459` | ✅ PASS |
| BHV-20 | Lane membership, bands, re-entry | `:473-491`, `:712` (standalone re-entry), `:643-645` (embedded) | ✅ PASS |
| BHV-21 | signal/object; object flows dashed | `:448`, `:497` `flow.dashed` | ✅ PASS |
| BHV-22 | Implicit sequence edges | `:465-467` | ✅ PASS |
| BHV-23 | Region verbs | `:527-534` | ✅ PASS |
| BHV-24 | Region laid out with its own layout, one box in the parent | `:540-547` default. `:675-681` `engine="flex"`, `direction="right"`, `gap=30` honoured in the layout. `tests/test_layered.py:296-303` | ✅ PASS |
| BHV-25 | Edge crosses the region border | `:554`, `tests/test_layered.py:229`, `:305` | ✅ PASS |
| BHV-26 | Same node sizes and relative positions standalone vs embedded | `:575` `rel(o1, …) == rel(o2, …)` | ✅ PASS |
| BHV-31 | ValueError for `final` and `flow_final` | `:300`, `:687` exact messages | ✅ PASS |
| BHV-32 | ValueError for incoming edges to initial | `:307` | ✅ PASS |
| BHV-33 | "fork X has 1 branch" | `:624` | ✅ PASS |
| BHV-34 | Empty lane ≥ 200 px with label | `:503-504` | ✅ PASS |
| BHV-35 | Duplicate id ValueError | `:582` | ✅ PASS |

Negative control: `:627-630` (no issues on well-formed fixtures).

**Status**: 31/31 covered. 30 exact PASS, 1 PASS with the accepted, documented deviation (BHV-14). No spec-precision gaps remain.

---

## Discrimination Sensor

Scratch: `git worktree add --detach <scratchpad>/bhv-wt2 7ee7f55`. Each mutant was applied alone by exact-string replacement (asserted unique). Then `uv run --all-extras pytest -q -x tests/test_behavior.py tests/test_layered.py` was run, and the file was restored with `git checkout` in the scratch. The scratch was clean after each mutant. The worktree has been removed.

| # | File | Mutation | Result |
| - | ---- | -------- | ------ |
| M7 | `behavior.py` `lane()` | Lane reuse disabled | ✅ Killed (`test_lanes_hold_nodes_inside_an_embedded_activity`) |
| M11 | `model.py` `_check_pseudo` | `flow_final` dropped from the check | ✅ Killed (`test_edges_out_of_flow_finals_rejected`) |
| M13 | `themes/default/theme.yaml` | region `dashed: true` → `false` | ✅ Killed (`test_orthogonal_regions_render_dashed`) |
| M15 | `backends/figma.py` | Symbol label not emitted | ✅ Killed (`test_figma_writes_symbol_text_inside`) |
| N1 | `layered.py:507` | Bar stretching removed | ✅ Killed (`test_fork_and_join_bars_span_their_branches`) |
| N2 | `layered.py:641` | Bar ports back to fractions | ✅ Killed (same test, via the straight-edge assertion) |
| N3 | `behavior.py:269` | Region `layout` dict ignored | ✅ Killed (`test_region_takes_its_own_layout`) |
| N4 | `behavior.py:276` | Region engine forced to `layered` | ✅ Killed (same) |
| N5 | `behavior.py:36` | Lane scope regression (pre-2ef6c98 condition) | ✅ Killed (`test_lanes_hold_nodes_inside_an_embedded_activity`) |
| N6 | `layered.py:502-505` | Right-neighbour clamp of the bar removed | ❌ Survived (advisory) |
| N7 | `behavior.py:271` | Region `direction` from layout ignored | ✅ Killed |
| N8 | `behavior.py:272` | `gap`/`columns`/`align`/`padding` passthrough dropped | ✅ Killed |
| N9 | `layered.py:645` | Bar port de-duplication (two edges to the same column) removed | ❌ Survived (advisory) |

**Sensor depth**: expanded (13 mutants, 4 re-runs from iteration 1 plus 9 on the new code)
**Result**: ✅ PASS. 11/13 killed. All mutants touching a spec-defined outcome are killed. N6 and N9 are defensive branches ("never over a neighbour", keep two ports apart) that no AC specifies. A probe with an extra flow sharing ranks with the bars gave identical output with and without N6, so the branch is not reached by the fixtures. These are recorded as advisory follow-ups, not blocking fix tasks.
**Isolation**: the real tree was never written by the sensor. Its porcelain afterwards differs from the pre-sensor baseline only by concurrent main-session CSS edits (`autolayout/__init__.py`, `css.py`, `layout.py`, `model.py` (adds `Zone.gid`), `qa.py`, `scene.py`, `tests/test_css.py`). None of these is a sensor mutation. No `git stash` was used.

---

## Gate Check

- At 7ee7f55 (scratch): `uv run --all-extras pytest -q tests/test_behavior.py tests/test_layered.py` → **159 passed**. Full `pytest -q` → **278 passed, 3 skipped** (dot / soffice not installed, pre-existing), 0 failed. `ruff check src tests examples` → clean.
- Test integrity: the behavior tests grew by 9 functions (1 in 2ef6c98, 8 in 7ee7f55). None were deleted or weakened.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / surgical | ✅ Bar stretching is one post-pass plus one port branch. The region `layout` change is confined to `region()` |
| No scope creep | ✅ |
| Matches patterns | ✅ |
| Spec-anchored outcomes | ✅ |
| Every test maps to an AC | ✅ (new tests are tagged with their BHV and gap ids) |
| Guidelines | none (strong defaults applied) |

---

## Remaining gaps (advisory, non-blocking)

1. **A1 (Minor), N6 survived**: no test puts a fork/join next to another node in the same rank, so the neighbour clamp at `layered.py:502-505` is unverified. Suggested test: a bar whose rank is shared with a neighbour, asserting no overlap.
2. **A2 (Minor), N9 survived**: no test has two edges from one bar to the same column. Suggested: assert distinct port x positions in that case.
3. **A3 (Tracking), BHV-14 dividers**: the deviation is accepted for the MVP. Either implement true dividers later or reword BHV-14 to "dashed nested region boxes".
4. **A4 (Housekeeping)**: `tasks.md:35` feature status still reads "In Progress".

---

## Requirement Traceability Update

| Requirement | New Status |
| ----------- | ---------- |
| BHV-01..13, 15..26, 31..35 | ✅ Verified |
| BHV-14 | ✅ Verified with documented deviation (dashed boxes) |
| BHV-27, 28-30 | Deferred (out of MVP) |

---

## Summary

**Overall**: ✅ Ready (MVP).
**Spec-anchored check**: 31/31 matched. 0 spec-precision gaps. 1 accepted deviation (BHV-14).
**Sensor**: 11/13 killed. M7, M11, M13 and M15 are now killed. N6 and N9 are advisory.
**Gate**: 278 passed, 3 skipped (env), 0 failed. Ruff clean.

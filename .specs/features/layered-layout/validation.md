# Layered Layout Validation

**Date**: 2026-10-12
**Spec**: `.specs/features/layered-layout/spec.md`
**Diff range**: `c6485e3..54a1311` (branch `feat/behavior-css-mvp`, 6 commits: 9316177, fa5920b, f8d011c, 82e1542, 4bf1ac9, 54a1311)
**Scope**: MVP ACs LAY-01..17, LAY-20..22 (LAY-18/19 deferred, P2, out of scope)
**Verifier**: independent sub-agent (author ≠ verifier)

**Verdict: FAIL (conditional).** The implementation behaves correctly on every probe I ran. The verdict is FAIL because 7 discrimination-sensor mutants survived and 3 AC clauses have no test (LAY-08 for an adjacent-rank back-edge, LAY-09's label beside the loop, LAY-10's separate labels). The fix tasks below are about the tests only. None of them needs a code change.

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 Layout graph carries loops and hints | ✅ Done | `tests/test_layered.py:14,24` |
| T2 Layered engine for flat graphs | ✅ Done | |
| T3 Orthogonal obstacle router | ✅ Done | |
| T4 Groups and lanes | ⚠️ Done, weak tests | No test checks routes inside lanes (M18 survived) |
| T5 Per-group engines in apply_layout | ✅ Done | |
| T6 Labels avoid boxes | ✅ Done | Nothing asserts that two labels stay apart (M7 survived) |

---

## Spec-Anchored Acceptance Criteria

Test line numbers are for `tests/test_layered.py` at 54a1311 unless a row says otherwise. HEAD has moved since then (6192492), but this file is unchanged.

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| LAY-01 | Each edge's target is in a later rank than its source (except reversed edges) | `:87` `_rank_axis(res, b, dir)[0] >= _rank_axis(res, a, dir)[1] + 80 - 0.5` for every ORDER edge | ✅ PASS |
| LAY-02 | `down` puts ranks at increasing y, `right` at increasing x | `:83-87` parametrized over `down`/`right`; `_rank_axis` uses y for down and x for right (`:78-80`) | ✅ PASS |
| LAY-03 | At least `rank_gap` between ranks and `gap` between nodes in one rank | `:87` (+80 = rank_gap); `:98` `right[0] - (left[0]+left[2]) >= 48 - 0.5`; `:362-370` rank_gap from the theme | ⚠️ PASS + spec-precision gap: the spec says `gap`, but the engine and the test use `node_gap` (48), not `gap` (40). Only one same-rank pair is checked |
| LAY-04 | No overlapping node boxes | `:93-95` `assert not _overlap(a, b)` for every pair; `tests/test_autolayout.py:60` engine invariants with `layered` | ✅ PASS |
| LAY-05 | Laying out twice gives identical coordinates | `:103` `a.boxes == b.boxes and a.routes == b.routes` | ⚠️ PASS in-process only. **M9b survived**: a hash-based tie-break gives different layouts across `PYTHONHASHSEED` values and the suite stays green. The real code is stable across seeds 1-5 (probe) |
| LAY-06 | No edges: one rank, in declaration order | `:108-110` `len(ys) == 1`; `boxes a.x < b.x < c.x` | ✅ PASS |
| LAY-07 | Cycles: reversed for ranking, drawn in the original direction | `:119-120` route starts on `backorder` top and ends on `receive` bottom | ⚠️ PASS on drawing direction. Nothing checks that the reversed set is minimal, or that the other edges in a cyclic graph keep their rank order |
| LAY-08 | A multi-rank back-edge goes round the outer side; an adjacent-rank back-edge stays in the gap; no segment crosses a node | `:137` `max(x of e6) > right` (multi-rank); `:126-130` no `_seg_hits_box` for any route | ❌ GAP: no test covers the **adjacent-rank** clause (M4 survived). The `:113`/`:123` back-edge spans 2 ranks. The probe shows the real code does keep adjacent back-edges in the gap |
| LAY-09 | A self-loop leaves and re-enters the same side, with its label beside the loop | `route.loop` `:198-200` same x=260, different y, bulges out; engine `:275` `pts[0][0] == pts[-1][0] == bx + bw`; binding `:321` `src/dst startswith "b.right"`, `len(via) == 2` | ⚠️ PARTIAL: "label beside the loop" is not asserted (`:353-356` only checks that the label avoids boxes). No test reserves room for a same-rank neighbour (M14 survived) |
| LAY-10 | Parallel edges get separate routes and separate labels | `:142-143` `routes e0 != e1` and the start points differ | ⚠️ PARTIAL: nothing checks "separate labels" |
| LAY-11 | Every non-self edge is an orthogonal polyline | `:128` `abs(p.x-q.x)<1e-6 or abs(p.y-q.y)<1e-6`; router `:185`, `:234` | ✅ PASS (engine routes are only checked for `down`) |
| LAY-12 | The label sits on its route and its box intersects no node box | `:353-356` `len(pills)==4`; `not _overlap(pill, node)`. The pill geometry matches `layout.py:50-54` | ⚠️ PASS on non-intersection. Spec-precision gap: "on its route" is neither defined nor asserted, and the implementation can put the pill beside the segment |
| LAY-13 | Edges leaving a decision node use distinct sides or positions | `:148` `routes["e2"][0] != routes["e3"][0]` with `stock` as decision | ✅ PASS (M2 killed) |
| LAY-14 | An authored anchor is kept and routed from | `:311` `anchored.src == "client.bottom" and anchored.dst == "c.top" and not anchored.via` | ⚠️ PASS on keeping the anchor. Spec-precision gap: "route from it" is implemented as no route at all (straight line), and nothing checks that this line avoids nodes |
| LAY-15 | Members sit inside the group box with padding and label band; no non-member inside | `:223` `_inside(b,g) and _inside(c,g)`; `:224` band `>= 50`; `:226` `not _overlap(a/d, g)`; `tests/test_autolayout.py:49,52` | ✅ PASS (side and bottom padding only checked with tolerance) |
| LAY-16 | Lanes are bands spanning the diagram along the flow; members stay inside their band | `:254` members inside their lane; `:255` disjoint; `:257/259` equal top/height (down) or left/width (right); `:262` shared ranks | ✅ PASS |
| LAY-17 | An edge crossing a group or lane border goes through it without crossing other nodes | `:231-237` cross-group routes are orthogonal, do not hit nodes and end on the borders; router `:182-187`; regions `:299-309` | ⚠️ PASS for groups and regions. **No test covers cross-lane routes** (M18 survived). The probe shows the real code's lane routes do not hit nodes |
| LAY-20 | `spinagram check` reports overflow with the excess in px | `:382` `any(i.kind == "overflow" ...)` | ⚠️ PARTIAL: the px excess is not asserted. `qa.py:25` does format it ("exceeds its area by {n}px") |
| LAY-21 | Disconnected components side by side, in declaration order | `:153-154` a's right edge ≤ c.x and b's right edge ≤ d.x | ✅ PASS (M12 killed) |
| LAY-22 | More than 300 nodes: layout completes and warns, naming the bound | `:163` `any("300" in str(msg))`; `:164` all 301 boxes present | ✅ PASS (M13 killed) |

**Status**: ❌ 1 AC has a full gap (LAY-08 adjacent clause). 4 ACs are partial (LAY-09, LAY-10, LAY-17 lanes, LAY-20 px). 4 have spec-precision gaps (LAY-03, LAY-05, LAY-12, LAY-14).

---

## Edge Cases

- [x] LAY-20 overflow reported (kind only, see above)
- [x] LAY-21 components side by side
- [x] LAY-22 more than 300 nodes warns and completes. Probe: a random DAG with 300 nodes and 600 edges took 0.15 s, under the 2 s success criterion (no test covers the time bound)

---

## Gate Check

- **Build gate** (`uv run ruff check src tests examples && uv run pytest -q`), run in a scratch worktree at 54a1311:
  - ruff: all checks passed
  - pytest with the default env: 78 passed, 9 skipped, 1 failed. The failure is `test_engine.py::test_examples_render_all_backends` because the `pptx` extra is not installed. It is environmental and fails the same way at c6485e3
  - pytest with `uv run --all-extras`: **104 passed, 3 skipped, 0 failed**. The skips are the missing `dot` runtime and the vector extra
- **Test count before feature** (c6485e3, default env): 48 passed. **After**: 78 passed (+30: 29 in `test_layered.py`, plus `layered` added to the ENGINES parametrization)
- No tests were deleted or weakened. `tests/test_autolayout.py` only changes by adding `layered` to ENGINES

---

## Discrimination Sensor

Scratch setup: `git worktree add --detach <scratchpad>/wt 54a1311`. I ran `tests/test_layered.py` and `tests/test_autolayout.py` against each mutant, with all extras installed. The worktree was removed afterwards. The real tree was never edited. Its `git status` now shows ` M src/spinagram/layout.py`, `scene.py` and `tests/test_behavior.py`, plus HEAD at 6192492. All of that is concurrent work by the main session, not anything I changed.

| # | File (54a1311) | Mutation | Killed? |
| - | -------------- | -------- | ------- |
| M1 | `engines/layered.py:331` | Skip cycle reversal (`reversed_.add` → `pass`) | ✅ Killed (`test_cycle_edge_drawn_in_original_direction`) |
| M2 | `engines/layered.py:618` | Every diamond port collapsed to bottom centre | ✅ Killed (`test_decision_edges_leave_distinct_ports`) |
| M3 | `engines/layered.py:567` | Long back-edge routed in the gap (no outer track) | ✅ Killed (`test_long_back_edge_goes_round_the_outer_side`) |
| M4 | `engines/layered.py:567` | Adjacent back-edge forced onto the outer track | ❌ Survived |
| M5 | `engines/layered.py:232` | Lanes not shifted apart | ✅ Killed (`test_lanes_are_disjoint_full_span_bands`) |
| M6 | `autolayout/__init__.py` `clear()` | Label placement ignores node boxes | ✅ Killed (`test_label_pills_avoid_node_boxes`) |
| M7 | `autolayout/__init__.py` `clear()` | Label placement ignores labels already placed | ❌ Survived |
| M8 | `route.py:73` | Router segment check always passes | ✅ Killed (`test_cross_group_edges_routed_without_crossing_nodes`) |
| M8b | `route.py:69` | Router ignores every obstacle | ✅ Killed (same test) |
| M9 | `engines/layered.py:347` | Kahn ready-queue tie-break by `hash` | ⚪ Survived, but equivalent: output is identical across 5 hash seeds on the fixtures |
| M9b | `engines/layered.py:396` | Initial ordering tie-break by `hash(k)` | ❌ Survived. The layout differs across `PYTHONHASHSEED` 1-5 and the in-process determinism test still passes |
| M10 | `engines/layered.py:622` | Box ports collapse to the centre (parallel edges) | ✅ Killed (`test_parallel_edges_get_separate_routes`) |
| M11 | `autolayout/__init__.py` | Anchored edges re-routed | ✅ Killed (`test_crossing_edge_rerouted_and_anchored_edge_kept`) |
| M12 | `engines/layered.py:286` | Components placed in reverse order | ✅ Killed (`test_no_edges_is_one_rank_in_declaration_order`) |
| M13 | `engines/layered.py:83` | No warning above 300 nodes | ✅ Killed (`test_large_graph_warns_but_completes`) |
| M14 | `engines/layered.py:308` | No room reserved beside a self-loop node | ❌ Survived |
| M15 | `engines/layered.py:159` | Group label band ignored | ✅ Killed (`test_group_members_inside_and_others_outside`) |
| M16 | `route.py:141` | Self-loop re-enters on another side | ✅ Killed (`test_self_loop_leaves_and_reenters_one_side`) |
| M17 | `engines/layered.py:482` | rank_gap halved | ✅ Killed (`test_targets_rank_after_sources[down]`) |
| M18 | `engines/layered.py:259` | Lane-level routes skip the lane shift | ❌ Survived |

**Sensor depth**: lightweight-plus (20 mutants)
**Result**: 14 of 20 killed, 1 equivalent, 5 survived (M4, M7, M9b, M14, M18). **FAIL.**

---

## Ranked Gaps and Fix Tasks (tests only; no code change needed per probes)

1. **[Major] LAY-08: no test covers an adjacent-rank back-edge** (M4). Add a test with e.g. `ship → stock` asserting that every route point lies between `stock` bottom and `ship` top, and that no point lies beyond the diagram's right edge.
2. **[Major] LAY-05: determinism is only checked in-process** (M9b). Add a subprocess test that runs the ORDER fixture under two different `PYTHONHASHSEED` values and asserts equal output, or assert a frozen golden set of coordinates.
3. **[Major] LAY-17/LAY-16: no test checks routes in a lanes layout** (M18). Add a same-lane edge (e.g. `a → c` in L1) and cross-lane edges, and assert the routes are orthogonal, end on their boxes and hit no node.
4. **[Minor] LAY-09: the self-loop needs a neighbour test and a label test** (M14). Use a node with a same-rank neighbour on its loop side and assert no hit. Assert that the loop label pill sits beside the loop, to the right of the node and within the loop's y range.
5. **[Minor] LAY-10: "separate labels" for parallel edges is not asserted.** Label both parallel edges and assert their `label_at` pills are disjoint.
6. **[Minor] Label-label separation is not discriminated** (M7). Use a fixture where two labels would collide by default.
7. **[Minor] LAY-20: the px excess is not asserted.** Assert that the overflow issue message contains the computed px.
8. **[Spec-precision] LAY-03**: the spec says `gap`, the implementation uses `node_gap`. Align the wording. **LAY-12**: define "on its route" (the pill touches the route or sits within N px of it). **LAY-14**: define "route from it" (anchored edges are left unrouted today). **LAY-07**: "minimal-heuristic" is unmeasurable as written.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / no scope creep | ✅ (the `region` hint and `model.Group.region` belong to the builders' feature, which is acceptable) |
| Surgical changes | ✅ |
| Matches patterns | ✅ (engine protocol, registry, tests styled like `test_autolayout.py`) |
| Spec-anchored outcome check | ⚠️ 4 spec-precision gaps flagged |
| Per-layer coverage (1:1 to MVP ACs) | ❌ LAY-08 adjacent clause, LAY-09 label, LAY-10 labels |
| Every test maps to a requirement | ✅ (`test_empty_lane_still_drawn_200px` maps to BHV-34, which is outside this spec but declared) |
| Documented guidelines | none (strong defaults applied, per tasks.md) |

---

## Requirement Traceability (proposed; spec.md not modified by the Verifier)

| Requirement | New status |
| ----------- | ---------- |
| LAY-01, 02, 04, 06, 11, 13, 15, 16, 21, 22 | ✅ Verified |
| LAY-03, 05, 07, 12, 14 | ⚠️ Verified with spec-precision/discrimination notes |
| LAY-08, 09, 10, 17, 20 | ❌ Needs test fix |

---

## Summary

**Overall**: ⚠️ Issues. The behavior is correct on every probe (adjacent back-edge in the gap, lane routes clear of nodes, self-loop clear of its neighbour, stable across hash seeds, 300 nodes and 600 edges in 0.15 s), but the tests do not cover all of it.
**Spec-anchored check**: 11 of 20 ACs fully matched; 1 gap, 4 partial, 4 spec-precision.
**Sensor**: 14 of 20 killed (1 equivalent, 5 survived).
**Gate**: with all extras, 104 passed and 3 skipped; ruff clean.
**Lessons distillation**: skipped. `lessons.py` writes into `.specs/`, and the Verifier was told not to modify any file other than this one.

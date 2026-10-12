# Layered Layout Validation (iteration 3, final before escalation)

**Date**: 2026-10-12
**Spec**: `.specs/features/layered-layout/spec.md`. Unchanged since 58b0990.
**Diff range**: `c6485e3..c3edd4a`. The layered-layout commits are 9316177, fa5920b, f8d011c, 82e1542, 4bf1ac9, 54a1311, 58b0990 and the fix commit **c3edd4a**, which is test-only (`tests/test_layered.py`, +51/-6). The behavior-diagrams commits are 841afcd, 6192492, 3d3fe31, f8ee4e1, f0240a1, 11918bb, e0a4a06, ba20206 and 2660dd9. They are out of scope, but two of them touch `src/spinagram/autolayout/__init__.py`, and those changes were checked for layered regressions (see below).
**Scope**: MVP ACs LAY-01..17 and LAY-20..22. LAY-18 and LAY-19 are P2 and deferred.
**Verifier**: independent sub-agent (author ≠ verifier), iteration 3 of 3

**Verdict: FAIL (narrow). Escalate to the user.** Iteration 2 left four gaps. Three are closed: M18 (LAY-17) is killed, F1 (LAY-12, the 6 px clause) is killed, and the junk `pts` assertion is gone. The fourth, **M9b (LAY-05, hash-ordered tie-breaks), is only killed for some hash seeds.** Across PYTHONHASHSEED 0-9, the new golden test fails the mutant for seeds 5, 7 and 8 and passes it for the other 7. The subprocess determinism test (seeds 1, 2, 3) never fails it. Because nothing fixes the hash seed (pytest-randomly is not installed), a default `pytest` run catches this regression only about 30% of the time. Every other AC is covered and discriminating, and the 5 fresh mutants were all killed.

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1-T6 | ✅ Done | |
| Fix 58b0990 (iteration 2) | ✅ | |
| Fix c3edd4a (iteration 3) | ⚠️ Partial | Parametrizes the lanes route test over `down`/`right` and checks the borders of all three edges. Adds `_route_pts` and `_gap_to_route` and asserts a ≤ 6.5 px gap in 3 label tests. Adds a frozen golden layout hash. Removes the junk `pts`. M9b is still only killed for some seeds |

---

## Spec-Anchored Acceptance Criteria

All line numbers are for `tests/test_layered.py` at **c3edd4a**. Lines up to :357 are unchanged from iteration 2.

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| LAY-01 | Each edge's target is in a later rank than its source, except reversed edges | `:87` `_rank_axis(res,b,dir)[0] >= _rank_axis(res,a,dir)[1] + 80 - 0.5` | ✅ PASS |
| LAY-02 | `down` puts ranks at increasing y, `right` at increasing x | `:83-87` parametrized over `down`/`right`, axis chosen at `:78-80` | ✅ PASS |
| LAY-03 | At least `rank_gap` between ranks and `node_gap` within a rank | `:87` (+80); `:98` `right[0]-(left[0]+left[2]) >= 48 - 0.5`; `:365-374` | ✅ PASS (N5 killed) |
| LAY-04 | No overlapping node boxes | `:93-95` `not _overlap(a, b)`; `tests/test_autolayout.py` `test_engine_invariants[layered]` | ✅ PASS (N5 killed) |
| LAY-05 | Laying out twice gives identical coordinates, using order-only tie-breaks with no hash ordering (spec §cross-cutting) | `:103` `a.boxes == b.boxes and a.routes == b.routes`; `:424` `outs[0] == outs[1] == outs[2]` (seeds 1-3); **new** `:531` `sha256(blob) == GOLDEN` | ❌ **Discrimination gap.** The golden test kills M9b only for hash seeds 5, 7 and 8 out of 0-9. The test process runs with a random seed, so the kill is probabilistic |
| LAY-06 | No edges: one rank, in declaration order | `:109` `len(ys) == 1`; `:110` `a.x < b.x < c.x` | ✅ PASS (N2 killed) |
| LAY-07 | Reverse the back-edges found by a DFS in declaration order, and draw them in their original direction | `:119-120`; `:396` | ✅ PASS |
| LAY-08 | A multi-rank back-edge goes round the outer side; an adjacent-rank back-edge stays in the gap; no segment crosses a node | `:137` `max(x of e6) > right`; `:395-401`; `:130` `not _seg_hits_box` | ✅ PASS |
| LAY-09 | A self-loop leaves and re-enters the same side, with its label beside the loop | `:198-200`, `:275`, `:321`; `:452-457`; `:460` `pill[0] >= min(xs) - 0.5`; **new** `:462` `_gap_to_route(pill, _route_pts(out, loop_e)) <= 6.5` | ✅ PASS. The junk `pts` assertion is removed |
| LAY-10 | Parallel edges get separate routes and separate labels | `:142-143`; `:473` `label_at` differ; `:474` `not _overlap(p1, p2)` | ✅ PASS |
| LAY-11 | Every non-self edge is an orthogonal polyline | `:128`; `:436` (lanes, now in both directions); router `:179-190` | ✅ PASS |
| LAY-12 | The label sits on its route or beside it (pill edge within 6 px), intersects no node box and no label placed before it | `:355-359` pills vs nodes and pills; **new** `:362` `_gap_to_route(_pill_box(e, th), _route_pts(out, e)) <= 6.5`; `:462`; `:475-476` | ✅ PASS. **Iteration-2 gap 3 closed** (F1 and N1 killed). The +0.5 px tolerance is acceptable. `_gap_to_route` measures segment bounding boxes, which is exact because the routes are orthogonal |
| LAY-13 | Edges leaving a decision node use distinct sides or positions | `:148` `routes["e2"][0] != routes["e3"][0]` | ✅ PASS (N3 killed) |
| LAY-14 | The anchor is kept and the edge is left exactly as the author defined it | `:311` `anchored.src == "client.bottom" and anchored.dst == "c.top" and not anchored.via` | ✅ PASS |
| LAY-15 | Members sit inside the group box with padding and label band; no non-member is inside | `:223`, `:224`, `:226` | ✅ PASS (N5 killed) |
| LAY-16 | Lanes are full-span bands; members stay inside their band | `:254-262` parametrized over `down`/`right` | ✅ PASS |
| LAY-17 | An edge crossing a group or lane border goes through it without crossing other nodes | `:231-237`; `:299-311`; **new** `:429-441` over `down`/`right`: `:440` `_on_border(res.routes[eid][0], res.boxes[a])` and `:441` `_on_border(res.routes[eid][-1], res.boxes[b])` for e0, e1 and e2 | ✅ PASS. **Iteration-2 gap 1 closed** (M18 killed by the `[right]` case) |
| LAY-20 | `spinagram check` reports the overflow and the excess in px | `:382`; `:490` `over[1] > 0`; `:492` `f"{over[1]}px tall" in issue.detail` | ✅ PASS |
| LAY-21 | Disconnected components sit side by side in declaration order | `:153-154` | ✅ PASS (N2 killed) |
| LAY-22 | Above 300 nodes, layout completes and warns, naming the bound | `:163` `"300" in str(x.message)`; `:164` | ✅ PASS (N4 killed) |

**Status**: 19 of 20 ACs are covered and discriminating. On LAY-05, the M9b mutant is killed only for some hash seeds.

---

## Regression Check: behavior-diagrams Changes to `autolayout/__init__.py`

- **ba20206** (`:328-332`): group-label bands are added to `node_boxes`, so edge labels avoid zone titles. Labels have more obstacles, but every LAY-12 test still passes, including the new ≤ 6.5 px route-gap check and the pill-vs-node check. No regression.
- **2660dd9** (`:125,128`): a root with a `lanes` hint keeps lanes in declaration order and passes `lanes` into the root hints. This applies only when `lanes` is set at the root, so it is neutral for layered diagrams without lanes. The LAY-16/17 lane tests pass in both directions. No regression.

---

## Edge Cases

- [x] LAY-20 overflow, with the px excess asserted
- [x] LAY-21 components side by side (N2 killed)
- [x] LAY-22 more than 300 nodes warns and completes (N4 killed). The time bound is still untested (informational)

---

## Gate Check

Run in a scratch worktree at c3edd4a:
- `uv run --all-extras ruff check src tests examples`: all checks passed
- `uv run --all-extras pytest -q`: **216 passed, 3 skipped, 0 failed**. The 3 skips are environmental (`dot` twice, `soffice`)
- Targeted run (`tests/test_layered.py tests/test_autolayout.py`): **57 passed, 2 skipped**
- Test integrity: no test was deleted or weakened. The lanes route test gained a `right` case and an `e1` border check, and the self-loop test now has a real assertion in place of `assert pts`

---

## Discrimination Sensor

Setup: `git worktree add --detach <scratchpad>/wt3 c3edd4a`. A script (`scratchpad/mut.py`) applied each mutant by exact string replacement, asserting that the source matched exactly once. It then ran `uv run --all-extras pytest -q tests/test_layered.py tests/test_autolayout.py` and restored the file. The worktree was removed afterwards and `git worktree prune` was run. `git status --porcelain` of the real tree matched the baseline before and after (only ` M .specs/features/layered-layout/validation.md`), so the real tree was never edited. HEAD moved to 712ebc6 during the run because the main session committed.

| # | File (c3edd4a) | Mutation | Result |
| - | -------------- | -------- | ------ |
| M18 | `engines/layered.py:259` | Lane-level routes skip the lane shift (`dx = 0.0`) | ✅ **Killed** (`test_routes_inside_lanes...[right]`) |
| M9b | `engines/layered.py:396` | Initial ordering key `(lane, key[k], k)` → `(lane, hash(k))` | ⚠️ **Seed-dependent**. PYTHONHASHSEED 0-9: killed for 5, 7 and 8 (`test_layout_matches_frozen_golden`), survived for 0-4, 6 and 9. `test_deterministic_across_hash_seeds` never kills it |
| F1 | `autolayout/__init__.py:377` | Vertical-segment beside offset 6 px → 40 px | ✅ **Killed** (3 tests: `:362`, `:462`, `:475`) |
| N1 | `autolayout/__init__.py:379` | Horizontal-segment beside offset 4 px → 40 px | ✅ Killed (2 tests, LAY-12) |
| N2 | `engines/layered.py` `_layout_level` | Components placed in reverse declaration order | ✅ Killed (3 tests, LAY-06/21 and golden) |
| N3 | `engines/layered.py` `_ports` | A decision with 2 out-edges gives both the same bottom port | ✅ Killed (LAY-13 and golden) |
| N4 | `engines/layered.py:83` | Warning bound `> MAX_NODES` → `> MAX_NODES + 1` | ✅ Killed (LAY-22) |
| N5 | `engines/layered.py` `_layout_level` | No `node_gap` between components | ✅ Killed (3 tests, LAY-03/04/15) |

**Sensor depth**: 8 mutants (the 3 iteration-2 survivors plus 5 fresh ones)
**Result**: 7 killed deterministically. M9b is killed for only 3 of 10 hash seeds. **FAIL** under the rule that a surviving mutant needs a fix task.

---

## Remaining Gaps

1. **[Minor, test-only] LAY-05, M9b: the determinism check depends on the hash seed.** `:531` runs in pytest's process, which has a random hash seed, and `:417-425` uses seeds 1-3 on a fixture where the mutant gives the same output for those seeds. **Fix:** have `test_deterministic_across_hash_seeds` run the golden fixture (`kinds={"stock": "decision"}, loops=["ship"]`, as at `:527-528`) in subprocesses for `PYTHONHASHSEED` in `range(10)`, and assert that each output's sha256 equals `GOLDEN`. Seeds 5, 7 and 8 are in that range, so the kill becomes deterministic. Cost: about 10 short subprocesses.
2. **[Info]** F4 from iteration 2: collinear tracks of different edges in one gap are not detected. No MVP AC requires distinct tracks.
3. **[Info]** The LAY-22 time bound is untested.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / surgical | ✅ c3edd4a is test-only |
| No scope creep | ✅ |
| Matches patterns | ✅ The helpers `_route_pts` and `_gap_to_route` are small and documented |
| Spec-anchored outcome check | ✅ All spec values are asserted (80, 48, 6 px, `300`, `px tall`) |
| Per-layer coverage (1:1 to MVP ACs) | ⚠️ LAY-05's discrimination depends on the hash seed |
| Every test maps to a requirement | ✅ |
| Documented guidelines | none (strong defaults applied, per tasks.md) |

---

## Requirement Traceability (proposed; the Verifier did not modify spec.md)

| Requirement | Status |
| ----------- | ------ |
| LAY-01..04, 06..17, 20..22 | ✅ Verified |
| LAY-05 | ⚠️ Implementation correct; the test kills the hash-order mutant only for some seeds |

---

## Summary

**Overall**: Iteration-2 gaps 1 (M18), 3 (F1) and 4 (junk `pts`) are closed. Gap 2 (M9b) is narrowed but not closed: it is killed for 30% of hash seeds instead of 0%. The implementation behaved correctly on every probe; what remains is a test-strength issue in one test.
**Spec-anchored check**: 19 of 20 ACs discriminating.
**Sensor**: 7 of 8 killed deterministically; M9b is seed-dependent.
**Gate**: 216 passed and 3 skipped (environmental); ruff clean.
**Next**: this was the last iteration, so escalate to the user. The recommended fix is a one-test change (gap 1). Accepting it as is would leave a regression guard that triggers about 30% of the time.
**Candidate lesson**: "A golden hash checked in-process detects hash-order nondeterminism only for the process's random seed. Pin it across a range of PYTHONHASHSEED values in subprocesses."

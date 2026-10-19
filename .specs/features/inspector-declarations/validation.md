# Validation Report: inspector-declarations (iteration 4, user-approved extra pass) - PASS

**Date**: 2026-10-19
**Spec**: `.specs/features/inspector-declarations/spec.md`
**Diff range**: `213db8b..HEAD` (HEAD = 5c2ecaf), excluding the built bundle `src/spinagram/ui/static`
**Verifier**: independent sub-agent (author ≠ verifier). Iteration 4 of the fix→re-verify loop, approved by the user after the 3-iteration limit.

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1-T10 | ✅ Done | feature work |
| T11-T14 | ✅ Done | Verifier fixes from iterations 1-3 (D1, M2-M4, M14, DECL-01 wording, gates, N5) |
| T15 (5c2ecaf) | ✅ Done | `test_quotes_must_pair` kills N3 |

---

## Spec-Anchored Acceptance Criteria

Legend: ✅ PASS = the test asserts the spec-defined outcome. 🔎 = UI-only AC with tests "none" in the Test Coverage Matrix (React components are build-gated). For these, the Verifier reviewed the code and it plausibly implements the AC, and the author checked it in a real browser. They are not test-covered.

| AC | Spec-defined outcome | Evidence | Result |
| -- | -------------------- | -------- | ------ |
| LAYOUT-01 | aside width == wrapper width (0 px gap) | `web/src/CodePanel.tsx:147` `flex min-w-0 flex-1` inside the flex wrapper at `web/src/DiagramView.tsx:251`; author: 627 == 627 | 🔎 |
| LAYOUT-02 | column 44 % of the row, min 420 px | `web/src/DiagramView.tsx:251` `w-[44%] min-w-[420px] shrink-0` | 🔎 |
| ELI-01 | `styled: false`, one element per tree item, empty styles/trace | `tests/test_css.py:649` `r["styled"] is False`; `:650` exact key list; `:653` `e["styles"] == {} and e["trace"] == {}` | ✅ PASS |
| ELI-02 | without the flag, `elements == []` | `tests/test_css.py:659` | ✅ PASS |
| ELI-03 | unstyled report keys == the styled copy's keys | `tests/test_ui.py:374-375` | ✅ PASS |
| ELI-04 | element list; selected element shows type, id, classes, attrs | `web/src/Inspector.tsx:261`, `:308-321` | 🔎 |
| HIL-01 | translucent tint + solid outline | `web/src/Inspector.tsx:77` | 🔎 |
| HIL-02 | `label W × H`, rounded | `web/src/inspect.test.ts:33` `toBe("node#users 182 × 64")` | ✅ PASS |
| HIL-03 | `edge a → b` without a size | `web/src/inspect.test.ts:50` | ✅ PASS |
| HIL-04 | chip below the box when chip + gap would cross the top | `web/src/inspect.test.ts:57-58`, `:63` `toBe(true)`, `:64` `toBe(false)` | ✅ PASS |
| DECL-01 | first `id:` entry (quoted or bare, then optional spaces and `,` `}` `#` or EOL), else first `title:`/`label:` | `tests/test_ui_declare.py:53-66`, `:108` first match, `:114` literal id, `:124` colon required | ✅ PASS |
| DECL-02 | first `id="…"`/`id='…'`, else the label as a quoted string | `tests/test_ui_declare.py:70-72`, `:108`, `:128` paired quotes `== 2` | ✅ PASS |
| DECL-03 | first `from -> to` (word-bounded), else a line with both `from:` and `to:` | `tests/test_ui_declare.py:80-82`, `:102` mixed quotes, `:108`, `:119` left boundary | ✅ PASS |
| DECL-04 | Python edge by its quoted label; no label → None | `tests/test_ui_declare.py:86-87` | ✅ PASS |
| DECL-05 | no match → None | `tests/test_ui_declare.py:91-93` | ✅ PASS |
| DECL-06 | `{file, line, text}` or null; diagram at its `id:` / `Diagram("id"` line | `tests/test_ui.py:388-395` exact dicts; `tests/test_ui_declare.py:97-98` | ✅ PASS |
| DECL-07 | Declaration section with `file:line` + monospace source line | `web/src/Inspector.tsx:205-221`, `:329` | 🔎 |
| DECL-08 | "Declaration not found in <file>" | `web/src/Inspector.tsx:207` | 🔎 |
| DECL-09 | Show in code opens the panel and selects the line | `web/src/DiagramView.tsx:69-73`, `web/src/CodePanel.tsx:138-142` | 🔎 |
| DECL-10 | code mode, inspect off: click selects the declaration line | `web/src/DiagramView.tsx:110` | 🔎 |
| KEY-01 | no single-key shortcut in input/textarea/select/contenteditable | `web/src/hooks.test.ts:73-80`; wiring at `web/src/hooks.ts:195` | ✅ PASS |
| SIDE-01 | `«` → 32 px rail labelled "Recent" | `web/src/App.tsx:192`, `:198` | 🔎 |
| SIDE-02 | the rail or `[` toggles the sidebar | `web/src/App.tsx:39` | 🔎 |
| SIDE-03 | restored from `localStorage["spinagram.sidebar"]`; no storage → expanded | `web/src/App.tsx:267-273` | 🔎 |

**Status**: ✅ All 13 test-covered ACs assert the spec outcome. 0 spec-precision gaps. The 11 UI-only ACs were code-reviewed by the Verifier and browser-checked by the author.

---

## Discrimination Sensor

Scratch: a fresh `git worktree add --detach …/scratchpad/wt5 HEAD`. Tests: `uv run --all-extras pytest -q -x -p no:cacheprovider tests/test_css.py tests/test_ui_declare.py tests/test_ui.py` and `bun test`.

Before each mutant, every `__pycache__` outside `.venv`/`node_modules` was deleted, and `PYTHONDONTWRITEBYTECODE=1` was set. Each mutant was applied, run and reverted. The unmutated suite passed before the run (115 passed). I confirmed separately that N3 is killed by `test_quotes_must_pair` (`assert 1 == 2`).

The worktree was removed with `git worktree remove --force`. Real-tree porcelain before and after was identical (`M .specs/LESSONS.md`, `M .specs/lessons.json`, `?? validation.md`).

| # | File:line | Description | Killed? |
| - | --------- | ----------- | ------- |
| M1 | `src/spinagram/ui/declare.py:39` | YAML node tries title/label before id | ✅ Killed |
| M2 | `src/spinagram/ui/declare.py:18` | YAML value unescaped in all branches | ✅ Killed |
| M3 | `src/spinagram/ui/declare.py:31` | edge arrow loses its left boundary | ✅ Killed |
| M4 | `src/spinagram/ui/declare.py:51-53` | last matching line instead of the first | ✅ Killed |
| M5 | `src/spinagram/css.py:672` | `all_elements` omits edges | ✅ Killed |
| M6 | `src/spinagram/css.py:670` | `all_elements` flag ignored | ✅ Killed |
| M7 | `src/spinagram/ui/workspace.py:476` | declaration text off by one line | ✅ Killed |
| M8 | `src/spinagram/ui/workspace.py:476` | absolute file path instead of `sf.rel` | ✅ Killed |
| M9 | `src/spinagram/ui/workspace.py:471` | `OSError` not caught | ✅ Killed |
| M10 | `src/spinagram/ui/workspace.py:466` | styles called without `all_elements` | ✅ Killed |
| M11 | `web/src/inspect.ts:29` | `Math.floor` instead of `Math.round` | ✅ Killed |
| M12 | `web/src/inspect.ts:29` | edges get a size | ✅ Killed |
| M13 | `web/src/inspect.ts:32` | chip never placed below | ✅ Killed |
| M14 | `web/src/inspect.ts:32` | below threshold ignores the gap | ✅ Killed |
| M15 | `web/src/hooks.ts:189` | contenteditable not treated as typing | ✅ Killed |
| M16 | `web/src/hooks.ts:189` | `select` dropped from the guard | ✅ Killed |
| N1 | `src/spinagram/ui/declare.py:14` | `_quoted` drops the `'v'` alternative | ✅ Killed |
| N2 | `src/spinagram/ui/declare.py:18` | `_yaml` drops the bare alternative | ✅ Killed |
| N3 | `src/spinagram/ui/declare.py:14` | `_quoted` accepts mismatched quotes | ✅ Killed |
| N4 | `src/spinagram/ui/declare.py:18` | `_yaml` bare branch not escaped | ✅ Killed |
| N5 | `src/spinagram/ui/declare.py:18` | key colon made optional | ✅ Killed |

**Sensor depth**: expanded (21 behavior-level mutants, the full set from iterations 1-3)
**Result**: 21/21 killed

---

## Interactive UAT Results

The Verifier did not run UAT (no browser). The author's browser checks for the 🔎 ACs are recorded in the iteration-1 notes: 627 == 627 px; chip `node#users 279 × 105`; Declaration `aws_layout.yaml:22`; lines 22/23 selected; `ei[` typed into the editor; 32 px rail; `"0"` persisted; `[` restores 256 px.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code | ✅ |
| Surgical changes | ✅ |
| No scope creep | ✅ (SIDE/KEY stories added mid-execution, logged in the spec) |
| Matches patterns | ✅ |
| Spec-anchored outcome check (asserted values match spec) | ✅ |
| Per-layer Coverage Expectation met (DECL-01..05 1:1 + edge cases) | ✅ |
| Every test maps to a spec requirement - no unclaimed tests | ✅ |
| Documented guidelines followed: `pyproject.toml`, `.specs/features/live-editor/tasks.md` | ✅ |

---

## Edge Cases

- [x] Spec file cannot be read → every declaration null, still served: `tests/test_ui.py:406`.
- [x] Regex characters in ids matched literally: `tests/test_ui_declare.py:114`.
- [x] List titles searched by the joined label; the Python list-title limit is logged in the spec's Assumptions.

---

## Gate Check

- **Gate command** (from tasks.md): `uv run ruff check src tests examples && uv run --all-extras pytest -q && (cd web && bun test && bunx bun@1.4.2 run build)`
- **Outcome in a fresh worktree**: ruff clean; pytest 627 passed, 3 skipped (vector extra not installed), 0 failed; bun 48 tests, 0 failed; build exit 0.
- **Test count before feature**: 448 Python test functions, 43 web tests.
- **Test count after feature**: 468 Python, 48 web.
- **Delta**: +20 Python; web +8 / -3. The 3 removed tests are the `jumpLine` tests, deleted with `jumpLine` and replaced by the server-side locator tests, as the spec logs.
- **Skipped tests**: 3 `tests/test_engine.py` vector-extra skips, which predate this feature.
- **Failures**: none.

---

## Fix Plans

None open.

Gaps closed over iterations 1-4:
- D1: mixed-quote YAML edges (3d33e70).
- M2, M3, M4: escaping, edge boundary and first-match tests (3d33e70).
- M14: chip threshold test (7d67c25).
- DECL-01 wording, and the list-title limit logged (8fb5f43).
- N5: key colon test, and gates moved to `--all-extras` (fcdc191).
- N3: paired-quotes test (5c2ecaf).

Iteration 2 wrongly reported N3 as killed. Iteration 3 corrected that, and this iteration confirms the kill with caches and bytecode removed between mutants.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| ELI-01..03, HIL-02..04, DECL-01..06, KEY-01 | Implemented | ✅ Verified |
| LAYOUT-01/02, ELI-04, HIL-01, DECL-07..10, SIDE-01..03 | Implemented | ✅ Verified (code-reviewed by the Verifier, browser-checked by the author; no automated test by design) |

---

## Summary

**Overall**: ✅ Ready

**Spec-anchored check**: 13/13 test-covered ACs match their spec outcome; 0 spec-precision gaps; 11 UI-only ACs code-reviewed
**Sensor**: 21/21 mutants killed
**Gate**: 627 Python and 48 web tests passed, build ok

**What works**: inspector for unstyled diagrams, declarations in the styles report and the panel, devtools-style hover chip, jump to the declaration line, editor-safe shortcuts, collapsible sidebar.

**Issues found**: none open. Remaining risk: the UI-only ACs depend on the author's browser check, with no automated UI test.

**Next steps**: none for verification. Lessons L-028..L-036 stay as candidates.

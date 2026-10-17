# Live editor Validation (final re-verify, iteration 3 of 3)

**Verdict:** PASS
**Result**: PASS ✅

**Date**: 2026-10-17
**Spec**: `.specs/features/live-editor/spec.md`
**Diff range**: `891104b^..HEAD` (HEAD `4808c58`)
- Fix iteration 1: `440335e..47f89b4` (T18-T23).
- Fix iteration 2: `c444a9f` (T24) and `4808c58` (T25 plus the rebuilt bundle).

**Verifier**: independent sub-agent (author ≠ verifier)

## Iteration history

1. **Iteration 1: FAIL.**
   - A multi-root display-path collision wrote the wrong file.
   - The watcher retarget test raced.
   - Quick double saves lost the server version.
   - `go()` bypassed the leave guard.
   - Lone surrogates returned a 500.
   - Three mutants survived.
2. **Iteration 2: FAIL.** The implementation was fixed, but four mutants on the new code survived (N3, N9, N10, N11).
3. **Iteration 3: PASS.**
   - N3, N10 and N11 are killed.
   - The navigation decision is extracted into `mayLeave()` and unit-tested.
   - The two remaining survivors delete a call site inside the `useRoute` React hook. They are accepted under the Test Coverage Matrix (see "Accepted residual" below).

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1-T17 | ✅ Done | Feature tasks |
| T18-T23 | ✅ Done | Fix iteration 1 |
| T24-T25 | ✅ Done | Fix iteration 2; all "Done when" boxes `[x]` |

---

## Gate Check

- **Gate**: `uv run ruff check src tests examples && uv run pytest -q && (cd web && bun test)`
- **Result**:
  - ruff: all checks passed.
  - pytest: **607 passed, 3 skipped, 0 failed**. `tests/test_ui_editor.py` alone: 39 passed.
  - bun: **43 pass, 0 fail** (102 expect calls, 4 files).
- **Test count**:

  | Point | pytest | bun |
  |---|---|---|
  | Before the feature | 568 | 26 |
  | After iteration 1 fixes | 603 | 41 |
  | Now | 607 | 43 |

  Removed: only the `languageOf` test, removed with that dead function in T22 (justified).
- **Skipped**: `test_autolayout.py:155`, `:165` (dot runtime not installed), `test_pptx_svg.py:129` (soffice not installed). All predate the feature.
- **Bundle (scratch worktree only)**: `bunx bun@1.4.2 install --frozen-lockfile && bunx bun@1.4.2 run build` (`tsc -b && vite build`) passed. The output is byte-identical to the committed bundle: `index-B2vhGHTz.js`, `index-G04dybD5.css` and the lazy chunk `codemirror-BWZTzdi0.js`. The worktree's `git status --porcelain` was empty after the build.

---

## Spec-Anchored Acceptance Criteria

Legend:
- ✅ PASS
- 🧱 implemented in a component or hook; covered by the build gate and logic tests (the Test Coverage Matrix sets SPA components to "none / build gate")

### P1: See and edit the code of a diagram

| ID | Spec-defined outcome | `file:line` + assertion | Result |
|---|---|---|---|
| EDIT-01 | Spec tab first, then cascade stylesheet files in cascade order | `tests/test_ui_editor.py:162` `[f["path"] for f in got] == ["a.py","team.css","own.css",str(shared.resolve())]`; tabs rendered in order `CodePanel.tsx:149` | ✅ |
| EDIT-02 | `.py`/`.css`/`.yaml`/`.yml` highlighted by language | `tests/test_ui_editor.py:64,67,69,71` `language == "python"` / `("css","\n")` / `"yaml"` ×2; modes `codemirror.ts:28` | ✅ 🧱 |
| EDIT-03 | Modified mark until saved or reverted | `web/src/editor.test.ts:13` `e.dirty` true; `:15` revert gives false; dot `CodePanel.tsx:161` | ✅ |
| EDIT-04 | Ctrl/Cmd+S or Save writes and clears the mark | `web/src/editor.test.ts:27` `toMatchObject({dirty:false,version:"v2",disk:"new\n"})`; `tests/test_ui_editor.py:275-276`; `Mod-s` `codemirror.ts:39` | ✅ 🧱 |
| EDIT-05 | Re-render ≤ 1 s for a spec of up to 50 nodes | `tests/test_ui_editor.py:577` `time.time() - t0 <= 1.0` with a 50-node, 49-edge spec, measured from `PUT /api/files` (`:574` 200) until the SVG shows the saved text. The 1-node test is at `:445` | ✅ (wall-clock test: watch for CI flakiness) |
| EDIT-06 | Load error: keep the editor text; error over the last good render; file and line named | Broken spec keeps its sheets `tests/test_ui_editor.py:482`; still writable `:485`; the list follows the last good load `:544` `["a.py","team.css","other.css"]`; a renamed diagram drops its old key `:552-553`; overlay `DiagramView.tsx:160,173`; file:line in the message `workspace.py:77` | ✅ |
| EDIT-07 | A clean tab follows the disk | `web/src/editor.test.ts:43` `toMatchObject({text:"changed\n",version:"v2",dirty:false})` | ✅ |
| EDIT-08 | Dirty tab + disk change → keep text; conflict notice with Reload / Keep mine | `web/src/editor.test.ts:56-58`; reload `:61`; keepMine `:64`; banner `CodePanel.tsx:183-192` | ✅ 🧱 |
| EDIT-09 | Refused save → file untouched, conflict notice | `tests/test_ui_editor.py:284-285`; 409 → refetch → conflict (`CodePanel.tsx` catch branch + `editor.test.ts:56-58`) | ✅ 🧱 |
| EDIT-10 | Confirm before leaving the diagram or reloading while dirty | Decision: `web/src/hooks.test.ts:52-53` (staying never asks; `asked` 0), `:58` (guard false → `false`), `:60`, `:62`, plus `confirmLeave` tests. Wired: hashchange `hooks.ts:65`, `go()` `hooks.ts:75`, Open folder `OpenFolder.tsx:38`, `beforeunload` in `CodePanel.tsx` | ✅ 🧱 (call sites: see Accepted residual) |

### P1: Source and save API

| ID | Spec-defined outcome | `file:line` + assertion | Result |
|---|---|---|---|
| SRC-01 | Files with path (relative to the root, absolute outside it), language, text, version; spec first | `tests/test_ui_editor.py:162-165`; route `:264-267`; unique paths with several roots `:468` | ✅ |
| SRC-02 | Write; return the new version | `tests/test_ui_editor.py:275` `r.json() == {"version": _sha(...)}` | ✅ |
| SRC-03 | Stale version → 409 with the current version; file unchanged | `tests/test_ui_editor.py:284` `409 and r.json()["version"] == _sha(before)`; `:285` | ✅ |
| SRC-04 | Unlisted path → 403, nothing written | `tests/test_ui_editor.py:292-293`, `:218-222`; several roots `:470-471`; after `open`, the old folder's sheet is refused by absolute and by relative path (`PermissionError`), `:530` `set(ws.editable()) == {"a.py"}`, unchanged `:535` | ✅ |
| SRC-05 | > 1 MiB → 413; non-UTF-8 → 422; nothing written | Exact 1 MiB: `tests/test_ui_editor.py:508` → 200. +1 byte: `:512` → 413. Raw `\xff`: `:303` → 422. Lone surrogate: `:495` `422 and error == "the text is not valid UTF-8"`, file unchanged `:496` | ✅ |
| SRC-06 | Missing `X-Spinagram: 1` → 403 | `tests/test_ui_editor.py:313,315` (`error == "missing X-Spinagram header"`), `:316`, `:318` (no ACAO), fs `:349`, open `:374` | ✅ |
| SRC-07 | Temp file in the same folder, then rename | `tests/test_ui_editor.py:242-245` | ✅ |
| SRC-08 | Keep the newline style | `tests/test_ui_editor.py:229` `read_bytes() == b"a { fill: red }\r\nb {}\r\n"` | ✅ |

### P1: Open a folder

| ID | Spec-defined outcome | `file:line` + assertion | Result |
|---|---|---|---|
| DIR-01 | Dialog: subdirectories, a parent entry and a path box | `tests/test_ui_editor.py:344`; UI in `OpenFolder.tsx` | ✅ 🧱 |
| DIR-02 | Subdirectories with the count of specs directly in each | `tests/test_ui_editor.py:33-34` `[("aws",2),("empty",0)]`; `:346` | ✅ |
| DIR-03 | Becomes the root; every spec loaded; shown in the catalog | `tests/test_ui_editor.py:124`, `:362-365` | ✅ |
| DIR-04 | Folder and subfolders watched; a save re-renders | `tests/test_ui_editor.py:385`; `:426-427` (watcher warmed on the old folder, then an event arrives from the opened one) | ✅ |
| DIR-05 | Bad path → workspace kept, "not a directory: <path>" | `tests/test_ui_editor.py:133-135`, `:373`, `:376`, `:348` | ✅ |
| DIR-06 | Subfolder-relative keys | `tests/test_ui_editor.py:92` | ✅ |
| DIR-07 | Skip list | `tests/test_ui_editor.py:42`, `:92`, `:109-110` | ✅ |
| DIR-08 | 2,000 cap in scan order, truncated in the UI | `tests/test_ui_editor.py:101-102`; notice `DiagramsPage.tsx:84` | ✅ |
| DIR-09 | A CLI directory is scanned recursively | `tests/test_ui_editor.py:92` | ✅ |
| DIR-10 | Trust note in the dialog | `OpenFolder.tsx` "Opening a folder runs its Python specs…" | ✅ 🧱 |

### P2: Jump to code

| ID | Spec-defined outcome | `file:line` + assertion | Result |
|---|---|---|---|
| JUMP-01 | First line with the title as a string literal, selected | `web/src/editor.test.ts:87` duplicate title → `toBe(1)`; `:83-84`; click `DiagramView.tsx:105-107`; select and scroll `codemirror.ts:61-66` | ✅ |
| JUMP-02 | No match → editor unchanged | `web/src/editor.test.ts:90-93` `toBeNull()` ×4 | ✅ |

**Status**: ✅ 30/30 ACs covered with evidence matching the spec-defined outcome. No spec-precision gaps remain: the EDIT-05 fixture now has 50 nodes.

---

## Edge Cases

- [x] **Shared stylesheet re-renders both diagrams**: `tests/test_ui_editor.py:457` `{"type":"diagram","keys":["d1.py#D1","d2.py#D2"]} in events`.
- [x] **Spec deleted while open → "file removed", Save disabled**: `CodePanel.tsx` 404 branch plus the header `file removed: <path>`; `merge` marking tested at `editor.test.ts:76`. 🧱
- [x] **No specs → "no diagrams in <path>"**: `DiagramsPage.tsx:92`. 🧱
- [x] **CRLF shown normally and kept on save**: `tests/test_ui_editor.py:61`, `:229`.
- [x] **Second quick save sends the first's version**: `web/src/editor.test.ts:36` `toMatchObject({text:"first and more\n",disk:"first\n",version:"v2",dirty:true})`; one save at a time in `CodePanel.tsx:58-59,71`.

---

## Discrimination Sensor

**Setup**:
- Scratch worktree: `git worktree add …/scratchpad/verifier-wt3 HEAD`.
- Web dependencies installed first (`bunx bun@1.4.2 install --frozen-lockfile`). The unmutated run gave 43 pass.
- Each mutant was applied alone and reverted with `git checkout -- <file>`.
- Python runs: `pytest -q tests/test_ui_editor.py` against `<wt>/src`.
- TS runs: `bun test` in `<wt>/web`. Every TS kill names its failing test.
- The real tree's `git status --porcelain` was `?? .specs/features/live-editor/validation.md` before, and the same after `git worktree remove --force` (matches).

| # | Mutation | File:line | Result |
|---|---|---|---|
| N3 | `_remember` not called on reload | `workspace.py:257` | ✅ Killed (`test_remembered_stylesheets_follow_the_last_good_load`, `test_a_renamed_diagram_drops_its_old_key`) |
| N10 | `_remember` keeps stale keys | `workspace.py:314-315` | ✅ Killed (`test_a_renamed_diagram_drops_its_old_key`) |
| N11 | `open` keeps the old folder's remembered sheets | `workspace.py:161` | ✅ Killed (`test_opening_a_folder_forgets_the_old_folders_stylesheets`) |
| N9b | `mayLeave` always true | `hooks.ts:53` | ✅ Killed ("going to another page asks the guard and obeys it") |
| N9c | `mayLeave` asks even when staying | `hooks.ts:53` | ✅ Killed ("staying on the same page never asks") |
| N8 | `confirmLeave` always true | `hooks.ts:48` | ✅ Killed (2 tests) |
| N9 | `go()` drops its `mayLeave` call | `hooks.ts:75` | ⚪ Survived: accepted residual (see below) |
| N9d | hashchange listener drops its `mayLeave` call | `hooks.ts:65` | ⚪ Survived: accepted residual (see below) |
| M12 | Delete `retarget.set()` | `server.py:152` | ✅ Killed **2/2 runs** |
| Spot-checks of earlier kills | M1 header guard, M2 version compare, M3 unlisted path, M6 non-atomic write, M8 size boundary, T3 last match, N1 multi-root display, N2, N4, N5 remembered sheets, N6 surrogate check, N7 `saved` ignores `sent` | various | ✅ All still killed |

**Sensor depth**: P0 (data-integrity write path)
- Iteration 3: 21 mutant runs, 19 killed, 2 accepted residual.
- Across the three iterations, every mutant on Python, `editor.ts` and the pure `hooks.ts` functions is killed.

### Accepted residual (N9, N9d): judged under the Test Coverage Matrix

The two survivors delete the one-line `mayLeave(...)` call inside `useRoute` (`hooks.ts:65`, `:75`). This is accepted, not a test gap, for four reasons:

1. **The matrix covers this case.** `tasks.md` sets SPA components to "none / Build gate (typecheck + bundle); behaviour covered by the logic tests". `useRoute` is React wiring that needs `window`, `location` and `history`. The repo has no DOM test environment, and adding one is outside this feature.
2. **The logic is unit-tested.** It now lives in one pure function used by both call sites, and `mayLeave`/`confirmLeave` mutants N8, N9b and N9c are all killed. The original verifier rule asked only that logic which could be unit-tested is unit-tested, and this logic now is.
3. **The remaining surface is one call per path.** It is the same class as other call sites already accepted as 🧱 build-gate only: `CodePanel` calling `saved(...)`, `OpenFolder` calling `confirmLeave()`, and `DiagramView` calling `setJump`.
4. **The worst case is contained.** If the call were dropped, a dirty buffer could be left without a prompt (UX). It does not reach the write path: no file is written, and the data-integrity paths are fully discriminated.

Recommendation (non-blocking): if a DOM test environment (e.g. happy-dom with `bun test`) is added later, cover `useRoute` call sites and `CodePanel` save wiring there.

---

## Code Quality

| Check | Status | Notes |
|---|---|---|
| No scope creep; minimal fixes | ✅ | T24 is tests only. T25 adds one 3-line pure function and routes both paths through it |
| No single-use abstraction / unnecessary flexibility | ✅ | `mayLeave` has two call sites. The dead `languageOf` was removed in T22 |
| Matches existing patterns | ✅ | `_err` conventions, the lock, and pure `editor.ts`/`hooks.ts` helpers tested with `bun test` |
| Security: CSRF header | ✅ | `server.py:47`; all four routes are tested; no CORS headers |
| Security: path allow-list | ✅ | Listed files only. Display paths are unique with several roots (`workspace.py:293`). Remembered sheets are reset on `open` (`workspace.py:161`) and tested |
| Security: atomic write | ✅ | Temp file in the same folder, fsync, mode kept, then `os.replace`; temp cleaned on failure |
| Security: size limit / encoding | ✅ | 413 above 1,048,576 bytes (boundary pinned); 422 for invalid UTF-8 bytes and lone surrogates before any write |
| Spec-anchored outcome check | ✅ | Exact statuses, messages, bytes and orderings asserted |
| Per-layer coverage expectation | ✅ | Domain 1:1 to ACs. Routes cover happy, 403, 404, 409, 413 and 422. Tab model transitions and the navigation decision are unit-tested. Components are build gate only, per the matrix |
| Every test maps to an AC, edge case or Done-when | ✅ | Tagged in the test names and comments |
| Guidelines followed | ✅ | `pyproject.toml` (ruff, pytest), the CI bundle check (byte-identical rebuild), the Test Coverage Matrix |

---

## Requirement Traceability Update

| Requirement | Status |
|---|---|
| EDIT-01-10, SRC-01-08, DIR-01-10, JUMP-01-02 | ✅ Verified |

---

## Summary

**Overall**: ✅ Ready

**Spec-anchored check**: 30/30 ACs matched; all 5 edge cases handled
**Sensor**: 19/21 killed this iteration; the 2 survivors (N9, N9d: call-site deletion inside a React hook) are accepted under the Test Coverage Matrix
**Gate**: ruff clean; pytest 607 passed / 3 skipped (environment); bun 43 pass; bundle rebuild byte-identical

**Non-blocking notes**:
- EDIT-05 is a wall-clock test (≤ 1.0 s) and could flake on a slow CI runner.
- A DOM test environment would close the call-site residual.

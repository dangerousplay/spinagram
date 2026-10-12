# Validation: diagram-catalog - PASS ✅

**Verdict**: PASS (iteration 2, HEAD 4fccddd)

**Date**: 2026-10-12
**Spec**: `.specs/features/diagram-catalog/spec.md`
**Diff range**: `main..HEAD` (735888a..4fccddd, 12 commits)
**Verifier**: independent sub-agent (author ≠ verifier)

## Iteration history

| Iteration | HEAD | Verdict | Notes |
| --------- | ---- | ------- | ----- |
| 1 | 0211f44 | FAIL | META-03: YAML `tags: 0` / `false` / `{}` (spec and `_defaults.yaml`) loaded silently as `[]` because of truthiness checks at `src/spinagram/yaml_io.py:55,137,173`. Lesson L-007 recorded. |
| 2 | 4fccddd | PASS | Commit 4fccddd (T11) switches the three checks to `is not None` (`src/spinagram/yaml_io.py:56,138,174`) and adds tests; all three reverted mutants are killed. |

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 Diagram fields | ✅ Done | `src/spinagram/model.py:228-273` |
| T2 YAML + folder defaults | ✅ Done | defect fixed by T11 |
| T3 metadata.py | ✅ Done | `src/spinagram/metadata.py` |
| T4 CLI filters | ✅ Done | `src/spinagram/cli.py:16-27,47-49,143` |
| T5 Workspace API | ✅ Done | `src/spinagram/ui/workspace.py:330-332` |
| T6 catalog.ts | ✅ Done | `web/src/catalog.ts` |
| T7 routes | ✅ Done | `web/src/hooks.ts:13-20` |
| T8 DiagramsPage | ✅ Done | `web/src/DiagramsPage.tsx` |
| T9 App shell | ✅ Done | `web/src/App.tsx`; iteration 1 rebuilt the bundle in a scratch worktree and got byte-identical `src/spinagram/ui/static` (T11 touches no web code) |
| T10 Docs | ✅ Done | python/yaml/cli/live-ui .mdx |
| T11 Fix falsy tags (iteration-1 gap) | ✅ Done | `src/spinagram/yaml_io.py:56,138,174`; `tests/test_metadata.py:66,108-119` |

---

## Spec-Anchored Acceptance Criteria

### P1: Diagram metadata

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| META-01 | category `Networking`, tags `["aws","hub"]` | `tests/test_metadata.py:12-13` - `d.category == "Networking"`, `d.tags == ["aws", "hub"]` | ✅ PASS |
| META-02 | YAML gives same as META-01 | `tests/test_metadata.py:57-58` - `d.category == "Networking"`, `d.tags == ["aws", "hub"]` | ✅ PASS |
| META-03 | non-list/non-string `tags` or non-string `category` fails naming id and key | `tests/test_metadata.py:34` - `match=r"N5: tags must be a list of strings"` (5, `["ok",3]`, dict); `tests/test_metadata.py:40` - `N6: category must be a string`; `tests/test_metadata.py:65-69` - YAML `tags: 5`, `[ok, 3]`, `0`, `false`, `{}`, `category: [x]` raise `Y1: {key} must be a`; `tests/test_metadata.py:114,118` - folder `tags: 0|false|{}` raise `Y1: tags must be a list of strings` (YAML) and `P1: tags must be a list of strings` (Python) | ✅ PASS (fixed in iteration 2) |
| META-04 | single string → one-element list | `tests/test_metadata.py:28` - `tags=" Kubernetes "` → `["kubernetes"]`; `tests/test_metadata.py:62` YAML same | ✅ PASS |
| META-05 | folder category fills unset, YAML and Python | `tests/test_metadata.py:96` - `== ["Platform", "Platform"]`; `tests/test_metadata.py:105` declared wins `== ["Networking", "Data"]` | ✅ PASS |
| META-06 | normalised union of folder + spec tags | `tests/test_metadata.py:129-130` - `[["aws","shared","team-a"],["gcp","shared","team-a"],["shared","team-a"]]` | ✅ PASS |
| META-07 | trim, lower, dedupe, sort | `tests/test_metadata.py:13` (`" Hub "`, `"AWS"`, `""`); `tests/test_metadata.py:17` `== ["alpha", "zeta"]` | ✅ PASS |

### P1: Inferred provider tags and category

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| META-08 | six packs → `aws,gcp,kubernetes,azure,oci,openstack` plus declared, from nodes/groups/zones | `tests/test_metadata.py:146` - `effective_tags(d) == ["aws","azure","gcp","kubernetes","oci","openstack","team"]` | ✅ PASS |
| META-09 | `aws-*` group/zone style → `aws` | `tests/test_metadata.py:155,158` - `effective_tags(...) == ["aws"]` | ✅ PASS |
| META-10 | dominant provider display name; tie → alphabetically first tag | `tests/test_metadata.py:168` `== "Google Cloud"`; `tests/test_metadata.py:177` tie k8s/gcp `== "Google Cloud"`; `tests/test_metadata.py:205-206` showcase map | ✅ PASS |
| META-11 | declared category wins | `tests/test_metadata.py:185` - `effective_category(d) == "Networking"` with `aws:s3` icon | ✅ PASS |
| META-12 | empty category, shown "Uncategorised" | `tests/test_metadata.py:193` `== ""`; `web/src/catalog.test.ts:72-74` label `UNCATEGORISED`, `category === ""` | ✅ PASS |

### P1: Search and grouped browsing

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| META-13 | API entries carry effective `category`, sorted `tags`, `subtitle` | `tests/test_ui.py:65-68` - `("Transit","Networking",["aws","team-a"])`, `(None,"Google Cloud",["gcp","kubernetes"])`; `tests/test_ui.py:49-50` empty defaults | ✅ PASS |
| META-14 | one section per category, by name, Uncategorised last; card = thumbnail, id, title, tags | `web/src/catalog.test.ts:72-73` labels `["AWS","Google Cloud","Kubernetes",UNCATEGORISED]`; card `web/src/DiagramsPage.tsx:105-117,135-158` (UI: typecheck/build + author walkthrough, per matrix) | ✅ PASS |
| META-15 | every term, case-insensitive substring of id/title/subtitle/category/tag | `web/src/catalog.test.ts:38-46` - `gcp01`, `HUB-AND`, `data tiers` (subtitle), `google` (category), `kube` (tag); `web azure` → `[]` | ✅ PASS |
| META-16 | every selected chip must be carried | `web/src/catalog.test.ts:52-54` - `["aws","networking"]` → `["AWS02"]`, `["gcp","aws"]` → `[]` | ✅ PASS |
| META-17 | "No diagrams match" + control clearing search and chips | `web/src/DiagramsPage.tsx:96-101` text and `onClick={clear}`; `web/src/DiagramsPage.tsx:19-22` clears both (code read) | ✅ PASS |
| META-18 | card opens the diagram view | `web/src/DiagramsPage.tsx:127` `href={href({ kind: "diagram", key: d.key })}`; `web/src/App.tsx:160-169` routes to `DiagramView` | ✅ PASS |
| META-19 | failed spec listed with its error | `web/src/DiagramsPage.tsx:16,71-87` - `f.path` + `<pre>{f.error}</pre>` | ✅ PASS |

### P1: Navbar and recent diagrams

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| META-20 | navbar Diagrams, Themes, Icon packs, Docs; active highlighted | `web/src/App.tsx:106-124` four items; `web/src/App.tsx:204-213` `aria-current="page"` + accent when active; `web/src/App.tsx:13` section map | ✅ PASS |
| META-21 | Docs opens `https://dangerousplay.github.io/spinagram/docs/` in new tab | `web/src/App.tsx:12` `DOCS_URL`; `web/src/App.tsx:117-118` `href={DOCS_URL} target="_blank"` | ✅ PASS |
| META-22 | Themes/Icon packs pages list all, linking to existing views | `web/src/App.tsx:180-183,269-309`; routes `web/src/hooks.test.ts:16-17` | ✅ PASS |
| META-23 | newest first, ≤10, no duplicates | `web/src/catalog.test.ts:80-82` order/dedupe; `web/src/catalog.test.ts:85-90` `MAX_RECENTS === 10`, length 10, `k9` evicted; wiring `web/src/App.tsx:29-36` | ✅ PASS |
| META-24 | left sidebar of recents, newest first, every section | `web/src/App.tsx:156` `<Recents>` outside the route switch; `web/src/App.tsx:94-98` order from `visibleRecents` | ✅ PASS |
| META-25 | stale entries omitted | `web/src/catalog.test.ts:96` - `visibleRecents(["gone","b","a"], {a,b})` → `["b","a"]` | ✅ PASS |
| META-26 | no storage → session-only, no failure | `web/src/catalog.test.ts:122-127` - throwing and `null` storage: `load()` `[]`, `save` `not.toThrow()`, then `["a"]` | ✅ PASS |
| META-27 | no route → Diagrams page | `web/src/hooks.test.ts:7` - `""`, `#`, `#/`, `#/d`, `#/d/` → `{kind:"diagrams"}` | ✅ PASS |

### P2: CLI filtering

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| META-28 | `--tag` repeatable, all must match, case-insensitive, on render/check/facts/layout | `tests/test_metadata.py:222` `--tag kubernetes` → `3 diagram(s)`; `tests/test_metadata.py:228` `KUBERNETES` + `gcp` → `1`; `tests/test_metadata.py:229-230` no match; `tests/test_metadata.py:254-256` render writes only GCP01 svg; `tests/test_metadata.py:257-259` facts/layout | ✅ PASS (note: facts only asserts exit 0; all commands share `_collect`, `src/spinagram/cli.py:143`) |
| META-29 | `--category` equals effective category, case-insensitive | `tests/test_metadata.py:234-235` - `aws` → 2, `google cloud` → 1 | ✅ PASS |
| META-30 | `--only` ∧ `--tag` ∧ `--category` | `tests/test_metadata.py:239` → 1; `tests/test_metadata.py:241` tag+category → 2 | ✅ PASS |
| META-31 | exit "no diagrams found" | `tests/test_metadata.py:247-248` - `pytest.raises(SystemExit, match="no diagrams found")` | ✅ PASS |

**Status**: ✅ All 31 ACs covered and matching spec outcomes; 0 spec-precision gaps.

---

## Discrimination Sensor

Scratch: temporary detached `git worktree` in the session scratchpad; Python run with `PYTHONPATH=<worktree>/src` (import path confirmed), TS with `bun test` via a node_modules symlink. Each mutant restored before the next; worktree removed with `git worktree remove --force`.

### Iteration 2 (changed lines, HEAD 4fccddd)

| Mutation | File:line | Description | Killed? |
| -------- | --------- | ----------- | ------- |
| R1 | `src/spinagram/yaml_io.py:56` | spec tags back to `data.get("tags") or []` | ✅ Killed (`test_yaml_invalid_metadata_names_id_and_key[tags: 0/false/{}]`) |
| R2 | `src/spinagram/yaml_io.py:138` | YAML folder merge back to `base.get("tags") and doc.get("tags")` | ✅ Killed (`test_invalid_folder_tags_fail_for_yaml_and_python[0/false/{}]`) |
| R3 | `src/spinagram/yaml_io.py:174` | Python folder tags back to `if base.get("tags")` | ✅ Killed (`test_invalid_folder_tags_fail_for_yaml_and_python[0/false/{}]`) |

### Iteration 1 (HEAD 0211f44; lines in that revision)

| Mutation | File:line | Description | Killed? |
| -------- | --------- | ----------- | ------- |
| M1 | `src/spinagram/metadata.py:55` | tie-break by insertion order instead of A-Z | ✅ Killed |
| M2 | `src/spinagram/metadata.py:36` | drop `aws-*` group style inference | ✅ Killed |
| M3 | `src/spinagram/metadata.py:38` | drop zone icon inference | ✅ Killed |
| M4 | `src/spinagram/metadata.py:62` | `matches` tag AND → OR | ✅ Killed |
| M5 | `src/spinagram/metadata.py:64` | category comparison case-sensitive | ✅ Killed |
| M6 | `src/spinagram/metadata.py:50` | declared category no longer wins | ✅ Killed |
| M7 | `src/spinagram/model.py:234` | no lower-casing | ✅ Killed |
| M8 | `src/spinagram/model.py:234` | keep empty tag | ✅ Killed |
| M9 | `src/spinagram/model.py:230` | single string not wrapped | ✅ Killed |
| M10 | `src/spinagram/yaml_io.py:138` | YAML folder tags not merged | ✅ Killed |
| M11 | `src/spinagram/yaml_io.py:170` | Python folder category overrides declared | ✅ Killed |
| M12 | `src/spinagram/yaml_io.py:174` | Python folder tags not merged | ✅ Killed |
| M13 | `src/spinagram/cli.py:23` | `_collect` ignores `--category` alone | ✅ Killed |
| M14 | `src/spinagram/cli.py:24` | `_collect` uses only first `--tag` | ✅ Killed |
| M15 | `src/spinagram/ui/workspace.py:331` | API reports declared, not effective, category | ✅ Killed |
| T1 | `web/src/catalog.ts:18` | chip filter AND → OR | ✅ Killed |
| T2 | `web/src/catalog.ts:13` | query `every` → `some` | ✅ Killed |
| T3 | `web/src/catalog.ts:12` | subtitle not searched | ✅ Killed |
| T4 | `web/src/catalog.ts:32` | Uncategorised sorted first | ✅ Killed |
| T5 | `web/src/catalog.ts:47` | recents cap `max + 1` | ✅ Killed |
| T6 | `web/src/catalog.ts:47` | recents no dedupe | ✅ Killed |
| T7 | `web/src/catalog.ts:52` | `visibleRecents` keeps stale | ✅ Killed |
| T8 | `web/src/catalog.ts:78` | `recentStore` drops memory fallback | ✅ Killed |
| T9 | `web/src/hooks.ts:18` | `parse` default → themes | ✅ Killed |

**Sensor depth**: expanded (27 manual behavior-level mutants across both iterations)
**Sensor kill ratio**: 27/27 killed (iteration 2: 3/3)

Isolation: real tree porcelain before and after the iteration-2 sensor showed only the uncommitted verifier files (`.specs/LESSONS.md`, `.specs/lessons.json`, this report).

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code | ✅ |
| Surgical changes | ✅ (T11 changes 3 lines of source plus tests) |
| No scope creep | ✅ |
| Matches patterns | ✅ |
| Spec-anchored outcome check (asserted values match spec) | ✅ |
| Per-layer Coverage Expectation met | ✅ |
| Every test maps to a spec requirement - no unclaimed tests | ✅ |
| Documented guidelines followed: `pyproject.toml` (pytest, ruff), `web/package.json` (tsc) | ✅ |

---

## Edge Cases

- [x] Empty tag after trimming dropped - `tests/test_metadata.py:13` (`""`); mutant M8 killed.
- [x] Same diagram opened twice → once - `web/src/catalog.test.ts:82`.
- [x] Workspace change on disk refreshes Diagrams page - `web/src/App.tsx:59-61` reloads `ws` on `workspace`; `web/src/DiagramsPage.tsx:12-16` derives from `ws` (code read).

---

## Gate Check

- **Gate command**: `uv run ruff check src tests && uv run pytest -q && cd web && bun test && bun run typecheck`
- **Result**: ruff clean; pytest 388 passed, 0 failed, 3 skipped; bun 17 pass, 0 fail; `tsc -b` exit 0
- **Test count before feature** (main): 349 passed, 3 skipped; 0 bun tests
- **Test count after feature**: 388 passed, 3 skipped; 17 bun tests
- **Delta**: +39 pytest (+6 in iteration 2), +17 bun
- **Skipped tests**: `tests/test_autolayout.py:155,165` (dot not installed), `tests/test_pptx_svg.py:129` (soffice not installed); these existed before the feature and depend on the environment
- **Failures**: none

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| META-01 .. META-31 | Implementing (META-03 Needs Fix after iteration 1) | ✅ Verified |

---

## Summary

**Overall**: ✅ Ready

**Spec-anchored check**: 31/31 ACs matched spec outcome; 0 spec-precision gaps
**Sensor**: 27/27 mutations killed (3/3 on the iteration-2 fix)
**Gate**: 388 pytest passed, 17 bun passed, ruff and tsc clean

**Non-blocking notes**: the facts filter test only checks the exit code, so `--tag`/`--category` on facts is shown only through the shared `_collect`. An explicit `tags: null` in a YAML spec overrides folder tags, which matches how the other folder-default keys behave.

**Lessons**: L-007 (ac_gap, iteration 1) kept as recorded; no new signal in iteration 2.

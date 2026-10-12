# Catalog Previews Validation - PASS (iteration 2)

**Date**: 2026-10-12
**Spec**: `.specs/features/catalog-previews/spec.md`
**Diff range**: `8f53bd2^..d6a9620` (spec commit 8f53bd2 through HEAD d6a9620, 12 commits; iteration-2 fixes 9a812d2, d6a9620)
**Iteration**: 2 of 3 (iteration 1 found 2 gaps, PREV-03 and PREV-07; both fixed and re-verified below)
**Verifier**: independent sub-agent (author ≠ verifier)

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 | ✅ Done | `src/spinagram/ui/themes.py:126-152` (`sample_diagram`, `theme_thumbnail`); grid layout fix 551fad1 |
| T2 | ✅ Done | `src/spinagram/ui/server.py:100-107`, route `server.py:161` |
| T3 | ✅ Done | `web/src/catalog.ts:89-134` tested |
| T4 | ✅ Done | `web/src/ThemesPage.tsx`, shared `web/src/CatalogShell.tsx` |
| T5 | ✅ Done | `web/src/PacksPage.tsx`; dark-only icon chip fix 76cd72e (`PacksPage.tsx:65`) |
| T6 | ✅ Done | `web/src/App.tsx:183-185`; static bundle rebuilt in diff |
| T7 | ✅ Done | `docs/content/docs/live-ui.mdx` (+4 lines) |
| T8 | ✅ Done | 9a812d2: `packSample` at `web/src/catalog.ts:110-111`, used at `web/src/PacksPage.tsx:45`; bundle rebuilt (`src/spinagram/ui/static/index.html` → `index-BVtRnxlD.js`) |
| T9 | ✅ Done | d6a9620: `tests/test_ui.py:161` asserts the message |

---

## Spec-Anchored Acceptance Criteria

| ID | Criterion | Spec-defined outcome | `file:line` + assertion | Verdict |
| -- | --------- | -------------------- | ----------------------- | ------- |
| PREV-01 | GET `/api/themes/<ref>/thumbnail.svg` | SVG of the sample diagram rendered with that theme | `tests/test_ui.py:155` - `r.status_code == 200 and content-type.startswith("image/svg+xml")`; `tests/test_ui.py:156` - `r.text.startswith("<svg") and ">corp<" in r.text and "#FF0000" in r.text` (theme name and colour reach the SVG); `tests/test_ui.py:157` built-in ref 200 | ✅ PASS |
| PREV-02 | unknown ref | 404 | `tests/test_ui.py:158` - `c.get("/api/themes/nope/thumbnail.svg").status_code == 404` | ✅ PASS |
| PREV-03 | theme fails to load | 422 **with the error message** | `tests/test_ui.py:161` - `r.status_code == 422 and "no-such-base" in r.json()["error"]` (actual message `theme 'no-such-base' not found (...)`); M17 now killed | ✅ PASS |
| PREV-04 | sample uses only defined node styles | styles = defined ∩ {default, dark, soft, warning, alert, neutral} | `tests/test_ui.py:141` - `styles == ["dark", "default"]` (stub defining default/dark/custom); `tests/test_ui.py:143` - default theme yields all six | ✅ PASS |
| PREV-05 | Themes page cards | card per theme: thumbnail, name, ref, "active" badge; sections Built-in then Custom | `web/src/previews.test.ts:63` - `themeSections(THEMES)` equals `[["Built-in",["default","night"]],["Custom",["active"]]]`; TSX: thumbnail `web/src/ThemesPage.tsx:45`, name `:54`, ref `:55`, active badge `:56-59`, sections `:23-29` | ✅ PASS (note: built-in cards show the label "built-in" instead of the ref, `ThemesPage.tsx:55`; built-in ref == name, `src/spinagram/ui/themes.py:24`, so the ref is still visible) |
| PREV-06 | theme search | name or ref contains every term, case-insensitive | `web/src/previews.test.ts:33` - `"NIGHT"` → `["night"]`; `:34` `"act"` matches ref; `:35` - `"night corp"` → `[]` (AND) | ✅ PASS |
| PREV-07 | pack sample icons | 12 icons at evenly spaced positions of the **sorted** icon list; all when ≤ 12 | `web/src/previews.test.ts:51` - 120 → `[0,10,…,110]`; `:52` 13 → first 12; `:55-57` ≤ 12 returns all. Sorting: `web/src/catalog.ts:110-111` `packSample` sorts a copy by name then samples; `web/src/previews.test.ts:65` - reversed 24 names → `packSample(shuffled)` equals the even-indexed sorted names; `:69-70` - `["b","a"]` → `["a","b"]` and caller's list unchanged; wired at `web/src/PacksPage.tsx:45` (API keeps index order, `src/spinagram/ui/catalog.py:76-79`); M16/M16b/M16c killed | ✅ PASS |
| PREV-08 | not downloaded | "Not downloaded" instead of icons | TSX `web/src/PacksPage.tsx:55-58` - `!p.fetched` renders `"Not downloaded"` (or "Downloading…" while fetching); icons fetched only when `p.fetched` (`:38-41`) | ✅ PASS (component, by reading) |
| PREV-09 | Icon packs page cards | card per pack: name, title, icon count; sections Downloaded then Not downloaded | `web/src/previews.test.ts:69` - `packSections(PACKS)` equals `[["Downloaded",["aws","k8s"]],["Not downloaded",["gcp"]]]`; `:75-76` empty sections omitted; TSX name `web/src/PacksPage.tsx:85`, title `:86`, count `:87` (`"— "` when not downloaded, count unknown) | ✅ PASS |
| PREV-10 | pack search | name or title contains every term, case-insensitive | `web/src/previews.test.ts:42` - `"google"` matches title only; `:43` - `"k8s kube"` (terms across name+title); `:44` - `"aws google"` → `[]` | ✅ PASS |
| PREV-11 | card click opens view | theme sheet / pack view | TSX `web/src/ThemesPage.tsx:37` - `href({kind:"theme", ref})`; `web/src/PacksPage.tsx:53` - `href({kind:"pack", name})`; routed by `web/src/hooks.ts:16-17,26-29` and `web/src/App.tsx:172-181` | ✅ PASS (component, by reading) |
| PREV-12 | no match | "No themes match" / "No packs match" + control clearing search | `web/src/CatalogShell.tsx:60` - `No {what} match`; `:61-63` "Clear search" button; used at `web/src/ThemesPage.tsx:22` (`what="themes"`, `onClear={() => setQuery("")}`) and `web/src/PacksPage.tsx:22` (`what="packs"`) | ✅ PASS (component, by reading) |

**Status**: ✅ All ACs covered - 12/12 matched spec outcome; no spec-precision gaps.

---

## Discrimination Sensor

Isolated worktree `git worktree add --detach <scratchpad>/wt HEAD` (HEAD d6a9620); `web/node_modules` symlinked;
Python run with `uv run --project <wt> --all-extras pytest tests/test_ui.py` (worktree `src` confirmed as the
imported package); TS with `bun test` in `<wt>/web`. Each mutant reverted with `git checkout -- <file>` inside
the worktree. Worktree removed and pruned; real-tree porcelain unchanged (only this report and `.specs/lessons*`).
All iteration-1 mutants were re-run against HEAD, plus three mutants on the new `packSample`.

| # | File:line | Mutation | Iteration 1 | Iteration 2 |
| - | --------- | -------- | ----------- | ----------- |
| M1 | `src/spinagram/ui/themes.py:132` | drop `if s in defined` (use all six styles) | ✅ Killed | ✅ Killed |
| M2 | `src/spinagram/ui/themes.py:137` | omit last defined style (`styles[:-1]`) | ✅ Killed | ✅ Killed |
| M3 | `src/spinagram/ui/server.py:104` | unknown ref 404 → 422 | ✅ Killed | ✅ Killed |
| M4 | `src/spinagram/ui/server.py:106` | broken theme 422 → 500 | ✅ Killed | ✅ Killed |
| M5 | `src/spinagram/ui/themes.py:152` | render with `default` theme instead of `ref` | ✅ Killed | ✅ Killed |
| M6 | `web/src/catalog.ts:92` | `terms.every` → `terms.some` (AND → OR) | ✅ Killed | ✅ Killed |
| M7 | `web/src/catalog.ts:91` | drop lowercasing of fields | ✅ Killed | ✅ Killed |
| M8 | `web/src/catalog.ts:96` | filterThemes ignores `ref` | ✅ Killed | ✅ Killed |
| M9 | `web/src/catalog.ts:100` | filterPacks ignores `title` | ✅ Killed | ✅ Killed |
| M10 | `web/src/catalog.ts:106` | first n instead of evenly spaced | ✅ Killed | ✅ Killed |
| M11 | `web/src/catalog.ts:105` | `<= n` → `< n` | ➖ Equivalent (length == n samples identity either way) | excluded |
| M12 | `web/src/catalog.ts` `sections` | keep empty sections | ✅ Killed | ✅ Killed |
| M13 | `web/src/catalog.ts` `themeSections` | Custom before Built-in | ✅ Killed | ✅ Killed |
| M14 | `web/src/catalog.ts` `packSections` | Downloaded = `fetched \|\| count > 0` | ➖ Equivalent (count > 0 iff fetched, `src/spinagram/ui/catalog.py:65`) | excluded |
| M14b | `web/src/catalog.ts` `packSections` | Downloaded = `!p.error` | ✅ Killed | ✅ Killed |
| M15 | `web/src/catalog.ts:106` | `Math.floor` → `Math.round` | ✅ Killed | ✅ Killed |
| M16 | `web/src/catalog.ts:111` (was `PacksPage.tsx:45`) | drop the sort before sampling | ❌ Survived | ✅ Killed |
| M16b | `web/src/catalog.ts:111` | sort the caller's array in place | - | ✅ Killed |
| M16c | `web/src/catalog.ts:111` | sort descending | - | ✅ Killed |
| M17 | `src/spinagram/ui/server.py:106` | 422 body `str(exc)` → constant `"error"` | ❌ Survived | ✅ Killed |

**Sensor depth**: expanded (18 non-equivalent behavior mutants)
**Sensor result**: 18/18 killed, 0 survived - PASS ✅

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code | ✅ |
| Surgical changes | ✅ (DiagramsPage refactored onto shared `CatalogShell`; justified by "laid out like the Diagrams page") |
| No scope creep | ✅ |
| Matches patterns | ✅ (`theme_thumbnail` handler mirrors `theme_preview`) |
| Spec-anchored outcome check | ✅ (PREV-03 message and PREV-07 sorting fixed in iteration 2) |
| Per-layer Coverage Expectation met | ✅ PREV-07 sort now in the unit-tested logic layer (`web/src/catalog.ts:110`) |
| Every test maps to a spec requirement | ✅ (test names/describe blocks cite PREV ids) |
| Documented guidelines followed | none beyond `pyproject.toml` / `web/package.json` - strong defaults applied |

---

## Edge Cases

- [x] No match → "No themes match" / "No packs match" + Clear search (`web/src/CatalogShell.tsx:57-65`); hidden when the list itself is empty (`ThemesPage.tsx:22`, `PacksPage.tsx:22`)
- [x] Theme defining fewer styles → sample uses only those (`tests/test_ui.py:141`); no defined style → falls back to one default box (`src/spinagram/ui/themes.py:137`)
- [x] Broken theme in list → card shows "theme failed to load" instead of requesting a thumbnail (`web/src/ThemesPage.tsx:39-41`)

---

## Gate Check

- **Gate command** (real tree): `uv run ruff check src tests && uv run pytest -q && cd web && bun test && bun run typecheck`
- ruff: All checks passed
- pytest: 390 passed (HEAD d6a9620), 3 skipped (dot runtime x2, soffice x1 - environment, unrelated to this feature), 0 failed
- bun test: 26 pass, 0 fail (3 files, 67 expects)
- typecheck (`tsc -b`): exit 0
- **Delta**: +2 Python tests (`tests/test_ui.py:134`, `:148`), +9 TS tests (`web/src/previews.test.ts`); no tests removed or weakened (iteration 2 strengthened `tests/test_ui.py:161`)
- `bun run build` not run on the real tree (it rewrites the tracked static bundle); the rebuilt bundle is committed in 9a812d2 (`index.html` references `index-BVtRnxlD.js`, which contains the sort)

---

## Fix Plans

Iteration 1 fixes, both applied and verified:

- Fix 1 (PREV-07 sort untested, M16) → T8 / 9a812d2: `packSample` in `web/src/catalog.ts:110-111`, tests `web/src/previews.test.ts:61-72`. Verified.
- Fix 2 (PREV-03 message unasserted, M17) → T9 / d6a9620: `tests/test_ui.py:161`. Verified.

No open fix tasks.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| PREV-01..PREV-12 | Implementing | ✅ Verified (PREV-03, PREV-07 after iteration-2 fixes) |

---

## Summary

**Overall**: ✅ Ready

**Spec-anchored check**: 12/12 ACs matched spec outcome, 0 spec-precision gaps
**Sensor**: 18/18 non-equivalent mutants killed (2 equivalent excluded)
**Gate**: ruff clean; 390 pytest passed (3 env skips); 26 bun tests passed; typecheck clean

**What works**: thumbnail endpoint and error mapping (with message), defined-styles-only sample, search (AND, case-insensitive, correct fields), sorted and evenly spaced pack samples, section order and omission, cards, empty state, routing.

**Notes (non-blocking)**: built-in theme cards show "built-in" in the ref slot (`web/src/ThemesPage.tsx:55`; ref == name for built-ins); `tasks.md` header still says `**Status**: In Progress` (orchestrator to set Done).

**Lessons**: L-008, L-009 recorded from iteration 1 (surviving mutants M16, M17); iteration 2 adds no signal.

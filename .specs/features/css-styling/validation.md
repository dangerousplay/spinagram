# CSS-like Styling Validation (iteration 3, final)

**Date**: 2026-10-12
**Spec**: `.specs/features/css-styling/spec.md`
**Diff range**: `c9e6b74..ab7411f` (feature commits c9e6b74, 3a3d07b, 5d5e09c, 71d5f4f, 70e01e6, 43f1fdf, dbdc584, dc4cb39, 202353c, fix 4413a8f, and fix **ab7411f**, which this iteration judges. The other commits in the range belong to layered-layout, behavior-diagrams and docs.)
**Verifier**: independent sub-agent (author ≠ verifier)
**MVP scope (tasks.md:37)**: unchanged from iteration 2. CSS-01..07, the MVP subsets of CSS-08/09/10, CSS-12..22, CSS-27, CSS-29 and CSS-30. Deferred: CSS-11, CSS-23..26, CSS-28.

---

## Iteration-2 gaps

| Gap | Fix in ab7411f | Evidence | Status |
| --- | -------------- | -------- | ------ |
| R1 (CSS-14): F9 survived, because no test covered a *defined* custom property with a function fallback | `tests/test_css.py:562-565` adds `:root { --x: #FFFFFF } #api { fill: var(--x, rgb(1, 2, 3)) }` → `fill == "#FFFFFF"` (`:564`), plus a nested `var(--a, var(--b))` → `#0000FF` (`:565`) | **F9 still survives** (re-run below). The mutant substitutes `'#FFFFFF)'`, and `_colour` (`src/spinagram/css.py:321-326`) accepts any string that starts with `#` and keeps `h[:6]`, so it parses `'#FFFFFF)'` as `#FFFFFF`. The new assertion therefore cannot tell the two results apart | ❌ **Open** |
| R2 (CSS-30): negative `font-size` absence not asserted | `tests/test_css.py:160` `assert "font-size" not in out[api][""]` | The fresh mutant F10 (`_length` threshold `< 0` → `< -1`, which accepts `font-size: -1px`) is killed by `test_unknown_property_and_negative_values_warn` | ✅ Closed |
| Note (c): golden comment wording | `tests/test_css.py:491` now says "rendered at 46d7696, before any CSS code existed" | Matches the iteration-2 hash check at 46d7696 | ✅ Closed |

### Root cause of the surviving F9 (new finding, CSS-16)

The test is not the only problem. `_colour` never validates hex digits or length (`src/spinagram/css.py:321-326`). Probes at ab7411f:

| Input | Result |
| ----- | ------ |
| `'#FFFFFF)'` | `('#FFFFFF', 1.0)` |
| `'#GGGGGG'` | `('#GGGGGG', 1.0)`: an invalid colour reaches the SVG |
| `'#12'` | `('#12', 1.0)` |
| `'#1234567890'` | `('#123456', 1.0)` |

CSS-16 requires an error naming file, line, selector and value when a colour cannot be resolved. Malformed hex values pass silently instead. CSS-16 is still marked PASS below because every value its tests use is handled correctly, but this is a real defect: it is the reason the R1 assertion cannot discriminate.

A discriminating assertion exists. With F9 applied, `:root { --x: white } #api { fill: var(--x, rgb(1, 2, 3)) }` raises `t.css:1: #api: cannot resolve colour 'white)'`, while the real code yields `#FFFFFF`. Validating hex in `_colour` would also make the current `:564` assertion kill F9.

---

## Spec-Anchored Acceptance Criteria

All references are to `tests/test_css.py` at ab7411f. The fix added one line at :160 and four at :562-565, so references to lines at or after :160 are shifted by +1 from iteration 2, and those at or after :562 by +5 in total.

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| CSS-01 matching rule applies | Declarations land only on the elements the rule matches | `:94` `out[api][""]["fill"] == "#444444"`; `:99` `out[edge][""].get("fill") is None` | ✅ PASS |
| CSS-02 selector forms | type, class, id, attr forms, `*`, descendant, `>`, lists, `:first-child`, `:last-child`, `:not()` | `:41` parametrized `_m(sel, el) is expected`; real tree `:198-213` | ✅ PASS |
| CSS-03 cascade | (importance, specificity, order) | `:94-98`; specificity `:47-49`. M1 killed (iter 1) | ✅ PASS |
| CSS-04 `!important` | Beats non-important declarations, inline included | `:96` `stroke-width == 7.0`. M2 killed | ✅ PASS |
| CSS-05 inline `css=` | Above every non-important sheet declaration | `:97`; Python `:179`. M3 killed | ✅ PASS |
| CSS-06 `edge[from=]`/`edge[to=]` | Matches by endpoint id | `:34`; real diagram `:591` (edge:0 `#00FF00`, edge:1 no stroke). M19 killed | ✅ PASS |
| CSS-07 inheritance | color and font-* inherit, other properties do not | `:106-110`, `:118`. M4 killed | ✅ PASS |
| CSS-08 (MVP subset) | fill, stroke, width, dasharray, radius, opacity, box-shadow reach the scene | `:297-311`; values `:145-146` | ✅ PASS |
| CSS-09 (MVP subset) | color, size, weight, italic on pseudo-elements and group labels | `:300-301`, `:308`, `:321`; group label `:607` | ✅ PASS |
| CSS-10 (MVP subset) | stroke, width, dasharray, opacity, markers | `:304-306`, `:328`; opacity `:547` | ✅ PASS |
| CSS-12 same look per backend | Same values in SVG, PPTX and Figma | SVG `:367-380`; PPTX `:408-421`, `:524-531`; Figma `:448-453`, `:539`, `:620-624`; opacity `:548-553`. M12, M18, F4-F6 killed | ✅ PASS |
| CSS-13 nearest equivalent + one warning | One warning per backend+property+value | `:582` `sorted(prefixes) == ["figma", "pptx"]`; content `:427-431`. M17, F7 killed | ✅ PASS |
| CSS-14 `var()` | Custom property from `:root` or an ancestor, else fallback, else theme token | `:127-130`; function fallback `:561`; defined beats fallback `:564`; nested `:565`. F11, F12 killed | ⚠️ **FAIL (sensor)**: F9 survives, see R1 |
| CSS-15 bare token | Resolved through theme colours | `:129` | ✅ PASS |
| CSS-16 unresolved colour → error (file, line, selector, value) | Raise naming all four | `:135` full regex; box-shadow `:558` | ✅ PASS for tested values; ⚠️ latent defect: malformed hex accepted (see above) |
| CSS-17 `class_=` | Node, edge, group | `:173-182` | ✅ PASS |
| CSS-18 `d.stylesheet()` / `Diagram(css=)` | Cascade position after the theme | `:170-180`, `:263` | ✅ PASS |
| CSS-19 YAML `stylesheets:`/`css:`, folder defaults | Folder sheets, then the spec's sheets; Python too | `:236`, `:245`, `:515`, `:517`. F1, F2 killed | ✅ PASS |
| CSS-20 `style="dark"` + `.dark` | Same render; class matches | `:189`, `:195`; golden `:501` | ✅ PASS |
| CSS-21 syntax error | file, line, column, token; skip; continue | `:66-69` | ✅ PASS |
| CSS-22 unknown property | Warning with file, line, nearest | `:156` exact message; `:347` via check | ✅ PASS |
| CSS-27 byte-identical SVG without CSS | Unchanged output | `:501` golden (hash verified in iter 2 at 46d7696, 7ee7f55, 4413a8f; comment `:491` corrected). M15 killed | ✅ PASS |
| CSS-29 unknown font-family | Theme font + one warning | `:337-339`; `:599`. M16 killed | ✅ PASS |
| CSS-30 negative width/size | Ignore + warn | `:157-160` (warnings for both; `stroke-width` and `font-size` absent). F10 killed | ✅ PASS |

**Status**: 23/24 in-scope ACs pass. CSS-14 fails the sensor (F9).

---

## Discrimination Sensor (iteration 3)

Scratch: `git worktree add --detach <scratchpad>/wt3 ab7411f`. Each mutant ran `uv run --all-extras pytest -q tests/test_css.py`, the file was restored with `git checkout src` after each run, and the worktree was removed at the end. Baseline: 66 passed.

| # | File | Mutation | Killed? (test) |
| - | ---- | -------- | -------------- |
| F9 | `css.py:394` (`_substitute`, applied to this scanner only) | `depth += {"(": 1, ")": -1}` → `{")": -1}` (stops at the first `)`) | ❌ **SURVIVED** (66 passed). Probe: `_substitute('var(--x, rgb(1, 2, 3))', {'--x': '#FFFFFF'})` gives `'#FFFFFF)'`, which lenient hex parsing turns back into `#FFFFFF` |
| F10 (new) | `css.py:360` (`_length`) | `if x < 0` → `if x < -1` (accepts `font-size: -1px`) | ✅ `test_unknown_property_and_negative_values_warn` |
| F11 (new) | `css.py:399` (`_substitute`) | A fallback is preferred over a defined custom property | ✅ `test_var_fallback_may_contain_a_function` |
| F12 (new) | `css.py:388` (`_substitute`) | `range(8)` → `range(1)` (nested `var()` not resolved) | ✅ `test_var_fallback_may_contain_a_function` |

Side observation: a first, over-broad F9 sed also changed the identical depth scanners in `:not(` parsing (`css.py:159`) and `_split_ws` (`css.py:300`). All 66 tests still passed. Nested parentheses inside `:not()` and inside space-split values such as `box-shadow: 1px 1px 2px rgb(0, 0, 0)` are therefore not discriminated either. This is not a separate gap, but worth covering when R1 is fixed.

**Result**: 3/4 killed. F9 is a non-equivalent survivor.

**Isolation**: the only real-tree file this Verifier changed is this report. Compared with the pre-run snapshot, the real tree now also shows ` M .specs/project/STATE.md`, `?? .specs/LESSONS.md` and `?? .specs/lessons.json`. The Verifier did not write these; another process changed them during the run. No git stash was used.

---

## Gate Check (at ab7411f, scratch worktree)

- `uv run --all-extras pytest -q tests/test_css.py`: **66 passed**
- `uv run --all-extras pytest -q`: **301 passed, 3 skipped**, 0 failed
- `ruff check src tests examples`: All checks passed

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / surgical | ✅ ab7411f is test-only (+6/-1) |
| No scope creep | ✅ |
| Spec-anchored outcomes | ⚠️ The R1 assertion checks the right outcome but cannot discriminate because `_colour` is lenient |
| Every test maps to an AC | ✅ |

---

## Remaining Gaps (fix tasks)

1. **R1, Minor (CSS-14), still open**: make F9 killable. Either (a) use a non-hex defined value, e.g. `:root { --x: white } #api { fill: var(--x, rgb(1, 2, 3)) }` → `fill == "#FFFFFF"` (verified to kill F9), or (b) better, fix R3, which makes the existing `:564` assertion kill F9.
2. **R3, Minor (CSS-16), new**: `_colour` (`src/spinagram/css.py:321-326`) accepts malformed hex (`#GGGGGG`, `#12`, `#FFFFFF)`, `#1234567890`). Validate with `re.fullmatch(r"#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})", v)` and otherwise raise, so the CSS-16 error path reports it. Add a test asserting `fill: #GGGGGG` raises `cannot resolve colour`.
3. Optional: add nested-paren cases for `:not(...)` and a `box-shadow` with `rgb(...)` to cover the scanners at `css.py:159` and `css.py:300`.

## Requirement Traceability Update

| Requirement | New Status |
| ----------- | ---------- |
| CSS-01..13, 15, 17..22, 27, 29, 30 | ✅ Verified |
| CSS-14 | ⚠️ Behaviour correct; test does not discriminate (R1) |
| CSS-16 | ⚠️ Verified for tested values; malformed hex accepted (R3) |

## Summary

**Overall**: ❌ FAIL (strict: one surviving non-equivalent mutant). R2 and the golden comment are closed. R1 is not: the new assertion is correct in intent, but lenient hex parsing in `_colour` hides the F9 defect. That leniency is a real CSS-16 defect (R3).
**Spec-anchored check**: 23/24 fully matched; CSS-14 fails the sensor.
**Sensor**: 3/4 killed this iteration (F10, F11, F12 killed; F9 survived).
**Gate**: 301 passed, 3 skipped, 0 failed; ruff clean.

**Verdict: PASS** (iteration 3 of 3, final: both iteration-2 gaps, EDG-18 and OUT-03, are closed; 102/102 ACs matched the spec; 13/13 mutants killed; gate green)

# Validation: layout-engine - PASS (re-verification iteration 3)

**Date**: 2026-10-21
**Spec**: `.specs/features/layout-engine/spec.md` (102 requirement IDs; the Assumptions table includes the 2026-10-21 EDG-09 / OUT-04 clarifications)
**Diff range**: `main..HEAD` (65 commits, `1389c0b` spec … `c1d5b73` lessons) on `feat/layout-engine-improvements`. Since iteration 2 (`HEAD~2..HEAD`, commits `8309dc8` and `c1d5b73`), only `tests/test_engine_route.py` (+10), `tests/test_engine_output.py` (+1) and the lessons files changed. `git diff 75c39b3..HEAD -- src` is empty, so the source verified in iterations 1 and 2 is unchanged.
**Verifier**: independent sub-agent (author ≠ verifier). It ran read-only over the real tree and did its mutations in a throwaway `git worktree`.

---

## Iteration-2 gaps: re-check

| # | Gap (iteration 2) | New evidence `file:line` - assertion | Spec outcome matched? | Sensor |
| - | ----------------- | ------------------------------------ | --------------------- | ------ |
| 1 | EDG-18: the engine's crossing penalty (default 120) was never exercised | `tests/test_engine_route.py:231-238` `test_engine_ortho_pays_the_crossing_penalty`. It builds boxes `a` (200,300,200×60) and `b` (700,500,200×60), a prior edge (450,480)→(750,480), then `d.edge("a","b", route="ortho")` through `build_scene` (the real engine path, no test-supplied penalty). `:238` - `crossings(cs) == 0 and _axis_aligned(cs[1].points)` | ✅ "The router adds a crossing penalty per crossing with edges already routed". With the 120 default the ortho route detours to 0 crossings; with penalty 0 it crosses once (shown in iteration 2) | N1 (`route.py:58` `penalty *`→`0 *`) **killed** by this test |
| 2 | OUT-03: strict `>` boundary untested | `tests/test_engine_output.py:54` adds `("0.4.0", ">0.4", False)`, `("0.4.1", ">0.4", True)`, `("0.4.0", "<0.4", False)`. `:60` - `satisfies(version, spec) is ok`. The warning path is still pinned at `:86-87` / `:89` | ✅ "Warn when the installed version does not satisfy `requires`": `>` and `<` are now strict at the boundary | N11 (`version.py:43` `v > t`→`v >= t`) **killed** (`test_version_specifiers[0.4.0->0.4]`) |

---

## Documented deviations (verified, not counted as failures)

| Deviation | Where it is documented |
| --------- | ---------------------- |
| CHK-03: `check --json` embeds issues under an `issues` key of each style report | `src/spinagram/cli.py:232` (`# SPEC_DEVIATION`) |
| L1: `d.legend(...)` is `add_legend(items="auto", place=...)` | `src/spinagram/model.py:650` (`SPEC_DEVIATION`) |
| T2: Noto Sans Math bundled alongside Noto Sans Symbols 2 | commit body `SPEC_DEVIATION` (T2) |
| STY-01: `color: none` on text warns and keeps the colour | `src/spinagram/layout.py:78` (`# SPEC_DEVIATION`) |
| `low-contrast` thresholds 2.0 / 1.5, raisable by the theme | Spec Assumptions (confirmed `y`) |
| Placement checks only on hand-placed diagrams | `src/spinagram/qa.py:375` |
| Glyph coverage known only for fonts with a file | `src/spinagram/text.py:37-39` |

---

## Spec-Anchored Acceptance Criteria (all 102 IDs)

Legend: ✅ the assertion targets the spec-defined outcome. Test paths are relative to `tests/`. The src is unchanged since `75c39b3`, and the only test changes since iteration 2 are appended tests (`test_engine_route.py` after `:228`) and one row inserted at `test_engine_output.py:54`. So every iteration-2 citation still holds. Citations in `test_engine_output.py` after `:53` moved by +1 and are re-anchored below.

### P1 Text fits (T1)

| ID | Spec-defined outcome | Evidence | Result |
| -- | -------------------- | -------- | ------ |
| TXT-01 | Wrap at spaces first | `test_engine_textfit.py:79` - `set(lines) <= set(_space_wrap(text, width))`; `:74` | ✅ |
| TXT-02 | Break after `-./:·`, no hyphen | `test_engine_textfit.py:38` - `"".join(lines) == token`; `:40` - `ln[-1] in BREAK_ON` | ✅ |
| TXT-03 | Never break inside IPv4/CIDR | `test_engine_textfit.py:42`; `:57` - `lines == ["10.0.0.0/22·", "10.0.8.0/21"]` | ✅ |
| TXT-04 | Shrink in 1 px steps to 0.85 × base | `test_engine_textfit.py:136-137`, `:140`, `:148` - `== [21, 16]` | ✅ |
| TXT-05 | Grow box height | `test_engine_textfit.py:144` - `res.height > h`; `:255` - `s.h > 80` | ✅ |
| TXT-06 | `fit="none"` = 0.3 wrap | `test_engine_textfit.py:130-131` | ✅ |
| TXT-07 | `overflow-x/y` detail names the last strategy | `test_engine_textfit.py:275` - `detail.endswith(" after shrink to 21px")`; `:283` | ✅ |
| TXT-08 | `fit` / `min_scale` / `break_on` per node and as theme/YAML `defaults.node` | `test_engine_textfit.py:239`, `:241`, `:248`, `:364`, `:375`, `:385` | ✅ |
| TXT-09 | Zone label width includes letter spacing | `test_engine_textfit.py:301` | ✅ |

### P1 Zone header (Z1) and outlines (Z2)

| ID | Spec-defined outcome | Evidence | Result |
| -- | -------------------- | -------- | ------ |
| ZON-01 | Icon ≥ 14 px inside top/left | `test_engine_zones.py:225`; `:247` | ✅ |
| ZON-02 | Same 28 px icon height | `test_engine_zones.py:226` | ✅ |
| ZON-03 | Label centre ±1 px of the icon centre | `test_engine_zones.py:227` | ✅ |
| ZON-04 | Chips left to right before the label | `test_engine_zones.py:288`, `:290` | ✅ |
| ZON-05 | 5 px strip | `test_engine_zones.py:293` | ✅ |
| ZON-06 | `content_top` = header bottom + 12 | `test_engine_zones.py:308-309` (F3 gap 12→8: killed, `test_content_top[icon]` 250 ≠ 254) | ✅ |
| ZON-07 | `inset: false` keeps flush | `test_engine_zones.py:253-254`, `:259` | ✅ |
| ZON-08 | `upper: false` keeps case | `test_engine_zones.py:265` | ✅ |
| ZON-09 | dash solid/dashed/dotted/list | `test_engine_zones.py:86-89` | ✅ |
| ZON-10 | stroke / stroke_width / fill incl. none | `test_engine_zones.py:113-115`; `:30` | ✅ |
| ZON-11 | id + class; selectors apply | `test_engine_zones.py:38`; `:165-166` (F10 zone selector key: killed) | ✅ |
| ZON-12 | SVG dasharray == PPTX `a:custDash` | `test_engine_zones.py:141`, `:143`, `:144` | ✅ |
| ZON-13 | CSS `fill: none` no fill, no raise | `test_engine_zones.py:180` | ✅ |

### P1 Edge labels (E1) and zone targets (E2)

| ID | Spec-defined outcome | Evidence | Result |
| -- | -------------------- | -------- | ------ |
| EDG-01 | Candidate order | `test_engine_labels.py:30-31` | ✅ |
| EDG-02 | Reject node/header/label/arrowhead/margin | `test_engine_labels.py:131-136`, `:148`, `:157-158`, `:211` | ✅ |
| EDG-03 | First free wins | `test_engine_labels.py:98-99` | ✅ |
| EDG-04 | Least overlap + `label-collision` with count | `test_engine_labels.py:102`; `:113` - least cost | ✅ |
| EDG-05 | `label_at` unchanged | `test_engine_labels.py:166` | ✅ |
| EDG-06 | Identical across `PYTHONHASHSEED` | `test_engine_labels.py:242` | ✅ |
| EDG-07 | Zone / `zone:<id>[.<side>[@frac]]` | `test_engine_endpoints.py:70-71`, `:80-81`, `:89`, `:105` | ✅ |
| EDG-08 | Facing side, clamp 24 | `test_engine_endpoints.py:70-71` | ✅ |
| EDG-09 | Bus 10 px inside, spans all direct children's centres (or the side minus 24 px), arrowhead at the border | `test_engine_endpoints.py:191`/`:196`, `:200`, `:201-202` | ✅ |
| EDG-10 | Zone-border edges excluded | `test_engine_endpoints.py:134` | ✅ |
| EDG-11 | PPTX connector bound to the zone | `test_engine_endpoints.py:152`, `:154` | ✅ |
| EDG-12 | Unknown zone → `KeyError` | `test_engine_endpoints.py:93-94` | ✅ |

### P1 Diagnostics and `check --fix` (C1)

| ID | Spec-defined outcome | Evidence | Result |
| -- | -------------------- | -------- | ------ |
| CHK-01 | 9 new kinds | `test_engine_check.py:99`, `:121`, `:149`; `test_engine_glyphs.py:171`; `test_engine_sizing.py:230`, `:249`; `test_engine_route.py:163` | ✅ |
| CHK-02 | Fix dicts with the 4 ops | `test_engine_check.py:199`, `:209`, `:218`, `:227`, `:250`, `:262` (F4 nudge sign flipped: killed, `test_apply_fix_per_op[nudge]`) | ✅ |
| CHK-03 | `--json` with fix dicts | `test_engine_check.py:49-50` (documented deviation) | ✅ |
| CHK-04 | `<stem>.fixed.yaml`, source unchanged | `test_engine_check.py:336`, `:338`, `:344` | ✅ |
| CHK-05 | Python: one suggestion per fix, no files | `test_engine_check.py:363-368` | ✅ |
| CHK-06 | `render --relayout` fixes in memory | `test_engine_check.py:384-385` | ✅ |
| CHK-07 | Re-check clean | `test_engine_check.py:293`, `:314`, `:412` (F11 move-label x/y swapped: killed, `test_d2_first_iteration_converges_with_check_fix`) | ✅ |
| CHK-08 | Safe-area guard | `test_engine_check.py:302` | ✅ |

### P2 Icons (I1, I2) and glyphs (T2)

| ID | Spec-defined outcome | Evidence | Result |
| -- | -------------------- | -------- | ------ |
| ICN-01 | Intrinsic aspect | `test_engine_icons.py:30`, `:38` | ✅ |
| ICN-02 | Fit by height, max 4 × h, centred | `test_engine_icons.py:53`; `:75-76` | ✅ |
| ICN-03 | 1:4 wordmark ≥ 24 px | `test_engine_icons.py:62-63` | ✅ |
| ICN-04 | `variant` alias | `test_engine_icons.py:129` (F5 alias lookup bypassed: killed) | ✅ |
| ICN-05 | Icon-only centred | `test_engine_icons.py:88-89` | ✅ |
| ICN-06 | `badges=` Python + YAML | `test_engine_icons.py:161`, `:179` | ✅ |
| ICN-07 | 40 %, min 14, halo +3 | `test_engine_icons.py:162-164` | ✅ |
| ICN-08 | Top-right, leftward, inset 6 | `test_engine_icons.py:164-165` | ✅ |
| ICN-09 | No text intersects a badge | `test_engine_icons.py:168-170` | ✅ |
| ICN-10 | > 3 → `ValueError` | `test_engine_icons.py:185` | ✅ |
| TXT-10 | Per-char cmap | `test_engine_glyphs.py:70-71` | ✅ |
| TXT-11 | Body then bundled | `test_engine_glyphs.py:75-76` | ✅ |
| TXT-12 | SVG tspan + embed | `test_engine_glyphs.py:129-131` | ✅ |
| TXT-13 | PPTX `a:latin`/`a:sym` | `test_engine_glyphs.py:158-159` | ✅ |
| TXT-14 | `glyph-missing` once per char/role | `test_engine_glyphs.py:171-175` | ✅ |
| TXT-15 | Fallback metrics | `test_engine_glyphs.py:112` | ✅ |

### P2 Boxes, rows, zones fit (B1, I4, Z3)

| ID | Spec-defined outcome | Evidence | Result |
| -- | -------------------- | -------- | ------ |
| BOX-01 | Content-sized | `test_engine_sizing.py:34-36` | ✅ |
| BOX-02 | Row/column context managers | `test_engine_sizing.py:72-73`, `:77-78`, `:110` | ✅ |
| BOX-03 | Largest member's size, capped | `test_engine_sizing.py:70`, `:75`, `:260-261` | ✅ |
| BOX-04 | `ValueError` naming the widest | `test_engine_sizing.py:89` | ✅ |
| BOX-05 | Legacy forms | `test_engine_sizing.py:97-100` | ✅ |
| BOX-06 | `same_icon_size` / `icon-size-mismatch` | `test_engine_sizing.py:132-135` | ✅ |
| ZON-14 | `fit="children"` | `test_engine_sizing.py:177-178` | ✅ |
| ZON-15 | Innermost first | `test_engine_sizing.py:192-194` (F1 outermost-first order: killed) | ✅ |
| ZON-16 | `equalize="siblings"` | `test_engine_sizing.py:208` (F2 `max`→`min`: killed) | ✅ |
| ZON-17 | clips / underused 0.35 | `test_engine_sizing.py:230`, `:249-251` | ✅ |
| ZON-18 | `with d.zone()` | `test_engine_sizing.py:151-152`, `:160` | ✅ |

### P2 Trunks, ortho routing, legend (E3, E4, L1)

| ID | Spec-defined outcome | Evidence | Result |
| -- | -------------------- | -------- | ------ |
| EDG-13 | `bundle` / `fan_in` | `test_engine_route.py:196`, `:198`, `:228` (F9 `fan_in` grouping disabled: killed) | ✅ |
| EDG-14 | One trunk, midway | `test_engine_route.py:202-204` | ✅ |
| EDG-15 | One arrowhead | `test_engine_route.py:205`, `:207-209` | ✅ |
| EDG-16 | Different targets → `ValueError` | `test_engine_route.py:216` | ✅ |
| EDG-17 | `route="ortho"` avoids nodes | `test_engine_route.py:78-79` | ✅ |
| EDG-18 | The router adds a crossing penalty (default 120) per crossing with edges already routed | `test_engine_route.py:28` (router unit with an explicit penalty); `:122` - `(straight, ortho) == (1, 0)`; **`:238`** - `crossings(cs) == 0 and _axis_aligned(cs[1].points)` through `build_scene` with the engine default | ✅ (closed; N1 killed) |
| EDG-19 | Declaration order, identical | `test_engine_route.py:143` | ✅ |
| EDG-20 | `edge-crossings: n` | `test_engine_route.py:163` | ✅ |
| EDG-21 | `via`/`curve` kept | `test_engine_route.py:94` | ✅ |
| LEG-01 | `meaning=` | `test_engine_legend.py:42`, `:59` | ✅ |
| LEG-02 | One row per distinct style | `test_engine_legend.py:42` | ✅ |
| LEG-03 | Row removal | `test_engine_legend.py:49` | ✅ |
| LEG-04 | Edge line dash/colour; zone mini rect fill + outline | `test_engine_legend.py:83-87`, `:88` | ✅ |
| LEG-05 | Band / fitted card | `test_engine_legend.py:94`, `:103-107`, `:118` | ✅ |

### P3 Grid, icons, labels, CSS, parity, output

| ID | Spec-defined outcome | Evidence | Result |
| -- | -------------------- | -------- | ------ |
| GRD-01 | `d.grid` cells | `test_engine_grid.py:23`, `:33-34`, `:42-43` | ✅ |
| GRD-02 | align helpers | `test_engine_grid.py:82`, `:92` | ✅ |
| GRD-03 | Straight edges on shared span | `test_engine_grid.py:117` (F7 span midpoint moved to a quarter: killed, `test_straight_edge_is_axis_aligned[down]`) | ✅ |
| GRD-04 | `not-straight` | `test_engine_grid.py:127` | ✅ |
| GRD-05 | `at_left(0.35)` anchors | `test_engine_grid.py:140`, `:143`, `:148` | ✅ |
| ICN-11 | Fallback chain | `test_engine_icons.py:223` | ✅ |
| ICN-12 | Source recorded | `test_engine_icons.py:224`, `:231`, `:239` | ✅ |
| ICN-13 | `icons report` | `test_engine_icons.py:258-261` | ✅ |
| TXT-16 | label `size=` | `test_engine_textfit.py:317` | ✅ |
| TXT-17 | Roles | `test_engine_textfit.py:332-333` (F6 role `upper` ignored: killed, `test_label_roles[zone-label]`) | ✅ |
| TXT-18 | `max_width` | `test_engine_textfit.py:345-346` | ✅ |
| STY-01 | CSS `none` | `test_engine_zones.py:180`, `:189-190` | ✅ |
| STY-02 | Element types | `test_engine_style.py:41-43`; `test_engine_zones.py:165` | ✅ |
| STY-03 | Icon-only defaults | `test_engine_style.py:48`, `:54` | ✅ |
| STY-04 | Golden per backend | `test_engine_parity.py:96`, `:103`, `:120`, `:139` | ✅ |
| OUT-01 | `output=` names | `test_engine_output.py:29`, `:38` | ✅ |
| OUT-02 | `--name-from` | `test_engine_output.py:29` | ✅ |
| OUT-03 | Warn `version-mismatch` when the installed version does not satisfy `requires` | `test_engine_output.py:60` - `satisfies(version, spec) is ok` over `:50-55` (`>=`, `<`, `==.*`, `~=`, `!=`, `<=`, **`>`, strict `<`**); `:86-87` warning text + issue detail; `:89` no warning when satisfied | ✅ (closed; N11 killed) |
| OUT-04 | `<metadata>` sha256 of the SVG without that element, stable | `test_engine_output.py:116`, `:122` | ✅ |

**Status**: ✅ 102/102 ACs matched the spec outcome. 0 gaps. 0 open spec-precision gaps.

Contrast thresholds (Assumptions row `low-contrast`): `test_engine_check.py:158` `test_theme_raises_contrast_to_wcag` pins the theme override (F8, theme limits ignored: killed).

---

## Edge Cases

- [x] Box narrower than its padding stops at min_scale: `test_engine_textfit.py:171`
- [x] Empty text no-op: `test_engine_textfit.py:165`
- [x] Unresolved zone icon → label alone: `test_engine_zones.py:270`
- [x] Edge into a zone containing its source → inner face: `test_engine_endpoints.py:55`, `:70-71`
- [x] Exhausted E1 candidates on a canvas edge are deterministic: `test_engine_labels.py:242`, `:157-158`
- [x] `check --fix` with nothing fixable writes no file: `test_engine_check.py:338`

---

## Discrimination Sensor

Isolated scratch: `git worktree add --detach …/scratchpad/verify3 HEAD`. Tests ran with the real venv interpreter, `PYTHONPATH=<scratch>/src` (confirmed: `spinagram.__file__` resolves into the scratch), `PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider`. Every `__pycache__` was deleted before and after each mutant. Each mutation was an exact single-occurrence replacement (asserted) and was restored with `git checkout` in the scratch. Scratch baseline: 668/668 engine tests pass. The scratch's `git status --porcelain` was empty before it was removed. The worktree was removed and pruned afterwards. The real tree's `git status --porcelain` matches the pre-sensor baseline (`?? .specs/features/layout-engine/validation.md`, `?? improvements-layout-engine.md`).

| # | File:line | Mutation | Tests run | Killed? |
| - | --------- | -------- | --------- | ------- |
| N1 (re-run) | `src/spinagram/engine/route.py:58` | EDG-18: ortho cost `penalty * sum(...)` → `0 * sum(...)` | test_engine_route.py | ✅ Killed (`test_engine_ortho_pays_the_crossing_penalty`) |
| N11 (re-run) | `src/spinagram/engine/version.py:43` | OUT-03: `">": v > t` → `v >= t` | test_engine_output.py | ✅ Killed (`test_version_specifiers[0.4.0->0.4]`) |
| F1 | `src/spinagram/engine/zones.py:112` | ZON-15: fit order `-_depth` → `_depth` (outermost first) | test_engine_sizing.py | ✅ Killed (`test_nested_fit_resolves_innermost_first[2-levels]`) |
| F2 | `src/spinagram/engine/zones.py:130` | ZON-16: equalize `max(z.h)` → `min(z.h)` | test_engine_sizing.py | ✅ Killed (`test_equalize_siblings[equalize]`) |
| F3 | `src/spinagram/engine/zones.py:42` | ZON-06: header `gap` 12 → 8 (content_top) | test_engine_zones.py | ✅ Killed (`test_content_top[icon]`) |
| F4 | `src/spinagram/engine/fix.py:47` | CHK-02: nudge applies `-dx/-dy` (sign flip) | test_engine_check.py | ✅ Killed (`test_apply_fix_per_op[nudge]`) |
| F5 | `src/spinagram/engine/icons.py:64` | ICN-04: variant alias lookup bypassed (`return name`) | test_engine_icons.py | ✅ Killed (`test_icon_variant_resolves_theme_alias[box-wordmark-alias]`) |
| F6 | `src/spinagram/layout.py:155` | TXT-17: label role `upper` ignored | test_engine_textfit.py | ✅ Killed (`test_label_roles[zone-label]`) |
| F7 | `src/spinagram/engine/endpoints.py:115` | GRD-03: shared-span midpoint → quarter point | test_engine_grid.py | ✅ Killed (`test_straight_edge_is_axis_aligned[down]`) |
| F8 | `src/spinagram/qa.py:209` | Contrast limits ignore the theme's `defaults.check.contrast` | test_engine_check.py | ✅ Killed (`test_theme_raises_contrast_to_wcag`) |
| F9 | `src/spinagram/layout.py:409` | EDG-13: `fan_in` grouping disabled | test_engine_route.py | ✅ Killed (`test_bundle_shares_one_trunk_and_one_arrowhead[fan_in-auto-right-2sources]`) |
| F10 | `src/spinagram/css.py:582` | ZON-11: zone selector key `zone:<id>` → `zone-<id>` | test_engine_zones.py, test_engine_style.py | ✅ Killed (`test_css_reaches_zones_without_gid[type-id]`) |
| F11 | `src/spinagram/engine/fix.py:38` | CHK-07: `move-label` target x/y swapped | test_engine_check.py, test_engine_labels.py | ✅ Killed (`test_d2_first_iteration_converges_with_check_fix`) |

**Sensor depth**: P0-full (13 behaviour-level mutations: the 2 iteration-2 survivors plus 11 new ones in areas not mutated in iterations 1–2)
**Sensor outcome**: 13/13 killed, so the sensor passes.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / surgical changes | ✅ `8309dc8` is tests only (+10 route, +1 output row); no src changes |
| No scope creep | ✅ |
| Matches patterns | ✅ The new version rows join the existing `parametrize` table; the route test reuses `_conns`, `crossings`, `_axis_aligned` |
| Spec-anchored outcome check | ✅ 102/102 |
| Per-layer coverage expectation | ✅ |
| Every test maps to a spec requirement | ✅ The new tests carry their IDs in comments (EDG-18, OUT-03) |
| Documented guidelines | `pyproject.toml` (pytest, ruff); otherwise strong defaults |

---

## Gate Check

- **Gate command**: `uv run ruff check src tests && uv run pytest -q`
- **Gate outcome**: ruff exit 0 ("All checks passed!"). pytest exit 0: **1184 passed, 3 skipped**, 0 failed
- **Test count before feature**: 516 passed, 3 skipped
- **Test count at iteration 2**: 1180 passed. **Now**: 1184 passed (+4: 1 engine route test and 3 version rows). No tests were removed and no assertion was weakened (the diff only adds lines)
- **Skipped (pre-existing, environment)**: `test_autolayout.py:155`, `:165` (dot not installed), `test_pptx_svg.py:129` (soffice not installed)

---

## Fix Plans

None.

---

## Requirement Traceability Update

| Requirement | New Status |
| ----------- | ---------- |
| All 102 IDs (TXT-01..18, ZON-01..18, EDG-01..21, CHK-01..08, ICN-01..13, BOX-01..06, LEG-01..05, GRD-01..05, STY-01..04, OUT-01..04) | ✅ Verified |

---

## Summary

**Overall**: ✅ Ready (iteration 3 of 3)

**Spec-anchored check**: 102/102 ACs matched the spec outcome; 0 gaps; 0 spec-precision gaps
**Sensor**: 13/13 killed (N1 and N11 now killed; 11 fresh mutants killed)
**Gate**: 1184 passed, 0 failed, 3 skipped (pre-existing); ruff clean

**What works**: The engine-level EDG-18 test pins the default crossing penalty through `build_scene`, and the strict `>` / `<` rows pin OUT-03's boundaries. Fresh mutants in zone fit order, sibling equalize, `content_top` gap, nudge sign, `move-label` target, variant alias, label role casing, the straight-edge span midpoint, theme contrast limits, `fan_in` grouping and the CSS zone selector key were all killed.

**Next steps**: None. The feature is verified.

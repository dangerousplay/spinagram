# Validation: css-inspector

**Verdict**: PASS
**Result**: PASS (iteration 2, HEAD a4b0fc3)

## Iteration 2 (HEAD `a4b0fc3`, range `066d38d..a4b0fc3`)

Commit `a4b0fc3` fixes the INS-08 defect and adds tests for iteration-1 gaps 1-5 and 7. All 21 requirements are now met.

- **Gate**: `uv run --all-extras pytest -q` gives 340 passed, 3 skipped. `uv run --all-extras ruff check src tests examples docs/scripts` gives "All checks passed!".
- **INS-08 fix**: `cli._check` prints `inspect_fmt.unused(reports)` once in both modes, and `--styles` calls `render(..., unused_selectors=False)`. Covered by tests/test_css_inspector.py:326 (two diagrams share a sheet; `.cold` printed once and `.hot` not at all, with and without `--styles`).
- **New evidence**:
  - INS-04: tests/test_css_inspector.py:340 (inherited-from line and `::body` section in the CLI output)
  - INS-02: :353 (a declared property is not listed as inherited)
  - INS-07: :359 (auto mode follows the TTY and `NO_COLOR`)
  - INS-12: :373 (`kinds` and `id`)
  - INS-03: :380 (example SVGs stay identical after `inspect`)

### Sensor, iteration 2 (isolated worktree, since removed; real tree unchanged)

| Mutant | Result | Killing test |
|--------|--------|--------------|
| M07 `NO_COLOR` ignored | killed | test_auto_colour_follows_tty_and_no_color |
| M17 CLI "inherited from" section dropped | killed | test_check_styles_prints_inherited_and_pseudo_sections |
| M18 CLI pseudo-element sections dropped | killed | test_check_styles_prints_inherited_and_pseudo_sections |
| M22 inherited list includes declared properties | killed | test_declared_properties_are_not_listed_as_inherited |
| M23 full revert of the INS-08 fix (per-diagram unused under `--styles`) | killed | test_check_styles_unused_counts_every_diagram, test_check_styles_plain_output |
| M24 `--styles` prints per-diagram lists and the aggregate | killed | test_check_styles_unused_counts_every_diagram |

Cumulative: 24 mutants, 24 killed.

### Remaining gaps (non-blocking)

1. INS-03: the new test proves that `inspect` does not mutate the diagram, so the render stays byte-identical. It does not compare traced and untraced `compute` across every example; only the synthetic tree at :70 does that. Low risk, since rendering never passes `trace`.
2. INS-09: inline `css:` in `_defaults.yaml` still relies on the existing spec-reload path (workspace.py:201); no test targets it. This was accepted by the coordinator.
3. INS-13, INS-14 and DOC-*: still verified manually, by design.

---

## Iteration 1 (HEAD `0e0b51a`), kept as history

Iteration-1 verdict: FAIL. One spec deviation: INS-08 was wrong under `check --styles` when more than one diagram was checked. Everything else was met, but several outcomes had no discriminating test (see the gaps below).

- **Diff range**: `066d38d..HEAD` (HEAD = `0e0b51a`, branch `feat/behavior-css-mvp`), 47 files, +2150/-58
- **Gate**: `uv run --all-extras pytest -q` gives 334 passed, 3 skipped. `uv run --all-extras ruff check src tests examples docs/scripts` gives "All checks passed!". All 41 tests in `tests/test_css_inspector.py` and `tests/test_ui.py` ran, none skipped (node and python-pptx are present).
- **Verifier**: independent; did not write the code. The mutants ran in a scratch git worktree that has since been removed, and `git status --porcelain` of the real tree is unchanged.

## Per-requirement outcome check

| ID | Verdict | Evidence (spec outcome asserted) | Notes |
|----|---------|----------------------------------|-------|
| INS-01 | PASS | tests/test_css_inspector.py:39-48 (applied/overridden, `var()` resolved, origin, line, specificity, unknown, invalid); :51-56 (inline origin, `!important`, null selector and specificity) | Killed M01. |
| INS-02 | PARTIAL | tests/test_css_inspector.py:59-67 (`from` key, pseudo-elements inherit through the node) | The "and not declared on the element" clause is untested: M22 (declared values also listed as inherited) survived. |
| INS-03 | PARTIAL | tests/test_css_inspector.py:70-75 (same computed styles with and without the trace, one synthetic tree) | Nothing checks "SVG of every example stays byte-identical". The render path never passes `trace`, so the risk is low. |
| INS-04 | PARTIAL | tests/test_css_inspector.py:183-196 (header, cascade line, winner first, `var()` arrow, overridden marker, unknown warning, quiet elements) | No test covers inherited values with their source or pseudo-element sections in the CLI output: M17 and M18 survived. Both appear in the docs' generated output (css-reference.mdx:141), but no test checks them. |
| INS-05 | PASS | tests/test_css_inspector.py:120-125 (`select`, invalid selector raises); :207-212 (CLI filter, exit 2 with "invalid selector" on stderr) | Killed M06 and M19. |
| INS-06 | PASS | tests/test_css_inspector.py:215-219 (JSON, filtered by `--select`) | Killed M20. Same structure as the UI: the endpoint returns `css.inspect` plus geometry (workspace.py `styles`). |
| INS-07 | PARTIAL | tests/test_css_inspector.py:183-186 (pipe gives plain text); :199-204 (`--color always`: strike-through, swatch, no plain marker) | No test covers the TTY or `NO_COLOR` branch, and M07 (NO_COLOR ignored) survived. A manual run with `script` on a TTY printed 6 SGR sequences without NO_COLOR and 0 with NO_COLOR=1, so the behaviour is correct but unguarded. |
| INS-08 | **FAIL** (for `--styles`) | tests/test_css_inspector.py:110-117 (theme sheets excluded); :222-227 (plain check: info lines, not counted as issues); :237-241 (`unused()` aggregates across diagrams) | `--styles` prints each report's own `unused` (inspect_fmt.py:170-172), not the cross-diagram aggregate. Reproduced with `a.yaml` (uses `.hot`), `b.yaml` (does not) and a shared `s.css`: `check a.yaml b.yaml` prints nothing (correct), but `check --styles a.yaml b.yaml` prints `info: unused selector .hot s.css:1` (wrong). |
| INS-09 | PASS | tests/test_ui.py:319-331 (only the users re-render, event keys exact, unused sheet gives no event) | Killed M11. Inline `css:` in `_defaults.yaml` goes through the existing spec-reload path (workspace.py:201), but no test covers inline css there specifically. |
| INS-10 | PASS | tests/test_ui.py:334-349 (external folder watched, re-render, the set follows the specs) | Killed M12. `watch_loop` re-arms when `watch_dirs` changes (server.py). The loop itself is not tested; that is acceptable. |
| INS-11 | PASS | tests/test_ui.py:352-363 (theme event, every key, new colour) | Killed M13. |
| INS-12 | PASS | tests/test_ui.py:283-306 (report, geometry: box for nodes, groups, text and the diagram, points, route and label for edges, size, unused, warnings); :309-316 (404, 422, unstyled); tests/test_css_inspector.py:95-107 (keys, type, classes, attrs, parent, styles, trace, sheets) | Killed M10. `kinds` and `id` are present in the payload but not asserted. |
| INS-13 | MET (manual) | web/src/DiagramView.tsx: the report is refetched on `rev` and selection is kept by key; `Overlay` highlights the selection; Inspector.tsx:145 strikes through overridden declarations; the panel lists classes (291), attrs (296), computed values and source rules. The bundle `index-Ca7Vfcvq.js` is referenced from static/index.html and contains the new code. | No automated test, by design. If the element disappears, the key stays selected and the panel shows nothing; the selection comes back if the element reappears. That is acceptable. |
| INS-14 | MET (manual) | DiagramView.tsx `onMove` sets hover only when no button is pressed; `onUp` ignores moves over 4 px (a drag pans); Overlay draws a dashed outline on hover | No automated test, by design. |
| INS-15 | PASS | tests/test_css_inspector.py:266-274 (scene, SVG rect and symbol path, stroke opaque); :277-287 (pptx alpha on fill, not on line, symbols); :290-307 (figma `fillOpacity`, multiplied by `opacity`) | Killed M14, M15, M16 and M21. |
| INS-16 | PASS | tests/test_css_inspector.py:128-132; :230-234 | |
| INS-17 | PASS | tests/test_css_inspector.py:135-141, :144-148; tests/test_ui.py:305-306 | Killed M03. |
| INS-18 | PASS | tests/test_ui.py:366-380 (event, RenderError naming the file, recovery) | |
| DOC-01 | MET (manual) | docs/content/docs/css-reference.mdx:11-59: matrix for nodes/groups, text and edges, with SVG/PNG, PowerPoint and Figma columns; exact, approximated with how, or ignored. Spot-checked against the backends: `fill-opacity` (pptx `_fill_alpha`, figma `fillOpacity`); `opacity` approximated in pptx (`_blend`). | |
| DOC-02 | MET (manual) | css-reference.mdx:61-129 with examples/styling/gallery/01..08 and docs/public/assets/css/g01..g08.svg: fills, strokes, radius, dashes, opacity, `fill-opacity`, shadows, markers, `::title`/`::body`/`::label`, `var()` and tokens, classes, ids, attributes, inheritance from groups | |
| DOC-03 | MET (manual) | css-reference.mdx:131-168: `check --styles` output generated from real colour output by docs/scripts/css_gallery.py (rendered as styled `<pre>` spans, not Shiki `ansi`, which departs from that spec assumption but meets the requirement), options table, live inspector and live reload sections, screenshot | |

## Discrimination sensor (22 mutants: 18 killed, 4 survived)

| # | Mutant | Result | Killing test |
|---|--------|--------|--------------|
| M01 | overridden never marked (status stays applied) | killed | test_trace_statuses_origin_and_specificity |
| M02 | inherited `from` source lost | killed | test_trace_lists_inherited_values_with_their_source |
| M03 | empty value accepted | killed | test_syntax_error_keeps_the_valid_trace |
| M04 | theme sheets counted for unused | killed | test_unused_selectors_only_from_own_sheets |
| M05 | `unused()` without cross-diagram aggregation | killed | test_unused_needs_every_diagram_to_miss_it |
| M06 | `--select` ignored in text output | killed | test_check_styles_select_and_bad_selector |
| M07 | `NO_COLOR` ignored in auto mode | **survived** | none |
| M08 | plain "(overridden)" marker dropped | killed | test_check_styles_plain_output |
| M09 | rule groups reversed (winner last) | killed | test_check_styles_plain_output |
| M10 | geometry zone-to-group mapping off by one | killed | test_styles_endpoint_returns_report_and_geometry |
| M11 | `stylesheets_changed` returns every key | killed | test_saving_a_stylesheet_rerenders_only_its_users |
| M12 | `watch_dirs` omits the external folder | killed | test_external_stylesheet_folder_is_watched |
| M13 | `classify` treats theme.css as a plain sheet | killed | test_theme_css_rerenders_everything |
| M14 | SVG `fill-opacity` dropped | killed | test_fill_opacity_reaches_the_scene_and_svg |
| M15 | pptx fill alpha dropped (boxes) | killed | test_fill_opacity_in_pptx |
| M16 | figma `fillOpacity` dropped | killed | test_fill_opacity_in_figma |
| M17 | CLI "inherited from" section dropped | **survived** | none |
| M18 | CLI pseudo-element sections dropped | **survived** | none |
| M19 | `select` uses all() instead of any() over a selector list | killed | test_select_filters_by_selector |
| M20 | `--json` ignores `--select` | killed | test_check_json |
| M21 | pptx symbol fill alpha dropped | killed | test_fill_opacity_in_pptx |
| M22 | inherited list also includes declared properties | **survived** | none |

## Ranked gaps

1. **INS-08 defect (`--styles`, several diagrams)**: per-diagram unused selectors are printed even when another checked diagram that uses the sheet matches the selector (inspect_fmt.py:170-172, cli.py `_check`). Fix: in `--styles` mode, print the `inspect_fmt.unused(reports)` aggregate once instead of each report's `unused`, and add a test with two diagrams sharing one sheet.
2. **INS-04 untested parts (M17, M18)**: no CLI test asserts the "inherited from <element>" lines or the `::title`/`::body`/`::label` sections. Add a group with `color` and a `::title` rule to the CLI fixture.
3. **INS-02 "not declared" clause (M22)**: add a case where the element declares an inherited property (for example `color`) and assert it is absent from `inherited`.
4. **INS-07 TTY and NO_COLOR branch (M07)**: unit-test `inspect_fmt.use_color("auto", fake_tty)` with and without `NO_COLOR`. The behaviour was verified manually and is correct.
5. **INS-03 scope**: the test compares computed styles on one synthetic tree, but the spec promises byte-identical SVG for every example. Low risk, since rendering never passes `trace`.
6. **INS-09 inline css in `_defaults.yaml`**: covered only by the existing spec-reload path; no test targets it.
7. **INS-12 precision**: `kinds` and `id` are not asserted; the JSON shape of the trace is not cross-checked against web/src/api.ts types (the build gate only).

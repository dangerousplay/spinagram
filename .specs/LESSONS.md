# LESSONS - auto-maintained by scripts/lessons.py

> Machine-owned. Do NOT hand-edit. Changes are overwritten on the next `lessons.py` write.
> Canonical state lives in `.specs/lessons.json`. Edit lessons only via the script.
> promote_threshold=2 distinct features · window_days=45 · quarantine_threshold=2

## Confirmed (load these at Specify/Design)

Corroborated across multiple features. Safe to apply as guidance.

### L-001 - Pin determinism with a golden output hash checked across many PYTHONHASHSEED values, not a few in-process runs.
- signal: `surviving_mutant` · recurrence: 2 feature(s) · scope: `tests` · harmful: 0
- features: layered-layout, excalidraw-backend
- evidence: M9b (hash tie-break) (tests) (+1 more)
- last seen: 2026-10-19T18:02:51Z

### L-014 - Give every clause of a multi-clause acceptance criterion its own assertion
- signal: `surviving_mutant` · recurrence: 2 feature(s) · scope: `tests` · harmful: 0
- features: annotations, excalidraw-backend
- evidence: validation.md M21/M39/M40 ANN-03 ANN-10 ANN-22 (tests) (+1 more)
- last seen: 2026-10-19T18:02:51Z

### L-017 - Test each layout property on every band side or branch it applies to, not only the default side
- signal: `surviving_mutant` · recurrence: 2 feature(s) · scope: `tests` · harmful: 0
- features: legend-css, excalidraw-backend
- evidence: validation.md M12/M13 src/spinagram/annotate.py:187,370 (LCSS-08) (tests) (+1 more)
- last seen: 2026-10-19T18:02:51Z

## Candidates (under observation - do NOT load as guidance yet)

Seen once or not yet corroborated. Tracked, not trusted.

### L-002 - Give placement ACs a measurable bound (e.g. pill within 6 px of its segment) before writing the test.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `spec` · harmful: 0
- features: layered-layout
- evidence: LAY-12 (spec)
- last seen: 2026-10-12T04:39:39Z

### L-003 - Guard output-unchanged-without-the-feature with a golden render captured before the feature, not an identity check.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: css-styling
- evidence: M15 (CSS-27) (tests)
- last seen: 2026-10-12T04:39:39Z

### L-004 - When an AC describes geometry that depends on layout (bars spanning branches), test the laid-out result, not the default size.
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: behavior-diagrams
- evidence: BHV-02 / G1 (tests)
- last seen: 2026-10-12T04:39:39Z

### L-005 - Never pipe the test command into tail before chaining a commit; check pytest's own exit code.
- signal: `gate_fail` · recurrence: 1 feature(s) · scope: `process` · harmful: 0
- features: layered-layout
- evidence: 99549c5 (process)
- last seen: 2026-10-12T04:39:39Z

### L-006 - Parse value formats with a full match; lenient prefix parsing hides upstream bugs from tests.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `src` · harmful: 0
- features: css-styling
- evidence: F9 / R3 (CSS-16) (src)
- last seen: 2026-10-12T04:41:36Z

### L-007 - Check optional spec keys with is-None, not truthiness, so falsy wrong-typed values like 0, false or {} still fail validation
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `yaml-loaders` · harmful: 0
- features: diagram-catalog
- evidence: META-03 src/spinagram/yaml_io.py:55 (yaml-loaders)
- last seen: 2026-10-12T17:25:04Z

### L-008 - Keep every data transformation an AC names (sorting, filtering, sampling) in the unit-tested pure-logic module, not inline in a component
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `web-ui` · harmful: 0
- features: catalog-previews
- evidence: M16 web/src/PacksPage.tsx:45 (PREV-07) (web-ui)
- last seen: 2026-10-12T17:38:46Z

### L-009 - When an AC requires an error response to carry the error message, assert the message text, not just that an error field is present
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `routes` · harmful: 0
- features: catalog-previews
- evidence: M17 tests/test_ui.py:161 (PREV-03) (routes)
- last seen: 2026-10-12T17:38:46Z

### L-010 - Assert that styled values reach the rendered scene shapes, not only the computed style map
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `css` · harmful: 0
- features: annotations
- evidence: validation.md M35/M36 src/spinagram/annotate.py:207,228 (css)
- last seen: 2026-10-12T18:18:23Z

### L-011 - Derive expected geometry independently instead of reusing the function under test
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: annotations
- evidence: validation.md M07 tests/test_annotations.py:330 (tests)
- last seen: 2026-10-12T18:18:23Z

### L-012 - Assert the exact numeric value in diagnostic messages, not just the message prefix
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `qa` · harmful: 0
- features: annotations
- evidence: validation.md M37 tests/test_annotations.py:726 (qa)
- last seen: 2026-10-12T18:18:23Z

### L-013 - Cover first-match rules with a fixture that has at least two candidates
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: annotations
- evidence: validation.md M38 src/spinagram/model.py:492 (tests)
- last seen: 2026-10-12T18:18:23Z

### L-015 - When a spec says first-use order over mixed element types, state the order across types
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `spec` · harmful: 0
- features: annotations
- evidence: validation.md ANN-01 src/spinagram/annotate.py:84 (spec)
- last seen: 2026-10-12T18:18:23Z

### L-016 - Copy fixture paths from the real upstream source so every naming form it actually uses, including optional-group branches, is exercised
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: selfhosted-icons
- evidence: validation.md M02 src/spinagram/icon_packs/network.yaml:13 tests/test_icon_packs.py:51 (ICON-09) (tests)
- last seen: 2026-10-12T19:04:51Z

### L-018 - When an explicit setting overrides an automatic rule, test it under the condition that triggers the rule
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: legend-css
- evidence: validation.md M15 src/spinagram/annotate.py:354 (LCSS-08) (tests)
- last seen: 2026-10-12T20:03:34Z

### L-019 - When a default moves from code to the stylesheet, test that every loader path, including YAML, leaves the value unset
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `yaml-loaders` · harmful: 0
- features: legend-css
- evidence: validation.md M30 src/spinagram/yaml_io.py:140 (LCSS-04) (yaml-loaders)
- last seen: 2026-10-12T20:03:34Z

### L-020 - When new enum values are added, cover each one in every consumer that branches on it, including qa checks
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: legend-css
- evidence: validation.md M20/M21 src/spinagram/annotate.py:525-526 (ANN-12 for left/top) (tests)
- last seen: 2026-10-12T20:03:34Z

### L-021 - Give every clause of a multi-clause acceptance criterion its own assertion
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: legend-css
- evidence: validation.md LCSS-05 clause 2 tests/test_legend_css.py:42 (tests)
- last seen: 2026-10-12T20:03:34Z

### L-022 - When one function reserves space and another draws into it, assert both against the same independently derived size
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: legend-css
- evidence: validation.md iter2 M12 src/spinagram/annotate.py:187 (LCSS-08) (tests)
- last seen: 2026-10-12T20:09:01Z

### L-023 - When files are addressed by a derived path, test with two roots holding the same relative path: the path must stay unique or a save hits the wrong file.
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `ui/workspace` · harmful: 0
- features: live-editor
- evidence: SRC-04 workspace.py display() (ui/workspace)
- last seen: 2026-10-17T17:49:20Z

### L-024 - Watcher tests must warm the watcher and wait for quiet before acting, or a trailing event from setup masks the behaviour under test.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests/watcher` · harmful: 0
- features: live-editor
- evidence: M12 server.py retarget.set() (tests/watcher)
- last seen: 2026-10-17T17:49:20Z

### L-025 - When a cache is reset on a state switch, test the scenario where the new state cannot overwrite the cached entry (e.g. a broken spec), not only the happy reload.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `ui/workspace` · harmful: 0
- features: live-editor
- evidence: N11 workspace.py open() (ui/workspace)
- last seen: 2026-10-17T17:49:20Z

### L-026 - Keep state transitions that react to async results (saves, refetches) in pure editor.ts functions with unit tests, not inside React components.
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `web` · harmful: 0
- features: live-editor
- evidence: edge case: two quick saves, CodePanel.tsx (web)
- last seen: 2026-10-17T17:49:20Z

### L-027 - Timing ACs need the spec's stated workload (e.g. 50 nodes) in the test, measured to the observable outcome, not to an intermediate event.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: live-editor
- evidence: EDIT-05 (tests)
- last seen: 2026-10-17T17:49:20Z

### L-028 - When a spec says first match, include a fixture with two matches and assert the first one is returned
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: inspector-declarations
- evidence: validation.md M4 (src/spinagram/ui/declare.py:50) (tests)
- last seen: 2026-10-19T05:07:41Z

### L-029 - Test literal matching of regex metacharacters with a pattern that holds the metacharacter against text that only matches it as a wildcard
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: inspector-declarations
- evidence: validation.md M2 (src/spinagram/ui/declare.py:17) (tests)
- last seen: 2026-10-19T05:07:41Z

### L-030 - Test every word boundary a matcher claims, on both sides, with a near-miss prefix and suffix
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: inspector-declarations
- evidence: validation.md M3 (src/spinagram/ui/declare.py:30) (tests)
- last seen: 2026-10-19T05:07:41Z

### L-031 - Test placement thresholds with a value between the boundaries each term of the formula sets
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: inspector-declarations
- evidence: validation.md M14 (web/src/inspect.ts:32) (tests)
- last seen: 2026-10-19T05:07:41Z

### L-032 - Do not compose regex fragments that use numbered backreferences; use named groups unique per fragment
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `regex` · harmful: 0
- features: inspector-declarations
- evidence: DECL-03 D1 (src/spinagram/ui/declare.py:31) (regex)
- last seen: 2026-10-19T05:07:41Z

### L-033 - State token terminators in matching ACs as an exact pattern, not a prose list
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `spec` · harmful: 0
- features: inspector-declarations
- evidence: DECL-01 (validation.md) (spec)
- last seen: 2026-10-19T05:07:41Z

### L-034 - Test that a matcher enforces its required delimiters with a near-miss line that omits each one
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: inspector-declarations
- evidence: validation.md iteration 2 N5 (src/spinagram/ui/declare.py:18) (tests)
- last seen: 2026-10-19T05:13:32Z

### L-035 - Gate commands must install every optional extra the full test suite needs, or those tests must skip without it
- signal: `gate_fail` · recurrence: 1 feature(s) · scope: `gates` · harmful: 0
- features: inspector-declarations
- evidence: validation.md iteration 2 Gate Check (tests/test_engine.py::test_examples_render_all_backends) (gates)
- last seen: 2026-10-19T05:13:32Z

### L-036 - Test quoted-string matching with a near-miss where the value is followed by the other quote character inside a longer string
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: inspector-declarations
- evidence: validation.md iteration 3 N3 (src/spinagram/ui/declare.py:14) (tests)
- last seen: 2026-10-19T05:16:52Z

### L-037 - Pick geometry fixtures that hit every structural branch the real inputs have, such as multiple subpaths and closed paths that do not end on their start.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: excalidraw-backend
- evidence: M08,M16 src/spinagram/backends/excalidraw.py:49-50,207 (EXC-05) (tests)
- last seen: 2026-10-19T18:02:51Z

### L-038 - Test a rounding rule with a value where rounding and truncation give different results.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: excalidraw-backend
- evidence: M15 src/spinagram/backends/excalidraw.py:195 (Opacity row) (tests)
- last seen: 2026-10-19T18:02:51Z

### L-039 - When an AC reuses a helper's coordinates in another format, state which reference point the output uses, such as left edge or centre.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `spec` · harmful: 0
- features: excalidraw-backend
- evidence: EXC-07 spec.md (Label.place() x is the centre for align=center) (spec)
- last seen: 2026-10-19T18:02:51Z

## Quarantined (failed when applied - ignore)

A confirmed lesson that recurred alongside failure. Kept for the maintainer to review.

_none_

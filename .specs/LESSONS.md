# LESSONS - auto-maintained by scripts/lessons.py

> Machine-owned. Do NOT hand-edit. Changes are overwritten on the next `lessons.py` write.
> Canonical state lives in `.specs/lessons.json`. Edit lessons only via the script.
> promote_threshold=2 distinct features · window_days=45 · quarantine_threshold=2

## Confirmed (load these at Specify/Design)

Corroborated across multiple features. Safe to apply as guidance.

_none_

## Candidates (under observation - do NOT load as guidance yet)

Seen once or not yet corroborated. Tracked, not trusted.

### L-001 - Pin determinism with a golden output hash checked across many PYTHONHASHSEED values, not a few in-process runs.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `tests` · harmful: 0
- features: layered-layout
- evidence: M9b (hash tie-break) (tests)
- last seen: 2026-10-12T04:39:39Z

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

## Quarantined (failed when applied - ignore)

A confirmed lesson that recurred alongside failure. Kept for the maintainer to review.

_none_

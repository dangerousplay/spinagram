# CSS Inspector, Live Reload and Backend Support Docs

**Status**: Approved (2026-10-12, "proceed with the css live inspector and live reload; document the supported features by backend with examples of styling, pretty output")
**Builds on**: `.specs/features/css-styling/` (implements its deferred CSS-23, CSS-24, CSS-25, CSS-28)

## Problem Statement

Stylesheets now drive the look of diagrams, but authors cannot see why an element looks the way it does:
which rule won, which declaration was overridden, what a `var()` resolved to. `spinagram serve` ignores
`.css` saves, so the edit-look loop is broken for styling. The docs list CSS properties but not what each
backend (SVG, PNG, PowerPoint, Figma) does with them.

## Goals

- [ ] One cascade trace, shared by the CLI and the live UI, that explains every computed value.
- [ ] Saving any stylesheet in a diagram's cascade refreshes that diagram in `serve`.
- [ ] A docs page an author can trust: property × backend, with rendered examples.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Editing CSS inside the UI | Read-only inspector first; the source of truth stays in files |
| Opening the rule in an editor | Editor protocols differ; the origin `file:line` is shown |
| Remaining CSS-08..11 properties (padding, text-align, icon-size, …) | Separate feature |

---

## Assumptions & Open Questions

- Assumption: the inspector is read-only and lives in the existing `serve` SPA (`web/`), rebuilt into `src/spinagram/ui/static`.
- Assumption: element hit-testing uses geometry the server returns, so the SVG output does not change (keeps CSS-27).
- Assumption: Shiki's `ansi` code-block language renders the captured colour output in the docs.
- Open questions: none.

## User Stories

### P1: Cascade trace ⭐ MVP

1. WHEN the cascade resolves an element THEN the system SHALL record, per element and pseudo-element, every matched declaration with its property, raw value, value after `var()` substitution, origin (`file:line` or `inline`), selector, specificity, `!important` flag and status (`applied`, `overridden`, `invalid`, `unknown`).  <!-- INS-01 -->
2. WHEN a computed value is inherited and not declared on the element THEN the trace SHALL list it as `inherited` with the key of the element it came from.  <!-- INS-02 -->
3. The system SHALL produce the same computed styles with and without tracing (tracing never changes rendering; SVG of every example stays byte-identical).  <!-- INS-03 -->

### P1: `spinagram check --styles` ⭐ MVP (CSS-23)

1. WHEN `spinagram check --styles` runs THEN the system SHALL print, for each element of each selected diagram, a header (`type#id.class…`), the declarations grouped by rule in cascade order (winning rule first) with origin and specificity, overridden declarations marked, inherited values with their source, and the pseudo-element sections that have declarations.  <!-- INS-04 -->
2. WHEN `--select SELECTOR` is given THEN only elements matching that CSS selector SHALL be printed; IF the selector is invalid THEN the command SHALL exit 2 with the parse error.  <!-- INS-05 -->
3. WHEN `--json` is given THEN the system SHALL print the trace as JSON (the same structure the live UI uses).  <!-- INS-06 -->
4. WHERE stdout is a terminal and `NO_COLOR` is unset (or `--color=always`) the output SHALL use ANSI colours, struck-through overridden declarations and a colour swatch next to colour values; `--color=never` or a pipe SHALL print plain text.  <!-- INS-07 -->
5. WHEN a selector in a diagram's own stylesheets (not the theme's) matches no element in any checked diagram using that sheet THEN `check` SHALL print it as `info: unused selector` with `file:line`, without counting it as an issue.  <!-- INS-08 (CSS-28) -->

### P1: Live reload of stylesheets ⭐ MVP (CSS-24)

1. WHILE `serve` runs, WHEN a `.css` file referenced by a diagram (spec folder or elsewhere) or inline in its folder defaults is saved THEN the system SHALL re-render exactly the diagrams whose cascade includes it and publish a `diagram` event for their keys.  <!-- INS-09 -->
2. WHEN a referenced stylesheet lives outside the spec folders and the theme THEN the watcher SHALL watch its folder, and SHALL follow changes to the set of referenced folders.  <!-- INS-10 -->
3. WHEN the theme's `theme.css` is saved THEN every diagram SHALL re-render (theme change path).  <!-- INS-11 -->

### P1: Live inspector ⭐ MVP (CSS-25)

1. WHEN the UI requests `api/diagrams/<key>.styles` THEN the server SHALL return the elements (key, type, kinds, id, classes, attributes, label, scene geometry: box for nodes and groups, polyline for edges), the trace, the stylesheets in cascade order, unused selectors and warnings.  <!-- INS-12 -->
2. WHEN inspect mode is on and the user clicks an element THEN the UI SHALL highlight it and show its classes, attributes, computed style and source rules (overridden ones struck through), and SHALL keep the selection across live reloads while the element exists.  <!-- INS-13 -->
3. WHEN inspect mode is on and the pointer hovers an element THEN the UI SHALL outline it; a drag SHALL still pan and SHALL NOT select.  <!-- INS-14 -->

### P2: `fill-opacity`

1. WHEN `fill-opacity` is set on a node, group, region or lane THEN SVG/PNG SHALL emit `fill-opacity`, PowerPoint SHALL set the fill alpha, and Figma SHALL set the fill paint opacity (today the value is parsed and dropped).  <!-- INS-15 -->

### P1: Docs ⭐ MVP

1. The docs SHALL have a page with a property × backend matrix (SVG, PNG, PowerPoint, Figma/FigJam) stating per cell: exact, approximated (and how), or ignored — derived from the backend code.  <!-- DOC-01 -->
2. The page SHALL show styling examples: CSS source next to its rendered SVG, covering fills, strokes and dashes, radius, shadows, opacity, markers, text pseudo-elements, `var()` and theme tokens, classes and ids, and inheritance from groups.  <!-- DOC-02 -->
3. The docs SHALL document `check --styles` (with real colour output) and live reload in `serve`.  <!-- DOC-03 -->

---

## Edge Cases

- WHEN a diagram has no stylesheet and no inline CSS THEN `check --styles` SHALL say so for that diagram and print no elements.  <!-- INS-16 -->
- IF a stylesheet has a syntax error THEN the inspector SHALL still show the trace for the valid rules and list the error under warnings.  <!-- INS-17 -->
- WHEN a stylesheet file is deleted while `serve` runs THEN the affected diagram SHALL show the render error and recover when the file returns.  <!-- INS-18 -->

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| INS-01 | Cascade trace | Execute | Pending |
| INS-02 | Cascade trace | Execute | Pending |
| INS-03 | Cascade trace | Execute | Pending |
| INS-04 | check --styles | Execute | Pending |
| INS-05 | check --styles | Execute | Pending |
| INS-06 | check --styles | Execute | Pending |
| INS-07 | check --styles | Execute | Pending |
| INS-08 | check --styles | Execute | Pending |
| INS-09 | Live reload | Execute | Pending |
| INS-10 | Live reload | Execute | Pending |
| INS-11 | Live reload | Execute | Pending |
| INS-12 | Live inspector | Execute | Pending |
| INS-13 | Live inspector | Execute | Pending |
| INS-14 | Live inspector | Execute | Pending |
| INS-15 | fill-opacity | Execute | Pending |
| INS-16 | Edge cases | Execute | Pending |
| INS-17 | Edge cases | Execute | Pending |
| INS-18 | Edge cases | Execute | Pending |
| DOC-01 | Docs | Execute | Pending |
| DOC-02 | Docs | Execute | Pending |
| DOC-03 | Docs | Execute | Pending |

## Success Criteria

- [ ] `spinagram check --styles examples/styling` explains every styled property of the demo.
- [ ] Editing `examples/styling/brand.css` under `serve` refreshes the slide without a restart.
- [ ] The docs page renders with the matrix and live examples; the docs build passes.

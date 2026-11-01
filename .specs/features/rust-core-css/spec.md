# Rust core: CSS selector matching and cascade

**Status:** Verified · **Size:** Large · **Branch:** `spike/rust-core`
**Builds on:** `rust-core-svg-png`, STATE.md 2026-11-01 (Rust core port pattern)

## Problem Statement

Styling runs `compute()` in `css.py`: every rule's selectors are matched against every element and pseudo-element,
declarations are sorted by the cascade and `var()` references are substituted. It is about 1 % of build time today,
but it grows with rules × elements, it will run once per frame for CSS animations, and the WASM editor needs the
cascade without Python. This feature moves selector parsing, matching, cascade ordering and `var()` substitution into
the Rust core, while Python keeps stylesheet tokenizing (tinycss2), value typing against the theme, warnings, the trace
and inheritance of typed values. Output stays identical.

## Goals

- [ ] With `SPINAGRAM_RUST=1`, `compute()`, `styles()`, `select()` and `inspect()` return exactly what Python returns, for every example and every CSS test.
- [ ] Matching and cascade are at least 5x faster than Python on a 500-node, 200-rule diagram (measured).

## Out of Scope

| Feature | Reason |
|---|---|
| Tokenizing stylesheets in Rust (cssparser) | tinycss2 error messages are user-facing and pinned by tests |
| Value typing (`PROPS`: colours, lengths, shadows) in Rust | Needs the theme's tokens and PIL colour names; cheap per value; next slice with animation |
| CSS animation (`@keyframes`, `animation`, `transition`) | Separate feature; this slice is its foundation |
| New selectors or properties | Pure port |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
|---|---|---|---|
| Boundary | Python sends the element tree (parent index, type, kinds, id, classes, attrs, inline decls parsed by tinycss2) and the rules (selector texts, decls name/value/important, order) as JSON; Rust returns, per element and pseudo-element (`""`, `title`, `body`, `label`), the matched declarations in cascade order as `(rule index or inline, selector index, decl index, resolved value or null for custom properties)` | No Python callbacks in the matching loop; Python's typing, warnings and trace code stays the single implementation | y |
| Selector errors | Python's `parse_selectors` still validates selectors and raises; Rust parses only selectors Python accepted | Error messages stay Python's; Rust parse parity is tested on the accepted corpus | y |
| `var()` semantics | Rust reproduces `_substitute` exactly: up to 8 passes, fallback after the first comma, unknown `--x` with no fallback becomes the token name `x` | Identical resolved values | y |
| Custom-property scope | Custom properties inherit from the parent element; pseudo-element declarations see the element's custom properties plus their own | Mirrors `resolve()` | y |
| Equality of output | `compute()` result (values per element/pseudo), the warnings list and the `trace` structure compared with `==`, plus `inspect()` JSON | The user-visible contract | y |
| Benchmark diagram | Synthetic: 500 nodes in 20 groups, 200 rules mixing every selector feature, generated with a fixed seed | Repeatable | y |
| Crates over handwritten code | cssparser for tokenizing; selectors crate for matching if it reproduces the grammar exactly, else minimal glue with a recorded reason | User directive 2026-11-01 | y |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: The cascade runs in Rust with identical results ⭐ MVP

**User Story**: As a spinagram user with the Rust core, I want styling computed in Rust so that large and animated
diagrams stay fast, with exactly the same look.

**Acceptance Criteria**:

1. WHERE the Rust core is active, `css.compute()` SHALL take matching, cascade order and `var()` substitution from the core and return values, warnings and trace equal to the Python path. <!-- optional-feature --> (CSS-01)
2. WHEN the Rust core parses any selector accepted by `parse_selectors` THEN its parts (combinators, type, id, classes, attrs, pseudo-classes, nested `:not` lists), pseudo-element and specificity SHALL equal Python's. <!-- event --> (CSS-02)
3. WHEN a selector uses any supported feature (type incl. node kinds, `*`, `.class`, `#id`, `[attr]`, `[attr=value]` quoted and unquoted, descendant, `>`, selector lists, `:first-child`, `:last-child`, `:root`, `:not(list)`, `::title`, `::body`, `::label`) THEN the Rust match result SHALL equal Python's for every element. <!-- event --> (CSS-03)
4. The Rust cascade SHALL order declarations by `(important, specificity, rule order, declaration index)` with inline declarations at levels 1 (normal) and 3 (important), as Python does. <!-- ubiquitous --> (CSS-04)
5. WHEN a value contains `var()` THEN the Rust core SHALL return the same resolved string as `_substitute`, including nested references, fallbacks containing functions, and unknown names falling back to the theme token name. <!-- event --> (CSS-05)
6. WHERE the Rust core is active, `css.select()` SHALL return the same keys in the same order as Python. <!-- optional-feature --> (CSS-06)
7. WHERE the Rust core is active, `css.inspect()` SHALL return a report equal to Python's, including `unused` selectors. <!-- optional-feature --> (CSS-07)
8. WHILE the Rust core is not active the CSS functions SHALL behave exactly as before this feature. <!-- state --> (CSS-08)
9. IF a colour property cannot be resolved THEN the Rust path SHALL raise the same `CssValueError` message as Python. <!-- unwanted --> (CSS-09)

**Independent Test**: For every example and CSS test fixture, compare `compute`/`inspect` output across modes; full suite in both modes.

---

### P2: Parity and speed checked automatically

**Acceptance Criteria**:

1. WHEN `rust/bench/css_parity.py` runs THEN it SHALL compare `inspect()` output across modes for every example and at least 1,000 seeded random (tree, stylesheet) pairs covering every selector feature and `var()` form, report timings on the benchmark diagram, and exit non-zero on any difference. <!-- event --> (PAR-21)
2. WHEN CI's `rust` job runs THEN it SHALL run `css_parity.py`. <!-- event --> (PAR-22)

---

## Edge Cases

- WHEN an element has no parent THEN `:first-child`/`:last-child` treat it as its own only sibling, and `:root` matches it (CSS-03).
- WHEN `::label` is used alone THEN it matches any element's label pseudo-element (CSS-02, CSS-03).
- WHEN a declaration is an unknown property THEN the warning text, with its "did you mean" hint, SHALL be identical (CSS-01; produced in Python).
- WHEN a `var()` nests more than 8 levels THEN both paths stop after 8 passes with the same partially substituted string (CSS-05).
- WHEN the diagram has no stylesheet and no inline css THEN `styles()` returns `({}, [])` without calling the core (CSS-08).

## Implicit-requirement dimensions

| Dimension | Coverage |
|---|---|
| Input validation & bounds | Selector validation stays in Python (assumption); `var()` 8-pass bound (edge case) |
| Failure / partial-failure states | CSS-09 colour error; invalid/unknown declarations keep their warnings (CSS-01) |
| Idempotency / retry | N/A because compute is a pure function of tree and rules |
| Auth boundaries & rate limits | N/A because this is a local library |
| Concurrency / ordering | CSS-04 cascade order; CSS-06 key order |
| Data lifecycle / expiry | N/A because nothing is stored |
| Observability | `inspect()` trace parity (CSS-07); PAR-21 timings |
| External-dependency failure | CSS-08 (core absent → Python) |
| State-transition integrity | N/A because there are no state machines in scope |

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
|---|---|---|---|
| CSS-01 | P1 | Done | Verified |
| CSS-02 | P1 | Done | Verified |
| CSS-03 | P1 | Done | Verified |
| CSS-04 | P1 | Done | Verified |
| CSS-05 | P1 | Done | Verified |
| CSS-06 | P1 | Done | Verified |
| CSS-07 | P1 | Done | Verified |
| CSS-08 | P1 | Done | Verified |
| CSS-09 | P1 | Done | Verified |
| PAR-21 | P2 | Done | Verified |
| PAR-22 | P2 | Done | Verified |

**Coverage:** 11 total, 11 mapped to tasks, 0 unmapped.

---

## Success Criteria

- [ ] Full suite green in both modes; `css_parity.py` 100 % identical.
- [ ] Matching + cascade ≥ 5x faster on the benchmark diagram.
- [ ] Example SVGs byte-identical in both modes.

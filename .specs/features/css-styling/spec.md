# CSS-like Styling Specification

## Problem Statement

Styling in spinagram is a fixed set of named theme styles (`default`, `dark`, `soft`… for nodes; a colour
per edge style; zone styles) resolved in `theme.py` (`node_style`, `edge_color`, `zone_style`). Authors
cannot target elements by kind, class, id or position, cannot set stroke widths, dashes, fonts, shadows
or opacity per element, and cannot share a stylesheet across diagrams without writing a whole theme.
A CSS subset (selectors, cascade, specificity, custom properties) gives broad, familiar styling for
architecture and the new behavior diagrams alike, across every backend.

## Goals

- [ ] Any visual property spinagram draws can be set from a stylesheet with standard CSS selectors.
- [ ] The same stylesheet produces the same look in SVG, PNG, PowerPoint and Figma (within each format's capabilities, with documented fallbacks).
- [ ] Existing themes and diagrams render unchanged (byte-identical SVG) when no stylesheet is used.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Full CSS (layout properties: `display`, `flex`, `grid`, `position`, `margin` on elements) | Layout belongs to the layout engines and their hints |
| `@media`, `@keyframes`, animations, transitions, `:hover` and other interactive pseudo-classes | Output is static slides and documents |
| Arbitrary HTML/CSS rendering inside nodes | Text stays plain with wrapping |
| Gradients and filters other than drop shadow in P1 | Inconsistent support in PowerPoint and Figma export; P3 |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Syntax | Real CSS subset parsed from `.css` files and strings | User chose (2026-10-12) | y (2026-10-12) |
| Where stylesheets come from | Cascade order (lowest first): built-in defaults → theme `theme.css` → `stylesheets:` of `_defaults.yaml` → diagram `css=` / `d.stylesheet()` → element inline `css=` | Mirrors browser cascade (user agent → author → inline) and existing theme/defaults layering | n |
| Element types (type selectors) | `diagram`, `node`, `edge`, `group`, `region`, `lane`, `label`, `table`, plus every node kind as its own type (`decision`, `state`, `initial`, `cylinder`…) matching also `node` | Lets `state { }` and `node { }` both work | n |
| Inline CSS keyword | `css=` (Python) / `css:` (YAML), not `style=` | `style` already names a theme style; changed 2026-10-12 during design | y (2026-10-12) |
| Classes | `class_="critical api"` in Python, `class: critical api` in YAML; the existing `style="dark"` adds class `dark` | Keeps current specs valid while unifying named styles into classes | n |
| Theme named styles | Theme `styles:` keep working and are compiled into equivalent rules at theme specificity | Backward compatibility; byte-identical goal | n |
| Parser | `tinycss2` (pure Python, BSD) for tokenizing; own selector matcher and property mapper | Robust CSS tokenization without a browser engine | n |
| Units | `px` (and unitless numbers as px) for lengths; `%` only for `opacity`; colours as hex, `rgb()`, `rgba()`, CSS named colours, theme tokens (`var(--primary)` and bare token names) | The canvas is px; tokens keep themes in control | n |
| Unsupported property in a backend | Render the nearest equivalent and emit one warning per property and backend (e.g. dotted dasharray in PowerPoint → `sysDot`) | Never silently drop styling | n |

**Open questions:** none - all resolved or logged above (required before the spec is confirmed).

---

## User Stories

### P1: Stylesheets with selectors and cascade ⭐ MVP

**User Story**: As an author, I want to write `node.critical { fill: #FEE2E2; stroke: #DC2626 }` and have every critical node styled so that styling is declarative and reusable.

**Why P1**: Core of the feature.

**Acceptance Criteria**:

1. WHEN a stylesheet rule's selector matches an element THEN the system SHALL apply the rule's declarations to that element.  <!-- CSS-01 -->
2. The system SHALL support selectors: type (`node`, `edge`, `state`…), class (`.critical`), id (`#api`), attribute presence and equality (`[icon]`, `[kind=decision]`, `[label="yes"]`), universal (`*`), descendant (`group.vpc node`), child (`region > state`), selector lists (`a, b`), and the pseudo-classes `:first-child`, `:last-child`, `:not(…)`.  <!-- CSS-02 -->
3. WHEN several rules set the same property on an element THEN the system SHALL use the declaration with the highest (importance, specificity, source order), per CSS Cascade Level 4 without layers.  <!-- CSS-03 -->
4. WHEN a declaration uses `!important` THEN the system SHALL let it win over non-important declarations regardless of specificity.  <!-- CSS-04 -->
5. WHEN an element has inline CSS (`css="stroke-width: 6"` in Python, `css:` in YAML) THEN the system SHALL apply it above all non-important stylesheet declarations.  <!-- CSS-05 -->
6. WHEN an edge selector uses `edge[from=api]` or `edge[to=db]` THEN the system SHALL match edges by endpoint node id.  <!-- CSS-06 -->
7. WHEN a group or region is styled with an inherited property (`color`, `font-family`, `font-size`, `font-weight`, `font-style`) THEN the system SHALL inherit it into descendants that do not set it.  <!-- CSS-07 -->

**Independent Test**: Load a stylesheet with competing rules (type, class, id, inline, `!important`) on a three-node diagram; assert the resolved computed style of each element against a table.

---

### P1: Visual properties across backends ⭐ MVP

**User Story**: As a designer, I want fills, strokes, dashes, corner radii, fonts, opacity and shadows to look the same in SVG, PowerPoint and Figma.

**Why P1**: Styling that only works in SVG fails the "editable everywhere" promise.

**Acceptance Criteria**:

1. The system SHALL support for nodes, groups, regions and lanes: `fill`, `stroke`, `stroke-width`, `stroke-dasharray`, `border-radius`, `opacity`, `fill-opacity`, `box-shadow` (one shadow: offset-x offset-y blur colour), `padding`, `min-width`, `min-height`, `text-align`, `vertical-align`.  <!-- CSS-08 -->
2. The system SHALL support for text (node titles via `title` pseudo-element `::title`, bodies via `::body`, edge labels via `::label`, group labels): `color`, `font-family`, `font-size`, `font-weight`, `font-style`, `text-transform`, `letter-spacing`, `line-height`.  <!-- CSS-09 -->
3. The system SHALL support for edges: `stroke`, `stroke-width`, `stroke-dasharray`, `opacity`, `marker-start`, `marker-end` (`none`, `arrow`, `open-arrow`, `diamond`, `open-diamond`, `circle`, `bar`), `edge-route` (`straight`, `orthogonal`, `curved`).  <!-- CSS-10 -->
4. The system SHALL support `icon-size`, `icon-position` (`left`, `top`, `right`) and `icon-tone` (`light`, `dark`) for nodes with icons.  <!-- CSS-11 -->
5. WHEN a styled diagram renders to SVG, PowerPoint and Figma THEN each backend SHALL produce the same fill, stroke colour, stroke width, dash pattern class, radius, font and shadow for every element, as asserted per backend in tests.  <!-- CSS-12 -->
6. IF a backend cannot express a property value THEN the system SHALL render the nearest equivalent and emit one warning naming backend, property and value.  <!-- CSS-13 -->

**Independent Test**: Render a fixture exercising every property to SVG, PPTX and Figma JS; assert attributes per backend (SVG attributes, DrawingML `a:prstDash`/`a:effectLst`/`a:ln w`, Figma `strokes`/`effects`).

---

### P1: Theme tokens and custom properties ⭐ MVP

**User Story**: As a brand owner, I want stylesheets to use theme colours by name so that one stylesheet works across brands.

**Why P1**: Keeps themes in control of the palette.

**Acceptance Criteria**:

1. WHEN a value is `var(--name)` THEN the system SHALL resolve it from custom properties declared on `:root` or an ancestor, falling back to the theme colour token `name`.  <!-- CSS-14 -->
2. WHEN a value is a bare theme token (`fill: primary-soft`) THEN the system SHALL resolve it through the theme colours.  <!-- CSS-15 -->
3. IF a colour value or token cannot be resolved THEN the system SHALL raise an error naming the file, line, selector and value.  <!-- CSS-16 -->

**Independent Test**: Render the same stylesheet with two themes; assert colours follow each theme's tokens.

---

### P1: Classes and stylesheets from Python and YAML ⭐ MVP

**User Story**: As an author, I want to attach classes and stylesheets from code so that styling stays next to the diagram.

**Why P1**: Python is the primary authoring UI.

**Acceptance Criteria**:

1. WHEN the author passes `class_="critical"` to any builder method creating a node, edge, group or region THEN the system SHALL add that class to the element.  <!-- CSS-17 -->
2. WHEN the author calls `d.stylesheet(path_or_css)` or passes `css="…"` to `Diagram` THEN the system SHALL add that stylesheet to the diagram's cascade after theme sheets.  <!-- CSS-18 -->
3. WHEN a YAML spec has `stylesheets: [file.css]` and/or `css: |` THEN the system SHALL load them in the same cascade position.  <!-- CSS-19 -->
4. WHEN a node keeps the existing `style="dark"` THEN the system SHALL render it exactly as before (theme named style), and the element SHALL also match `.dark`.  <!-- CSS-20 -->

**Independent Test**: The same styled diagram written in Python and YAML resolves identical computed styles.

---

### P1: Diagnostics ⭐ MVP

**User Story**: As an author, I want mistakes in stylesheets reported precisely so that I can fix them fast.

**Acceptance Criteria**:

1. IF a stylesheet contains a syntax error THEN the system SHALL report file, line, column and the offending token, skip the broken rule, and continue with the rest.  <!-- CSS-21 -->
2. IF a declaration names an unknown property THEN `spinagram check` SHALL warn with file, line and the nearest known property name.  <!-- CSS-22 -->
3. WHEN `spinagram check --styles ID` runs THEN the system SHALL print, for each element of diagram ID, its computed style and the rule (file:line) that set each property.  <!-- CSS-23 -->

**Independent Test**: Feed a stylesheet with a syntax error, an unknown property and a typo'd token; assert messages and that valid rules still apply.

---

### P2: Live UI integration

**User Story**: As an author, I want `spinagram serve` to re-render when a stylesheet changes and show the computed style of a clicked element.

**Acceptance Criteria**:

1. WHILE `spinagram serve` runs the system SHALL re-render diagrams when any stylesheet in their cascade is saved.  <!-- CSS-24 -->
2. WHEN the user clicks an element in the live UI THEN the system SHALL show its classes, computed style and source rules.  <!-- CSS-25 -->

---

### P3: Gradients and multiple shadows

**Acceptance Criteria**:

1. WHERE a backend supports gradients the system SHALL render `fill: linear-gradient(…)`; elsewhere it SHALL use the first colour stop and warn.  <!-- CSS-26 -->

---

## Edge Cases

- WHEN no stylesheet and no class are used THEN the system SHALL produce byte-identical SVG to the current release for every example in `examples/`.  <!-- CSS-27 -->
- IF a selector matches no element THEN `spinagram check` SHALL list it as unused (info level, not an error).  <!-- CSS-28 -->
- WHEN `font-family` names a font the theme does not embed THEN the system SHALL fall back to the theme's font for that role and warn once per family.  <!-- CSS-29 -->
- IF `stroke-width` or `font-size` is negative THEN the system SHALL ignore the declaration and warn.  <!-- CSS-30 -->

---

## Implicit-Requirement Dimensions

| Dimension | Coverage |
| --------- | -------- |
| Input validation & bounds | CSS-16, CSS-21, CSS-22, CSS-30 |
| Failure / partial-failure states | CSS-21 (broken rule skipped, rest applies) |
| Idempotency / retry / duplicate handling | Deterministic cascade (source order tie-break); duplicate declarations follow CSS-03 |
| Auth boundaries & rate limits | N/A because local library code |
| Concurrency / ordering | Source order is part of the cascade (CSS-03); file order follows the cascade list |
| Data lifecycle / expiry | N/A because no stored state |
| Observability | CSS-23 computed-style trace; CSS-28 unused selectors |
| External-dependency failure | `tinycss2` is a hard dependency of the base package; import failure is a packaging error |
| State-transition integrity | N/A because stateless |

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| CSS-01 | P1: Selectors and cascade | Design | Pending |
| CSS-02 | P1: Selectors and cascade | Design | Pending |
| CSS-03 | P1: Selectors and cascade | Design | Pending |
| CSS-04 | P1: Selectors and cascade | Design | Pending |
| CSS-05 | P1: Selectors and cascade | Design | Pending |
| CSS-06 | P1: Selectors and cascade | Design | Pending |
| CSS-07 | P1: Selectors and cascade | Design | Pending |
| CSS-08 | P1: Visual properties | Design | Pending |
| CSS-09 | P1: Visual properties | Design | Pending |
| CSS-10 | P1: Visual properties | Design | Pending |
| CSS-11 | P1: Visual properties | Design | Pending |
| CSS-12 | P1: Visual properties | Design | Pending |
| CSS-13 | P1: Visual properties | Design | Pending |
| CSS-14 | P1: Tokens | Design | Pending |
| CSS-15 | P1: Tokens | Design | Pending |
| CSS-16 | P1: Tokens | Design | Pending |
| CSS-17 | P1: Python and YAML | Design | Pending |
| CSS-18 | P1: Python and YAML | Design | Pending |
| CSS-19 | P1: Python and YAML | Design | Pending |
| CSS-20 | P1: Python and YAML | Design | Pending |
| CSS-21 | P1: Diagnostics | Design | Pending |
| CSS-22 | P1: Diagnostics | Design | Pending |
| CSS-23 | P1: Diagnostics | Design | Pending |
| CSS-24 | P2: Live UI | - | Pending |
| CSS-25 | P2: Live UI | - | Pending |
| CSS-26 | P3: Gradients | - | Pending |
| CSS-27 | Edge cases | Design | Pending |
| CSS-28 | Edge cases | Design | Pending |
| CSS-29 | Edge cases | Design | Pending |
| CSS-30 | Edge cases | Design | Pending |

**ID format:** `CSS-NN`

**Coverage:** 30 total, 0 mapped to tasks, 30 unmapped ⚠️

---

## Success Criteria

- [ ] A "brand" stylesheet of under 40 lines restyles every example diagram, and the result matches across SVG, PPTX and Figma per the CSS-12 assertions.
- [ ] All existing examples render byte-identically without a stylesheet (CSS-27).

# Catalog Previews Specification

## Problem Statement

The Diagrams page browses visually (searchable thumbnail cards in sections), but the Themes and Icon packs
pages are plain text lists. Choosing a theme or pack means opening each one. Both pages should use the same
visual card grid so a user sees what a theme looks like and what a pack contains before opening it.

## Goals

- [ ] Themes and Icon packs pages show searchable card grids with a visual preview per card, laid out like
      the Diagrams page.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Switching the active theme from the UI | UI stays read-only |
| Fetching packs from the index page | The pack view already has Fetch; one place for side effects |
| Custom sample diagrams per theme | One built-in sample shows every theme the same way |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Theme preview | A built-in sample diagram rendered with that theme (full slide, chrome included) | Shows colours, fonts, styles and chrome at once; "sample diagram per theme" was a deferred idea | n |
| Sample content | Nodes in the theme's node styles among default, dark, soft, warning, alert, neutral (those it defines), one group, edges | Works for themes that define fewer styles | n |
| Pack preview | 12 icons spread evenly over the pack's sorted icon list | Representative and deterministic; no curation per pack | n |
| Sections | Themes: "Built-in" then "Custom"; packs: "Downloaded" then "Not downloaded" | Mirrors category sections; separates what is usable now | n |
| Search fields | Themes: name, ref; packs: name, title | The visible identifiers | n |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Theme cards ⭐ MVP

**User Story**: As a UI user, I want each theme shown as a card with a rendered sample so that I can compare themes at a glance.

**Acceptance Criteria**:

1. WHEN the UI requests `/api/themes/<ref>/thumbnail.svg` THEN the server SHALL return an SVG of the sample diagram rendered with that theme.
2. IF the theme ref is unknown THEN the thumbnail endpoint SHALL return 404.
3. IF the theme fails to load THEN the thumbnail endpoint SHALL return 422 with the error message.
4. The sample diagram SHALL use only node styles the theme defines.
5. WHEN the user opens Themes THEN the UI SHALL show a card per theme with the thumbnail, name, ref and an "active" badge on the active theme, in sections "Built-in" then "Custom".
6. WHEN the user types in the search box THEN the UI SHALL show only themes whose name or ref contains every whitespace-separated term (case-insensitive).

**Independent Test**: open Themes, see the default theme card with a rendered slide.

### P1: Pack cards ⭐ MVP

**User Story**: As a UI user, I want each icon pack shown as a card with sample icons so that I see its style before opening it.

**Acceptance Criteria**:

1. WHEN a pack is downloaded THEN its card SHALL show 12 icons taken at evenly spaced positions of its sorted icon list (all icons when it has 12 or fewer).
2. IF a pack is not downloaded THEN its card SHALL show "Not downloaded" instead of icons.
3. WHEN the user opens Icon packs THEN the UI SHALL show a card per pack with name, title and icon count, in sections "Downloaded" then "Not downloaded".
4. WHEN the user types in the search box THEN the UI SHALL show only packs whose name or title contains every whitespace-separated term (case-insensitive).
5. WHEN the user clicks a theme or pack card THEN the UI SHALL open that theme sheet or pack view.

**Independent Test**: open Icon packs, see aws, gcp and k8s cards with icon grids.

---

## Edge Cases

- IF no theme or pack matches THEN the page SHALL show "No themes match" / "No packs match" with a control that clears the search.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| PREV-01 | P1: Theme cards - thumbnail endpoint | Tasks | Implementing |
| PREV-02 | P1: Theme cards - unknown ref 404 | Tasks | Implementing |
| PREV-03 | P1: Theme cards - broken theme 422 | Tasks | Implementing |
| PREV-04 | P1: Theme cards - defined styles only | Tasks | Implementing |
| PREV-05 | P1: Theme cards - card grid and sections | Tasks | Implementing |
| PREV-06 | P1: Theme cards - search | Tasks | Implementing |
| PREV-07 | P1: Pack cards - sample icons | Tasks | Implementing |
| PREV-08 | P1: Pack cards - not downloaded | Tasks | Pending |
| PREV-09 | P1: Pack cards - card grid and sections | Tasks | Pending |
| PREV-10 | P1: Pack cards - search | Tasks | Implementing |
| PREV-11 | P1: Pack cards - card opens view | Tasks | Pending |
| PREV-12 | Edge: no match | Tasks | Implementing |

**Coverage:** 12 total, 12 mapped to tasks, 0 unmapped

---

## Success Criteria

- [ ] Themes and Icon packs pages look like the Diagrams page: search box, sections, preview cards.

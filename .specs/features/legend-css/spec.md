# Legend Placement and Styling via CSS Specification

## Problem Statement

A legend's colours, border and title can be styled with CSS, but where it sits and how its entries are laid out are
fixed: `add_legend(position=...)` picks right or bottom in code, and sizes come from the theme. Authors who restyle a
whole set of diagrams with one stylesheet cannot move or reshape every legend from that stylesheet.

## Goals

- [ ] One stylesheet rule places, sizes and lays out the legend (and the steps panel that shares its band) on every
      diagram it applies to.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Free positioning (x/y) of the legend | The band keeps legends off the content; free placement was ruled out for annotations |
| Separate placement for the steps panel | Steps share the legend's band by design |
| Swatch shapes other than the computed element style | Swatches mirror the diagram |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Property names | `placement`, `width`, `columns`, `gap`, `padding`, `swatch-width`, `swatch-height`, `display` on `legend`; `font-size` on `legend::body` | Read as CSS; `position` already means something else in CSS | n |
| Placement values | `right` (default), `left`, `top`, `bottom` | Every edge of the layout area | n |
| Precedence | An explicit `add_legend(position=...)` / YAML `position:` beats CSS; without it CSS decides, else `right` | Same as inline style beating stylesheets | n |
| `columns` | A positive integer forces that many entries per row; without it, side bands use one column (two when tall and labels fit) and top/bottom bands flow by label width | Keeps today's behaviour as the default | n |
| `display: none` | Hides the legend card; the band then holds only the steps panel, or disappears when there are no steps | Lets a theme or deck sheet turn legends off | n |
| Defaults | Unset properties keep the theme's `defaults.annotations` values | Backward compatible | n |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Placement from CSS ⭐ MVP

**User Story**: As an author restyling many diagrams, I want `legend { placement: bottom }` in one stylesheet to move every legend.

**Acceptance Criteria**:

1. WHEN a stylesheet sets `legend { placement: left }` THEN the band SHALL be reserved on the left edge of the layout area and the legend card SHALL start at the area's left edge.
2. WHEN it sets `placement: top` THEN the band SHALL be reserved at the top and the card SHALL start at the area's top edge.
3. WHEN it sets `placement: bottom` or `right` THEN the band SHALL be placed as with `position="bottom"` / `"right"`.
4. WHEN `add_legend(position=...)` is given explicitly THEN it SHALL win over the stylesheet's `placement`.
5. IF `placement` has another value THEN the stylesheet SHALL report a warning naming the allowed values and the legend SHALL keep its default side.
6. WHILE the band is on the left or top, automatic layout SHALL place content in the area minus the band, starting after it.

**Independent Test**: one stylesheet with `legend { placement: left }` moves the legend of a diagram to the left.

### P1: Size and layout from CSS ⭐ MVP

**User Story**: As an author, I want to size the legend and lay out its entries from CSS.

**Acceptance Criteria**:

1. WHEN `legend { width: 300 }` is set on a left or right band THEN the band SHALL be 300 px wide (plus the gap) and the card 300 px wide.
2. WHEN `legend { columns: 3 }` is set THEN entries SHALL be laid out three per row.
3. WHEN `legend { gap: 20 }` is set THEN rows SHALL be 20 px apart.
4. WHEN `legend { padding: 30 }` is set THEN the card's title and first swatch SHALL be inset by 30 px.
5. WHEN `legend { swatch-width: 60; swatch-height: 20 }` is set THEN every swatch SHALL be 60 × 20 px.
6. WHEN `legend::body { font-size: 20 }` is set THEN entry labels SHALL use 20 px text.
7. WHEN `legend { display: none }` is set THEN no legend card SHALL be drawn, and IF there are no steps THEN no band SHALL be reserved.

**Independent Test**: a stylesheet with every property renders a legend with the given geometry.

### P2: Documentation and showcase

**Acceptance Criteria**:

1. The annotations docs SHALL list every legend property with its values and default.
2. One showcase diagram SHALL place its legend from its stylesheet, and `spinagram check examples/showcase` SHALL report 0 issues.

---

## Edge Cases

- IF `columns` is not a positive integer THEN the stylesheet SHALL report a warning and the default layout SHALL apply.
- WHEN `display: none` hides the legend and steps exist THEN the steps panel SHALL take the band alone.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| LCSS-01 | P1: Placement - left | Tasks | Implementing |
| LCSS-02 | P1: Placement - top | Tasks | Implementing |
| LCSS-03 | P1: Placement - bottom/right | Tasks | Implementing |
| LCSS-04 | P1: Placement - explicit wins | Tasks | Implementing |
| LCSS-05 | P1: Placement - invalid value | Tasks | Implementing |
| LCSS-06 | P1: Placement - area after the band | Tasks | Implementing |
| LCSS-07 | P1: Size - width | Tasks | Implementing |
| LCSS-08 | P1: Size - columns | Tasks | Implementing |
| LCSS-09 | P1: Size - gap | Tasks | Implementing |
| LCSS-10 | P1: Size - padding | Tasks | Implementing |
| LCSS-11 | P1: Size - swatch size | Tasks | Implementing |
| LCSS-12 | P1: Size - label font size | Tasks | Implementing |
| LCSS-13 | P1: Size - display none | Tasks | Implementing |
| LCSS-14 | P2: Docs | Tasks | Implementing |
| LCSS-15 | P2: Showcase | Tasks | Implementing |

**Coverage:** 15 total, 15 mapped to tasks, 0 unmapped

---

## Success Criteria

- [ ] Changing one line of a stylesheet moves and reshapes the legends of every diagram that uses it.

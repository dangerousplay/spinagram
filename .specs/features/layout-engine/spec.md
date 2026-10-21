# Layout Engine Improvements Specification

Source roadmap: `.specs/features/layout-engine/roadmap.md` (copy of `improvements-layout-engine.md`, 2026-10-20).
Item codes (T1, Z1, E1…) refer to that roadmap.

## Problem Statement

Dense architecture diagrams (~60 nodes, nested zones, ~25 edges) need many render → inspect → hand-edit
iterations: text overflows, zone icons sit on outlines, edge labels cover boxes and arrowheads, group targets are
absolute points, and dashed/dotted zones require private `Group`/`gid` tricks. `check` misses most of these
defects. The author should declare content and intent; the engine should own fitting, placement and routing, and
`check` should report and auto-fix what the engine cannot.

## Goals

- [ ] Every workaround in the roadmap Appendix is replaceable by a public API (19 rows → 0 rows needing internals).
- [ ] A fixed-width box never draws text outside its bounds while fitting strategies remain (T1).
- [ ] `check` reports the 9 new diagnostic kinds and `check --fix` clears every safe-fixable P0 diagnostic.
- [ ] Existing specs that use none of the new opt-in features render identically except where output was broken
      (overflowing text, colliding labels, icons on outlines); each intentional golden change is pinned by a test.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| General constraint solver (Cassowary-style) | G1 is limited to named grids, alignment helpers and straight edges (decision 6) |
| Rewriting Python spec source files | `--fix` on `.py` prints suggested edits only (decision 5) |
| New Figma-specific tests | Figma receives new scene fields best-effort (decision 3) |
| Auto-layout engine changes (flex/dot/elk/d2/layered) | Roadmap targets fixed-coordinate slides; engines keep current behaviour |
| Markdown export of text | Roadmap T1 note: the engine already treats text literally; no converter is in this repo |
| `spinagram serve` UI panels for new diagnostics | UI work is a separate feature (STATE deferred ideas: QA panel) |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Back-compat policy | Default-on only where current output is broken (T1 fitting, E1 avoidance, Z1 inset for icon zones, T2 fallback); everything else opt-in | Keeps existing decks stable; golden hash regenerated once with intent tests | y |
| AWS-style flush corner icons | Zone style key `header: {inset: false}` keeps the 0.3 flush placement | AWS group convention is flush; must stay reachable | y |
| Front-end parity | Every new Python API has a YAML equivalent | Project goal: both front-ends share every feature | y |
| Backend coverage | SVG, PNG, PPTX tested; Figma best-effort | Roadmap S2 names three backends | y |
| Symbol fallback font | Bundle Noto Sans Symbols 2 (OFL) as last fallback; embed in SVG and PPTX | Default theme has no symbol coverage; offline rendering required | y |
| `check --fix` on YAML | Writes `<stem>.fixed.yaml` next to the source; never overwrites | Same freeze approach as `spinagram layout` | y |
| `check --fix` on Python | Prints suggested kwarg edits per element; exit 1 while P0 issues remain | Python cannot be rewritten safely | y |
| Safe fixes | `move-label`, `resize`, `nudge` (into safe area), `shrink-font` | Geometry-only, no semantic change | y |
| G1 scope | `d.grid(cols, rows, gutter)`, `cell=`, `align_x/align_y/center_on`, `straight=True` | No general solver | y |
| E4 router | Existing A* router (`autolayout/route.py`) + crossing penalty; opt-in `route="ortho"` | Reuse proven code | y |
| `requires` mismatch | Warning (stderr + `check` issue `version-mismatch`), render continues | Reproducibility aid, not a gate | y |
| Test style | Data-driven tests: each requirement exercised by a `pytest.mark.parametrize` scenario table (ids per scenario) | User request: DDT with different scenarios | y |
| Fit default `min_scale` | 0.85 of the base size; `break_on` default `-./:·` | Roadmap T1 values | n (roadmap/agent default) |
| Long-token protection | Tokens matching IPv4/CIDR (`\d+\.\d+\.\d+\.\d+(/\d+)?`) never break internally | Roadmap T1 golden `10.0.0.0/22 · 10.0.8.0/21` | n (roadmap/agent default) |
| Zone header defaults | padding 14, icon_size 28, gap below header 12, label vertically centred on icon | Roadmap Z1 values | n (roadmap/agent default) |
| E1 arrowhead region | last 14 px of the edge; side offset = label half-height + 6 px | Roadmap E1 values | n (roadmap/agent default) |
| `zone-underused` threshold | fill ratio < 0.35 of the zone's content area | Flags the D1 ~120 px blank sibling; tunable in theme `defaults.check` | n (roadmap/agent default) |
| `low-contrast` threshold | Near-invisible only: text < 2.0:1, icons < 1.5:1; theme `defaults.check.contrast` raises to WCAG (3 / 4.5 / 3) | Strict WCAG flags the default theme and brand icons in every example (asked 2026-10-20) | y |
| Safe area | theme `canvas.margin` (default 80) | Existing token | n (roadmap/agent default) |
| Output naming | `Diagram(output=...)` / YAML `output:` → `<output>.<ext>`; `render --name-from id\|file\|slug` (default `slug`, current behaviour) | Stable names without breaking current ones | y |
| Badge cap | 3 badges per box; more → `ValueError` | Roadmap I2 | n (roadmap/agent default) |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Text fits its box (T1) ⭐ MVP

**User Story**: As a diagram author, I want long titles, hostnames and CIDR lists to fit their box automatically so that I never hand-tune widths or font sizes.

**Why P1**: Most frequent manual fix in D1/D2.

**Acceptance Criteria**:

1. WHEN a title or body line is wider than the text area THEN the engine SHALL wrap at spaces first.
2. WHEN a single token is still wider than the text area after space wrapping THEN the engine SHALL break it after one of the `break_on` characters (default `-./:·`) without inserting a hyphen.
3. The engine SHALL never break inside an IPv4 address or CIDR token (e.g. `10.0.8.0/21`).
4. WHEN wrapping cannot fit the text and `fit` includes `shrink` THEN the engine SHALL reduce font size in 1 px steps down to `min_scale` × base size (default 0.85).
5. WHEN shrinking cannot fit the text and `fit` includes `grow` THEN the engine SHALL increase box height to fit the text.
6. WHERE `fit="none"` is set the engine SHALL keep the 0.3 behaviour (wrap at spaces only).
7. IF all strategies fail THEN `check` SHALL report `overflow-x` or `overflow-y` with the last strategy tried in the detail (e.g. `after shrink to 15px`).
8. The engine SHALL accept `fit`, `min_scale` and `break_on` per node and as theme/YAML `defaults.node` keys.
9. The engine SHALL measure uppercase zone labels including their letter spacing.

**Independent Test**: Parametrized scenarios with tokens of 10–60 chars in a 230 px box: every rendered line width ≤ text-area width, CIDR tokens intact.

---

### P1: Zone header with inset icon and label (Z1) ⭐ MVP

**User Story**: As an author, I want zone icons and labels laid out as a header inside the zone so that logos never sit on outlines and content starts below the header.

**Why P1**: Visible defect in every zone with an icon.

**Acceptance Criteria**:

1. WHEN a zone has an icon THEN the engine SHALL place the icon bounding box ≥ `header.padding` (default 14) px inside the outline on the top and left.
2. The engine SHALL size every zone header icon to the same `header.icon_size` (default 28) height across all zones of a diagram.
3. WHEN a zone has an icon and a label THEN the engine SHALL place the label's vertical centre within ±1 px of the icon's vertical centre.
4. WHEN a zone has a list of icons THEN the engine SHALL draw them left to right as header chips before the label.
5. WHERE `header.strip` is set the engine SHALL draw an accent bar 5 px tall along the zone top in the strip colour.
6. The engine SHALL expose `zone.content_top` = header bottom + 12 px.
7. WHERE a zone style sets `header: {inset: false}` the engine SHALL keep the 0.3 flush-corner placement.
8. WHERE `header.upper` is false the engine SHALL keep the label's original case.

**Independent Test**: Scenario table over (dash, icon count, wordmark/symbol, label length): geometry asserts on scene items.

---

### P1: Dashed and dotted zone outlines (Z2) ⭐ MVP

**User Story**: As an author, I want `dash`, `stroke`, `stroke_width`, `fill` (incl. `none`) and `id` on zones so that I can express network vs AZ without internals.

**Why P1**: Current workaround mutates private model state.

**Acceptance Criteria**:

1. The engine SHALL accept `dash` values `solid`, `dashed` (pattern `8 6`), `dotted` (pattern `2 6`, round caps) and an explicit list of numbers on zone styles and `d.zone(...)`.
2. The engine SHALL accept `stroke`, `stroke_width` and `fill` (including `none`) on `d.zone(...)` and YAML zones.
3. The engine SHALL give every zone an `id` (explicit, or `z<index>`) and a `class` attribute matching its style, so `zone#id`, `zone.<style>` and `#id` CSS selectors apply.
4. WHEN a zone has a dash pattern THEN the SVG SHALL carry the same `stroke-dasharray` and the PPTX SHALL carry an equivalent `a:custDash`.
5. WHEN CSS sets `fill: none` on a zone THEN the engine SHALL render the zone without fill instead of raising.

**Independent Test**: Parametrized zones × backends; assert SVG attribute and PPTX XML pattern.

---

### P1: Edge labels avoid obstacles (E1) ⭐ MVP

**User Story**: As an author, I want edge labels placed where they cover no box, header, label or arrowhead so that I stop setting `label_at` by hand.

**Why P1**: Needed on most labelled edges in D1/D2.

**Acceptance Criteria**:

1. WHEN an edge has a label and no `label_at` THEN the engine SHALL try candidates in order: midpoint; offsets ±20 %, ±35 % of the length along the edge; each of those shifted to either side by half label height + 6 px.
2. The engine SHALL reject a candidate whose rectangle intersects a node, a zone header, a placed edge label, the arrowhead region (last 14 px) or lies outside the canvas margin.
3. WHEN at least one candidate is free THEN the engine SHALL use the first free candidate.
4. IF no candidate is free THEN the engine SHALL place the label at the candidate with the smallest overlap area and `check` SHALL report `label-collision` listing the number of candidates tried.
5. WHERE `label_at` is set the engine SHALL use it unchanged.
6. The engine SHALL produce identical label positions for identical input across runs and `PYTHONHASHSEED` values.

**Independent Test**: 200 seeded random short edges; whenever a free candidate exists, no label intersects an obstacle.

---

### P1: Zones as edge targets (E2) ⭐ MVP

**User Story**: As an author, I want to connect a node to a zone so that group relationships need no absolute points.

**Why P1**: Replaces hand-computed border points and crossing fan-outs.

**Acceptance Criteria**:

1. The engine SHALL accept a `Zone` object or the string `zone:<id>` (optionally `zone:<id>.<side>[@frac]`) as an edge endpoint.
2. WHEN a zone endpoint has no side THEN the engine SHALL pick the zone side facing the other endpoint and the point on it closest to the other endpoint's centre, clamped 24 px from corners.
3. WHERE `fan="bus"` is set the engine SHALL draw a bus bar inside the zone, 10 px from that side, spanning the zone's direct children on that side, with the arrowhead at the border.
4. The engine SHALL exclude edges ending on a zone border from the "edge passes through box" check for that zone.
5. WHEN a PPTX connector targets a zone THEN the connector SHALL be bound to the zone shape.
6. IF `zone:<id>` names no zone THEN the engine SHALL raise `KeyError` naming the id.

**Independent Test**: Scenario table of source positions around a zone; assert endpoint lies on the expected side.

---

### P1: Richer diagnostics and `check --fix` (C1) ⭐ MVP

**User Story**: As an author, I want `check` to find what I currently see only in the PNG and fix the safe cases so that dense diagrams converge in one pass.

**Why P1**: D2 needed 6 render iterations.

**Acceptance Criteria**:

1. The `check` command SHALL report `icon-touches-border`, `header-overlap`, `icon-overflows-box`, `glyph-missing`, `zone-underused`, `zone-clips-child`, `outside-safe-area`, `low-contrast` and `edge-crossings` diagnostics.
2. The engine SHALL attach to each fixable issue a machine-readable fix dict with `op` in `move-label`, `resize`, `nudge`, `shrink-font`.
3. WHEN `check --json` is given THEN the CLI SHALL print issues including their `fix` dicts as JSON.
4. WHEN `check --fix` runs on a YAML spec THEN the CLI SHALL write `<stem>.fixed.yaml` with the safe fixes applied and SHALL leave the source unchanged.
5. WHEN `check --fix` runs on a Python spec THEN the CLI SHALL print one suggested edit per fix (`<element>: w=240`) and SHALL not modify files.
6. WHEN `render --relayout` runs THEN the CLI SHALL apply safe fixes in memory before rendering.
7. WHEN fixes are applied THEN re-running `check` on the fixed spec SHALL report zero issues of the fixed kinds whenever the fix was applicable.
8. IF a fix would move an element outside the canvas safe area THEN the engine SHALL skip that fix and keep the issue.

**Independent Test**: A broken fixture spec (D2-like first iteration) → `check --fix` → fixed spec has zero P0 diagnostics.

---

### P2: Icon aspect ratio (I1)

**User Story**: As an author, I want wordmarks to keep their aspect ratio so that wide logos stay legible.

**Why P2**: Wordmark zones only.

**Acceptance Criteria**:

1. The engine SHALL read an icon's intrinsic aspect ratio from the SVG `viewBox` (or width/height) or the raster size.
2. The engine SHALL fit icons by height with `icon_max_width` (default 4 × height) and centre them vertically in their slot.
3. WHEN a 1:4 wordmark is placed in a 40 px tall header THEN the engine SHALL render it ≥ 24 px tall inside its container.
4. WHERE `variant="wordmark"` or `"symbol"` is given the engine SHALL resolve `<icon>-wordmark` / `<icon>-symbol` aliases from the theme when present and the plain icon otherwise.
5. WHEN an icon-only box uses `align="center"` THEN the engine SHALL centre the icon inside the box.

---

### P2: Badges (I2)

**User Story**: As an author, I want up to 3 small corner badges per box so that platform logos sit on the node.

**Acceptance Criteria**:

1. The engine SHALL accept `badges=[...]` (≤ 3) on boxes in Python and YAML.
2. The engine SHALL size badges at 40 % of the main icon size (minimum 14 px) with a white halo circle 3 px larger.
3. The engine SHALL place badges in the top-right corner, stacking leftward, inset 6 px.
4. The engine SHALL reduce the text-area width so no text line intersects a badge.
5. IF more than 3 badges are given THEN the engine SHALL raise `ValueError`.

---

### P2: Glyph fallback (T2)

**User Story**: As an author, I want missing glyphs to fall back per character so that `×` never renders as tofu.

**Acceptance Criteria**:

1. The engine SHALL check each character against the selected font's cmap at layout time.
2. WHEN a character is missing THEN the engine SHALL fall back to the body font, then to the bundled Noto Sans Symbols 2.
3. The SVG backend SHALL emit the fallback font as a `tspan` font-family run and embed it.
4. The PPTX backend SHALL emit the fallback run with its own `a:latin`/`a:sym` font.
5. The `check` command SHALL report `glyph-missing: '×' (U+00D7) in heading font, fell back to <font>` once per character and font role.
6. The engine SHALL measure fallback runs with the fallback font metrics.

---

### P2: Content-sized boxes and same-size rows (B1)

**User Story**: As an author, I want `w`/`h` optional and rows of equal size so that I stop computing card sizes.

**Acceptance Criteria**:

1. WHEN a box in a fixed-coordinate diagram has `w=0` and `h=0` THEN the engine SHALL size it to its content (icon + title + body + padding) at theme sizes.
2. The engine SHALL provide `with d.row(x=, y=, gap=, same_size=, max_width=)` and `with d.column(...)` context managers that position children.
3. WHERE `same_size=True` the engine SHALL give all members the largest member's size, capped by `max_width` / count.
4. IF members cannot fit within `max_width` after fitting THEN the engine SHALL raise `ValueError` naming the widest member.
5. The existing function forms `d.row(items, ...)` and `d.column(items, ...)` SHALL keep their 0.3 behaviour.
6. WHERE `same_icon_size=True` (I4) the engine SHALL use the smallest member icon size for every member, and `check` SHALL report `icon-size-mismatch` within explicit rows otherwise.

---

### P2: Nested zones sized to children (Z3)

**Acceptance Criteria**:

1. WHERE a zone has `fit="children"` the engine SHALL set its rectangle to the bounding box of its children plus `padding` (default 24) and its header height.
2. The engine SHALL resolve nested `fit="children"` zones innermost first.
3. WHERE `equalize="siblings"` is set on sibling zones the engine SHALL give them the maximum sibling height.
4. The `check` command SHALL report `zone-clips-child` when a child extends past its zone and `zone-underused` when the content fill ratio is below 0.35.
5. The engine SHALL accept `with d.zone(...) as z:` so nodes and zones created inside become its children.

---

### P2: Shared trunks (E3)

**Acceptance Criteria**:

1. The engine SHALL accept `d.bundle([e1, e2, ...], trunk="right"|"left"|"top"|"bottom")` and `fan_in=True` on edges sharing a target.
2. WHEN edges are bundled THEN the engine SHALL route them orthogonally through one shared trunk line placed in the free channel on the trunk side, midway between the sources' extent and the target.
3. WHEN bundled edges share a target THEN the engine SHALL draw one arrowhead at the target.
4. IF bundled edges do not share a target THEN the engine SHALL raise `ValueError`.

---

### P2: Crossing-aware orthogonal routing (E4)

**Acceptance Criteria**:

1. WHERE `route="ortho"` is set on an edge or as `defaults.edge.route` the engine SHALL route the edge orthogonally around nodes using the obstacle router.
2. The router SHALL add a crossing penalty (default 120 px-equivalent) per crossing with already-routed edges.
3. The engine SHALL route ortho edges in declaration order and produce identical routes across runs.
4. The `check` command SHALL report `edge-crossings: n` when n > 0 for the diagram.
5. WHERE `via` or `curve` is set the engine SHALL keep the edge's explicit route.

---

### P2: Automatic legend (L1)

**Acceptance Criteria**:

1. The engine SHALL accept `meaning="..."` on edges and zones.
2. WHERE `d.legend(items="auto")` is called the engine SHALL add one legend row per distinct (colour, dash) edge style and per distinct zone (fill, stroke, dash) style that carries a `meaning`.
3. WHEN the last element with a given meaning is removed THEN the legend SHALL no longer contain that row.
4. The legend SHALL draw edge rows as a short line with the edge's dash/colour and zone rows as a mini rectangle with the zone's fill and outline.
5. WHERE `place="band"` the legend SHALL use the existing annotation band; WHERE `place=(x, y, w, h)` it SHALL render as a card fitted (T1) into that cell.

---

### P3: Grid and constraint helpers (G1, E5)

**Acceptance Criteria**:

1. The engine SHALL provide `d.grid(cols=[...], rows=[...], gutter=)` returning an object indexed `g[col, row]` that yields `(x, y)` usable as `cell=` on nodes and zones.
2. The engine SHALL provide `d.align_x(*nodes)`, `d.align_y(*nodes)` and `d.center_on(node, other)` applied before scene build.
3. WHEN `d.edge(a, b, straight=True)` is drawn between boxes whose spans overlap on one axis THEN the engine SHALL pick anchors on the shared span midpoint so the edge is axis-aligned.
4. IF `straight=True` boxes do not overlap on either axis THEN `check` SHALL report `not-straight` for that edge.
5. The engine SHALL provide `node.left(frac)`-style anchor methods `node.at_left(0.35)` etc. returning anchor strings, keeping `node.left` as a property.

---

### P3: Icon fallback chain and report (I3)

**Acceptance Criteria**:

1. The engine SHALL read `icons.fallback: {concept: [ref, ref, ...]}` from the theme and resolve `concept:<name>` to the first available entry.
2. The engine SHALL record per icon the resolved source: `official` (pack), `theme` (alias/dir), `fallback:<n>`.
3. The CLI SHALL provide `spinagram icons report <paths>` listing each used icon, its resolved reference and source.

---

### P3: Free labels with roles (T3)

**Acceptance Criteria**:

1. The engine SHALL accept `size=` on `d.label(...)` as the font size.
2. WHERE `role="zone-label"|"caption"|"footnote"` is given the engine SHALL apply that theme typography (zone-label: uppercase, letter spacing 0.06 em, zone label colour).
3. WHERE `max_width` is given the engine SHALL wrap the label to that width.

---

### P3: CSS and theme consistency (S1)

**Acceptance Criteria**:

1. The CSS engine SHALL accept `none` for colour properties (`fill`, `stroke`, `color`).
2. The CSS engine SHALL expose element types `zone`, `node`, `edge`, `label` and `chip` to selectors.
3. The engine SHALL render icon-only boxes (no title, no text) with no shadow and no stroke unless styled.

---

### P3: Backend parity (S2)

**Acceptance Criteria**:

1. The test suite SHALL include a parametrized golden check per backend (SVG, PNG, PPTX) for dash patterns, icon-only boxes, classed free labels, edges to absolute points, zone targets and fallback glyphs.

---

### P3: Output naming and reproducibility (O1)

**Acceptance Criteria**:

1. WHERE `output="name"` is set on a diagram the renderer SHALL write `<name>.<ext>` for each format.
2. WHERE `render --name-from id|file|slug` is given the renderer SHALL derive file names from that source (default `slug`).
3. WHERE a spec declares `requires` the CLI SHALL warn `version-mismatch` when the installed version does not satisfy it.
4. The SVG backend SHALL write a `<metadata>` content hash (sha256 of the scene) that is identical for identical input.

---

## Edge Cases

- IF a box is narrower than its padding THEN fitting SHALL stop at `min_scale` and report `overflow-x` (no infinite loop).
- IF text is empty THEN fitting SHALL be a no-op.
- WHEN a zone has an icon that cannot be resolved THEN the header SHALL lay out the label alone and warn as today.
- IF an edge targets a zone that contains its source THEN the engine SHALL attach to the inner face of the nearest side.
- IF the E1 candidate list is exhausted on a canvas edge THEN placement SHALL still be deterministic.
- IF `check --fix` finds no fixable issue THEN it SHALL not write a `.fixed.yaml` file.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| TXT-01 | P1: Text fits (wrap spaces) | Execute | Implementing |
| TXT-02 | P1: Text fits (break tokens) | Execute | Implementing |
| TXT-03 | P1: Text fits (CIDR intact) | Execute | Implementing |
| TXT-04 | P1: Text fits (shrink) | Execute | Implementing |
| TXT-05 | P1: Text fits (grow) | Execute | Implementing |
| TXT-06 | P1: Text fits (fit=none) | Execute | Implementing |
| TXT-07 | P1: Text fits (overflow detail) | Execute | Implementing |
| TXT-08 | P1: Text fits (options/defaults) | Execute | Implementing |
| TXT-09 | P1: Text fits (letter spacing) | Execute | Implementing |
| ZON-01 | P1: Zone header (padding) | Execute | Implementing |
| ZON-02 | P1: Zone header (icon size) | Execute | Implementing |
| ZON-03 | P1: Zone header (label centre) | Execute | Implementing |
| ZON-04 | P1: Zone header (chips) | Execute | Implementing |
| ZON-05 | P1: Zone header (strip) | Execute | Implementing |
| ZON-06 | P1: Zone header (content_top) | Execute | Implementing |
| ZON-07 | P1: Zone header (flush opt-out) | Execute | Implementing |
| ZON-08 | P1: Zone header (upper) | Execute | Implementing |
| ZON-09 | P1: Zone outlines (dash values) | Execute | Implementing |
| ZON-10 | P1: Zone outlines (stroke/fill) | Execute | Implementing |
| ZON-11 | P1: Zone outlines (id/class CSS) | Execute | Implementing |
| ZON-12 | P1: Zone outlines (SVG/PPTX parity) | Execute | Implementing |
| ZON-13 | P1: Zone outlines (fill none CSS) | Execute | Implementing |
| EDG-01 | P1: Edge labels (candidates) | Execute | Implementing |
| EDG-02 | P1: Edge labels (rejection) | Execute | Implementing |
| EDG-03 | P1: Edge labels (first free) | Execute | Implementing |
| EDG-04 | P1: Edge labels (fallback + report) | Execute | Implementing |
| EDG-05 | P1: Edge labels (label_at) | Execute | Implementing |
| EDG-06 | P1: Edge labels (deterministic) | Execute | Implementing |
| EDG-07 | P1: Zone targets (endpoint forms) | Execute | Implementing |
| EDG-08 | P1: Zone targets (side/point) | Execute | Implementing |
| EDG-09 | P1: Zone targets (bus) | Execute | Implementing |
| EDG-10 | P1: Zone targets (check exclusion) | Execute | Implementing |
| EDG-11 | P1: Zone targets (PPTX binding) | Execute | Implementing |
| EDG-12 | P1: Zone targets (unknown id) | Execute | Implementing |
| CHK-01 | P1: Diagnostics (new kinds) | Tasks | In Tasks |
| CHK-02 | P1: Diagnostics (fix dicts) | Execute | Implementing |
| CHK-03 | P1: Diagnostics (--json) | Execute | Implementing |
| CHK-04 | P1: Fix (YAML) | Execute | Implementing |
| CHK-05 | P1: Fix (Python) | Execute | Implementing |
| CHK-06 | P1: Fix (render --relayout) | Execute | Implementing |
| CHK-07 | P1: Fix (convergence) | Execute | Implementing |
| CHK-08 | P1: Fix (safe-area guard) | Execute | Implementing |
| ICN-01 | P2: Icon aspect (intrinsic ratio) | Execute | Implementing |
| ICN-02 | P2: Icon aspect (fit by height) | Execute | Implementing |
| ICN-03 | P2: Icon aspect (wordmark ≥24px) | Execute | Implementing |
| ICN-04 | P2: Icon aspect (variant) | Execute | Implementing |
| ICN-05 | P2: Icon aspect (centred icon-only) | Execute | Implementing |
| ICN-06 | P2: Badges (API) | Execute | Implementing |
| ICN-07 | P2: Badges (size/halo) | Execute | Implementing |
| ICN-08 | P2: Badges (placement) | Execute | Implementing |
| ICN-09 | P2: Badges (text clearance) | Execute | Implementing |
| ICN-10 | P2: Badges (cap) | Execute | Implementing |
| TXT-10 | P2: Glyph fallback (cmap) | Execute | Implementing |
| TXT-11 | P2: Glyph fallback (chain) | Execute | Implementing |
| TXT-12 | P2: Glyph fallback (SVG) | Execute | Implementing |
| TXT-13 | P2: Glyph fallback (PPTX) | Execute | Implementing |
| TXT-14 | P2: Glyph fallback (check) | Execute | Implementing |
| TXT-15 | P2: Glyph fallback (metrics) | Execute | Implementing |
| BOX-01 | P2: Content-sized boxes | Tasks | In Tasks |
| BOX-02 | P2: Row/column context managers | Tasks | In Tasks |
| BOX-03 | P2: same_size | Tasks | In Tasks |
| BOX-04 | P2: max_width failure | Tasks | In Tasks |
| BOX-05 | P2: Legacy row/column | Tasks | In Tasks |
| BOX-06 | P2: same_icon_size (I4) | Tasks | In Tasks |
| ZON-14 | P2: Zones fit children | Tasks | In Tasks |
| ZON-15 | P2: Nested resolution order | Tasks | In Tasks |
| ZON-16 | P2: equalize siblings | Tasks | In Tasks |
| ZON-17 | P2: clips/underused checks | Tasks | In Tasks |
| ZON-18 | P2: zone context manager | Tasks | In Tasks |
| EDG-13 | P2: Bundle API | Tasks | In Tasks |
| EDG-14 | P2: Bundle trunk routing | Tasks | In Tasks |
| EDG-15 | P2: Bundle single arrowhead | Tasks | In Tasks |
| EDG-16 | P2: Bundle target mismatch | Tasks | In Tasks |
| EDG-17 | P2: Ortho routing | Tasks | In Tasks |
| EDG-18 | P2: Crossing penalty | Tasks | In Tasks |
| EDG-19 | P2: Ortho determinism | Tasks | In Tasks |
| EDG-20 | P2: edge-crossings check | Tasks | In Tasks |
| EDG-21 | P2: explicit route kept | Tasks | In Tasks |
| LEG-01 | P2: meaning= | Tasks | In Tasks |
| LEG-02 | P2: auto rows | Tasks | In Tasks |
| LEG-03 | P2: row removal | Tasks | In Tasks |
| LEG-04 | P2: row swatches | Tasks | In Tasks |
| LEG-05 | P2: placement | Tasks | In Tasks |
| GRD-01 | P3: grid cells | Tasks | In Tasks |
| GRD-02 | P3: align helpers | Tasks | In Tasks |
| GRD-03 | P3: straight edges | Tasks | In Tasks |
| GRD-04 | P3: not-straight check | Tasks | In Tasks |
| GRD-05 | P3: anchor methods (E5) | Tasks | In Tasks |
| ICN-11 | P3: fallback chain | Tasks | In Tasks |
| ICN-12 | P3: icon source record | Tasks | In Tasks |
| ICN-13 | P3: icons report CLI | Tasks | In Tasks |
| TXT-16 | P3: label size= | Tasks | In Tasks |
| TXT-17 | P3: label roles | Tasks | In Tasks |
| TXT-18 | P3: label max_width | Tasks | In Tasks |
| STY-01 | P3: CSS none colours | Execute | Implementing |
| STY-02 | P3: CSS element types | Tasks | In Tasks |
| STY-03 | P3: icon-only box defaults | Tasks | In Tasks |
| STY-04 | P3: backend golden parity (S2) | Tasks | In Tasks |
| OUT-01 | P3: output= names | Tasks | In Tasks |
| OUT-02 | P3: --name-from | Tasks | In Tasks |
| OUT-03 | P3: requires warning | Tasks | In Tasks |
| OUT-04 | P3: SVG metadata hash | Tasks | In Tasks |

**Coverage:** 102 total, 102 mapped to tasks (T1–T60), 0 unmapped

---

## Success Criteria

- [ ] Every Appendix workaround has a public replacement covered by a DDT scenario.
- [ ] Full test suite green; previous 516 tests still pass (golden hash updates pinned by intent tests).
- [ ] A D2-like fixture passes `check --fix` with zero remaining P0 diagnostics.

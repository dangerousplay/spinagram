# Layout engine improvements: text, overflow, positioning

**Goal:** the author declares content and intent: what exists, how it is grouped, and how it relates. The engine
owns text fitting, overflow, positioning, spacing, icon placement and edge routing. `check` catches anything the
engine cannot fix itself and says how to fix it.

**Basis.** These notes come from building two architecture diagrams with a corporate brand theme (an `extends: default` theme with its own fonts, icon pack and CSS) on 2026-10-20. Both
were dense: about 60 nodes, nested zones, about 25 edges each.

- **D1:** an autoscaling CI runner fleet on OpenStack. Projects contain networks, networks contain AZs, and AZs
  contain VM groups. Egress goes through NAT to a destinations group.
- **D2:** a load-balanced Git service across two sites (VMware clusters). It has a NAS with replication and a
  log pipeline to an observability SaaS.

Engine versions:
- The diagrams were rendered with the published **spinagram 0.3.0** package (uv tool install).
- This repository (`diagramkit` 0.1.0, HEAD `d2ccf78`, 2026-10-08, uncommitted changes present) is the earlier
  internal engine. It shares the same model (`Diagram.zone(..., icon=)`, absolute coordinates). Every item below
  applies to both unless noted.

Hostnames, IPs and product names were replaced with placeholders (`node-a`, `10.0.0.0/24`, `lb-pool-https`).

---

## Prioritised roadmap

| # | Item | Pri | Effort |
|---|---|---|---|
| 1 | [T1](#t1-fit-text-to-the-box-instead-of-only-reporting-overflow) Fit text in the box (wrap, break long tokens, shrink to a minimum) | P0 | M |
| 2 | [Z1](#z1-zone-header-with-inset-icon-and-label) Zone header with an inset icon, label and optional chips | P0 | S |
| 3 | [Z2](#z2-dashed-and-dotted-outlines-as-first-class-zone-styles) Dashed and dotted outlines as first-class zone styles | P0 | S |
| 4 | [E1](#e1-edge-labels-avoid-boxes-labels-and-their-own-arrowhead) Edge labels that avoid boxes, other labels and their own arrowhead | P0 | M |
| 5 | [E2](#e2-zones-and-zone-borders-as-edge-targets) Zones and zone borders as edge targets (fan-in to a group) | P0 | M |
| 6 | [C1](#c1-check---fix-and-richer-diagnostics) `check --fix` and richer diagnostics | P0 | L |
| 7 | [I1](#i1-icon-placement-that-respects-aspect-ratio-wordmarks) Icon placement that respects aspect ratio (wordmarks) | P1 | S |
| 8 | [I2](#i2-badges-more-than-one-icon-per-card) Badges: more than one icon per card | P1 | M |
| 9 | [T2](#t2-glyph-coverage-fallback) Glyph-coverage fallback per character | P1 | S |
| 10 | [B1](#b1-content-sized-boxes-and-equal-size-rows) Content-sized boxes and equal-size rows and columns | P1 | M |
| 11 | [Z3](#z3-nested-zones-sized-to-their-children) Nested zones sized to their children | P1 | M |
| 12 | [E3](#e3-shared-trunks-and-buses) Shared trunks and buses (many-to-one routing) | P1 | M |
| 13 | [E4](#e4-crossing-aware-routing-in-fixed-layouts) Crossing-aware orthogonal routing in fixed layouts | P1 | L |
| 14 | [L1](#l1-automatic-legend-from-used-styles) Automatic legend from the styles actually used | P1 | M |
| 15 | [G1](#g1-grid-and-constraint-layout-for-hand-placed-slides) Grid and constraint layout for hand-placed slides | P2 | L |
| 16 | [I3](#i3-icon-pack-gaps-and-a-declared-fallback-chain) Icon pack gaps and a declared fallback chain | P2 | S |
| 17 | [S1](#s1-css-and-theme-consistency) CSS and theme consistency (zones, labels, `none`) | P2 | S |
| 18 | [S2](#s2-backend-parity-svg-png-pptx) Backend parity (SVG, PNG, PPTX) for outlines and chips | P2 | S |
| 19 | [O1](#o1-output-naming-and-reproducibility) Output naming, determinism and version pinning | P2 | S |

Effort: S ≈ ≤2 days, M ≈ 1 week, L ≈ 2+ weeks.

---

## Text

### T1. Fit text to the box instead of only reporting overflow

- **Problem.** Long single tokens (hostnames, CIDR lists, `runner-*-<template>-*`) and long titles overflow the
  box. Today `check` reports `overflow-x` / `overflow-y`, and the author fixes it by hand: widen the box, shrink
  the font or shorten the text.
- **Evidence.**
  - D2: `lb-pool-https-8081` overflowed a 230 px card (`'…' is 175px > 166px`). I widened every pool card to 240
    and moved the column.
  - D1: subnet cards with `name + CIDR` and manager cards with 3-line bodies were resized by trial and error,
    over several renders.
  - Markdown-like characters in text (`*` in `runner-*-x-*`) were read as emphasis by a downstream converter.
    The engine should treat text as literal.
- **Proposed behaviour.** Fitting runs in this order and stops at the first step that fits:
  1. Wrap at spaces.
  2. Wrap at safe break points inside long tokens: after `-`, `.`, `/`, `:` and `·`, never splitting
     `10.0.0.0/24`. Use a zero-width marker, without inserting a hyphen into technical tokens.
  3. Shrink the font by 1 px steps down to `min_size` (theme default: 85 % of the base size).
  4. Grow the box height if the zone or grid allows it.
  5. Only then report overflow, naming the strategy that failed.
  Fitting uses the real font metrics (already true for the width), including letter spacing on uppercase zone
  labels.
- **API sketch.**
  ```python
  d.box("lb-pool-https-8081", text="8 members · nginx :8081",
        fit="shrink", min_title_size=14, break_on="-./:·")   # defaults come from the theme
  ```
  ```yaml
  defaults: {node: {fit: shrink-then-grow, min_scale: 0.85, break_on: "-./:·"}}
  ```
- **Acceptance.** A box of fixed width receives tokens of growing length (10 to 60 characters). The engine must
  never draw text outside the box. `check` reports overflow only when `min_size` and growth are exhausted.
  Golden test with `10.0.0.0/22 · 10.0.8.0/21` staying unbroken.
- **Priority** P0 · **Effort** M.

### T2. Glyph-coverage fallback

- **Problem.** The theme's heading font has no `×`. The title "Managers default · 2×" rendered as "2⸝". Nothing
  warned about it.
- **Evidence.** D1 manager card titles. Worked around by writing "(2)" instead of "2×".
- **Proposed behaviour.**
  - At layout time, check every glyph against the font's cmap.
  - Fall back per character to the body font, then to a bundled symbol font (e.g. Noto Sans Symbols).
  - Embed the fallback in SVG and PPTX.
  - `check` reports `glyph-missing: '×' (U+00D7) in heading font, fell back to <font>`.
- **Acceptance.** Render `"× → ⚠ ✓ ·"` in every theme font role. No tofu or substitute glyphs in the PNG, and
  `check` lists each fallback.
- **Priority** P1 · **Effort** S.

### T3. Free labels with roles

- **Problem.** `d.label(...)` takes `title_size` (passing `size=` crashes with `cannot unpack non-iterable
  int`). Free labels used as zone headers needed their own CSS class to match zone-label typography.
- **Proposed behaviour.**
  - Accept `size=`.
  - Add `role="zone-label" | "caption" | "footnote"` so a label inherits the matching theme typography
    (uppercase, tracking, colour).
  - Wrap labels to `max_width` when it is given.
- **Priority** P2 · **Effort** S.

---

## Boxes and layout

### B1. Content-sized boxes and equal-size rows

- **Problem.** Every box needed explicit `w`/`h`. Rows looked consistent only because the author computed
  sizes, and cards with short text kept large empty areas.
- **Evidence.** D2 node row (3 × 196 px). D1 VM cards (height 36 after two iterations). D2 right column (cards
  resized to fit the 80 px margin).
- **Proposed behaviour.**
  - `w`/`h` become optional.
  - The engine measures content (icon + title + body at the theme sizes), then applies `same_size` across a row,
    column or group: the largest member wins, capped by the available width.
- **API sketch.**
  ```python
  with d.row(x=928, y=294, gap=12, same_size=True, max_width=612):
      for n in nodes: d.box(n.name, text=n.role, icon="logos:gitlab")
  ```
- **Acceptance.** A row of three cards with titles of different lengths renders with equal sizes, no overflow,
  within `max_width`. It fails loudly if that is impossible.
- **Priority** P1 · **Effort** M.

### G1. Grid and constraint layout for hand-placed slides

- **Problem.** Fixed-coordinate slides (the only way to get a precise architecture view) required manual
  arithmetic: column x, gaps, label baselines, `@0.9383` edge fractions so that arrows stay vertical. Every
  change cascaded into many coordinate edits.
- **Evidence.**
  - D2 needed edges anchored at `nfs.top@0.9383` and `gitlab.bottom@0.9211`, both computed by hand.
  - D1 egress anchors at `eg.bottom@0.7762`.
  - D2 (four iterations) needed `y` shifts in AZ areas to stop zone labels colliding with cards.
- **Proposed behaviour.**
  - A light constraint layer: named columns and rows, alignment constraints (`align_x(a, b)`, `center_on(edge)`)
    and "vertical edge" intents.
  - An edge declared `straight=True` between two boxes in the same column aligns its anchors automatically.
- **API sketch.**
  ```python
  g = d.grid(cols=[80, 280, 900, 1600], rows=[175, 772], gutter=20)
  nfs = d.box(..., cell=g[2, 1])
  d.edge("net.bottom", nfs.top, straight=True)       # engine picks matching x on both ends
  ```
- **Priority** P2 · **Effort** L.

---

## Zones and areas

### Z1. Zone header with inset icon and label

- **Problem.** `d.zone(label, icon=...)` draws the icon flush at `(z.x, z.y)`, on top of the border, at a fixed
  32 px, with the label after it. The result:
  - Logos sit on dashed and dotted outlines and overflow rounded corners.
  - Logos look different sizes across zones.
  - The label is not vertically centred on the icon.
  - Uppercasing applies only to the zone label.
- **Evidence.** D2's F5 badge overflowed the corner. The VMware symbol was faint and touched the dotted border,
  the Dell logo sat on the NAS corner, and the GitLab logo sat on the dashed network border.
  - D1 had the same problem on the OpenStack and Neutron headers.
  - **Workaround in both specs:**
    1. Draw a zone without a label.
    2. Add a `d.box(None, icon=..., class_="chip")` 40 px tall, 14 px from the corner, with
       `width = icon + 20` (120 px for a wordmark).
    3. Add `d.label(LABEL.upper(), class_="hdr")` at a computed baseline.
  - Header items then collided with content, so the content was pushed down by hand. `align="center"` on an
    icon-only box moved the icon to the top of the box and overflowed it. The default left alignment is
    required.
- **Proposed behaviour.**
  - A header model owned by the engine: `padding` (default 14), `icon_size` (theme), a vertically centred label,
    and an optional row of `chips` (logos or badges).
  - Content placement starts below the header automatically (`content_top = header.bottom + gap`).
  - Zones get an optional header **strip**: a 4–6 px accent bar or tinted band from the theme token.
- **API sketch.**
  ```python
  d.zone("AZ site-a · RHEL 9", style="az", icon=["logos:vmware", "logos:redhat"],
         header={"padding": 14, "strip": "green"})
  ```
  ```yaml
  zone: {header: {padding: 14, icon_size: 28, chip: true, strip: null, label_upper: true}}
  ```
- **Acceptance.**
  - Golden PNG crops of the four corners: icon bounding box ≥ padding from the outline, the same size for all
    zones, label centre within ±1 px of the icon centre.
  - `check` reports `icon-touches-border` if an override violates this.
- **Priority** P0 · **Effort** S.

### Z2. Dashed and dotted outlines as first-class zone styles

- **Problem.** Zone styles support `dashed: true` (fixed `10 7`) but no pattern, no dotted style and no stroke
  width per pattern. CSS `stroke-dasharray` reaches only zones that carry a `gid`, and only zones built from
  auto-layout `Group`s get one. The CSS also rejects `fill: none` (`cannot resolve colour 'none'`).
- **Evidence.** To express "network = dashed, AZ = dotted", both specs append an empty
  `Group(id=gid, label=None)` to `d.groups` and set `zone.gid = gid` by hand, then style `#gid` in a
  stylesheet. This relies on internals and could break in any release (see Appendix).
- **Proposed behaviour.**
  - `stroke`, `stroke_width`, `dash` (`solid | dashed | dotted | [pattern]`) and `fill` (including `none`) on
    zone styles and on `d.zone(...)`.
  - Every zone gets an `id` (or `gid`) so CSS can always target it with `#id` or `.class`.
- **API sketch.**
  ```python
  d.zone("subnet-a · 10.0.0.0/24", id="net-a", dash="dashed", stroke="green-dark")
  d.zone("AZ a", id="az-a", dash="dotted", fill="green-bg")
  ```
  ```css
  zone.az { stroke-dasharray: 2 6; }   /* also works without a gid */
  ```
- **Acceptance.** The same zone renders with the same dash pattern in SVG, PNG and PPTX (`custDash`). A test
  asserts the PPTX XML contains the expected pattern.
- **Priority** P0 · **Effort** S.

### Z3. Nested zones sized to their children

- **Problem.** Nested zones (project, then network, then AZ, then VM group) were sized by hand. When one sibling
  had less content (the single-AZ project in D1), its area kept the sibling's height and showed a large blank
  region. When content grew, outer zones clipped it and `check` did not report it.
- **Evidence.** D1: the second project's AZ area was sized to match the first project and left ~120 px empty.
  D2: the AZ height was raised twice because the header and a 2-row card stack did not fit.
- **Proposed behaviour.**
  - Zones accept `fit="children"` with padding and a header (Z1). The engine computes the bounding box of the
    children, including nested zones.
  - `equalize="siblings"` is opt-in, so blank space is never a silent default.
  - `check` reports `zone-clips-child` and `zone-underused` (fill ratio < threshold).
- **Priority** P1 · **Effort** M.

---

## Icons

### I1. Icon placement that respects aspect ratio (wordmarks)

- **Problem.** Icons are placed in a square of `icon_size`. Wide wordmarks (`logos:vmware`) become tiny, or
  push out of a short box when `icon_size` is raised. Square symbols for the same vendor (`selfhosted:vmware`)
  are too pale to recognise.
- **Evidence.** D2: the VMware wordmark needed a 120×40 chip with `icon_size=100`. With `align="center"` it
  rendered below the chip, overlapping the next row.
- **Proposed behaviour.**
  - Icons carry their intrinsic aspect ratio from the pack metadata. Placement fits by height, with a
    `max_width`, and centres vertically.
  - A `variant="symbol" | "wordmark"` hint lets the theme pick the right asset.
- **Acceptance.** A 1:4 wordmark in a 40 px tall header renders at least 24 px tall, centred, inside its
  container.
- **Priority** P1 · **Effort** S.

### I2. Badges: more than one icon per card

- **Problem.** A card has one icon. "Git node on VMware running RHEL" needed the RHEL and VMware logos at zone
  level, not on the node.
- **Proposed behaviour.** Up to 3 small corner badges, auto-sized at about 40 % of the main icon, placed in
  `top-right` / `bottom-right`, with a white halo. Badges never overlap text, because text width is reduced
  to make room.
- **API sketch.** `d.box("node-a", icon="logos:gitlab", badges=["logos:redhat", "logos:vmware"])`
- **Priority** P1 · **Effort** M.

### I3. Icon pack gaps and a declared fallback chain

- **Problem.** No official icon was found for:
  - F5 (load balancer vendor);
  - an OpenStack availability zone;
  - GitLab Runner (falls back to the GitLab logo);
  - NAT;
  - a generic S3-compatible cache whose backend is unknown.
  In each case the author picked a fallback by hand and documented it in a README.
- **Proposed behaviour.**
  - Each theme declares an `icons.fallback` chain per concept, e.g. `load-balancer: [logos:f5,
    network:loadbalancer-circle-green]`. Resolution records which entry was used.
  - `spinagram icons report` lists every icon used with its source (official, theme, fallback). That output can
    replace the hand-written README tables.
- **Priority** P2 · **Effort** S.

### I4. Icon size consistency per row

- **Problem.** `icon_size` was set per box to keep rows uniform. Theme `icon_scale` derives the icon size from
  the box height, so rows with mixed heights got mixed icon sizes.
- **Proposed behaviour.** `same_icon_size=True` on a row or group, with a default derived from the smallest
  member. `check` warns about `icon-size-mismatch` within a row.
- **Priority** P2 · **Effort** S.

---

## Edges

### E1. Edge labels avoid boxes, labels and their own arrowhead

- **Problem.**
  - Edge labels default to the edge midpoint. On short gaps they hide the arrowhead or cover a box. `check`
    detects this, but every fix is a hand-set `label_at=(x, y)`.
  - Labels also overlapped a zone header ("replicação" over the NAS area title) without any warning.
- **Evidence.**
  - D2: the `logs` label covered the observability card, so it was dropped and moved to the legend.
  - D2: the `replicação` label covered the arrowhead and then the zone header. It ended up below the cards.
  - D1: `IP da VM`, `IP NAT` and `NFS` all needed `label_at`.
- **Proposed behaviour.** Candidate positions are tried in order: midpoint, then offsets along the edge, then
  either side of the edge at the label's half-height plus 6 px. Each candidate is scored against:
  - box rectangles;
  - zone header rectangles;
  - other labels;
  - the arrowhead region (last 14 px);
  - the canvas margins.
  The best candidate wins. If none is clean, `check` reports it with the candidates it tried.
- **Acceptance.** With 200 random short edges between fixed boxes, no label intersects a box, header or
  arrowhead whenever at least one free candidate exists. The result is deterministic for the same input.
- **Priority** P0 · **Effort** M.

### E2. Zones and zone borders as edge targets

- **Problem.** "Traffic goes to all destinations" and "the pool reaches every node in the network" are
  relationships to a group. They had to be drawn to absolute points on the zone border, computed by hand.
- **Evidence.**
  - D1: `d.edge(eg.top, (720, 298))` to hit the destinations zone border.
  - D2: `d.edge(pool.right, (900, 377))` to the network zone border, replacing four crossing node edges.
- **Proposed behaviour.**
  - Zones become valid endpoints: `d.edge(pool, net_zone)`.
  - The engine picks the nearest side and a free point on it. It can draw a short "bus" bar inside the zone,
    with the arrowhead at the border.
  - Edges ending on a zone border are excluded from "edge passes through box" checks.
- **API sketch.** `d.edge(pool, "zone:net-a", label="HTTPS", fan="bus")`
- **Priority** P0 · **Effort** M.

### E3. Shared trunks and buses

- **Problem.** Two sources to one target (two log shippers to one observability service) should share a trunk.
  Hand-placed `via` points were needed.
- **Evidence.** D2: `via=[[1580, y_src], [1580, y_dst]]` on both edges. D1: the NAT path with
  `via=[[1620, 243]]`.
- **Proposed behaviour.** `d.bundle([e1, e2], trunk="right")` or `fan_in=True` on edges with the same target.
  The engine routes a shared orthogonal trunk in the free channel between columns and merges the arrowheads.
- **Priority** P1 · **Effort** M.

### E4. Crossing-aware routing in fixed layouts

- **Problem.**
  - With absolute coordinates, edges are straight or follow hand-made `via`. Crossing edges (two pools × two
    sites) were reduced only by redesigning the semantics (see E2).
  - Diagonal edges from fan-outs (clients → three virtual servers) are acceptable, but they cross other edges
    at random angles.
- **Proposed behaviour.**
  - An orthogonal router for unanchored edges in fixed layouts. It uses obstacle-aware A* on a visibility
    graph of box and zone corners, penalises crossings and bends, and keeps channels between columns.
  - `route="ortho"` per edge or as the diagram default.
  - `check` reports the crossing count and suggests a swap order of anchors.
- **Priority** P1 · **Effort** L.

### E5. Anchor ergonomics

- **Problem.** Anchors are strings (`"node.left@0.35"`), so ids must be interpolated (`"%s.left@0.35" %
  box.id`). There is no `node.left(0.35)` helper, and straight-edge alignment is manual (see G1).
- **Proposed behaviour.** `box.left(0.35)` returns an anchor, and `d.edge(a, b, straight=True)` picks
  fractions that make the edge axis-aligned when the geometry allows it.
- **Priority** P2 · **Effort** S.

---

## Legend

### L1. Automatic legend from used styles

- **Problem.** `add_legend` maps classes and styles to labels in the annotation band. It cannot show line
  styles (solid, dashed, colour) or zone outline semantics, and it takes canvas space outside the layout.
  - Both diagrams built the legend by hand from tiny zones and short edges between absolute points.
  - The tiny legend zones needed the same empty-Group trick (Z2).
- **Proposed behaviour.**
  - `d.legend(place="cell" | "band", items="auto")` collects every edge style (colour + dash) and zone style
    (fill, outline pattern) actually used.
  - Each semantic gets a label from the spec (`edge(..., meaning="replication")`, `zone(..., meaning="network")`)
    or from the theme.
  - The legend renders as a card that fits its cell (T1).
- **Acceptance.** Adding a dashed grey edge with `meaning="replication"` adds exactly one legend row. Removing
  the last such edge removes the row.
- **Priority** P1 · **Effort** M.

---

## Checks

### C1. `check --fix` and richer diagnostics

- **Problem.** `check` found real issues (label covers box, label hides arrowhead, overflow-x). It did not
  find these, all visible only in the PNG:
  - icons touching or crossing zone borders;
  - zone headers overlapped by content or labels;
  - zone headers overlapped by a free label at the same baseline;
  - wordmarks rendering outside their box;
  - missing glyphs (T2);
  - large unused areas;
  - content outside the safe margin (the right column ended 13 px past the 80 px margin).
  Every issue needed a render, a visual review and manual coordinate edits. D2 took 6 render iterations.
- **Proposed behaviour.**
  - New diagnostics:
    - `icon-touches-border`
    - `header-overlap`
    - `icon-overflows-box`
    - `glyph-missing`
    - `zone-underused`
    - `zone-clips-child`
    - `outside-safe-area`
    - `low-contrast` (WCAG contrast of text and icon against the fill, e.g. a green icon on a dark-green card)
    - `edge-crossings: n`
  - Each diagnostic carries a machine-readable fix: `{"op": "move-label", "edge": "e13", "to": [x, y]}`,
    `{"op": "resize", "node": "...", "w": 240}`.
  - `check --fix` applies the safe ones to a frozen copy of the spec (YAML), or prints a diff for Python specs.
  - `render --relayout` runs the fixes in memory.
- **Acceptance.** The D2 spec at its first iteration (before the hand fixes listed in the Appendix) passes
  `check --fix` with zero remaining P0 diagnostics, and the PNG matches the hand-fixed one within tolerance.
- **Priority** P0 · **Effort** L.

---

## Theme, CSS and backends

### S1. CSS and theme consistency

- **Problem.**
  - CSS reaches zones only through `group:<gid>` (Z2).
  - `fill: none` is rejected even though zone styles accept `fill: none` in YAML.
  - Free labels and icon-only boxes need classes to opt out of card styling (shadow, stroke).
  - Python specs can register empty `Group`s, but nothing documents that this is safe.
- **Proposed behaviour.**
  - A single selector model for every element kind (`zone`, `node`, `edge`, `label`, `chip`).
  - `none` accepted for colour properties.
  - Documented defaults for icon-only boxes: no shadow, no stroke unless styled.
- **Priority** P2 · **Effort** S.

### S2. Backend parity (SVG, PNG, PPTX)

- **Observation.** Dashed and dotted zone outlines set through CSS did reach PPTX as `custDash` (verified: 16
  custom dashes in the slide XML), and chips rendered as native shapes. Parity is good today and should be
  locked with tests.
- **Proposed behaviour.** A golden test per backend for:
  - dash patterns;
  - icon-only boxes;
  - free labels with classes;
  - edges to absolute points;
  - fallback glyphs (T2).
  PPTX connectors should stay bound when an edge targets a zone (E2).
- **Priority** P2 · **Effort** S.

---

## Other

### O1. Output naming and reproducibility

- **Problem.**
  - Output files are named `<id>-<slugified title>.*` plus a shared `diagrams.pptx`. Every project copies them
    to stable names afterwards (`cp out/R01-... runners.svg`).
  - The engine behaviour that the workarounds rely on (zone `gid`, icon alignment) is version-specific and not
    pinned in the spec.
- **Proposed behaviour.**
  - `Diagram(..., output="runners-network")`, or `render --name-from id|file`, writes stable names. Per-diagram
    PPTX is optional.
  - Specs can declare `requires = "spinagram>=0.4,<0.5"`, and the CLI warns on mismatch.
  - Rendering stays deterministic for the same input. Add a hash in the SVG metadata so CI can detect drift.
- **Priority** P2 · **Effort** S.

---

## Appendix: workarounds in the current specs

Remove these once the corresponding item ships.

| Workaround | Where | Replaced by |
|---|---|---|
| Append an empty `Group` and set `zone.gid` to style dashed/dotted outlines through `#gid` CSS | D1 `area()`, D2 `area()`, D2 legend swatches | Z2, S1 |
| Header "chip": icon-only `d.box(None, icon=..., class_="chip")` 40 px tall, 14 px inset, width = icon + 20 (120 for a wordmark), plus `d.label(LABEL.upper(), class_="hdr")` at baseline `y + 38`; zone drawn without a label | D1 `area(icon=...)`, D2 `area(chips=...)` | Z1, I1 |
| Left alignment for icon-only boxes (`align="center"` pushes the icon out of the box) | both specs | I1 |
| Content pushed down by hand below headers (AZ y offsets, subnets moved right of the network label) | D1 project/network, D2 AZ rows | Z1, Z3 |
| `"(2)"` instead of `"2×"` in titles (missing glyph) | D1 manager titles | T2 |
| Hand-computed anchor fractions (`@0.9383`, `@0.7762`, `@0.9211`) for straight vertical edges | D1 egress, D2 NFS edge | G1, E5 |
| Absolute-point endpoints on zone borders for group targets | D1 egress → destinations, D2 pools → network | E2 |
| Hand `via` trunks for many-to-one edges | D2 log shippers → observability, D1 NAT path | E3 |
| `label_at` on most labelled edges; one label removed (`logs`) and moved to the legend | both | E1 |
| Hand-built legend (short edges between absolute points, tiny zones, free labels) | D2 | L1 |
| Pools widened from 230 to 240 px and font sizes tuned per box to clear `overflow-x` | D2 | T1, B1 |
| Right column resized to stay inside the 80 px safe margin after visual review | D2 | C1 (`outside-safe-area`) |
| Sibling zone sized to match its neighbour, leaving blank space | D1 single-AZ project | Z3 |
| Icon fallbacks chosen by hand and listed in a README (load balancer, NAT, cache, AZ, runner) | both READMEs | I3 |
| Outputs renamed with `cp` after each render | both | O1 |

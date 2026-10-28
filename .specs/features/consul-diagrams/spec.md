# Consul Diagram Improvements Specification

Source roadmap: `.specs/features/consul-diagrams/roadmap.md` (copy of `improvements-consul-diagrams.md`, 2026-10-28).
Scenario numbers (#1…#13) refer to that roadmap; item codes such as E2, T2 and Z3 refer to
`.specs/features/layout-engine/roadmap.md`.

## Problem Statement

Five brand-themed Consul-on-AWS diagrams (A01–A05, spinagram 0.4.0) needed hand fixes that the engine or
`check` should own. Edges crossed zone headers, centred icons touched titles, and every card and zone carried
absolute `x/y/w/h`. Snakes, zone targets and helpers were copied between repos, and themes resolved only from a
local clone. `check` reported **0 issues** while two of these defects were visible in the PNG, so a person had
to review every render.

## Goals

- [ ] `check` reports scenarios #1 and #2 (`edge-crosses-zone-header`, `icon-overlaps-text`) on the
      fixtures that reproduce them, and the engine has an option that renders each one clean.
- [ ] The A03-like fixture (zone band + row of cards) is written with no `x=` on cards or zones and renders
      within 2 px of its hand-placed twin.
- [ ] A 12-step, 3-phase snake (A04) is one `d.snake(...)` call with zero hand anchors, `via` points or
      reversed lists, and `check` reports no header crossing and no edge through a box.
- [ ] Specs stop vendoring helpers: `d[id]`, `d.distribute`, `route="elbow"` and zone anchors are public.
- [ ] A theme `extends: <name>` resolves on CI through `SPINAGRAM_THEME_PATH` or an installed package.
- [ ] An SVG with a ~400 KB embedded brand font shrinks below 25 % of its size with the default `--fonts subset`.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Bundling a second symbol font for glyph maps (#7, second half) | T2 already bundles Noto Sans Symbols 2 + Math; `glyph_map` covers the brand case |
| `check --fix` size threshold for nudges (#8, second half) | 0.4 already attaches a `nudge` fix to every `outside-safe-area` issue; it moves a 10 px overflow today (pinned by a regression test) |
| Rewriting Python spec source files | `--fix` on `.py` prints suggestions only (0.4 decision) |
| Auto-layout engines (flex/dot/elk/d2/layered) | All scenarios are hand-placed slides; engine-laid-out diagrams keep current behaviour |
| `serve` UI panels for the new diagnostics | Deferred UI work (STATE: QA panel) |
| Publishing an actual `<brand>-spinagram-theme` package | Only the resolution mechanism ships; the brand theme stays private |
| WOFF2 output for subsets | Needs `brotli`, which is not a dependency; subsets keep the source font's flavour (TTF/OTF) |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Scope | All 13 scenarios on one branch, in the roadmap's suggested order | User choice 2026-10-28 | y |
| SVG fonts default | `subset`; `embed` keeps whole fonts; `link` uses Google Fonts URLs | User: follow the doc. Default theme has no font files, so its goldens do not move | y |
| Shared text scale default | `same_text_scale` defaults to the container's `same_size` | User: follow the doc | y |
| Centred-icon space reservation | Default-on (current output is broken: icon over text) | User choice; matches the 0.4 back-compat policy | y |
| Back-compat policy | Unchanged from 0.4: default-on only where output was broken, plus the two user-approved defaults above | Stable decks | y |
| YAML parity | Every new Python API has a YAML equivalent | Project goal | y |
| Test style | DDT: each requirement exercised through a `pytest.mark.parametrize` scenario table with readable `ids=` | 0.4 user rule | y |
| Placement checks | New geometry checks (`edge-crosses-zone-header`, `text-scale-mismatch`, nested `zone-underused`) run on hand-placed diagrams only; `icon-overlaps-text`, `glyph-mapped` and `icon-generic-for-service` run on every scene | Same split as 0.4 (`qa.py:375`): engines own their own placement | n (agent default) |
| Header-crossing fix on `via` / `curve` edges | No fix (HDR-04 asks for an anchor fix or reroute on every edge joining two nodes) | `via` / `curve` win over `route`, so a reroute is ignored, and new anchors keep the author's bend points, so the crossing usually stays. `SPEC_DEVIATION` at `qa.py` `_anchor_fix`; pinned by `test_cd_headers.py` `via-no-fix` | n (agent default) |
| Header obstacle exemption | The router ignores the header of a zone the edge ends on (zone endpoint) only; a header over an end box (a card drawn under it) stays an obstacle | Otherwise a zone target is unreachable from the top. Exempting headers over end boxes never removed an issue in 585 probes and added a header crossing in 187 (the route left through the header), so it was dropped; pinned by `test_cd_route.py` `test_ortho_from_a_card_under_its_zone_header` | n (agent default) |
| Centred icon gap | Theme `defaults.node.icon_text_gap`, default 8 px; icon floor `defaults.node.icon_min`, default 24 px | Roadmap #2 names `icon_min`; 8 px matches the header gap scale | n (agent default) |
| `align="auto"` rule | Top icon when `h > w` and the text fits the centred layout at base size; left icon otherwise | Roadmap #2 wording | n (agent default) |
| Zone row padding | Rows inside a zone use the zone's `padding` (default 24, as `fit="children"`) on left, right and bottom; top is `content_top` | Reuses `FIT_PADDING` | n (agent default) |
| Vendor packs for #6 | Packs named in `metadata.PROVIDERS` whose index is already cached (never fetched by `check`) | No network in `check`; reuse the provider list | n (agent default) |
| Vendor title matching | Exact match of a 1–3 word kebab n-gram (≥ 4 chars) of the node title against a pack icon name or alias; longest n-gram first, then pack name A–Z | Low false-positive rate for a P2 hint | n (agent default) |
| Glyph map location | Theme key `text.glyph_map` (mapping char → replacement), merged through `extends` | Groups with other text settings | n (agent default) |
| Text-scale mismatch threshold | max/min final size of the same block role among siblings > 1.10 | Roadmap #10 "differ by more than 10 %" | n (agent default) |
| Theme packages | Entry-point group `spinagram.themes`; value `pkg` (its directory) or `pkg.mod:ATTR` (a path) | Standard plugin mechanism, no new dependency | n (agent default) |
| `distribute` bounds | `within=(x0, x1)` is required (the DSL does not know the theme's safe area) | Diagram has no theme at build time | n (agent default) |

**Open questions:** none.

---

## User Stories

### P1: Edges keep clear of zone headers (#1) ⭐ MVP

**User Story**: As a diagram author, I want routed edges to avoid zone headers and `check` to report any edge
that crosses one, so I no longer have to spot header crossings in the PNG.

**Why P1**: A04 shipped header crossings that `check` did not report.

**Acceptance Criteria**:

1. WHEN an edge is routed orthogonally (`route="ortho"` or `defaults.edge.route: ortho`) THEN the router SHALL treat every zone header rectangle as an obstacle, except the header of a zone the edge ends on.
2. WHEN a connector segment enters a zone header rectangle (interior shrunk by 1 px) THEN `check` SHALL report `edge-crosses-zone-header` (P0) on the edge id with detail `crosses the header of zone '<zone shape id>'`.
3. The rule SHALL NOT report the final segment of an edge whose endpoint is that zone's border (`zone:<id>` target).
4. WHEN the crossing edge joins two nodes THEN the issue SHALL carry a fix: the first anchor pair from the candidate fractions `0.5, 0.65, 0.35, 0.8, 0.2, 0.85, 0.15` (on the edge's current sides, source fraction outer loop) whose straight segment crosses no header and no node; else `{"op": "reroute", "edge": id, "route": "ortho"}`.
5. The anchor fix SHALL be `{"op": "anchor", "edge": id, "src": "<node>.<side>@<f>", "dst": "<node>.<side>@<f>"}`, and `check --fix` SHALL apply `anchor` and `reroute` like the 0.4 safe fixes (YAML copy, Python suggestions).
6. WHERE a zone sets `header="right"` (or `header={"align": "right"}`) THEN the engine SHALL lay the header out from the right: icons end `padding` px inside the right outline and the label ends `label_gap` px before the first icon (or 24 px inside the outline without icons), with the header rectangle covering exactly those items.
7. WHERE a zone sets `header="none"` THEN the engine SHALL draw neither header icon nor label and SHALL record no header rectangle for it.
8. WHEN the roadmap's original A04 (plain row order, centred anchors) is checked THEN `check` SHALL report at least one `edge-crosses-zone-header`; WHEN the same edges use `route="ortho"` THEN it SHALL report none.

**Independent Test**: Scenario table (header align × edge direction × route) asserting crossing count and issue presence.

---

### P1: Centred icons never touch the text (#2) ⭐ MVP

**User Story**: As an author, I want centred cards to keep the icon clear of the title and `check` to flag any
overlap that remains, so I can keep `align="center"`.

**Why P1**: A01/A03/A04 cards overlapped silently.

**Acceptance Criteria**:

1. WHEN a box with `align="center"`, an icon and text is built THEN its label box SHALL start at icon bottom + `icon_text_gap` (theme `defaults.node.icon_text_gap`, default 8).
2. WHEN the text does not fit the remaining height at base size THEN the engine SHALL shrink the icon in 1 px steps down to `icon_min` (theme `defaults.node.icon_min`, default 24) before shrinking text, and stop at the first icon size where the text fits.
3. WHEN the icon is at `icon_min` and the text still does not fit THEN the node's normal fit (shrink, grow) SHALL run on the remaining height, and an unfitted result SHALL still report `overflow-y` as in 0.4.
4. WHEN a node's icon rectangle intersects the rectangle of its first text line by more than 0.5 px on both axes THEN `check` SHALL report `icon-overlaps-text` (P0) with detail `icon overlaps the first text line by <N>px` (N = vertical overlap, rounded).
5. The `icon-overlaps-text` issue SHALL carry `{"op": "resize", "node": id, "h": <height that clears the overlap>}` when the resized box stays in the safe area.
6. WHERE `align="auto"` is set THEN the engine SHALL use the centred layout when `h > w` and the text fits it at base size (fit strategy `wrap` or `break`), and the left-icon layout otherwise.
7. The engine SHALL accept `align: auto` and `icon_min`/`icon_text_gap` in YAML (`align` on nodes, the two others under `defaults.node`).

**Independent Test**: Table of (w, h, title length, body length, icon size) centred cards: no first-line overlap,
icon ≥ `icon_min`; a forced-overlap fixture yields `icon-overlaps-text`.

---

### P1: Zone bands with automatic rows (#3) ⭐ MVP

**User Story**: As an author, I want to give a zone a vertical band and drop a row of cards in it so that sizes
and positions follow from the content, not from `spread()` arithmetic.

**Why P1**: Every A0x zone and card carried absolute coordinates.

**Acceptance Criteria**:

1. WHERE `d.zone(..., band=(y0, y1))` is given THEN the engine SHALL set the zone's `y = y0` and `h = y1 - y0`, and, unless `x`/`w` are given, `x = margin` and `w = canvas width - 2 × margin`.
2. WHEN `d.row(...)` or `d.column(...)` is used inside `with d.zone(...)` without `x`/`y` THEN the container SHALL belong to that zone, with its content area `[zone.x + pad, zone.x + zone.w - pad] × [content_top, zone.y + zone.h - pad]` (`pad` = zone `padding`, default 24).
3. The engine SHALL place a zone container per `align`: `center` (default inside a zone) centres it on both axes in the content area; `start` puts it at the content area's top-left; `end` at its right, vertically centred.
4. WHEN `row(items, ...)` is called without `w`/`h` or without `x`/`y` THEN the builder SHALL create the nodes as a container, size them from their content (or from `w`/`h` when given) and return the list of nodes, instead of raising `TypeError`.
5. WHEN `row`/`column` is called outside a zone without `x`/`y` THEN the builder SHALL raise `TypeError` naming the missing keys.
6. WHERE `cols=N` is set on a zone row THEN each member SHALL be `(content width − (N−1) × gap) / N` wide, and the builder SHALL raise `ValueError` when the row has more than N members.
7. A zone row without `max_width` SHALL use the content width as `max_width`, so content that cannot fit raises the 0.4 `cannot fit` error.
8. YAML SHALL accept `band: [y0, y1]` on zones and `zone: <id>`, `align`, `cols`, `same_text_scale` on `rows`/`columns` entries.
9. WHEN the A03-like fixture is written with bands and rows THEN every card and zone SHALL be within 2 px of the hand-placed twin.

**Independent Test**: Scenario table (count × same_size × align × cols × padding) asserting card x/y/w against
independently computed expected rectangles.

---

### P2: Zones as anchored edge targets (#4)

**User Story**: As an author, I want `z.top`, `z.at_top(0.8)` and friends on zones so that arrows into a zone
need no computed coordinates.

**Why P2**: E2 already accepts `zone:<id>.<side>@<frac>`; this adds the object API.

**Acceptance Criteria**:

1. A `Zone` SHALL expose `at(side, frac=0.5)`, properties `top`, `bottom`, `left`, `right` and methods `at_top/at_bottom/at_left/at_right(frac)` returning `zone:<id>.<side>[@frac]`.
2. IF the zone has no id THEN these SHALL raise `ValueError`; IF the side is unknown THEN `ValueError` naming the valid sides.
3. WHEN such an anchor is an edge endpoint THEN the arrowhead tip SHALL lie on the zone outline (within 0.5 px) at that fraction, outside the header rectangle's interior.

**Independent Test**: Table of sides × fractions: endpoint equals the expected outline point.

---

### P2: Multi-row processes as one call (#5)

**User Story**: As an author, I want `d.snake(steps, cols=4, zones=[...])` so that a multi-row process needs no
hand-built rows, reversed lists or anchor fractions.

**Why P2**: A04 needed all three.

**Acceptance Criteria**:

1. `d.snake(steps, cols, *, y, h, x=None, w=None, gap=40, row_gap=60, zones=None, mode="boustrophedon", **edge_kw)` SHALL create one node per step (a title string or a dict of node fields), chain consecutive steps with edges, and return the nodes.
2. In `boustrophedon` mode, even rows (0, 2…) SHALL run left to right and odd rows right to left; in `restart` mode every row SHALL run left to right.
3. Card width SHALL be `(row width − (cols−1) × gap) / cols`, where the row width is `w` (default: canvas width − 2 × margin) minus `2 × pad` when zones are given; card height SHALL be `h`.
4. WHERE `zones` is given THEN the engine SHALL draw one zone per row (a label string or a dict of zone fields) spanning the full row width, with the cards starting at the zone's `content_top`, and the builder SHALL raise `ValueError` when the zone count differs from the row count.
5. The engine SHALL draw in-row edges straight between facing sides and turn edges (row r → row r+1) with `route="ortho"`, so that no snake edge crosses a zone header or a box.
6. Rows SHALL stack downwards from `y`, separated by `row_gap` (between zone outlines when zones are given, between card rows otherwise).
7. YAML SHALL accept `snakes: [{steps, cols, y, h, x, w, gap, row_gap, zones, mode}]`.
8. IF `cols < 1`, `steps` is empty or `mode` is unknown THEN the builder SHALL raise `ValueError`.

**Independent Test**: DDT over steps 5–14 × cols 2–5 × mode × zones: zero `edge-crosses-zone-header`, zero
`edge-through-box`, expected row direction per row.

---

### P2: Vendor icon hint (#6)

**User Story**: As an author, I want `check` to tell me when a card titled after a cloud service uses a
generic icon, and optionally swap it, so reviewers do not have to catch it.

**Why P2**: "Lambda" shipped with a concept gear.

**Acceptance Criteria**:

1. WHEN a node's icon resolved from a non-pack source (theme alias, icon dir or `concept:` chain) and a 1–3 word kebab n-gram of its title (≥ 4 chars) exactly matches an icon name or alias of a cached vendor pack THEN `check` SHALL report `icon-generic-for-service` (P2) with detail `'<title>' matches <pack>:<name>; icon '<icon>' is generic`.
2. The match SHALL prefer the longest n-gram, then the pack name A–Z, so identical input gives identical output.
3. `check` SHALL NOT fetch packs: a pack whose index is not cached is skipped.
4. WHERE the theme sets `icons.prefer_vendor_for_services: true` THEN the engine SHALL draw the matched vendor icon instead, and `check` SHALL NOT report the hint for that node.
5. A node whose icon already comes from a pack (`aws:lambda`) SHALL never be reported.

**Independent Test**: Fake cached `aws` index; table of titles × icon sources → issue presence and matched ref.

---

### P2: Theme glyph map (#7)

**User Story**: As a theme author, I want to map characters the brand font lacks (`→`) to ones it has (`›`) so
that specs stay readable without hand-replacing characters.

**Why P2**: Fallback fonts change metrics and are missing in PPTX.

**Acceptance Criteria**:

1. WHERE the theme sets `text.glyph_map: {"→": "›"}` THEN the engine SHALL replace each mapped character in every diagram text (title, subtitle, kicker, source, node title/text/lines, edge labels, zone labels, tables, legend items, step and callout texts) before layout.
2. WHEN at least one character was replaced THEN `check` SHALL report one `glyph-mapped` (P2) issue per mapped character with detail `'→' (U+2192) replaced by '›' (theme glyph_map)`.
3. A mapped character SHALL NOT also produce a `glyph-missing` issue.
4. A replacement MAY be several characters or empty; IF a key is not a single character THEN theme loading SHALL raise `ValueError`.

**Independent Test**: Table of maps × text locations: the rendered scene has the replacement, issue count matches.

---

### P2: Coordinates relative to the safe area (#8)

**User Story**: As an author, I want `origin="safe"` so that a spec written for one margin keeps working on a
theme with another.

**Why P2**: 30 px → 40 px margin moved every element by hand.

**Acceptance Criteria**:

1. WHERE `Diagram(..., origin="safe")` (YAML `origin: safe`) is set THEN the engine SHALL offset every hand-placed coordinate by the theme margin on both axes. That covers nodes, zones (and `band`), containers, snakes, tables, the fixed legend, absolute edge points, `via`, `curve`, `label_at` and legend `place` cells.
2. The default `origin="canvas"` SHALL keep 0.4 output unchanged.
3. IF `origin` is neither `canvas` nor `safe` THEN the builder SHALL raise `ValueError`.
4. WHEN a node overflows the safe area by 10 px THEN `check` SHALL attach a `nudge` fix that moves it inside, and `check --fix` SHALL apply it (regression).

**Independent Test**: Same spec at margins 30/40/80 with `origin="safe"`: zero `outside-safe-area`.

---

### P3: Nested zones count as content (#9)

**User Story**: As an author, I want an account zone containing a region zone not to be called underused.

**Why P3**: Forced merging of AWS nesting levels.

**Acceptance Criteria**:

1. WHEN `zone-underused` measures a zone THEN its content SHALL be the area of its direct child zones plus the nodes not inside any of those child zones, with overlaps counted once.
2. Child zones SHALL be the declared children (`with d.zone`) when present, else the zones whose rectangle lies mostly (> 50 %) inside it and inside no other such child.
3. WHEN the Account › Region › VPC fixture is checked THEN no `zone-underused` SHALL be reported; WHEN a zone holds only a small child zone (< 35 % of the area) THEN it SHALL still be reported.

**Independent Test**: Table of nesting fixtures with expected fill ratios (computed by hand in the test).

---

### P3: Shared text scale in a row (#10)

**User Story**: As an author, I want sibling cards in a row to share one text size so that one long title does
not leave three sizes on the slide.

**Why P3**: Visual polish.

**Acceptance Criteria**:

1. `row`/`column` SHALL accept `same_text_scale` (default: the container's `same_size`).
2. WHEN it is on THEN every member's title and body SHALL use the smallest final size (per block role) reached by any member when fitted alone.
3. WHEN it is off and sibling sizes for one role differ by more than 10 % (max/min > 1.10) THEN `check` SHALL report `text-scale-mismatch` (P2) on the container (`row<k>`/`column<k>`) listing the sizes.
4. Turning it on SHALL leave rows whose members already share sizes unchanged.

**Independent Test**: Row of 5 cards with one long title: sizes equal with the flag, issue without it.

---

### P3: Built-in helpers (#11)

**User Story**: As an author, I want node lookup, distribution and elbow routes built in so that specs stop
copying `_dk.py`.

**Why P3**: Ergonomics.

**Acceptance Criteria**:

1. `d["id"]` SHALL return the node with that id, else the zone with that id, else raise `KeyError` naming the id.
2. `d.distribute(n, w=None, gap=0, *, within=(x0, x1))` SHALL return `n` x positions: with `w`, a block of `n·w + (n−1)·gap` centred in `within`; without `w`, it SHALL fill `within` (w = (width − (n−1)·gap)/n) and return `(xs, w)`.
3. IF the block is wider than `within` or `n < 1` THEN `distribute` SHALL raise `ValueError`.
4. WHERE `route="elbow"` is set THEN the edge SHALL be drawn as `p1 → bend → bend → p2` with the middle segment at `mid` (a y for vertical exits, an x for horizontal exits), default the midpoint. When `p1` is a node anchor the exit axis follows its side, otherwise the dominant axis of `p2 − p1`.
5. YAML SHALL accept `route: elbow` and `mid:` on edges; `route` values other than `ortho`, `elbow` or none SHALL raise `ValueError`.

**Independent Test**: Tables of distribute inputs and elbow side combinations with hand-computed points.

---

### P3: Theme by name (#12)

**User Story**: As a team, we want `extends: <brand>` to resolve on any machine so that CI can render diagrams.

**Why P3**: Portability.

**Acceptance Criteria**:

1. The engine SHALL resolve a theme name in order: built-in → a path (absolute, `~`, or relative to the extending theme) → each directory of `SPINAGRAM_THEME_PATH` (`os.pathsep`-separated) holding `<name>/theme.yaml` → an installed entry point named `<name>` in group `spinagram.themes`.
2. An entry point value `pkg` SHALL resolve to the package directory; `pkg.mod:ATTR` SHALL resolve to the path in `ATTR`.
3. IF nothing resolves THEN the engine SHALL raise `FileNotFoundError` listing every location searched, in order.
4. Resolution SHALL apply to both `Theme.load(name)` / `-t name` and `extends:`.

**Independent Test**: Table of (env path, entry point, relative path) setups → resolved directory or error text.

---

### P3: Smaller SVGs (#13)

**User Story**: As a docs maintainer, I want committed SVGs to carry only the glyphs they use so that a diagram
is tens of KB, not ~420 KB.

**Why P3**: Repo size.

**Acceptance Criteria**:

1. The SVG backend SHALL accept `fonts` = `subset` (default), `embed` or `link`; the CLI SHALL expose it as `render --fonts` and the API as `backend_options={"svg": {"fonts": ...}}`.
2. WHEN `subset` THEN each embedded face SHALL contain exactly the characters drawn in that face (plus space), using fontTools, keeping the source flavour (TTF/OTF).
3. WHEN `embed` THEN faces SHALL be embedded byte-for-byte as in 0.4.
4. WHEN `link` THEN no font file SHALL be embedded and the style SHALL `@import` one Google Fonts CSS2 URL per family with its used weights.
5. Subset output SHALL be byte-identical across runs and `PYTHONHASHSEED` values.
6. WHEN a ~400 KB font face is used for a short title THEN the subset SVG SHALL be < 25 % of the `embed` SVG.
7. PNG output (rendered from SVG) SHALL use the subset fonts.

**Independent Test**: Render with each mode: parse the embedded font, compare its cmap to the used characters.

---

## Edge Cases

- WHEN a zone has `band` and `fit="children"` THEN the builder SHALL raise `ValueError` (two sources of height).
- WHEN a zone row is empty THEN it SHALL be ignored.
- WHEN `snake` has fewer steps than `cols` THEN it SHALL draw one row with the steps left-aligned in the row.
- WHEN the glyph map maps a character to itself THEN nothing SHALL be reported.
- WHEN `SPINAGRAM_THEME_PATH` lists a missing directory THEN it SHALL be listed as searched and skipped.
- WHEN a subset font cannot be produced (fontTools error) THEN the backend SHALL embed the whole font and warn.
- WHEN a centred icon card has no text THEN the 0.4 icon-only centring SHALL apply unchanged.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| HDR-01 | P1 #1 router header obstacles | Tasks | Pending |
| HDR-02 | P1 #1 `edge-crosses-zone-header` | Tasks | Pending |
| HDR-03 | P1 #1 own-zone endpoint exemption | Tasks | Pending |
| HDR-04 | P1 #1 anchor/reroute fix | Tasks | Pending |
| HDR-05 | P1 #1 apply anchor/reroute | Tasks | Pending |
| HDR-06 | P1 #1 header right | Tasks | Pending |
| HDR-07 | P1 #1 header none | Tasks | Pending |
| HDR-08 | P1 #1 A04 acceptance | Tasks | Pending |
| ICO-01 | P1 #2 reserve icon + gap | Tasks | Pending |
| ICO-02 | P1 #2 icon shrink to icon_min | Tasks | Pending |
| ICO-03 | P1 #2 then text fit | Tasks | Pending |
| ICO-04 | P1 #2 `icon-overlaps-text` | Tasks | Pending |
| ICO-05 | P1 #2 resize fix | Tasks | Pending |
| ICO-06 | P1 #2 `align="auto"` | Tasks | Pending |
| ICO-07 | P1 #2 YAML keys | Tasks | Pending |
| BND-01 | P1 #3 band | Tasks | Pending |
| BND-02 | P1 #3 zone container content area | Tasks | Pending |
| BND-03 | P1 #3 align | Tasks | Pending |
| BND-04 | P1 #3 row(items) without w/h or x/y | Tasks | Pending |
| BND-05 | P1 #3 missing x/y outside zone | Tasks | Pending |
| BND-06 | P1 #3 cols | Tasks | Pending |
| BND-07 | P1 #3 max_width = content width | Tasks | Pending |
| BND-08 | P1 #3 YAML | Tasks | Pending |
| BND-09 | P1 #3 A03 parity | Tasks | Pending |
| ZAN-01 | P2 #4 zone anchor API | Tasks | Pending |
| ZAN-02 | P2 #4 errors | Tasks | Pending |
| ZAN-03 | P2 #4 tip on outline | Tasks | Pending |
| SNK-01 | P2 #5 snake API | Tasks | Pending |
| SNK-02 | P2 #5 row direction | Tasks | Pending |
| SNK-03 | P2 #5 card size | Tasks | Pending |
| SNK-04 | P2 #5 zones per row | Tasks | Pending |
| SNK-05 | P2 #5 edges clear | Tasks | Pending |
| SNK-06 | P2 #5 row stacking | Tasks | Pending |
| SNK-07 | P2 #5 YAML | Tasks | Pending |
| SNK-08 | P2 #5 errors | Tasks | Pending |
| VND-01 | P2 #6 hint | Tasks | Pending |
| VND-02 | P2 #6 deterministic match | Tasks | Pending |
| VND-03 | P2 #6 no fetch | Tasks | Pending |
| VND-04 | P2 #6 prefer vendor swap | Tasks | Pending |
| VND-05 | P2 #6 pack icons exempt | Tasks | Pending |
| GLM-01 | P2 #7 map texts | Tasks | Pending |
| GLM-02 | P2 #7 `glyph-mapped` | Tasks | Pending |
| GLM-03 | P2 #7 no glyph-missing | Tasks | Pending |
| GLM-04 | P2 #7 validation | Tasks | Pending |
| ORG-01 | P2 #8 origin safe | Tasks | Pending |
| ORG-02 | P2 #8 default unchanged | Tasks | Pending |
| ORG-03 | P2 #8 validation | Tasks | Pending |
| ORG-04 | P2 #8 nudge regression | Tasks | Pending |
| ZUN-01 | P3 #9 content = child zones + free nodes | Tasks | Pending |
| ZUN-02 | P3 #9 child zone detection | Tasks | Pending |
| ZUN-03 | P3 #9 fixtures | Tasks | Pending |
| TSC-01 | P3 #10 flag | Tasks | Pending |
| TSC-02 | P3 #10 smallest size | Tasks | Pending |
| TSC-03 | P3 #10 `text-scale-mismatch` | Tasks | Pending |
| TSC-04 | P3 #10 no-op when equal | Tasks | Pending |
| HLP-01 | P3 #11 `d[id]` | Tasks | Pending |
| HLP-02 | P3 #11 distribute | Tasks | Pending |
| HLP-03 | P3 #11 distribute errors | Tasks | Pending |
| HLP-04 | P3 #11 elbow | Tasks | Pending |
| HLP-05 | P3 #11 YAML + route validation | Tasks | Pending |
| THM-01 | P3 #12 resolution order | Tasks | Pending |
| THM-02 | P3 #12 entry point values | Tasks | Pending |
| THM-03 | P3 #12 error lists paths | Tasks | Pending |
| THM-04 | P3 #12 load and extends | Tasks | Pending |
| FNT-01 | P3 #13 modes | Tasks | Pending |
| FNT-02 | P3 #13 subset glyphs | Tasks | Pending |
| FNT-03 | P3 #13 embed unchanged | Tasks | Pending |
| FNT-04 | P3 #13 link | Tasks | Pending |
| FNT-05 | P3 #13 deterministic | Tasks | Pending |
| FNT-06 | P3 #13 size bound | Tasks | Pending |
| FNT-07 | P3 #13 PNG uses subset | Tasks | Pending |

**Coverage:** 71 total, 71 mapped to tasks, 0 unmapped.

---

## Success Criteria

- [ ] Every scenario in the roadmap Summary has either an automatic fix in the engine or a `check` diagnostic, and 11 of the 13 have both or a public API.
- [ ] Full gate green: `uv run ruff check src tests && uv run pytest -q` (the pre-existing `test_web_unit` bun failure excluded and noted).
- [ ] Default-theme golden SVG hashes unchanged except where an intent test pins the change (centred icon cards).

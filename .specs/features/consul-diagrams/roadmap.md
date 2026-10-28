# spinagram: scenarios and improvements to cut manual positioning and quirk fixes

Source: the five diagrams in `docs/diagrams/specs` (A01–A05, spinagram 0.4.0, a company brand theme), built on
2026-10-28 by adapting the study specs `c02`/`c09`. Every item below is a fix done by hand in this session.
It complements [`improvements-layout-engine.md`](improvements-layout-engine.md) (item ids such as T2, Z3 and E2
refer to that doc). Copied from a private infrastructure repo (Consul on AWS).

## Summary

| # | Scenario | Hand fix in the spec today | Proposal | Priority |
|---|---|---|---|---|
| 1 | Edge crosses a zone header | Snake row reversed + `@0.85` anchors | Router and `check` treat zone headers as obstacles | P0 |
| 2 | Top icon touches the title | Remove `align="center"`, shorten body, `icon_size=40` | Reserve icon height; QA rule; auto fallback to left icon | P0 |
| 3 | Zone with a row of cards | `spread()` + absolute `x/y/w/h` for the zone and each card | `with d.zone(...): d.row(...)` sized and centred automatically | P0 |
| 4 | Arrow into a zone | Tuple endpoint `(nlb.x + nlb.w/2, 260)` | Zones return anchors (`z.top`, `z.top@0.8`) | P1 |
| 5 | Multi-row process | Hand-built snake, reversed `spread()`, `via` points | `d.snake(steps, cols=4)` primitive | P1 |
| 6 | Generic icon on a cloud service | brand concept gear on "Lambda" until reviewed | `check` hint: title matches a pack service → suggest `aws:*` | P1 |
| 7 | Glyph missing in brand font | Replaced `→` with `·` in every text | Theme `glyph_map` / bundled symbol fallback | P1 |
| 8 | Safe-area off by a few px | Changed `y=30` → `y=40` everywhere | Coordinates relative to the safe area; `check --fix` nudge | P2 |
| 9 | Nested zone counted as empty | Merged account and region zones | `zone-underused` counts child zones as content | P2 |
| 10 | Uneven text shrink in a row | Accepted (Secrets Manager wraps and shrinks) | Row-level shared text scale | P2 |
| 11 | Node lookup and helpers | `box = {}` dict, own `_dk.py` (`spread`, `elbow`) | Ship `distribute`, `elbow` and `d[id]` in the engine | P2 |
| 12 | Theme path not portable | `extends: ~/projetos/<brand>-diagramkit/theme` | Theme by name (registry / env var) | P2 |
| 13 | Large committed SVGs | ~420 KB each (embedded fonts) | Font subsetting / `--fonts link` | P3 |

`check` reported **0 issues** while scenarios 1 and 2 were visibly broken in the PNG. These two are the most
valuable: they need a person to look at every render.

## Scenarios

### 1. Edge crosses a zone header (P0)

**What happened (A04):** three phase zones stacked vertically, each with a header label at the top-left and a
row of 4 steps. The edge from the last step of a row to the first step of the next row dropped through the
header text ("CADA NÓ · CLOUD-INIT…", "PÓS-APPLY · MANUAL"). `check` did not flag it.

**Hand fix:** reversed the second row (right → left) so the drop lands on the right side, and used
`bottom@0.85 → top@0.85` anchors to clear the third header.

**Proposal:**
- The router (`route="ortho"` and `via`-less edges) treats each zone header box as an obstacle, like nodes (extends E4).
- New QA rule `edge-crosses-zone-header` with `--fix` suggesting a new anchor fraction or a header side.
- Zone option `header: left|right|none` (or `label_align`) so a header can move away from incoming edges.

**Acceptance:** the original A04 (no snake, centred anchors) renders without crossings or `check` reports
`edge e7 crosses zone z2 header`.

### 2. Top icon touches the title (P0)

**What happened (A01 services, A03 rules, A04 steps):** `align="center"` cards with icon + title + body at
h = 120–140. The icon bottom touched or overlapped the title baseline. `check` did not flag it.

**Hand fix:** removed `align="center"` (left icon), shortened the A01 non-voter body to one line, set
`icon_size=40` on the AZ cards.

**Proposal:**
- Centred layout reserves `icon_h + gap` before laying out text; when it does not fit, shrink the icon down to a
  floor (theme `icon_min`), then text, then report.
- QA rule `icon-overlaps-text` (bbox intersection of icon and first text line).
- `align="auto"`: top icon when the card is taller than wide and the text fits, left icon otherwise.

**Acceptance:** the first A01/A03/A04 renders produce either a clean layout or an `icon-overlaps-text` issue.

### 3. Zone with a row of cards (P0)

**What happened (all diagrams):** each zone and each card got absolute `x/y/w/h`, computed with a helper
`spread(n, w, gap)` copied from the study. Changing one width means recomputing the zone and its neighbours.

**Note:** 0.4.0 already has `row()`, `grid()`, `fit="children"` and full auto layout; the specs inherited the
study's absolute style. What is missing is the mixed case: a fixed band (y range) whose content is centred and
sized automatically.

**Proposal:**
```python
with d.zone("Secrets Manager · <ENV>/consul/*", band=(330, 500)):   # x = full safe width
    d.row(["ca-cert", "cert", "key", "ca-key"], same_size=True, gap=20, align="center")
```
- `band=(y0, y1)` fixes the vertical slot; x/w default to the safe area; children centred.
- Optional `cols=` to force equal columns across zones (A03's two SG zones).

**Acceptance:** A02/A03 written without any `x=` on cards, same output within a few px.

### 4. Arrow into a zone (P1)

**What happened (A01, A02, A03):** arrows from the NLB to the VPC zone and from the Lambda to the Secrets
Manager zone used a tuple endpoint at a computed coordinate.

**Proposal:** `d.zone()` returns an object with `.top/.bottom/.left/.right` and `@frac`, usable in `d.edge`
(E2 covers groups in auto layout; this is the hand-placed variant). The arrowhead stops at the border, outside the header.

### 5. Multi-row process (P1)

**What happened (A04):** 12 steps in 3 phases. Row direction, inter-row drops and anchor fractions were all manual.

**Proposal:** `d.snake(steps, cols=4, zones=[...])` lays out boustrophedon rows, routes the turn edges outside
headers (see 1) and accepts one zone per row. Variant `snake="restart"` for left-to-right every row with a
routed return edge.

### 6. Generic icon on a cloud service (P1)

**What happened:** "Lambda" got the brand concept-set `configuracao` gear; the user asked for the AWS icon.

**Proposal:** `check` hint `icon-generic-for-service`: the title or body matches an alias in a loaded pack
(`lambda`, `eventbridge`, `cloudwatch`…) while the icon comes from a concept set. Optional theme rule
`icons.prefer_vendor_for_services: true` to swap automatically.

### 7. Glyph missing in the brand font (P1)

**What happened:** `→` is not in the brand fonts; `check` reported `glyph-missing` and fell back to Noto Sans
Math (different metrics, PPTX without the font).

**Proposal:** theme `glyph_map: {"→": "›"}`, applied at load with a note in `check`, or a bundled symbol
font embedded with the brand fonts (extends T2).

### 8. Safe-area off by a few px (P2)

**What happened:** specs copied from a 30 px-margin canvas failed `outside-safe-area` by 10 px on the 40 px theme.

**Proposal:** `Diagram(..., origin="safe")` so `x/y` are relative to the safe area; `check --fix` moves
elements that overflow by less than N px.

### 9. Nested zone counted as empty (P2)

**What happened (A01):** Account › Region › VPC. The account zone got `zone-underused` (35 %) because only
direct nodes count. Fixed by merging account and region into one zone, losing the AWS nesting.

**Proposal:** `zone-underused` counts child zones' area as content (Z3 related).

### 10. Uneven text shrink in a row (P2)

**What happened (A01 services, left icon):** "Secrets Manager" wraps to two lines and its body shrinks, so the
five siblings show three different text sizes.

**Proposal:** `row(..., same_text_scale=True)` (default when `same_size=True`): every card uses the smallest
scale needed by any sibling. `check` warns when siblings differ by more than 10 %.

### 11. Node lookup and helpers (P2)

**What happened:** boxes created in loops were collected in a dict to draw edges later; each repo copies `_dk.py`
(`spread`, `elbow`).

**Proposal:** `d["sm"]` alias of `d.node("sm")`; ship `d.distribute(n, w, gap, within=...)` and
`d.edge(a, b, route="elbow", mid=y)` so specs stop vendoring helpers.

### 12. Theme path not portable (P2)

**What happened:** `theme.yaml` has `extends: ~/projetos/<brand>-diagramkit/theme`; it renders only on a
machine with that clone, so CI cannot run `make diagrams`.

**Proposal:** resolve `extends: <brand>` through `SPINAGRAM_THEME_PATH` or an installed theme package
(`pip install <brand>-spinagram-theme`), with a clear error listing the paths searched.

### 13. Large committed SVGs (P3)

**What happened:** each SVG is ~420 KB, mostly embedded fonts.

**Proposal:** subset fonts to the glyphs used (default for `svg`), or `--fonts link` (Google Fonts URL) for
docs that render in a browser.

## Suggested order

1. QA first (1, 2): new rules make every other quirk visible without a human review.
2. Layout primitives (3, 4, 5): remove most `x=`/`via`/`@frac` from the specs.
3. Ergonomics (6, 7, 8, 11, 12): fewer copied helpers and portable themes.
4. Polish (9, 10, 13).

## Test fixtures

The A01–A05 specs in the source repo (private) are good regression fixtures; commits below refer to it.

- Commit `c8ed6c9`: centred-icon cards that overlap (scenario 2) and the A04 snake workaround already applied.
  To reproduce scenario 1, restore the plain row order and centred anchors in A04: that version was never committed.
- Commit `bc5133e`: icon layout fixes.

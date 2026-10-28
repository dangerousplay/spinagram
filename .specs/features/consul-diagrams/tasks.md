# Consul Diagram Improvements Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow.**
Each task: RED tests first (DDT `pytest.mark.parametrize` tables with `ids=`), GREEN minimal implementation,
gate, one Conventional Commit ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

---

**Design**: `.specs/features/consul-diagrams/design.md`
**Status**: In Progress

---

## Test Coverage Matrix

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Engine helpers (`engine/*.py`, `qa.py`, `backends/fontsubset.py`) | unit | 1:1 to spec ACs, edge cases, DDT tables | `tests/test_cd_<area>.py` | `uv run pytest tests/test_cd_<area>.py -q` |
| Builder / model / YAML / theme integration | integration | Scene-level DDT per AC; YAML parity row per Python API; intent tests for golden changes | `tests/test_cd_<area>.py` | `uv run pytest -q` |
| Backends (svg, png) | integration | SVG font parse; PNG when playwright exists | `tests/test_cd_fonts.py` | `uv run pytest -q` |
| CLI (`check --fix`, `render --fonts`) | integration | Happy + error path via `cli.main([...])` | area files | `uv run pytest -q` |
| Docs | none | build gate | - | build gate |

## Gate Check Commands

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | Unit-only tasks | `uv run pytest tests/test_cd_<area>.py -q` |
| Full | Integration tasks | `uv run pytest -q --deselect tests/test_web_unit.py::test_web_unit_tests_pass` |
| Build | Phase ends, docs | `uv run ruff check src tests && uv run pytest -q --deselect tests/test_web_unit.py::test_web_unit_tests_pass` |

Baseline before T1: 1406 passed, 19 skipped (`test_web_unit` fails pre-existing: bun cannot resolve `react` in
`web/`; deselected in every gate).

---

## Execution Plan

All tasks are sequential (shared files: `model.py`, `layout.py`, `qa.py`, `yaml_io.py`), so no task is `[P]`.

```
Phase 1 QA (P0):        T1 → T2 → T3 → T4 → T5 → T6 → T7
Phase 2 primitives:     T8 → T9 → T10 → T11 → T12 → T13 → T14 → T15
Phase 3 ergonomics:     T16 → T17 → T18 → T19 → T20 → T21 → T22
Phase 4 polish:         T23 → T24 → T25 → T26 → T27
Phase 5 wrap-up:        T28 → T29
```

---

## Task Breakdown

### T1: Zone header align right and none ✅
**What**: `Zone.header` accepts `"left"|"right"|"none"` (or `{"align": …}`); right mirrors the header, none draws no header and records no header rect.
**Where**: `src/spinagram/engine/zones.py`, `src/spinagram/layout.py` (`zone_header`), `src/spinagram/model.py`
**Depends on**: None · **Reuses**: `header_layout`, `header_options` · **Requirement**: HDR-06, HDR-07
**Done when**: DDT over (align × icons 0/1/2 × label short/long) asserts icon/label x and header rect; YAML `header: right` row; unknown value → `ValueError`; gate passes.
**Tests**: integration · **Gate**: full · **Commit**: `feat(zones): header align right and none`

### T2: edge-crosses-zone-header diagnostic ✅
**What**: `qa` rule reporting edges whose segments enter a zone header rect (own-zone endpoint exempt), P0.
**Where**: `src/spinagram/qa.py`
**Depends on**: T1 · **Reuses**: `segment_hits`, `polyline`, `scene.zone_headers` · **Requirement**: HDR-02, HDR-03
**Done when**: DDT (straight/poly/curve edges × through/near/own-zone-target) asserts issue presence, item, exact detail; hand-placed only; gate passes.
**Tests**: unit · **Gate**: full · **Commit**: `feat(check): report edges crossing zone headers`

### T3: Router treats zone headers as obstacles ✅
**What**: `route_ortho` receives header rects as obstacles, skipping headers of zones bound at either end; A04-like fixture.
**Where**: `src/spinagram/engine/route.py`, `src/spinagram/layout.py` (`route_edges`)
**Depends on**: T2 · **Reuses**: `route_ortho`, `autolayout.route.route` · **Requirement**: HDR-01, HDR-08
**Done when**: A04 fixture (3 stacked phase zones × 4 steps, plain order, centred anchors) → straight: ≥1 `edge-crosses-zone-header`; ortho: 0 and 0 `edge-through-box`; DDT of header positions; ortho into a zone target still reaches the border; gate passes.
**Tests**: integration · **Gate**: full · **Commit**: `feat(route): route around zone headers`

### T4: Anchor and reroute fixes ✅
**What**: Attach `anchor` (candidate fractions) or `reroute` fixes to `edge-crosses-zone-header`; `engine/fix.py` applies both; Python suggestions.
**Where**: `src/spinagram/qa.py` (`fix_for`), `src/spinagram/engine/fix.py`
**Depends on**: T3 · **Reuses**: `endpoints.resolve`, `segment_hits`, `apply_to_diagram`, `suggest_python` · **Requirement**: HDR-04, HDR-05
**Done when**: DDT: geometry where a fraction clears → exact anchor fix (first in order); where none clears → reroute; `check --fix` on YAML writes `.fixed.yaml` with the new src/dst or route and re-check has 0 of the kind; Python prints suggestion; gate passes.
**Tests**: integration · **Gate**: full · **Commit**: `feat(fix): anchor and reroute fixes for header crossings`

### T5: Centred icon reserves its height ✅
**What**: Centred box with icon+text: label box starts at icon bottom + `icon_text_gap`; icon shrinks to `icon_min` before text shrinks.
**Where**: `src/spinagram/layout.py` (`box`), `src/spinagram/engine/icons.py` (`centre_layout`)
**Depends on**: T4 · **Reuses**: `textfit.fit_blocks`, `icon_fit.place` · **Requirement**: ICO-01, ICO-02, ICO-03, ICO-07 (theme keys)
**Done when**: DDT of card sizes × text lengths: first text top ≥ icon bottom + gap − 0.5, icon ≥ icon_min; icon-only centred unchanged; theme keys override; any default-theme golden hash change re-pinned with an intent test naming the centred card; gate passes.
**Tests**: integration · **Gate**: full · **Commit**: `fix(layout): keep centred icons clear of the text`

### T6: icon-overlaps-text diagnostic and fix ✅
**What**: `qa` rule on icon rect ∩ first text line rect, P0, with a `resize` fix.
**Where**: `src/spinagram/qa.py`
**Depends on**: T5 · **Reuses**: `_icon_rect`, `Label.place`, `measure`, `_inside` · **Requirement**: ICO-04, ICO-05
**Done when**: DDT of forced overlaps (explicit `icon_size` larger than room, left-icon layouts that do not overlap) → exact detail `by Npx`; fix `h` clears the overlap after `apply_to_diagram`; gate passes.
**Tests**: unit · **Gate**: full · **Commit**: `feat(check): report icons overlapping text`

### T7: align auto
**What**: `align="auto"` picks centred when `h > w` and the text fits at base size, left icon otherwise; YAML `align: auto`.
**Where**: `src/spinagram/layout.py`, `src/spinagram/engine/icons.py`, `src/spinagram/model.py` (comment)
**Depends on**: T6 · **Reuses**: `centre_layout` · **Requirement**: ICO-06, ICO-07
**Done when**: DDT (tall/wide × short/long text) → expected layout (icon x centred vs at padding); YAML row; gate passes.
**Tests**: integration · **Gate**: build · **Commit**: `feat(layout): align auto for icon cards`

### T8: Zone bands
**What**: `Zone.band=(y0, y1)`; model pass sets y/h and x/w default to the safe width; `band` + `fit="children"` → `ValueError`.
**Where**: `src/spinagram/model.py`, `src/spinagram/engine/zones.py` (`bands`), `src/spinagram/engine/model_passes.py` (`apply` order/trigger)
**Depends on**: T7 · **Reuses**: theme margin · **Requirement**: BND-01
**Done when**: DDT (band × explicit x/w × margin 40/80) asserts zone rect; error row; gate passes.
**Tests**: integration · **Gate**: full · **Commit**: `feat(zones): vertical bands`

### T9: Zone-attached containers in the DSL
**What**: `row/column` x/y optional; inside an open zone the container records `zone`; `row(items)` without w/h or x/y creates a container and returns nodes; outside a zone missing x/y → `TypeError`; new fields `align`, `cols`, `same_text_scale`.
**Where**: `src/spinagram/model.py`
**Depends on**: T8 · **Reuses**: `_container`, `_seq` · **Requirement**: BND-04, BND-05
**Done when**: DDT of call shapes → container fields / nodes returned / errors; old `row(items, x, y, w, h)` path unchanged (asserted positions); gate passes.
**Tests**: unit · **Gate**: full · **Commit**: `feat(dsl): rows and columns inside zones`

### T10: Zone container placement
**What**: `containers` pass: zone content area, default `max_width`, `cols` widths, `align` placement (center/start/end), cols overflow error.
**Where**: `src/spinagram/engine/model_passes.py`
**Depends on**: T9 · **Reuses**: `content_top`, `header_options`, `FIT_PADDING`, `min_width` · **Requirement**: BND-02, BND-03, BND-06, BND-07
**Done when**: DDT (count × same_size × align × cols × padding × header icon) asserts card rects against hand-computed values; too-wide row raises `cannot fit`; gate passes.
**Tests**: integration · **Gate**: full · **Commit**: `feat(layout): place rows in zone content areas`

### T11: YAML bands/rows and A03 parity
**What**: YAML `band`, `rows[].zone/align/cols/same_text_scale`; `dump` round-trip; A03-like fixture vs hand-placed twin within 2 px.
**Where**: `src/spinagram/yaml_io.py`, `tests/fixtures/`
**Depends on**: T10 · **Reuses**: `from_dict`, `_CONTAINER_KEYS`, `dump` · **Requirement**: BND-08, BND-09
**Done when**: YAML parity rows for each key; fixture parity assertion; round-trip `dump → from_dict` equal; gate passes.
**Tests**: integration · **Gate**: full · **Commit**: `feat(yaml): zone bands and zone rows`

### T12: Zone anchors
**What**: `Zone.at/top/bottom/left/right/at_*`.
**Where**: `src/spinagram/model.py`
**Depends on**: T11 · **Reuses**: `Node.at` pattern, `endpoints.resolve` · **Requirement**: ZAN-01, ZAN-02, ZAN-03
**Done when**: DDT sides × fractions: refs string and arrow tip on the outline (±0.5 px) outside the header interior; errors; gate passes.
**Tests**: integration · **Gate**: full · **Commit**: `feat(dsl): zone anchors`

### T13: Snake model and DSL
**What**: `Snake` dataclass, `Diagram.snakes`, `d.snake(...)` creating nodes, zones and edges; validation errors.
**Where**: `src/spinagram/model.py`
**Depends on**: T12 · **Reuses**: `add`, `_add_zone`, `edge` · **Requirement**: SNK-01, SNK-08
**Done when**: DDT of inputs → node/zone/edge counts and errors; turn edges have `route="ortho"`; gate passes.
**Tests**: unit · **Gate**: full · **Commit**: `feat(dsl): snake for multi-row processes`

### T14: Snake layout pass
**What**: `model_passes.snakes`: row width, card sizes, row direction by mode, zone rects, row stacking; in-row edge anchors.
**Where**: `src/spinagram/engine/model_passes.py`
**Depends on**: T13 · **Reuses**: `content_top`, `header_options` · **Requirement**: SNK-02, SNK-03, SNK-04, SNK-06
**Done when**: DDT (steps 5–14 × cols 2–5 × mode × zones) asserts card rects and per-row direction against hand-computed values; fewer steps than cols → one left-aligned row; gate passes.
**Tests**: integration · **Gate**: full · **Commit**: `feat(layout): lay out snakes`

### T15: Snake edges clear and YAML
**What**: Snake renders with 0 header crossings and 0 edges through boxes; YAML `snakes:`.
**Where**: `src/spinagram/yaml_io.py`, `src/spinagram/engine/model_passes.py` (if needed)
**Depends on**: T14 · **Reuses**: T2/T3 · **Requirement**: SNK-05, SNK-07
**Done when**: DDT over the T14 table + long header labels → `check` has no `edge-crosses-zone-header`/`edge-through-box`; A04 as a single `snake` call; YAML parity; gate passes.
**Tests**: integration · **Gate**: build · **Commit**: `feat(yaml): snakes`

### T16: Vendor service matcher
**What**: `engine/vendor.py`: n-grams, cached-only indexes, deterministic match.
**Where**: `src/spinagram/engine/vendor.py`
**Depends on**: T15 · **Reuses**: `icons.index(auto_fetch=False)`, `icons.kebab`, `metadata.PROVIDERS` · **Requirement**: VND-02, VND-03
**Done when**: DDT with a fake cached index (titles × expected ref/None, tie ordering); uncached pack never fetched (monkeypatched fetch asserts not called); gate passes.
**Tests**: unit · **Gate**: quick · **Commit**: `feat(icons): match node titles to vendor services`

### T17: Vendor hint and swap
**What**: `icon-generic-for-service` (P2) in `qa`; theme `icons.prefer_vendor_for_services` swaps the icon in the builder.
**Where**: `src/spinagram/layout.py`, `src/spinagram/qa.py`, `src/spinagram/scene.py`
**Depends on**: T16 · **Reuses**: icon trace sources · **Requirement**: VND-01, VND-04, VND-05
**Done when**: DDT (icon source theme/concept/pack × flag) → issue + exact detail or swapped icon path; gate passes.
**Tests**: integration · **Gate**: full · **Commit**: `feat(check): hint vendor icons for cloud services`

### T18: Theme glyph map
**What**: `text.glyph_map` validation, model pass replacing text, `glyph-mapped` issues, no `glyph-missing` for mapped chars.
**Where**: `src/spinagram/theme.py`, `src/spinagram/engine/model_passes.py`, `src/spinagram/layout.py`, `src/spinagram/qa.py`, `src/spinagram/scene.py`
**Depends on**: T17 · **Reuses**: `apply_facts` walk pattern · **Requirement**: GLM-01..04
**Done when**: DDT per text location × map → replaced in scene; issue count/detail; invalid key → `ValueError`; identity map → no issue; gate passes.
**Tests**: integration · **Gate**: full · **Commit**: `feat(theme): glyph map for characters the brand font lacks`

### T19: Safe-area origin
**What**: `Diagram.origin` (`canvas|safe`), YAML `origin`, translation pass; nudge regression.
**Where**: `src/spinagram/model.py`, `src/spinagram/engine/model_passes.py`, `src/spinagram/yaml_io.py`
**Depends on**: T18 · **Reuses**: — · **Requirement**: ORG-01..04
**Done when**: DDT per element type × margin 30/40/80 → offset by margin and 0 `outside-safe-area`; default unchanged (golden); invalid → `ValueError`; 10 px overflow gets and applies nudge; gate passes.
**Tests**: integration · **Gate**: full · **Commit**: `feat(dsl): coordinates relative to the safe area`

### T20: Node lookup and distribute
**What**: `Diagram.__getitem__`, `Diagram.distribute`.
**Where**: `src/spinagram/model.py`
**Depends on**: T19 · **Requirement**: HLP-01, HLP-02, HLP-03
**Done when**: DDT of lookups and distribute inputs → hand-computed xs/w or errors; gate passes.
**Tests**: unit · **Gate**: quick · **Commit**: `feat(dsl): node lookup and distribute`

### T21: Elbow route
**What**: `Edge.mid`, `route="elbow"`, route validation, YAML.
**Where**: `src/spinagram/model.py`, `src/spinagram/engine/endpoints.py`, `src/spinagram/layout.py`, `src/spinagram/yaml_io.py`
**Depends on**: T20 · **Reuses**: `Binding.side` · **Requirement**: HLP-04, HLP-05
**Done when**: DDT side combos × mid given/default → exact points; invalid route → `ValueError`; YAML row; gate passes.
**Tests**: integration · **Gate**: full · **Commit**: `feat(route): elbow edges`

### T22: Theme by name
**What**: `SPINAGRAM_THEME_PATH` and `spinagram.themes` entry points in `_resolve_dir`; error lists searched places.
**Where**: `src/spinagram/theme.py`
**Depends on**: T21 · **Reuses**: `_resolve_dir` · **Requirement**: THM-01..04
**Done when**: DDT setups (builtin, path, env dirs incl. missing, entry point pkg / pkg:ATTR, nothing) → resolved dir or exact error lines; `extends:` path covered; gate passes.
**Tests**: integration · **Gate**: build · **Commit**: `feat(theme): resolve themes by name`

### T23: Nested zones count as content
**What**: `zone-underused` content = child zones + free nodes, overlaps once; undeclared child zone detection.
**Where**: `src/spinagram/qa.py`
**Depends on**: T22 · **Reuses**: `_overlap` · **Requirement**: ZUN-01..03
**Done when**: DDT nesting fixtures with hand-computed ratios; Account›Region›VPC clean; tiny child still reported; gate passes.
**Tests**: unit · **Gate**: full · **Commit**: `fix(check): count child zones in zone-underused`

### T24: Shared text scale
**What**: Builder pre-pass applying the smallest per-role size across members of containers with the flag.
**Where**: `src/spinagram/layout.py`
**Depends on**: T23 · **Reuses**: `_Builder.node`, `self.fits` · **Requirement**: TSC-01, TSC-02, TSC-04
**Done when**: DDT (one long title / all equal / flag off / same_size default) → sizes; unchanged rows byte-identical; gate passes.
**Tests**: integration · **Gate**: full · **Commit**: `feat(layout): shared text scale in rows`

### T25: text-scale-mismatch diagnostic
**What**: P2 issue when siblings differ by > 10 % per role and the flag is off.
**Where**: `src/spinagram/qa.py`, `src/spinagram/layout.py` (scene sizes)
**Depends on**: T24 · **Requirement**: TSC-03
**Done when**: DDT around the 1.10 boundary (1.09 no, 1.11 yes) with exact detail; gate passes.
**Tests**: integration · **Gate**: full · **Commit**: `feat(check): report uneven text sizes in rows`

### T26: Font subset module
**What**: `backends/fontsubset.py`: subset to chars, keep flavour, cache, fallback on error.
**Where**: `src/spinagram/backends/fontsubset.py`
**Depends on**: T25 · **Reuses**: fontTools · **Requirement**: FNT-02, FNT-05, FNT-06
**Done when**: DDT on bundled Noto fonts: subset cmap == chars ∪ {space}; bytes identical across 2 runs and PYTHONHASHSEED 0..3; size ratio < 25 %; broken font → original bytes + warning; gate passes.
**Tests**: unit · **Gate**: quick · **Commit**: `feat(svg): font subsetting`

### T27: SVG font modes, CLI and PNG
**What**: `to_svg(fonts=)`, SVG backend option, `render --fonts`, link mode, PNG uses subset.
**Where**: `src/spinagram/backends/svg.py`, `src/spinagram/backends/png.py` (if needed), `src/spinagram/cli.py`, `src/spinagram/api.py`
**Depends on**: T26 · **Requirement**: FNT-01, FNT-03, FNT-04, FNT-07
**Done when**: DDT modes → embedded face bytes (embed == file), subset cmap, link `@import` URL text; CLI flag happy + invalid value; PNG test when chromium exists; gate passes.
**Tests**: integration · **Gate**: build · **Commit**: `feat(svg): fonts subset, embed or link`

### T28: Docs
**What**: Reference pages for every new API/theme key/check kind, release notes "what's new in 0.5", CHANGELOG unreleased, agent skill notes if they list check kinds.
**Where**: `docs/content/docs/**`, `CHANGELOG.md`, `src/spinagram/agent_skills/**`
**Depends on**: T27 · **Requirement**: — (all, documentation)
**Done when**: every new public name appears in docs; build gate passes.
**Tests**: none · **Gate**: build · **Commit**: `docs: consul diagram improvements`

### T29: Validation and state
**What**: Independent verifier pass (spec-anchored ACs + mutations) → `validation.md`; STATE.md decisions; spec traceability to Verified.
**Where**: `.specs/features/consul-diagrams/validation.md`, `.specs/project/STATE.md`, `spec.md`
**Depends on**: T28 · **Requirement**: all
**Done when**: verdict PASS or gaps fixed; build gate passes.
**Tests**: none · **Gate**: build · **Commit**: `docs(specs): record consul diagram verification`

---

## Diagram-Definition Cross-Check

| Task | Depends On (body) | Diagram | Status |
| ---- | ----------------- | ------- | ------ |
| T1 | None | start | ✅ |
| T2–T29 | previous task | linear chain | ✅ |

## Test Co-location Validation

| Task | Layer | Matrix Requires | Task Says | Status |
| ---- | ----- | --------------- | --------- | ------ |
| T2, T6, T9, T13, T16, T20, T23, T26 | engine helpers / model | unit | unit | ✅ |
| T1, T3–T5, T7, T8, T10–T12, T14, T15, T17–T19, T21, T22, T24, T25, T27 | builder / YAML / theme / backend / CLI | integration | integration | ✅ |
| T28, T29 | docs / specs | none | none | ✅ |

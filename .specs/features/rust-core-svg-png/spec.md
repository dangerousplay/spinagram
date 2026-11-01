# Rust core: scene model, SVG drawing and PNG without a browser

**Status:** In Tasks · **Size:** Large · **Branch:** `spike/rust-core`
**Builds on:** `rust-core-routing` (verified), STATE.md 2026-11-01 (Rust core port pattern)

## Problem Statement

The Rust core can measure text and route edges, but it cannot see a diagram: there is no shared scene model,
so other languages and the future WASM editor cannot draw anything, and every later slice (CSS, animation)
needs a scene to work on. PNG export also starts headless Chromium through Playwright, about 1.5 s per run
plus a 150 MB browser install. This feature gives Rust the scene (with a published JSON schema), ports the
SVG drawing step with byte-identical output, and renders PNG with resvg, with no browser.

## Goals

- [ ] Every example scene crosses into Rust as JSON and back without loss, against a committed JSON Schema.
- [ ] With `SPINAGRAM_RUST=1`, every example SVG is byte-identical to the Python writer in all three font modes.
- [ ] With the Rust core, PNG export needs no Playwright/Chromium and stays visually close to the Chromium PNG.

## Out of Scope

| Feature | Reason |
|---|---|
| Font subsetting in Rust | fontTools output is byte-pinned (FNT tests); `subsetter` would change embedded bytes. Stays Python |
| Building the scene in Rust (layout passes, model) | Later slices; this feature only carries a finished scene |
| PPTX, Figma, Excalidraw backends | Stay Python |
| Pixel-identical PNG vs Chromium | Different rasterizers; a similarity bound is the contract |
| Removing the Playwright path | Kept as `SPINAGRAM_PNG=chromium` and as the default without the core |
| CSS animation | Next features; the schema only reserves room (`version` field) |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
|---|---|---|---|
| Split of the SVG writer | Rust draws the items and returns `(defs, back, mid, front, chars)`; Python keeps `faces()` (font subset/embed/link), the `<svg>` head, `<metadata>` and the content hash | Font subsetting stays in fontTools; one assembly path for both modes keeps the hash identical | y |
| Scene transport | `spinagram.scene_json.dumps(scene)`: JSON with `"version": 1`; paths as absolute strings; tuples as arrays | Language-neutral; the same file is what other languages and WASM will read | y |
| Fields carried | Everything `to_svg` and `fonts()` read (items, size, background, title, sources, item_facts, meta_tooltips); QA-only fields are optional in the schema and omitted by default | Keep the payload small; QA stays Python | y |
| Python float formats | Rust reproduces `format(x, ".1f")` and `format(x, "g")` exactly | Byte identity | y |
| PNG engine choice | With the core active: resvg by default; `SPINAGRAM_PNG=chromium` forces Playwright. Without the core: Playwright as today | Users with the core get the fast path; nobody loses the old path | y |
| PNG fonts | resvg's font database gets the scene's font files (`Scene.fonts()` with a file), the bundled Noto fallbacks, then system fonts | Embedded `@font-face` data URIs are not used by resvg | y |
| PNG similarity bound | Per example at scale 1: mean absolute channel difference ≤ 8 (0–255) and ≤ 2 % of pixels with any channel differing by more than 64, vs the Chromium PNG | Same style of gate as the png-to-svg fidelity rule (mean Δ ≤ 8) | y |
| Schema generation | `schemars` derives `rust/schema/scene.schema.json` from the Rust structs; a test fails when the committed file is stale | One source of truth for other languages | y |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: The scene crosses into Rust ⭐ MVP

**User Story**: As a developer of another front-end (WASM editor, other languages), I want a documented scene JSON
that Rust reads so that I can draw spinagram diagrams without Python.

**Acceptance Criteria**:

1. WHEN `scene_json.dumps(scene)` runs THEN it SHALL return JSON with `"version": 1` and every field `to_svg` reads (items with their type tag, width, height, background, title, sources, item_facts, meta_tooltips). <!-- event --> (SCN-01)
2. WHEN the Rust core parses the JSON of any example scene and serializes it again THEN the result SHALL equal the input as JSON values. <!-- event --> (SCN-02)
3. The repository SHALL contain `rust/schema/scene.schema.json` generated from the Rust scene types, and a test SHALL fail when it differs from a fresh generation. <!-- ubiquitous --> (SCN-03)
4. WHEN the JSON of every example scene is validated against `scene.schema.json` THEN validation SHALL pass. <!-- event --> (SCN-04)
5. IF the JSON has a `version` other than 1 THEN the Rust core SHALL return an error naming the found and the supported version. <!-- unwanted --> (SCN-05)

**Independent Test**: Dump every example scene, round-trip it through the binding, compare; validate against the schema.

---

### P1: SVG drawn in Rust, byte for byte ⭐ MVP

**User Story**: As a spinagram user with the Rust core, I want SVGs drawn by the core with exactly the same bytes.

**Acceptance Criteria**:

1. WHERE the Rust core is active, `to_svg` SHALL draw the scene items in Rust and return a string byte-identical to the Python writer's, for `fonts` = `subset`, `embed` and `link`. <!-- optional-feature --> (SVG-01)
2. The Rust number formatting SHALL equal Python `format(x, ".1f")` and `format(x, "g")` for 0, -0.0, 0.05, 0.15, 0.25, 2.5, 1e-5, 123456, 1234567, 0.1 + 0.2, 1e16 and -3.75. <!-- ubiquitous --> (SVG-02)
3. The Rust escaping SHALL equal `html.escape(s, quote=False)` and `html.escape(s, quote=True)` for text containing `& < > " '` and non-ASCII. <!-- ubiquitous --> (SVG-03)
4. WHEN a scene embeds an image or icon THEN the Rust writer SHALL emit the same `data:` URI (MIME and base64) as Python. <!-- event --> (SVG-04)
5. WHEN connectors use markers or shapes use a box-shadow THEN the Rust writer SHALL emit the same `<marker>`/`<filter>` ids and the same defs order as Python. <!-- event --> (SVG-05)
6. WHEN items carry fact ids THEN the Rust writer SHALL emit the same `<title>` tooltips as Python. <!-- event --> (SVG-06)
7. WHILE the Rust core is not active `to_svg` SHALL produce the same bytes as before this feature. <!-- state --> (SVG-07)
8. The Rust writer SHALL report the characters drawn per face `(family, weight, italic)` exactly as the Python writer collects them, so the subset fonts are identical. <!-- ubiquitous --> (SVG-08)

**Independent Test**: Render every example in both modes and all three font modes; `diff -r` is empty.

---

### P2: PNG without a browser

**User Story**: As a spinagram user, I want PNG export to work without installing Chromium.

**Acceptance Criteria**:

1. WHERE the Rust core is active and `SPINAGRAM_PNG` is unset or `resvg`, `PngBackend` SHALL render with the Rust core's resvg renderer and SHALL NOT import Playwright. <!-- optional-feature --> (PNG-01)
2. WHERE `SPINAGRAM_PNG=chromium`, `PngBackend` SHALL render with Playwright as before. <!-- optional-feature --> (PNG-02)
3. WHEN a scene of width W and height H is rendered at scale s THEN the PNG SHALL be `round(W*s)` × `round(H*s)` pixels. <!-- event --> (PNG-03)
4. WHEN a scene uses a theme font file THEN the resvg renderer SHALL draw its text with that font file. <!-- event --> (PNG-04)
5. WHEN any example is rendered at scale 1 with resvg and with Chromium THEN the mean absolute channel difference SHALL be ≤ 8 and the share of pixels with a channel difference > 64 SHALL be ≤ 2 %. <!-- event --> (PNG-05)
6. IF the Rust core is not active and Playwright is missing THEN `PngBackend` SHALL raise the existing RuntimeError message unchanged. <!-- unwanted --> (PNG-06)

**Independent Test**: Uninstall nothing; set `SPINAGRAM_RUST=1`, render PNGs with Playwright import blocked: files appear with the right size and pass the similarity bound.

---

### P2: Parity checked automatically

**Acceptance Criteria**:

1. WHEN `rust/bench/svg_png_parity.py` runs THEN it SHALL report SVG byte identity per font mode over every example, PNG similarity per example (when Chromium is available), and Python vs Rust timings, and SHALL exit non-zero on any SVG difference or similarity breach. <!-- event --> (PAR-11)
2. WHEN CI's `rust` job runs THEN it SHALL run the SVG part of `svg_png_parity.py` and the schema freshness test. <!-- event --> (PAR-12)

---

## Edge Cases

- WHEN a text line is empty THEN both writers SHALL emit `&#160;` and count a no-break space as drawn (SVG-01, SVG-08).
- WHEN a block has fallback runs THEN the Rust writer SHALL emit the same nested `<tspan font-family=…>` (SVG-01).
- WHEN `Scene.sources` is non-empty THEN the `<metadata id="spinagram-sources">` JSON SHALL be identical (built in Python, SVG-01).
- IF an image file is missing THEN the Rust path SHALL raise `FileNotFoundError` naming the path, as Python does (SVG-04).
- WHEN a scene has a `Text` item whose id starts with `z` THEN it SHALL go to the back layer in both writers (SVG-01).

## Implicit-requirement dimensions

| Dimension | Coverage |
|---|---|
| Input validation & bounds | SCN-04, SCN-05 (schema, version) |
| Failure / partial-failure states | SCN-05, missing image edge case, PNG-06 |
| Idempotency / retry | N/A because rendering is a pure function of the scene (byte identity covers it) |
| Auth boundaries & rate limits | N/A because this is a local library |
| Concurrency / ordering | SVG-05 (defs order); the binding releases the GIL like the other slices |
| Data lifecycle / expiry | N/A because nothing is stored |
| Observability | PAR-11 reports parity and timings |
| External-dependency failure | PNG-02, PNG-06 (Playwright paths), core absent → Python (SVG-07) |
| State-transition integrity | N/A because there are no state machines in scope |

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
|---|---|---|---|
| SCN-01 | P1: scene | In Tasks | Implementing |
| SCN-02 | P1: scene | In Tasks | Implementing |
| SCN-03 | P1: scene | In Tasks | Implementing |
| SCN-04 | P1: scene | In Tasks | Implementing |
| SCN-05 | P1: scene | In Tasks | Implementing |
| SVG-01 | P1: SVG | In Tasks | Implementing |
| SVG-02 | P1: SVG | In Tasks | Implementing |
| SVG-03 | P1: SVG | In Tasks | Implementing |
| SVG-04 | P1: SVG | In Tasks | Implementing |
| SVG-05 | P1: SVG | In Tasks | Implementing |
| SVG-06 | P1: SVG | In Tasks | Implementing |
| SVG-07 | P1: SVG | In Tasks | Implementing |
| SVG-08 | P1: SVG | In Tasks | Implementing |
| PNG-01 | P2: PNG | In Tasks | Pending |
| PNG-02 | P2: PNG | In Tasks | Pending |
| PNG-03 | P2: PNG | In Tasks | Implementing |
| PNG-04 | P2: PNG | In Tasks | Implementing |
| PNG-05 | P2: PNG | In Tasks | Pending |
| PNG-06 | P2: PNG | In Tasks | Pending |
| PAR-11 | P2: parity | In Tasks | Pending |
| PAR-12 | P2: parity | In Tasks | Pending |

**Coverage:** 21 total, 21 mapped to tasks, 0 unmapped.

---

## Success Criteria

- [ ] 40 example SVGs byte-identical across modes in all three font modes; full suite green in both modes.
- [ ] PNG export of all examples works with Playwright blocked, within the similarity bound, and is faster than Chromium (measured).
- [ ] `scene.schema.json` committed and fresh; every example validates.

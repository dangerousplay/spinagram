# Rust engine evaluation for spinagram

Date: 2026-10-31. Status: research, no code changed.

Goals under test: (1) use the engine from other languages later, with Python staying the main front-end; (2) run live preview in the browser (WASM) for the web editor, instead of a round-trip to a Python server.

Legend: **[V]** verified on 2026-10-31 (crates.io API, GitHub API, local measurement). **[A]** assumed or estimated from experience, not checked.

---

## 1. Summary

- Goal 2 (fast live preview) does not need Rust. The Python engine already produces a scene in 3 to 250 ms for the examples [V]. Pyodide (option A) or an optimised server (option B) can reach it in weeks.
- Goal 1 (other languages) is the real argument for Rust. It only pays off if the Rust core owns the **whole spec-to-SVG pipeline** (YAML/JSON spec in, scene or SVG out). A Rust core that Python calls in small pieces gives no portability.
- Recommendation: **do not start a full port now.** Phase 0 is a cheap Pyodide spike plus a frozen "spec in, scene JSON out" contract. Start the Rust core (option C) only if the go criteria in section 8 hold. Total effort for C, phase 1 to 3: about 40 to 70 engineer-weeks. Full port (D): about 70 to 120.

---

## 2. What the engine is today

Measured from `src/spinagram/` [V]. Total Python in the package: 15,477 lines (including UI server, MCP server and bundled examples).

| Piece | Files | Lines | External dependencies |
|---|---|---|---|
| Model and Python DSL | `model.py` | 1,019 | none |
| YAML loader | `yaml_io.py` | 461 | PyYAML (`safe_load`, no comment preservation) |
| Scene types | `scene.py`, `shapes.py` | 270 + 248 | none |
| Layout (spec to scene) | `layout.py` | 766 | none |
| Engine passes (zones, endpoints, labels, route, fix, glyphs, legend, textfit, icons) | `engine/*` | about 1,350 | Pillow (icons), fontTools (via text) |
| Autolayout core | `autolayout/__init__`, `graph`, `sizing`, `route`, `flex`, `layered` | about 1,690 | none (layered is own pure-Python Sugiyama, deterministic) |
| Autolayout external adapters | `engines/dot.py` 179, `elk.py` 170, `d2.py` 296 | 645 | `dot` binary, Node/Bun plus npm ELK, `d2` binary (subprocess) |
| Text measure and wrap | `text.py` | 103 | Pillow `ImageFont` (measures at 10x, advances rounded), fontTools cmap |
| CSS cascade | `css.py` | 727 | tinycss2, Pillow `ImageColor` |
| Theme | `theme.py`, `themes/` | 391 | PyYAML |
| Icons and packs | `icons.py` | 501 | `urllib` download and cache, tar/zip, 13 pack indexes (52 KB) |
| QA, annotate, behavior, facts | `qa.py` 635, `annotate.py` 581, `behavior.py` 311, `facts.py` 195 | 1,722 | none known |
| SVG backend | `svg.py`, `fontsubset.py` | 318 + 45 | fontTools subsetting |
| PNG backend | `png.py` | 41 | Playwright and Chromium |
| PPTX backend | `pptx.py` | 592 | python-pptx, lxml |
| Figma backend | `figma.py` | 589 | emits a plugin script (JS), Pillow |
| Excalidraw backend | `excalidraw.py` | 262 | none |
| Vectorise | `vectorize.py` | 158 | vtracer, resvg-py (already Rust-backed) |
| UI server | `ui/*` | about 1,700 | starlette, uvicorn, watchfiles |
| Web app | `web/src` | 3,219 TS/TSX lines | Vite, React, CodeMirror |
| Bundled fonts | `fonts/` | 548 KB (2 Noto symbol fonts, OFL) | none |

Pipeline: YAML or Python DSL -> `Diagram` model -> engine passes and autolayout -> `build_scene` -> `Scene` (absolute geometry, resolved fonts, wrapped text) -> backend. The scene is already a clean, backend-neutral contract (`scene.py` says "backends read only these types"). That is the natural seam for a Rust split.

**Core to port for "scene + layout + text + SVG":** model 1,019 + yaml_io 461 + scene/shapes 518 + layout 766 + engine about 1,350 + autolayout core 1,690 + text 103 + css 727 + theme 391 + icons 501 + svg 363 = about **7,900 lines of Python**. Add qa/annotate/behavior/facts (about 1,700) for check and annotations: about 9,600.

### Measured latency today [V, local, warm Python, macOS]

| Diagram | YAML load | Scene build |
|---|---|---|
| `quickstart.yaml` | 1 ms | 39 ms first, 3 ms warm |
| `aws_layout.yaml` | 2 ms | 2 to 4 ms |
| `software_architecture.yaml` | 1 ms | 157 to 245 ms |

A cold CLI render of the larger consul example took 1.55 s end to end, mostly interpreter start, imports, PNG via Chromium and file output. Not measured: SVG string emission and the HTTP/React cycle. Conclusion: engine time is small, so the visible lag in the current editor is round-trip, parse, DOM swap and font subsetting, not layout.

### Tests pinning behaviour [V]

58 test files, **952 test functions** in `tests/`, plus a Node mock for Figma scripts (`tests/js/figma_mock.mjs`) and 3 web test suites. Areas: CSS and inspector (cascade), text fit and glyph fallback, engine passes (zones, routing, labels, endpoints, legend, grid, sizing, icons), layered layout, autolayout, YAML bands/zones (`test_cd_*`, about 23 files), backend parity, PPTX, Excalidraw, icon packs, MCP, UI. Most assert on scene or SVG facts, not on byte-exact output, which helps a port. Many call the Python API directly (`Diagram().box(...)`), so they only exercise Rust if the Python model delegates to it.

---

## 3. Rust crates per concern

Versions from the crates.io API on 2026-10-31 [V]. WASM and fit columns are my assessment [A] unless noted.

### 3.1 Bindings

| Option | Version | Use | Fit |
|---|---|---|---|
| PyO3 | 0.30.1, updated 2026-10-14 [V] | Python extension | Standard. Use `abi3` wheels (one wheel per OS/arch for Python 3.11+). |
| maturin | 1.16.0, 2026-10-29 [V] | Build and publish wheels | Standard. Handles manylinux, macOS universal2, Windows, sdist. |
| wasm-bindgen | 0.2.130, 2026-10-30 [V] | Rust to JS/WASM | Standard for browser and Node. Pair with `wasm-pack` or `cargo build` + `wasm-bindgen` CLI. |
| napi-rs | 3.16.1, 2026-10-31 [V] | Native Node addon | Good for a Node CLI or VS Code extension host. WASM is enough for most JS uses; napi only if speed or file access matters. |
| UniFFI | 0.32.2, 2026-09-23 [V] | Kotlin, Swift, Python, Ruby bindings | Good for Go-adjacent and mobile via generated bindings (Go is third-party). Pre-1.0. |
| C ABI (`cbindgen`, `extern "C"`) | n/a | Go (cgo), C#, Java FFI | Most portable. Keep the API to "JSON string in, JSON/SVG string out". |

Design rule that makes all of these cheap: expose one coarse function, `render(spec_json_or_yaml, options_json) -> {scene_json, svg, diagnostics}`. Every language binding is then a thin wrapper, and there is no object graph to marshal.

### 3.2 Graph layout

| Crate | Version / updated | Licence | WASM | Fit |
|---|---|---|---|---|
| `rust-sugiyama` | 0.4.0, 2025-09 [V] | MIT | yes (pure Rust) [A] | Plain layered layout, no compound graphs, no ports. Low usage (59k downloads). Spinagram's own layered engine (679 lines) is more capable (nested groups, dummy channels). **Port your own, do not adopt.** |
| `layout-rs` | 0.1.3, 2025-04 [V] | MIT | yes [A] | Graphviz-style DOT subset with its own layered layout. Stale, small. Reference only. |
| `petgraph` | 0.8.3, 2025-09 [V] | MIT/Apache | yes | Graph data structure and algorithms (toposort, SCC, DFS). Use for cycle breaking and ranking helpers. |
| `taffy` | 0.15.1, 2026-10-25 [V] | MIT | yes (used in Bevy, Dioxus, Zed-adjacent) | Flexbox, grid, block. Fits `flex.py` (129 lines) and the planned grid/constraint layout (roadmap G1). Parity with Spinagram's own flex semantics must be tested; the flex engine is small enough to port by hand instead. |
| ELK port | none found [V]: `elk-rs` on crates.io is an unrelated SMTP project | n/a | n/a | No Rust ELK. ELK stays JS (elkjs). In WASM it can run as JS next to the Rust module. |
| dagre port | `dagre-rs` 0.1.0, 2025-10, non-standard licence [V] | unclear | unknown | Immature. Skip. |
| Graphviz | `graphviz-rust` 0.9.9 [V] is only a DOT builder/wrapper that shells out | non-standard | no | Not an engine. Graphviz has no usable Rust port; in WASM use `@viz-js/viz` (JS) if wanted. |

Pick: port the existing layered engine and flex engine by hand; use petgraph only for helpers; keep dot/ELK/D2 as external adapters behind a trait.

### 3.3 Geometry

| Crate | Version | Fit |
|---|---|---|
| `kurbo` | 0.13.1, 2026-05 [V] | Bezier, path ops, bounding boxes, arc length, used by Vello/Linebender. Best choice for edge routing curves, rounded elbows, and SVG path output. |
| `lyon` | 1.0.19, 2026-03 [V] | Tessellation for GPU. Not needed (SVG output). |
| `euclid` | 0.22.14, 2026-03 [V] | Typed points/rects. Optional; plain `f64` structs are enough. |

### 3.4 Text

Parity here is the highest risk (section 6). Current measure: Pillow at 10x size, advances rounded to integer pixels, then scaled. The Rust result will differ by sub-pixel amounts unless the measurement is replicated deliberately.

| Crate | Version / updated | Licence | WASM | Fit |
|---|---|---|---|---|
| `skrifa` + `read-fonts` (fontations) | 0.49.0 / 0.46.0, 2026-10-21 [V] | MIT/Apache | yes | Active Google-backed font reading. Use for advances, cmap (glyph coverage), metrics. Replaces fontTools `getBestCmap` and Pillow advances. |
| `harfrust` | 0.15.0, 2026-10-22 [V] | MIT | yes | The maintained HarfBuzz port. Use only if complex shaping (kerning, ligatures, Arabic/Indic) matters. |
| `rustybuzz` | 0.20.1, **last release 2024-11** [V] | MIT | yes | Effectively superseded by harfrust. Avoid for new work. |
| `ttf-parser` | 0.25.1, **last release 2024-11** [V] | MIT/Apache | yes | Stable but no longer moving; resvg still depends on it. Fine, but prefer skrifa for new code. |
| `fontdb` | 0.24.0, 2026-07 [V] | MIT | partial: no system fonts in WASM, only in-memory `load_font_data` | Font database. In WASM, load bundled fonts only. |
| `cosmic-text` | 0.19.0, 2026-04 [V] | MIT/Apache | yes | Full text layout (wrap, shaping, bidi). Heavier than needed; its wrapping differs from Spinagram's own rules (break after `-./:·`, IPv4 protected). |
| `parley` | 0.12.0, 2026-10-09 [V] | MIT/Apache | yes | Linebender text layout. Pre-1.0, API still moving. |
| `swash` | 0.2.10, 2026-07 [V] | MIT/Apache | yes | Shaping and scaling; not needed. |

Pick: `skrifa` for metrics and cmap, own wrapper port of `textfit.py` and `wrap_paragraphs` (the rules are custom and pinned by tests), optional `harfrust` later. Do not adopt cosmic-text or parley for wrapping.

### 3.5 SVG and PNG

| Crate | Version / updated | Licence | WASM | Fit |
|---|---|---|---|---|
| `resvg` / `usvg` | 0.49.0, 2026-10-24 [V] | Apache/MIT | yes | **Replaces Chromium for PNG** and gives PNG/PDF from the same SVG. Gaps: no full CSS, limited `<foreignObject>`, text needs fonts loaded. Spinagram SVG embeds fonts as data URIs (subset); resvg does not read `@font-face` data URIs, so fonts must be passed to its `fontdb` directly. Needs a PNG parity check on dashes, markers, shadows, filters. Spinagram already uses `resvg-py` in `vectorize.py`. |
| `tiny-skia` | 0.12.0, 2026-02 [V] | BSD-3 | yes | Rasteriser under resvg. Direct use not needed. |
| `svg` | 0.18.0, **2024-09** [V] | MIT/Apache | yes | Tiny SVG builder. SVG emission is string formatting; hand-write it (the Python version is 318 lines) with `quick-xml` escaping or none. |
| `image`/`png` | n/a [A] | MIT | yes | For PNG encode, if resvg is not used. |

### 3.6 CSS

| Crate | Version | Licence | WASM | Fit |
|---|---|---|---|---|
| `cssparser` | 0.38.0, 2026-09 [V] | MPL-2.0 | yes | Tokeniser and parser, direct counterpart of `tinycss2` (Servo). Fits the 727-line cascade: tokenise, own rule/selector model. |
| `selectors` | 0.41.0, 2026-09 [V] | MPL-2.0 | yes | Servo's selector matching. Needs a trait impl for your element tree; powerful but heavy. Spinagram selectors are a small subset (types, classes, ids, attributes, combinators, custom properties [A, check `css.py`]); a hand matcher may be less work than the trait glue. |
| `lightningcss` | 1.0.0-alpha.72 (no stable), 2026-07 [V] | MPL-2.0 | yes | Parser plus transformer, with a heavy API aimed at bundling. Alpha. Skip. |

MPL-2.0 is file-level copyleft: fine for linking into an MIT project, but note it in the licence notices. Pick: `cssparser` plus own selector matcher (try `selectors` only if the subset grows).

### 3.7 YAML, including comment-preserving edits

| Crate | Version / updated | Licence | Notes |
|---|---|---|---|
| `serde_yaml` | 0.9.34+deprecated, 2024-03 [V] | MIT/Apache | Archived. Do not start on it. |
| `serde_yml` | 0.0.13, 2026-05 [V] | MIT/Apache | Now a **deprecated shim**; crates.io description says unmaintained. Avoid. |
| `yaml-rust2` | 0.13.0, 2026-09 [V] | MIT/Apache | Maintained fork of yaml-rust, YAML 1.2, event/tree API. Good, small. |
| `saphyr` | 0.3.3, 2026-10-27 [V] | MIT/Apache | Same lineage (successor-style of yaml-rust2), 1.2 compliant, active. Spans (marker positions) allow source-range edits. |
| `yaml-edit` | 0.3.6, 2026-10-31 [V] | Apache-2.0 | "A lossless parser and editor for YAML files", based on rowan (CST). The only crate found that targets comment-preserving edits. Young (252k downloads), 0.x. Verify flow-style handling and key insertion against the canvas editor's fixtures before betting on it. |
| `rowan` | 0.17.0 [V] | MIT/Apache | CST library under yaml-edit; could be used to build an own lossless layer. |
| JS side: `yaml` (eemeli) | n/a | ISC | The canvas-editor spec already picks it (`parseDocument` plus `String(doc)`). Mature and proven for comment preservation [A, from the spec's research]. |

Findings: for **reading**, use `saphyr` or `yaml-rust2` (deserialize into the model by hand; the loader has many shorthand forms such as `"src -> dst: label"`, so serde derive helps little). For **comment-preserving edits**, the canvas editor does not need Rust: eemeli `yaml` in the browser already satisfies the spec. If a Rust edit API is wanted later, `yaml-edit` is the candidate, with an own span-based fallback on top of saphyr (patch byte ranges for a changed scalar). Treat this as a separate, optional deliverable.

### 3.8 PPTX / OOXML

| Crate | Version | Fit |
|---|---|---|
| `zip` | 9.2.0, 2026-10-31 [V] | Container. Works in WASM. |
| `quick-xml` | 0.42.0, 2026-08 [V] | XML writer/reader. |
| `ooxmlsdk` | 0.14.0, 2026-10-19 [V] | Generated OOXML types, MIT/Apache. Large and 0.x; unproven for slides [A]. |
| `pptx-rs` | 0.1.0, 2024-02 [V] | Abandoned. |
| `docx-rs` | 0.4.22 [V] | DOCX only. |

There is no mature Rust PPTX library. python-pptx plus lxml (592 lines in `pptx.py`) stays in Python: **PPTX and Figma consume the scene JSON from Rust.** This is also why scene-as-contract matters.

---

## 4. Architecture options

### Comparison

| | A. Pyodide in browser | B. Optimised server | C. Hybrid Rust core (scene+layout+text+SVG), Python API, PPTX and Figma stay Python | D. Full port |
|---|---|---|---|---|
| Live preview latency | Cold start 5 to 15 s once (Pyodide runtime about 10 MB, plus Pillow, PyYAML, fontTools, tinycss2 wheels) [A]; warm render about 20 to 300 ms plus overhead, similar to native Python x1.5 to 3 [A] | Local: 30 to 120 ms (HTTP and DOM) [A]. Remote or slow disk: worse. Needs a running server | Cold start 100 to 400 ms (WASM about 1.5 to 3 MB gzipped incl. fonts excluded) [A]; warm render 1 to 20 ms [A] | Same as C |
| Other languages | None (Python only) | Anything that can call HTTP, needs a process | Strong: WASM for JS/TS, C ABI for Go, napi/UniFFI for others. Python via PyO3 | Strongest: all outputs, one binary CLI |
| Offline / static hosting | Yes (heavy first load) | No server, no editor | Yes | Yes |
| Python stays main front-end | Yes, unchanged | Yes | Yes (PyO3), DSL builds a spec for Rust | Python DSL is a thin builder |
| Work to ship | 2 to 4 weeks spike to product [A] | 1 to 3 weeks [A] | 40 to 70 weeks | 70 to 120 weeks |
| New toolchain | none | none | Rust, maturin, wasm-pack | Rust, plus rewrites of PPTX/Figma/PNG |

### What breaks, per option

| Piece | A. Pyodide | B. Server | C. Hybrid | D. Full |
|---|---|---|---|---|
| Graphviz `dot` adapter | Breaks (no subprocess) | Works | Browser: breaks, unless viz.js WASM is wrapped; native: works via subprocess trait | Same as C |
| ELK adapter (Node/Bun plus elkjs) | Breaks as subprocess; elkjs can run in the browser's JS (call across Pyodide's JS bridge) | Works | Browser: elkjs next to the WASM module, works; native: subprocess | Same as C |
| D2 adapter (`d2` binary) | Breaks (Go binary; d2 has a WASM build upstream [A]) | Works | Browser: breaks; native: subprocess | Same as C |
| Chromium PNG | Breaks. Use canvas `drawImage` from SVG in the browser | Works | Use `resvg` (native and WASM) | `resvg` |
| Icon packs | Download via `urllib` does not work in Pyodide (needs `pyodide.http`/fetch, CORS); caches need IndexedDB or the virtual FS | Works | The core takes icon SVG bytes as input; the host fetches and caches (browser: `fetch` plus IndexedDB; Python: today's cache). Cleaner than today | Same as C |
| Fonts in WASM | Pillow loads files from the virtual FS; need to ship or fetch font files; system fonts do not exist | Server fonts | The host passes font bytes; the core never reads disk. Bundle the 2 Noto symbol fonts (548 KB) and the theme fonts as assets | Same as C |
| `fontsubset` (fontTools) | Works (pure Python, slow in WASM) [A] | Works | Needs a Rust subsetter (`subsetter` crate from Typst [A, not verified]) or skip subsetting in preview | Same |
| Comment-preserving YAML edit | Not needed (JS `yaml`) | JS `yaml` | JS `yaml` | same |

### Notes

- **A** is cheap and reuses 100 % of the code and tests. Weak points: heavy cold start, Pyodide version churn (latest is 314.0.7 [V]), wheels for Pillow/fontTools must exist in the Pyodide distribution, and it delivers nothing for goal 1. It is a good way to **measure what in-browser preview feels like** before spending on Rust.
- **B** is the right fix if the pain is only the round-trip. Options: keep a warm process (already the case), push over WebSocket, debounce, diff the SVG (patch DOM nodes by id instead of replacing), cache icon data URIs and font subsets by content hash, skip subsetting in preview. The 157 to 245 ms scene time for the largest example suggests a profile pass (layered engine, icon resolution) could halve it.
- **C** is where goals 1 and 2 meet. The risk is the boundary. Two ways:
  1. *Spec boundary (recommended).* Rust owns YAML parse (or accepts a JSON spec), model passes, autolayout, CSS, text fit, scene, SVG. Python's `Diagram` DSL becomes a builder that serialises to the spec. Portable, but the Python `Diagram` object loses direct post-hoc mutation unless it re-serialises.
  2. *Scene boundary.* Python keeps model/layout and Rust only emits SVG from the scene. Tiny gain: SVG emission is 318 lines. Not worth it.
  Boundary 1 means the Python tests that build `Diagram` objects and inspect them keep working only if `Diagram` stays a Python data structure that serialises cleanly. Plan for a compatibility layer.
- **D** adds PPTX, Figma, Excalidraw and PNG in Rust. PPTX has no mature crate (hand-written OOXML), Figma output is JS text, so the payoff is mainly a single binary CLI. Defer.

---

## 5. Port effort (engineer-weeks, one experienced Rust engineer who knows the code)

Ranges include porting the tests to Rust or to the shared fixture runner, but not review latency. LOC are Python lines; Rust usually lands at 1.2 to 1.8 times that.

| Module | Python LOC | Weeks (range) | Complexity / risk |
|---|---|---|---|
| Spec model + serde-free loader (`model.py`, `yaml_io.py` incl. shorthand forms) | 1,480 | 4 to 7 | Many shorthands and validation messages (`SpecError` text is likely tested). Error-message parity is tedious. |
| Scene types + shapes + SVG emission | 836 | 2 to 3 | Easy. Golden diffs. |
| Theme + theme YAML loader | 391 | 1 to 2 | Easy. |
| CSS cascade, selectors, custom properties, inspector data (`css.py`) | 727 | 4 to 7 | **High**: specificity, inheritance, `var()`, error suggestions (difflib), `ImageColor` named colours table. Pinned by `test_css*.py`, `test_legend_css.py`, `test_engine_style.py`. |
| Text: measurement, wrap, glyph fallback, textfit (`text.py`, `engine/textfit.py`, `glyphs.py`) | 313 | 3 to 5 | **High parity risk**: Pillow 10x measure with integer rounding vs. skrifa advances; kerning. Must define a golden width table and choose whether to mimic rounding. |
| Layout (spec to scene), `layout.py` | 766 | 4 to 6 | Dense; touches every feature. |
| Engine passes: zones, endpoints, labels, route, fix, legend, icons | about 1,040 | 5 to 8 | Medium. Many `test_cd_*` and `test_engine_*` cases. |
| Autolayout core: graph, sizing, flex, layered, route | about 1,690 | 6 to 10 | **High**: layered is order-sensitive (barycentre ties, isotonic regression); float and iteration order must match exactly or snapshots shift. Use ordered maps. |
| External adapters (dot, elk, d2) behind a trait, subprocess | 645 | 1 to 2 (native), plus 1 to 2 for ELK-in-JS in the browser | Mostly glue. |
| Icons + packs (`icons.py`), cache, SVG sanitise and embed | 501 + engine/icons 117 | 3 to 5 | Network and cache move to the host; core only parses SVG bytes (usvg or quick-xml), colour recolour, viewBox. |
| QA / check / annotate / behavior / facts | 1,722 | 4 to 7 | Medium; many diagnostics. Can follow in a later phase. |
| Font subsetting for SVG (`fontsubset.py`) | 45 | 1 to 3 | Needs a Rust subsetter or defers to host. |
| Bindings: PyO3 + maturin CI (wheels), wasm-bindgen package + npm, C ABI | n/a | 3 to 5 | Build matrix and release automation dominate. |
| Python compatibility layer (DSL to spec, test harness switch) | n/a | 3 to 5 | Needed for the parity strategy. |
| Parity harness (golden scenes/SVG, differ, CI) | n/a | 2 to 3 | Do first. |
| PPTX in Rust (D only) | 592 | 6 to 10 | No mature crate; hand-written OOXML; python-pptx details (placeholders, text autofit). |
| Figma plugin script emitter (D only) | 589 | 2 to 4 | Emits JS text; easy but tied to the JS mock tests. |
| Excalidraw (D only) | 262 | 1 to 2 | Easy. |
| PNG via resvg (replace Chromium) | 41 | 1 to 3 | Visual parity of dashes, shadows, markers. |
| Web editor integration (WASM glue, workers, caching) | n/a | 3 to 5 | |

Totals:

| Scope | Weeks |
|---|---|
| Phase 1 to 3 (option C: scene, layout, text, CSS, SVG, adapters, bindings, harness, QA) | **40 to 70** |
| Option D extras (PPTX, Figma, Excalidraw, CLI, PNG) | +20 to 35 |
| Option D total | **70 to 120** (reasoning: 60 to 105 module sum plus integration contingency) |

The ranges are wide because I assumed the Python behaviour is only partly documented; most of the real specification lives in the 952 tests and the code. A realistic calendar for one engineer on C is 10 to 16 months.

### Risky parts

1. **Text fitting parity.** Pillow advances at 10x rounded to integers, plus fontTools cmap, versus skrifa/harfrust unrounded advances. Small width differences flip wrap points, which move boxes in autosized layouts. Mitigate: build a golden "width table" (string, font, size -> width) from Python, replicate the rounding in Rust, or accept and re-baseline tests once, deliberately. Also: Pyodide and Rust must use identical fonts.
2. **Layout parity.** Layered layout is deterministic but sensitive to iteration order and float ties. Python `dict` order is insertion order; Rust needs `IndexMap`. Also the improvements-layout-engine notes show the engine is still growing (fit, zone headers, E1 to E4 routing, G1 grid); porting a moving target doubles work. **Freeze or finish the roadmap items first, or port behind the parity harness.**
3. **CSS cascade.** The cascade, `var()` and inspector provenance data feed the UI Inspector; subtle ordering rules are pinned by tests.
4. **Icon cache and network.** Moves out of the core; the host contract must be designed before porting.
5. **External engines in WASM.** dot and D2 cannot run in the browser engine path; the editor must label those layouts "server only" or fall back to the Python server.
6. **Contributor barrier.** Today a contributor needs Python only. Rust raises it, and the 15 k-line codebase has one main author [A].

### Keeping parity

1. **Freeze a contract:** `spec -> scene.json` (versioned JSON schema of `scene.py`) plus `diagnostics.json` (check output).
2. **Golden corpus:** run the Python engine over all `examples/` (about 100 files) and every test fixture, store scene JSON and SVG. Rust must match with a tolerance (for example 0.01 px on geometry, exact on structure and text lines).
3. **Run the Python test suite against Rust through PyO3.** Add a switch (`SPINAGRAM_ENGINE=rust`) so `build_scene` delegates to the extension. The 952 tests then become the acceptance suite for each module. Tests that inspect internal Python objects need a shim or an explicit "python-only" mark.
4. **Differential fuzzing:** random specs (nodes, zones, edges, themes) rendered by both engines, compared on scene JSON. Cheap and finds rounding and ordering bugs.
5. **Port bottom-up in vertical slices** (text -> CSS -> theme -> scene/SVG -> model -> layout -> autolayout) with each slice individually callable from Python, so tests can switch module by module. This only works for slices with data in and out; layout needs the whole model, so slice 1 is "everything up to scene for flex-engine diagrams".

---

## 6. Benefits, use cases and costs

| Who | Gain | Needs C or D? |
|---|---|---|
| Web live editor users | Instant preview while typing or dragging (no server round-trip), works offline and on static hosting, drag preview can use real layout | C (or A with slower start) |
| JS/TS developers, docs sites, VS Code extension authors | `npm i @spinagram/core`: render in a webview or Node without Python | C |
| Go, Java, C# users | C ABI wrapper; render diagrams in CI tools | C, after JSON contract |
| Large diagrams | Estimate 10 to 50 times faster than CPython for layout and fit [A]; today largest example is about 0.2 s, so this matters only for hundreds of nodes. The skill description already says "not for graphs of hundreds of nodes", so the market is limited | C |
| CLI users | Single static binary, no Python or Playwright (resvg replaces Chromium for PNG). Fonts and icons still need to be shipped or fetched | D |
| Python users | Faster, but no API change; install gets larger and wheels must be built per platform; pure-Python fallback is lost unless both engines are kept | C |
| AI agents and MCP | Same API; faster loop | marginal |

Costs:

- **Two toolchains** (uv and cargo, plus wasm-pack and bun). Release pipeline: manylinux/musllinux/macOS/Windows abi3 wheels, WASM package, npm publish, C library artefacts.
- **Contributor barrier:** Python-only contributors cannot touch layout, CSS or text.
- **Dual engines during migration:** every feature added in the layout roadmap (T1, Z1, E1 to E4, G1) would have to be written twice or wait.
- **Packaging risk:** a pure-Python `pip install spinagram` that works on any platform becomes platform wheels (still fine with maturin).
- **Dependency semantics:** Pillow, fontTools, tinycss2 and PyYAML each define behaviour that tests rely on (named colours, YAML 1.1 booleans like `yes`/`no`, anchors). PyYAML is YAML 1.1; saphyr and yaml-rust2 are YAML 1.2, so `on`/`yes`/`no` booleans differ. This is a silent behaviour break that needs an explicit decision.

---

## 7. Option scoring for the stated goals

| | Goal 2: live preview | Goal 1: other languages | Cost | Reversible |
|---|---|---|---|---|
| A. Pyodide | Good after a slow first load | none | Low | Yes |
| B. Optimise server | Good enough locally | none (HTTP only) | Very low | Yes |
| C. Hybrid Rust | Best | Good | High | Partly |
| D. Full port | Best | Best | Very high | Hard |

---

## 8. Recommendation

**Do not port yet. Reduce uncertainty in 4 to 6 weeks, then decide on option C.** Rust earns its cost only if other-language use is a real product goal. For the editor alone, A or B suffices.

### Phase 0: now (4 to 6 weeks, about 1 engineer)

1. Profile and fix B: measure the editor round-trip end to end (YAML save, scene, SVG, DOM swap). Add SVG patching and a preview mode that skips font subsetting. Target under 100 ms for 50 nodes (the canvas spec asks for under 1 s today).
2. Spike A: load spinagram in Pyodide, render `quickstart.yaml` and `software_architecture.yaml` in a web worker; record cold start, warm render time, bundle size. Stub subprocess adapters.
3. Freeze the contract: write the JSON schema of `Scene`, a `spec.schema.json`, and the golden corpus (scene JSON plus SVG for all examples). This is useful with or without Rust and costs about 2 weeks.
4. Finish the layout roadmap items that change the scene shape (T1, Z1, Z2, E1, E2) before any port starts.
5. Do the canvas editor with JS `yaml` as already specified. It does not depend on Rust.

### Phase 1: milestone that delivers value alone (about 14 to 22 weeks)

"**`spinagram-core` WASM: spec to scene to SVG for the flex and layered engines**, used by the web editor for live preview."

- Scope: YAML/JSON spec loader, theme, CSS, text fit with bundled fonts, flex and layered layout, scene, SVG (no font subsetting, fonts referenced), icons passed in by the host. External engines stay on the Python server; the editor falls back to the server for `dot`, `elk`, `d2`.
- Deliverables: npm package, in-browser preview with under 30 ms warm render, the golden harness green for the covered subset, the Python test suite running against it through PyO3 (switch, off by default).
- Value: editor feels live, works offline, JS developers can embed it.

### Phase 2 (about 14 to 24 weeks)

Full core parity (QA/check, annotate, behavior, ELK in JS for browser, native subprocess adapters), PyO3 wheels, Python front-end switched to Rust by default behind a flag, then default after one release cycle. PNG via resvg.

### Phase 3 (about 12 to 24 weeks, optional)

C ABI and UniFFI/napi bindings, single-binary CLI, possibly PPTX/Figma/Excalidraw in Rust (D). Only if a user requests them; python-pptx stays acceptable otherwise.

### Go / no-go criteria

Go to Phase 1 if **all** hold after Phase 0:
- At least 2 concrete consumers outside Python exist (a JS app or VS Code extension plan, or a Go/other-language user), or the editor product depends on offline/static hosting.
- Pyodide spike shows cold start over 8 s or warm render over 300 ms for a 50-node diagram, **and** B cannot reach under 100 ms.
- The golden corpus and scene schema exist, and the layout roadmap items that change the scene are done.
- A maintainer commits to Rust for at least 12 months.

No-go (stay on A/B) if:
- The only goal is preview speed and A or B meets targets.
- Layout roadmap is still changing weekly.
- Text width parity cannot be reached within the golden tolerance after a 2-week text-only spike (port `text.py` and `textfit.py` and compare widths on the corpus: this is the cheapest port to try first and the best predictor of the rest).

### Crate picks

| Concern | Pick | Reason |
|---|---|---|
| Python bindings | PyO3 0.30 + maturin 1.16, abi3 | standard |
| WASM / JS | wasm-bindgen (+ napi-rs later if needed) | standard |
| Other languages | C ABI with JSON in/out, UniFFI where useful | portable |
| Layered layout | own port; petgraph for helpers | rust-sugiyama too limited, no ELK/dagre port |
| Flex / grid | own port of `flex.py`; taffy for future grid | small, parity |
| Geometry | kurbo | active, routing curves |
| Font data | skrifa + read-fonts; harfrust if shaping needed; fontdb with in-memory fonts | rustybuzz and ttf-parser are stale |
| Text wrap | own port of `textfit.py` | custom, test-pinned rules |
| SVG out | hand-written string builder | 318-line Python equivalent |
| PNG | resvg 0.49 (+ usvg, tiny-skia) | replaces Chromium |
| CSS | cssparser 0.38 + own selector matcher | lightningcss is alpha, `selectors` is heavy |
| YAML read | saphyr (or yaml-rust2) | maintained, YAML 1.2 (decide on 1.1 booleans) |
| YAML edit | JS `yaml` in the editor; yaml-edit as later candidate | only lossless Rust option, young |
| PPTX | stay python-pptx; zip + quick-xml if ported | no mature crate |

### Unverified items to check in Phase 0

- Pyodide cold-start and warm timings (all numbers above are estimates).
- Which Pillow, fontTools and tinycss2 wheels ship in Pyodide 314.x.
- `yaml-edit` behaviour on flow-style lists and comment insertion.
- resvg handling of Spinagram's SVG (dashes, shadows, markers, embedded fonts).
- Whether a Rust font subsetter (for example Typst's `subsetter`) fits the embedded-font mode.
- The CSS selector subset actually used (read `css.py` fully).
- WASM bundle size and speed numbers.

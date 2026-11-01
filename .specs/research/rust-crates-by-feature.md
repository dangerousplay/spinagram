# Rust crates by feature area, and the CSS animation stack

Date: 2026-10-31. Status: library research only. No source touched.

This extends `rust-engine-evaluation.md` (same folder). It keeps that file's picks and does not redo its comparisons. Where a pick is unchanged, the row says "unchanged".

Legend: **[V]** verified today (crates.io API, GitHub API, upstream source or docs fetched). **[A]** assumed or from memory, not checked. "Released" is the crates.io `updated_at` of the newest version, which is the best proxy for last release.

---

## 1. Summary

- The engine areas are covered by the earlier picks. Additions: `subsetter` for font subsetting (replaces the open question), `csscolorparser` for named colours (replaces Pillow `ImageColor`), `i_overlay` and `rstar` for QA geometry, `pythonize` and `schemars` for the Python boundary and scene schema.
- Animation has no off-the-shelf stack. Every piece is small custom code on top of `cssparser`, `kurbo`, `resvg` and an encoder. The one real design decision is a single **animation IR** (timelines of keyframed tracks) that all outputs read: CSS-in-SVG, SMIL, frame rendering, PPTX, Lottie.
- `resvg` does not animate. Confirmed in its README: "no animations" [V]. Frames must be produced by sampling the IR at time t, emitting a static SVG, and rendering that.
- No Rust crate writes Lottie JSON [V as far as search shows]. PPTX animation XML has no Python or mature Rust library; hand-write it.

---

## 2. Engine areas to crates

Every `crates.io` fact below was fetched on 2026-10-31 [V] unless marked.

### 2.1 Scene model: `scene.py`, `shapes.py`, `model.py`

| Need | Crate | Version | Released | Licence | WASM | Custom code |
|---|---|---|---|---|---|---|
| Data types, JSON | `serde` + `serde_json` | 1.0.154 (json) | 2026-10-11 | MIT/Apache | yes | The types themselves (`Scene`, `Diagram`), the shorthand forms |
| Ordered maps (Python dict order) | `indexmap` | 2.14.2 | 2026-09-05 | MIT/Apache | yes | none |
| JSON schema of the scene contract | `schemars` | 1.2.3 | 2026-10-12 | MIT | yes | Review the generated schema, pin it in CI |
| Rust types to and from Python objects | `pythonize` | 0.29.0 | 2026-08-28 | MIT | no (PyO3 only) | Likely skip: pass JSON strings across the boundary as the earlier doc says |
| Bindings | `pyo3` 0.30.1 [V, 2026-10-14], maturin 1.16.0 [V, 2026-10-29], wasm-bindgen 0.2.130 [V] | | | MIT/Apache | wasm-bindgen yes | unchanged |
| Geometry primitives | `kurbo` | 0.13.1 | 2026-05-13 | Apache/MIT | yes | unchanged |

### 2.2 Layout: `layout.py`, `autolayout/*`, `engine/*`

| Need | Crate | Version | Released | Licence | WASM | Custom code |
|---|---|---|---|---|---|---|
| Graph structure and algorithms | `petgraph` | 0.8.3 | 2025-09-30 | MIT/Apache | yes | Cycle breaking choices, ranking |
| Flex and future grid | `taffy` | 0.15.1 | 2026-10-25 | MIT | yes | Port `flex.py` by hand unless parity tests pass on taffy |
| Layered (Sugiyama) | none; own port | | | | | Whole engine (order-sensitive) |
| Route / zones / endpoints / labels / fix | `kurbo` for curves and segment intersection | 0.13.1 | 2026-05-13 | Apache/MIT | yes | All the rules (about 1,000 Python lines) |
| External engines dot, ELK, D2 | subprocess behind a trait; elkjs in browser | | | | no | Glue |

Unchanged from the earlier doc. `rust-sugiyama`, `layout-rs`, `dagre-rs` stay rejected.

### 2.3 Text: `text.py`, `engine/textfit.py`, `engine/glyphs.py`

| Need | Crate | Version | Released | Licence | WASM | Custom code |
|---|---|---|---|---|---|---|
| Font tables, advances, cmap, metrics | `skrifa` + `read-fonts` | 0.49.0 / 0.46.0 | 2026-10-21 | MIT/Apache | yes | Pillow-compatible rounding (decide) |
| Shaping, only if kerning or complex scripts matter | `harfrust` | 0.15.0 | 2026-10-22 | MIT | yes | optional |
| Font database for resvg | `fontdb` | 0.24.0 | 2026-07-29 | MIT | in-memory only | Host passes font bytes |
| Wrapping, fit, glyph fallback | none; own port | | | | | All of it (custom break rules) |

Unchanged. `rustybuzz` (2024-11) and `ttf-parser` (2024-11) are still the stale ones [V].

### 2.4 CSS and theme: `css.py`, `theme.py`

| Need | Crate | Version | Released | Licence | WASM | Custom code |
|---|---|---|---|---|---|---|
| Tokeniser and parser | `cssparser` | 0.38.0 | 2026-09-07 | MPL-2.0 | yes | Rule and declaration model, value parsers, `var()` |
| Selector matching | own matcher; `selectors` 0.41.0 (2026-09-30, MPL-2.0) as fallback | | | | yes | Subset matcher, specificity, cascade, inspector provenance |
| Colours: names, hex, rgb(), hsl(), oklch | `csscolorparser` | 0.9.0 | 2026-09-27 | MIT/Apache | yes [A] | Replaces Pillow `ImageColor`. Check that its named-colour list matches Pillow's on the test corpus |
| Colour maths (mixing, oklab) | `palette` 0.7.7 [V, 2026-08-02], optional | | | MIT/Apache | yes | Or write the 30 lines of oklab |
| Theme files | `saphyr` (see 2.5) | | | | | Loader |

Unchanged. `lightningcss` is still alpha (see section 3.1).

### 2.5 YAML: `yaml_io.py`

| Need | Crate | Version | Released | Licence | WASM | Custom code |
|---|---|---|---|---|---|---|
| Read | `saphyr` | 0.3.3 | 2026-10-27 | MIT/Apache | yes | Shorthand forms, error messages, YAML 1.1 booleans decision |
| Alternative | `yaml-rust2` | 0.13.0 | 2026-09-11 | MIT/Apache | yes | |
| Lossless edit (later) | `yaml-edit` | 0.3.6 [V in earlier doc] | 2026-10-31 | Apache-2.0 | yes [A] | Only if a Rust edit API is wanted |

Unchanged.

### 2.6 Icons: `icons.py`, `vectorize.py`, `engine/icons.py`

| Need | Crate | Version | Released | Licence | WASM | Custom code |
|---|---|---|---|---|---|---|
| Parse and normalise icon SVG, viewBox, recolour | `usvg` 0.49.0 [V, 2026-10-24] for full parse, or `roxmltree` 0.21.2 [V, 2026-10-24] + `svgtypes` 0.16.1 [V, 2026-01-09] for a light path | | | Apache/MIT | yes | Recolour rules, id-collision rewriting |
| Archive handling for packs | `zip` 9.2.0 [V, 2026-10-31, MIT]; `tar` and `flate2` [A] | | | | yes (zip) | Host fetches and caches; the core takes bytes |
| Raster to vector | `vtracer` | 0.6.5 | 2026-08-29 | MIT [A] | [A] yes | `vectorize.py` already calls vtracer, a Rust crate. Keep it Python-side or call the crate directly |
| Rasterise | `resvg` 0.49.0 | | 2026-10-24 | Apache/MIT | yes | |

### 2.7 Backends

| Backend | Crate | Version | Released | Licence | WASM | Custom code |
|---|---|---|---|---|---|---|
| SVG | none; string writer. `quick-xml` 0.42.0 [V, 2026-08-22, MIT] for escaping if wanted | | | | yes | All of `svg.py` (318 lines) |
| PNG | `resvg` + `tiny-skia` 0.12.0 [V, 2026-02-02, BSD-3] + `png` 0.18.1 [V, 2026-02-14] | | | | yes | Pass fonts to fontdb; parity check |
| PPTX | stays python-pptx + lxml. Rust fallback: `zip` + `quick-xml`; `pptx` 0.1.0 [V, 2026-02-25, MIT, 6 stars] is young | | | | yes | Unchanged |
| Figma | none | | | | | Emits JS text; `serde_json` for escaping |
| Excalidraw | `serde_json` | 1.0.154 | 2026-10-11 | MIT/Apache | yes | Mapping |
| Font subsetting (`fontsubset.py`) | `subsetter` | 0.2.6 | 2026-06-04 | MIT/Apache | yes [A] | Closes an open item of the earlier doc. Typst's subsetter, 8.7M downloads [V]. Check it covers the table set Spinagram embeds (glyf/CFF, cmap, hmtx) |

### 2.8 QA and annotations: `qa.py`, `annotate.py`

| Need | Crate | Version | Released | Licence | WASM | Custom code |
|---|---|---|---|---|---|---|
| Rect and segment overlap, distances | `kurbo` | 0.13.1 | 2026-05-13 | Apache/MIT | yes | The checks themselves |
| Polygon overlap, only if shapes are not rects | `i_overlay` | 9.1.0 | 2026-10-14 | MIT/Apache | yes [A] | Probably unneeded |
| Spatial index for many boxes | `rstar` | 0.13.0 | 2026-05-24 | MIT/Apache | yes | Optional; the diagrams are small |
| Contrast and colour checks | `csscolorparser` + own WCAG formula | | | | | 20 lines |
| Heavy geometry | `geo` 0.33.1 [V] | | | MIT/Apache | yes | Avoid; large for this need |

Nearly all QA and annotation work is custom rule code. No crate replaces it.

---

## 3. CSS animation stack

### 3.1 Parsing `@keyframes`, `animation-*`, `transition-*`, easing, time

| Option | Version | Released | Licence | Status | What it gives | What stays custom |
|---|---|---|---|---|---|---|
| `cssparser` | 0.38.0 | 2026-09-07 | MPL-2.0 | Stable, Servo, 112M downloads [V] | Tokens, generic at-rule and declaration parsing | Typed parsing of `@keyframes` body, shorthands, `cubic-bezier()`, `steps()`, `linear()`, `<time>` (about 400 to 600 lines [A]) |
| `lightningcss` | 1.0.0-alpha.72 | 2026-07-20 | MPL-2.0 | **Still alpha**. GitHub latest release tag v1.33.0 is the npm line, crate has no stable [V] | Typed `KeyframesRule`, `Keyframe`, `KeyframeSelector`, `EasingFunction`, `StepPosition`, `Time`, animation property types, with serialisation [V, source files exist upstream] | Wiring spinagram's cascade onto its types; its `transition.rs` holds only view-transition types, so the `transition-*` longhands and `transition` shorthand parse elsewhere in its property code [A] |
| `simplecss` | 0.2.2 | 2025-01-06 | Apache/MIT | Static CSS subset (resvg uses it) | Selectors and declarations | No at-rules like `@keyframes` [A]. Not suitable |
| `selectors` | 0.41.0 | 2026-09-30 | MPL-2.0 | Stable | Selector matching only | Irrelevant to animation values |

**Pick: `cssparser` plus own animation value parsers.** Reasons: it is already the pick for the cascade, so one tokeniser and one error model serve everything; animation grammar is small and fully specified; `lightningcss` is alpha and brings a bundler-sized dependency into the WASM build. Use `lightningcss` as a **test oracle only**: a dev-dependency test that parses the same animation strings with both and compares the typed result. Revisit adoption if its 1.0 ships.

Grammar to support first (all [A], from the CSS Animations and Easing specs):

- `@keyframes name { from|to|N% (, ...) { decls } }`, with the same name defined twice (last wins).
- `animation` shorthand and longhands: name, duration, timing-function, delay, iteration-count (`infinite`), direction (`normal|reverse|alternate|alternate-reverse`), fill-mode, play-state.
- `transition` shorthand and longhands: property, duration, timing-function, delay. Transitions need a trigger. A static diagram has none, so define spinagram triggers (for example step reveals, `:hover` in the browser editor only) before parsing them; parse now, defer semantics.
- Easing: keywords (`ease`, `ease-in`, `ease-out`, `ease-in-out`, `linear`), `cubic-bezier(a,b,c,d)`, `steps(n, jump-*|start|end)`, `linear(0, 0.25 50%, 1)`.
- Time: `s` and `ms`, negative delays allowed.
- Animatable properties to start with: `opacity`, `transform` (translate, scale, rotate), `fill`, `stroke`, `stroke-dashoffset`, `stroke-dasharray`, `stroke-width`, `d` (path), plus spinagram custom properties.

### 3.2 Interpolation and easing

| Crate | Version | Released | Licence | Verdict |
|---|---|---|---|---|
| `keyframe` | 1.1.1 | 2022-07-11 | MIT | Stale (4 years). API is a tween over keyframes with easings. Do not depend; the logic is 100 lines |
| `interpolation` | 0.3.0 | 2023-08-26 | MIT | Penner easings as functions. Stale, only named easings, no `cubic-bezier` |
| `simple-easing` | 1.1.1 | 2026-10-10 | MIT/Apache | Active. Penner easings, `no_std`. Fine for the optional extra names, but CSS needs only five keywords plus bezier and steps |
| `easer` | 0.3.0 | 2022-08-30 | MIT | Stale |
| `enterpolation` | 0.3.0 | 2025-05-08 | MIT/Apache | Generic curves and gradients. More than needed |
| `splines` | 5.0.0 | 2025-04-26 | MIT | Spline keyframes. Not CSS semantics |
| `cubic-bezier` | 1.0.0 | 2024-02-07 | not checked | 1.6k downloads. Not worth the dependency |
| `tween`, `animate`, `bevy_tweening` | 2.2.0, 0.8.0, 0.16.0 | 2026 | MIT/Apache | Game-oriented runtime tweeners. Wrong shape (stateful, per-frame) |
| `kurbo` | 0.13.1 | 2026-05-13 | Apache/MIT | Use for bezier maths: a CSS `cubic-bezier(x1,y1,x2,y2)` is a `CubicBez` from (0,0) to (1,1); solving x(t)=x needs a Newton iteration with bisection fallback, using kurbo's cubic solvers [A] |

**Pick: write the easing and interpolation module (about 300 lines [A]), use kurbo for the bezier solve, `csscolorparser` for colour parse, and own colour lerp** (CSS default is sRGB premultiplied; allow `in oklab` later). Optionally pull `simple-easing` only if named Penner curves become a spinagram feature. Match CSS exactly so the browser and the frame renderer agree; test by comparing against samples from a headless browser once, as golden values.

### 3.3 Path morphing and dash animation

| Topic | Crate | Verdict |
|---|---|---|
| Path data parse and write | `kurbo` `BezPath::from_svg` and `to_svg` [A], `svgtypes` 0.16.1 [V] | Use kurbo |
| Path morph | `flubber` 0.1.0 (2019, 1.9k downloads) [V] | Dead. No maintained crate found. Write own: both paths to cubic beziers, equal subpath and segment counts by subdividing, then lerp control points; rotate start index to minimise distance. About 250 lines [A] |
| Flow dash (edge "marching ants") | none needed | `stroke-dasharray` plus animated `stroke-dashoffset`. Loops seamlessly when the offset travels exactly one dash period (sum of the dash array). Works in every SVG viewer that runs CSS animation, and needs no path morph |
| Draw-on / reveal | none needed | `pathLength="1"`, `stroke-dasharray: 1`, animate `stroke-dashoffset` 1 to 0. Needs the path length: kurbo `ParamCurveArclen` [A] |
| Dash handling in frames | `kurbo::dash` or resvg | resvg renders dashed strokes and dash offset statically, so frame sampling just sets the offset per frame |

Morph is the only real algorithm. Defer it: connectors re-routing between steps can be a fade or a SMIL `d` animation with matched command structure.

### 3.4 Emitting animated SVG: CSS-in-SVG versus SMIL

| | CSS in `<style>` (`@keyframes`) | SMIL (`<animate>`, `<animateTransform>`, `<set>`) |
|---|---|---|
| Browsers, inline SVG | yes | yes (Chromium kept it after the suspended deprecation [V, search]) |
| `<img>` and CSS background | CSS animations run, scripts do not [A, verify in a browser] | runs [A] |
| Animate `d` (morph) | Chromium and Firefox only; not Safari [A] | yes, if the command structure matches |
| Easing | full `cubic-bezier`, `steps`, `linear()` | `calcMode="spline"` with `keySplines`; discrete via `calcMode="discrete"`. Per-segment, so a CSS easing maps to every segment [A] |
| Delays, loops, alternate, fill-mode | native | `begin`, `repeatCount`, `fill="freeze"`; `alternate` needs doubled keyTimes [A] |
| Reduced motion | `@media (prefers-reduced-motion)` | not available |
| Editors (Figma, Inkscape, Illustrator, PowerPoint import) | animation ignored | ignored by most |
| Matches the user-facing language | yes, source CSS maps 1:1 | needs translation |
| Static fallback | initial state is the first frame when not animated | same |

**Pick: CSS-in-SVG as the primary emitter.** The user already writes CSS, so the emitted file is nearly the source. Add SMIL only for `d` morphs, behind an option, with a static first frame as fallback. Rules for the emitter:

- Give animated nodes stable ids and classes; emit one `<style>` block; use `transform-box: fill-box; transform-origin` so transforms rotate about the node.
- Step-by-step reveal: emit delays on one shared timeline, or `animation-delay` multiples of a step length; for "click to advance", SVG cannot; offer PPTX or a tiny JS wrapper instead.
- Keep the static scene valid: no animated property may be needed to see the diagram. Elements that start hidden must be hidden by the animation (`animation-fill-mode: backwards`) and not by a base style, so non-animating viewers show everything.
- Font subsetting and embedded data URIs are unaffected.

### 3.5 Rendering frames: does resvg animate?

**No.** The resvg README says it renders "static SVG files", supports "the static SVG subset", and lists "No animations" and no events [V, fetched]. Its `unsupported.md` also lists no animation handling; animation elements are outside its scope. A CSS `<style>` block with `@keyframes` is read by `usvg` for static selectors only; the `animation` property is ignored [A].

So frames need our own sampler:

1. Resolve the animation IR to per-node property values at time t (own code, section 3.2).
2. Apply them to the scene (opacity, transform, fill, dash offset, path d).
3. Emit a static SVG by the existing SVG backend.
4. Rasterise with `resvg` (`usvg` parse, `tiny-skia` pixmap).

Cost per frame is parse plus render. For 1920x1080 at 30 fps over 5 s, that is 150 frames; resvg takes tens of milliseconds per simple frame [A, measure]. Optimise later by parsing once and mutating the `usvg` tree (it is a public, mutable tree [A]) instead of reparsing text.

Alternatives for the rasteriser:

| Crate | Version | Released | Licence | Note |
|---|---|---|---|---|
| `resvg` / `usvg` | 0.49.0 | 2026-10-24 | Apache/MIT | Pick. Same renderer as PNG, so frames equal the static output |
| `vello_cpu` | 0.3.0 | 2026-10-02 | Apache/MIT | CPU renderer from Linebender, 9M downloads. No SVG parse; would need an own scene walker. Pre-1.0 |
| `vello` | 0.11.0 | 2026-10-02 | Apache/MIT | GPU (wgpu). Overkill, no headless guarantee in CI |
| `hayro` | 0.8.0 | 2026-10-04 | Apache/MIT | PDF renderer. Not relevant |

### 3.6 Encoding: GIF, video, Lottie

| Target | Crate | Version | Released | Licence | WASM | Verdict |
|---|---|---|---|---|---|---|
| Animated GIF | `gif` | 0.14.2 | 2026-04-09 | MIT/Apache | yes | Pick. Quantisation: the crate's built-in NeuQuant path [A]. 256-colour limit and 1-bit alpha are format limits; dithering is custom if banding on gradients matters |
| GIF, high quality | `gifski` | 1.34.0 | 2025-07-13 | **AGPL-3.0** | no | Avoid (licence) |
| Palette | `imagequant` | 4.4.1 | 2025-07-13 | **GPL-3.0** | no | Avoid (licence) |
| Animated PNG | `png` 0.18.1 (APNG encode) [A]; `apng` 0.3.4 (2024-02) stale | | | MIT/Apache | yes | Good lossless option for slides |
| Animated WebP | `webp-animation` 0.10.0 (libwebp C) [V]; `image-webp` 0.2.4 is lossless, animation encode unverified [A] | | | MIT/Apache | partly | Optional |
| MP4 H.264 | `openh264` 0.9.9 (2026-10-15, BSD-2) + `minimp4` 0.1.2 (2024-06) or `mp4` 0.14.0 (2023-08) | | | | no (C code) | Works without ffmpeg. Cisco's binary is patent-licensed only when downloaded from Cisco; building from source carries your own patent exposure [A]. Muxers are stale |
| AV1 / WebM | `rav1e` 0.8.1 | | 2025-06-16 | BSD-2 | needs asm for speed | Slow, no muxer. Skip |
| Any codec via ffmpeg | `ffmpeg-sidecar` 2.7.0 (2026-10-18, MIT) runs the ffmpeg CLI; `ffmpeg-next` 9.0.0 (2026-08-05, WTFPL) links libav | | | | no | Pick for MP4/WebM: pipe raw frames into the ffmpeg CLI. Licensing is the user's ffmpeg build |
| `image` | 0.25.10 | 2026-03-10 | MIT/Apache | yes | Frame buffers; also wraps gif encoder |
| Lottie writer | none [V by search: results show only parsers and players] | | | | | Hand-write |
| Lottie reader/player (for validation) | `velato` 0.12.0 (2026-09-10, Apache/MIT), `rlottie` 0.5.4 (2026-03-07, MIT, wraps C lib) | | | | velato yes [A] | Use as the test renderer for emitted Lottie |

**Pick:** `gif` native for GIF (default, no external tools). MP4 and WebM through the ffmpeg CLI via `ffmpeg-sidecar`, or simply from Python with a subprocess, since the Python layer exists anyway; this keeps patent-encumbered codecs out of the wheel. Lottie: own `serde` structs for the subset needed (shape layers, transform keyframes with bezier easing handles, opacity, trim paths, dash). Lottie keyframes use bezier handles `o`/`i`, which is exactly a CSS `cubic-bezier`, so the mapping is direct for those curves; `steps()` becomes hold keyframes (`h: 1`); text must become glyph paths; filters and shadows are mostly unsupported by players. Validate output with `velato` in tests.

### 3.7 PowerPoint animation XML

Facts:

- python-pptx has no animation API. The `<p:timing>` tree is round-tripped as an opaque blob only; a feature request for `Shape.add_animation` is still open [V, GitHub issue found by search].
- A Rust crate exists: `pptx` 0.1.0 by hidemi-ito (2026-02-25, MIT, 22k downloads, 6 GitHub stars [V]). It has an `animation` module with `xml_gen.rs` that builds `<p:timing>`, claims entrance, exit, emphasis and motion-path effects [V from docs.rs listing]. It is very young. Its COMPATIBILITY.md has an "Animations" row marked "Not supported" next to a python-pptx comparison, so that row likely refers to python-pptx; verify before relying on it [A].
- `ooxmlsdk` 0.14.0 (2026-10-19): generated OOXML types, includes presentation timing types [A], huge.

**Pick: hand-write in the Python PPTX backend** (lxml, which `pptx.py` already uses), emitted from the animation IR serialised as JSON. Reasons: PPTX stays in Python per the earlier decision; the XML is a fixed set of templates; there is no mature crate. Practice from the search: copy `presetID`, `presetClass` and nesting from a PowerPoint-saved reference file, because PowerPoint accepts some malformed timing trees and then silently plays nothing [V, via a skills.sh note]. Build a golden `.pptx` test set by saving real PowerPoint output.

What maps and what does not:

| CSS concept | PowerPoint | Mapping |
|---|---|---|
| `opacity` 0 to 1 on a node | Entrance Fade, Exit Fade | direct |
| `transform: translate` | Motion path (`p:animMotion`) or entrance Fly In | direct for straight moves |
| `transform: scale` | Emphasis Grow/Shrink (`p:animScale`) | direct |
| `transform: rotate` | Emphasis Spin (`p:animRot`) | direct |
| `fill`, `stroke` colour | Emphasis Change Fill/Line Color (`p:animClr`) | direct |
| `animation-delay`, `duration` | `p:cTn` with `delay`, `dur` | direct |
| Step-by-step reveal | Click, With Previous, After Previous | the natural fit; best PPTX feature |
| `iteration-count: infinite`, `alternate` | `repeatCount="indefinite"`, `autoRev` | supported, but only for emphasis [A] |
| `cubic-bezier`, `steps` | only `accel` and `decel` percentages | approximate with accel/decel or drop |
| `stroke-dashoffset` flow | none | not mappable. Fallback: Wipe entrance for draw-on edges; ignore flow |
| Path morph | none | not mappable |
| Percent keyframes with 3+ stops | chain several effects | possible, verbose |

Report unmappable features as QA warnings, not silent loss.

### 3.8 Prior art

| Project | What it is | Version / date | Relevance |
|---|---|---|---|
| D2 | Go diagram tool. `--animate-interval` packs multiple boards into one SVG or GIF that steps through them; `style.animated` on connections gives flowing dashes [V, d2lang.com and man page] | since 0.3.0 | Closest product precedent. Board-per-step is a coarse model. Users complain that fixed intervals lose viewers and want step controls [V, discussion #2714] |
| `rustmotion` | Rust CLI that renders MP4/WebM/GIF/PNG from JSON scenes; skia-safe, openh264, minimp4, optional ffmpeg [V] | 0.8.1, 2026-10-01, MIT, 200 downloads | Pattern reference for a frame loop and encoders. Tiny community; skia-safe is not WASM-friendly |
| `velato`, `vello`, `vello_cpu` | Linebender Lottie renderer and renderers | 0.12.0, 0.11.0, 0.3.0 | Lottie validation; possible CPU renderer |
| `lottie-rs` (zimond) | Lottie parse and render toolkit, headless WebP export [V, search] | not verified | Reference only |
| `typst` | Typesetter with `typst-svg` 0.15.1 (2026-07-17). Static output; no animation feature [A] | | Source of `subsetter`; no animation prior art |
| `bevy_tweening`, `tween`, `animate` | Runtime tweening for games | | Wrong model (stateful, per-frame) |
| SVG tools in other ecosystems: Motion Canvas (TS), Manim (Python), SVGator (SaaS) | | [A] | Timeline-first tools; none consume CSS as the source |

No Rust diagram tool with CSS-driven animation was found. This is open ground, and the CSS-as-source idea is unusual.

---

## 4. Recommended animation architecture

One IR, many emitters. Put it in the scene contract, so Python and WASM see the same thing.

```
CSS (@keyframes, animation, transition)
   |  cssparser + own value parsers          (own, ~500 lines [A])
   v
Cascade resolves animations per node        (extends css.py port)
   v
Animation IR in scene JSON: tracks {target id, property, keyframes[{t, value}], easing, delay, duration, iterations, direction, fill}
   |
   +--> SVG CSS emitter (primary)                      own string writer
   +--> SMIL emitter (path morph, optional)            own
   +--> Sampler(t) -> static scene -> SVG -> resvg -> RGBA frames
   |        +--> gif crate (GIF), png (APNG), ffmpeg CLI (MP4/WebM)
   +--> Lottie writer (serde structs, test with velato)  own
   +--> JSON to Python PPTX backend (lxml, p:timing templates)
```

Crates in the animation stack: `cssparser`, `kurbo`, `csscolorparser`, `resvg`/`usvg`/`tiny-skia`, `gif`, `png`, `serde_json`, optional `ffmpeg-sidecar` and `simple-easing`. Licences are all permissive except MPL-2.0 for `cssparser` (already accepted in the earlier doc). Avoid `gifski` (AGPL) and `imagequant` (GPL).

Custom code estimate [A]: value parsers 500, easing and interpolation 300, sampler 300, CSS emitter 250, SMIL emitter 200, path morph 250, GIF/APNG glue 150, Lottie writer 600, PPTX timing templates 400 (Python). About 3,000 lines. Order of delivery: IR plus CSS emitter (value to users first), then sampler plus GIF, then PPTX step reveals, then Lottie and MP4.

Risks:

1. CSS inside SVG renders differently across viewers. Keep a browser golden test (headless Chromium, existing Playwright is available in Python tests) that samples computed styles at fixed times and compares with the Rust sampler.
2. `transform-origin` and `transform-box` behaviour in SVG differs from HTML; test rotate and scale.
3. `<img>` embedding of animated SVG: verify in browsers and GitHub READMEs before promising it [A].
4. Transition triggers are undefined on a static diagram; pick semantics first.
5. Frame render needs fonts in `fontdb`; same constraint as PNG.

## 5. Still unverified

- Whether CSS animations run in `<img>`-embedded SVG in current Chrome, Firefox and Safari (stated from memory).
- `csscolorparser` named colours versus Pillow `ImageColor` differences.
- `subsetter` table coverage for the fonts Spinagram embeds.
- `gif` crate quantisation quality on gradient-heavy diagrams.
- Whether `lightningcss` parses `transition-*` longhands in a usable typed form (only view-transition types seen in `transition.rs`).
- The `pptx` 0.1.0 crate's animation output against real PowerPoint.
- Per-frame resvg timing at 1080p.

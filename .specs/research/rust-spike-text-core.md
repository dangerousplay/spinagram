# Rust spike: text core, lines by feature and where the port pays off

**Date:** 2026-11-01 · **Branch:** `spike/rust-core`
**Decision taken:** port spinagram to Rust gradually, as crates with Python bindings, keeping Python supported.
**Related:** [rust-engine-evaluation.md](rust-engine-evaluation.md) (options, effort) ·
[rust-crates-by-feature.md](rust-crates-by-feature.md) (crate picks, CSS animation stack)

## 1. What the spike built

| Piece | Where | Lines |
|---|---|---|
| Font faces (skrifa): cmap coverage, advances, legacy `kern` pairs, FreeType fixed-point scaling | `rust/spinagram-core/src/font.rs` | ~130 |
| Text: measure with glyph fallback, wrap, wrap_paragraphs, break_token, wrap_fit | `rust/spinagram-core/src/text.rs` | ~210 |
| Fit: shrink in 1 px steps, then grow (`fit_blocks`) | `rust/spinagram-core/src/fit.rs` | ~140 |
| PyO3 bindings (abi3, Python ≥ 3.11), `spinagram_core._core` | `rust/spinagram-core-py/` | ~90 |
| Opt-in switch, `SPINAGRAM_RUST=1` | `src/spinagram/rust.py`, hooks in `text.py` and `engine/textfit.py` | ~45 |
| Parity and speed harness | `rust/bench/parity.py` | ~140 |

It ports 272 Python source lines (text.py, textfit.py, glyphs.py coverage) into about 520 lines of Rust.

## 2. Results (measured on this machine, macOS arm64, Python 3.13)

### Parity with the Python engine

| Check | Result |
|---|---|
| `measure()` vs Pillow: 1,266 strings from the examples × 15 sizes × 10 fonts (Noto bundled fallbacks, Arial, Arial Bold, Verdana, Georgia, Times, Courier, Trebuchet, Tahoma) | **100% exact, 189,900 samples**; the no-file estimate path is also 100% exact (37,980 samples) |
| `fit_blocks()`: 40,512 title + body boxes, 4 box sizes, 4 fit modes, 4 fonts | **40,512 / 40,512 identical** lines, sizes, strategy and ok |
| Full Python test suite with `SPINAGRAM_RUST=1` | **2,630 passed, 3 skipped** (same as pure Python) |
| All 40 example and docs SVGs rendered with and without the core | **byte-identical** |

Exact width parity took three steps, which is the main lesson of the spike:

1. Plain float scaling: up to 2 px off on strongly hinted fonts (Tahoma, Verdana).
2. FreeType's 16.16 fixed-point scale and 26.6 rounding (`FT_DivFix`, `FT_MulFix`): max error 0.41 px, Georgia exact.
3. Legacy `kern` pairs, added the way Pillow's basic layout does it (whole pixels into a 26.6 advance, so a
   pair counts 1/64 px at 10x): 100% exact on all fonts.

The earlier evaluation named text parity as the top port risk. With these three rules it is solved for the
fonts tested. Fonts without a `kern` table but with GPOS-only kerning behave the same, since Pillow's basic
layout ignores GPOS too. If Pillow is ever built with raqm (it is not here: `features.check('raqm')` is
False), widths would change in Python itself.

### Speed

| Work | Python | Rust via PyO3 | Speed-up |
|---|---|---|---|
| `measure()` × 1,266 strings, Arial 14 px | 163 ms | 1.0 ms | **165x** |
| `fit_blocks()` × 40,512 boxes | 40.0 s | 0.38 s | **105x** |

**But text is not where diagrams spend their time today.** The default theme ships no font files, so
`measure` uses the per-character estimate. In-process builds of all examples (46 scenes, warm) take
about 1.95 s either way, and text measuring and fitting is under 1% of it. The 100x matters for themes
with real fonts, for the live editor (every keystroke re-fits every box), and as the base layer every
other ported module needs. On its own, it does not make today's renders faster.

## 3. Where the time goes today (cProfile, 46 example scenes + SVG, warm)

| Share of build time | Where | Notes |
|---|---|---|
| **~49%** | `autolayout/route.py` `route` → `_search` (A* grid search for orthogonal edges), `seg_ok` 16% | Pure compute on small structs. The best Rust target by far |
| **~35%** | PyYAML, pure-Python scanner | About 20 points of it are icon-pack registries re-read through `Theme.load` for each spec file (`icons._load_file`, `api._theme` 15%) |
| ~16% | `autolayout/engines/layered.py` `run` | Partly overlaps routing above |
| ~1% | `css.py` cascade + tinycss2 | Small now; grows with animations (keyframes per element per frame) |
| <1% | text measure and fit | See above |
| <1% | `backends/svg.py` | String building |

**Two Python quick wins, no Rust needed:** `yaml.__with_libyaml__` is True but every call uses
`yaml.safe_load` (pure Python), so switching to `yaml.load(..., Loader=yaml.CSafeLoader)` should make
parsing several times faster. Caching the parsed icon registries and themes per process would remove the
repeated loads. Together these should cut about a third of build time in a day of work (estimate, not
measured). Do them first: they shrink the baseline every Rust comparison is made against.

## 4. Lines of code by feature (src/spinagram, 12,810 source lines without blanks and comments)

| Feature | Files | Lines | Source lines | Time share today | Rust gain | Port effort | Value of porting | Order |
|---|---|---|---|---|---|---|---|---|
| Text: measure, fit, glyph fallback | 3 | 341 | 272 | <1% | 100–165x measured; exact parity | **Done in spike** | Base layer for layout, editor and WASM | 0 |
| Edge routing | 2 | 317 | 265 | **~49%** | Very high: A* in Rust is typically 50–100x (estimate) → about half of build time | Low: 1–2 weeks | **Highest speed gain per line** | **1** |
| Scene model & Python DSL | 9 | 2,292 | 1,885 | low | None for speed. Needed as the shared data model (scene JSON, schemars) | Medium: the scene structs only, 2–3 weeks; the DSL stays Python | Lets every other port and every language share one model | 2 |
| Auto layout: layered + flex + graph + sizing | 6 | 1,569 | 1,363 | ~16% | High (graph loops, crossing reduction) | High: 6–10 weeks, order- and tie-sensitive | Live preview of auto layouts in WASM | 3 |
| Layout passes (zones, labels, endpoints, fix) | 11 | 1,886 | 1,634 | moderate | Medium | High: 6–9 weeks, most of the behaviour the tests pin | Completes spec → scene in Rust | 4 |
| CSS cascade & themes | 3 | 1,311 | 1,115 | ~1% | Low now; **high for animation** (per-frame cascade and interpolation) | Medium: 4–6 weeks (cssparser + own matcher) | Required for CSS animations and the WASM editor | 3 (with animation) |
| YAML spec loader | 1 | 461 | 407 | ~35% (mostly fixable in Python) | Medium after the libyaml fix | Low: 1–2 weeks (saphyr), watch YAML 1.1 vs 1.2 booleans | Needed for spec → SVG in WASM | 5 |
| Backend: SVG + PNG + font subset | 4 | 453 | 377 | <1% | Low for speed; **high for PNG** (resvg removes Chromium, about 1.5 s cold start) | Low: 2–3 weeks | PNG without a browser; animated frames for GIF/MP4 | 2 |
| Icons & vectorize | 2 | 659 | 542 | part of the YAML share | Medium | Medium: 2–4 weeks | WASM editor needs icon lookup | 6 |
| QA checks | 1 | 635 | 540 | low | Medium (geometry checks with rstar) | Medium | Fast checks while typing in the editor | 7 |
| Annotations & facts | 2 | 776 | 668 | low | Low | Medium | Completes the core | 8 |
| External engine adapters (dot, ELK, D2) | 3 | 645 | 553 | process-bound | None (they call external tools) | Keep in Python | — | never |
| Backend: PowerPoint | 1 | 592 | 521 | low | None (no mature Rust crate) | Keep in Python | — | never (for now) |
| Backend: Figma + Excalidraw | 2 | 851 | 746 | low | None | Keep in Python / JS | — | later |
| CLI, live UI server, MCP, skills | 14 | 2,258 | 1,922 | none | None | Keep in Python | — | never |

Effort is in engineer-weeks for one engineer who knows the code (estimates, in line with
rust-engine-evaluation.md). About 7,900 source lines are candidates for Rust; about 4,900 stay in Python
(adapters, PPTX, Figma, CLI, UI, MCP).

## 5. Where the rewrite gains the most

1. **Edge routing first.** About half of today's build time sits in 265 lines of A* search. It is the
   biggest speed win per line ported, has no dependencies beyond geometry, and its results are easy to
   check (same polylines).
2. **Scene structs + SVG writer + resvg next.** That gives a closed Rust path (scene → SVG → PNG) without
   Chromium, the basis for the WASM preview and for animation frames.
3. **CSS together with the animation feature.** Animations multiply cascade and interpolation work by
   the number of frames, so this is where Rust's speed starts to matter for CSS. Build the animation IR
   in the scene model from the start (see rust-crates-by-feature.md: cssparser plus own keyframe and easing
   parsers, CSS-in-SVG output, resvg frames, `gif`/`png` encoders, ffmpeg CLI for video).
4. **Layered, flex and the layout passes last.** They have the most code and the most pinned behaviour.
   Port them when the layout roadmap stops changing the scene shape.

## 6. How the port keeps Python working (pattern proven by the spike)

- Each slice lands as a Rust function with the same contract as the Python one, behind `SPINAGRAM_RUST=1`.
- The gate for a slice is: the Python suite passes with the flag on, the parity harness is 100%, and every
  example SVG is byte-identical. Then the flag flips to default-on for that slice, with the Python version
  kept as the fallback for one or two releases.
- Packaging (not done in the spike): build `spinagram-core` wheels with `maturin-action` for Linux, macOS
  and Windows (abi3, so one wheel per platform), and make spinagram depend on it. Alternatively, switch
  spinagram itself to the maturin build backend later.

## 7. Next steps

1. Python quick wins: `CSafeLoader`, and cache themes and icon registries (about 1 day).
2. Port `autolayout/route.py` + `engine/route.py` to Rust with the same harness (1–2 weeks).
3. CI: build and test the Rust workspace, run the Python suite with `SPINAGRAM_RUST=1`, publish wheels.
4. Freeze the scene JSON schema and add the animation IR to it before porting the scene model.

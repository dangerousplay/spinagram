# spinagram Rust core

The engine is being ported to Rust one slice at a time. Python stays the main API and keeps working
without these crates.

| Crate | What it is |
|---|---|
| `spinagram-core` | Pure Rust library: font metrics, text measurement, wrapping and fitting (ported from `text.py` and `engine/textfit.py`), orthogonal edge routing (ported from `autolayout/route.py`), the scene model and SVG drawing (ported from `backends/svg.py`) and PNG rendering with resvg |
| `spinagram-core-py` | PyO3 bindings, published as the `spinagram-core` wheel and imported as `spinagram_core` |

## Build and try it

```bash
cd rust && cargo test -p spinagram-core && cargo clippy --all-targets
cd spinagram-core-py && uvx maturin build --release -o ../target/wheels
cd ../.. && uv pip install --reinstall rust/target/wheels/spinagram_core-*.whl

SPINAGRAM_RUST=1 uv run --all-extras --no-sync pytest -q   # the Python suite against the Rust core
uv run --all-extras --no-sync python rust/bench/parity.py  # widths, fits and speed vs Pillow (a few minutes)
uv run --all-extras --no-sync python rust/bench/route_parity.py  # edge routes and speed vs the Python router
uv run --all-extras --no-sync python rust/bench/svg_png_parity.py  # SVG bytes per font mode, PNG vs Chromium
bash rust/bench/render_all.sh OUT                          # every example to SVG, for byte-identity checks
```

`SPINAGRAM_RUST=1` switches `spinagram.text.measure` and `spinagram.engine.textfit.fit_blocks` to the core
(see `src/spinagram/rust.py`). Without the flag or the wheel, everything is pure Python. Use `--no-sync`
so `uv run` does not remove the locally installed wheel.

## Slices

| Slice | Core entry point | Python switch |
|---|---|---|
| Text | `measure`, `wrap_paragraphs`, `wrap_fit`, `fit_blocks` | `spinagram.text.measure`, `spinagram.engine.textfit.fit_blocks` |
| Edge routing | `route(src, dst, obstacles, margin, sides, busy_src, busy_dst, crossing, guides, fracs)` | `spinagram.autolayout.route.route` |
| Scene and SVG | `scene_roundtrip(json)`, `svg_draw(json)` | `spinagram.backends.svg.to_svg` |
| PNG | `render_png(svg, width, height, scale, font_files)` | `spinagram.backends.png.PngBackend` |

### Routing slice

`route.rs` is a line-by-line port of `autolayout/route.py`: the same A* order (the open set sorts like Python's
`heapq` on `(f, g, (i, j), dir, prev)`), the same float summation order, and `round(x, 2)` semantics in `simplify`
(ties such as 0.125 and 2.675 round like Python).

The crossing penalty crosses the boundary as data. `engine.route.Crossings(cost, drawn)` is callable from Python
and the core reads its `cost` and `drawn` fields. `route()` runs in Rust when the core is active and `penalty` is
None or a `Crossings`; any other callable penalty runs the Python router. `busy` is passed as the busy sides of
`src` and `dst` only.

### Scene JSON and schema

`spinagram.scene_json.dumps(scene)` writes a finished scene as JSON with `"version": 1`: items tagged by `type`
(`shape`, `connector`, `text`, `line`, `image`, `table`), nested labels, text blocks, runs, fonts, icons, symbol
parts and cells, paths as absolute strings. Only the fields the SVG writer reads are carried; QA-only fields
stay in Python. Rust reads it with `scene.rs` (a `version` other than 1 is an error) and the format is
published as `rust/schema/scene.schema.json`, generated from the Rust types. A test fails when the committed
file is stale; regenerate it with `UPDATE_SCHEMA=1 cargo test -p spinagram-core schema`. Every example scene
round-trips through Rust unchanged and validates against the schema.

### SVG slice

With `SPINAGRAM_RUST=1` `to_svg` hands the scene to Rust as JSON; `svg.rs` draws the items and returns the
layers plus the characters drawn per font face. Python still builds the font faces (fontTools subsetting),
the `<svg>` head, the metadata and the content hash, in both modes, so the bytes are identical in `subset`,
`embed` and `link`. `pyfmt.rs` reproduces `format(x, ".1f")`, `format(x, "g")`, `repr(float)`,
`html.escape` and Python's `sum()`: 3.12+ sums floats with compensation and 3.11 adds plainly, so `svg_draw` takes
the interpreter's behaviour (`sys.version_info >= (3, 12)`) as an argument.

### PNG slice

With the core active, `PngBackend` renders with resvg (no Playwright, no Chromium) and passes the scene's font
files and the bundled Noto fallbacks to resvg's font database, then the system fonts. `SPINAGRAM_PNG=chromium`
forces the Playwright path; without the core Playwright is used as before. resvg is not pixel-identical to
Chromium: the contract is a similarity bound per example at scale 1 (mean absolute channel difference <= 8 and
at most 2 % of pixels with a channel difference > 64).

### Building on macOS 27

The macOS 27 linker writes a misaligned string table when the module has an odd number of indirect symbols, and
dyld then refuses to import it. If `import spinagram_core` fails with "mis-aligned LINKEDIT string pool", check
`otool -l .../_core.abi3.so | grep nindirectsyms` and change the parity (the module init touches one Python data
symbol for this reason). Linux and CI are not affected.

### Harnesses

| Script | What it checks |
|---|---|
| `bench/route_parity.py` | Records every `route()` call made while building the examples (57 calls) plus 2,500 seeded random scenarios, requires identical point lists, prints `N of N identical` and a timing table. Exits 1 on any difference. |
| `bench/svg_png_parity.py` | SVG byte identity per font mode over every example scene (48), PNG similarity against Chromium per example (skipped without Chromium or with `--svg-only`), and timings. Exits 1 on any SVG difference or similarity breach. |
| `bench/parity.py` | Text widths, fits and speed against Pillow (the text slice). |
| `bench/render_all.sh` | Renders every example to SVG; two runs, or Python versus `SPINAGRAM_RUST=1`, must give `diff -r` with no output. |

### Measured numbers

Developer machine, warm in-process, best of 3.

| Work | Before | After | Change |
|---|---|---|---|
| Build all examples, YAML cache (pure Python) | 1545 ms | 1273 ms | 18% faster |
| Build all examples with `SPINAGRAM_RUST=1` | 1262 ms | 394 ms | 3.2x |
| `route()` over the 57 recorded calls | 878 ms (Python) | 18.8 ms (Rust) | 46.6x |
| SVG writer, 48 scenes (subset) | 9 ms (Python) | 38 ms (Rust, includes building the scene JSON) | 0.2x |
| PNG at scale 1, 48 scenes | 4671 ms (Chromium, one browser start) | 4051 ms (resvg) | 1.2x |

PNG similarity against Chromium over the 48 scenes: worst mean channel difference 1.00 (limit 8), worst share of
pixels differing by more than 64 is 0.39 % (limit 2 %). The Rust SVG writer is slower end to end than the Python
one because most of its time goes into serializing the scene to JSON; it exists for byte-identical drawing by
other front-ends, not for speed. PNG saves the 150 MB Chromium install and its start-up; per scene resvg takes
about 40 ms for a 1920x1080 diagram.

The YAML work is smaller than planned because routing dominates the build; the Rust router is where the time goes.
Spec files stay on PyYAML's `SafeLoader` (libyaml accepts input it rejects); themes and icon registries use libyaml
and a stat-keyed parse cache.

## Parity rule

The Python implementation and its tests are the spec. Every ported slice must give identical results:
the same widths to the 1/64 px Pillow uses, the same lines, and byte-identical SVG for every example.

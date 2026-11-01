# spinagram Rust core

Rust is spinagram's main engine. The `spinagram` package is built with maturin: `rust/` compiles to the
`spinagram._core` extension inside it, and spinagram uses it by default; Python stays the API. The ported Python code stays too, as the reference the
parity checks compare against, and runs with `SPINAGRAM_RUST=0`.

| Crate | What it is |
|---|---|
| `spinagram-core` | Pure Rust library: font metrics, text measurement, wrapping and fitting (ported from `text.py` and `engine/textfit.py`), orthogonal edge routing (ported from `autolayout/route.py`), the scene model and SVG drawing (ported from `backends/svg.py`) PNG rendering with resvg, and CSS selector matching with the cascade (ported from `css.py`) |
| `spinagram-wasm` | `wasm-bindgen` exports of the same core for the browser: `renderSvg`, `reroute`, `applyOps`, `srcmap`, `registerFont`, `registerFile`. The editor canvas runs it in a Web Worker |
| `spinagram-core-py` | PyO3 bindings, compiled into the `spinagram` wheel as `spinagram._core` (root `pyproject.toml`, `[tool.maturin]`) |

## Build and try it

```bash
cd rust && cargo test -p spinagram-core && cargo clippy --workspace --all-targets -- -D warnings && cd ..
uv sync --all-extras                                # builds spinagram._core with maturin (editable install)

uv run --all-extras pytest -q                       # the suite on the Rust core (the default)
SPINAGRAM_RUST=0 uv run --all-extras pytest -q      # the suite on the pure-Python reference
uv run --all-extras python rust/bench/parity.py     # widths, fits and speed vs Pillow (a few minutes)
uv run --all-extras python rust/bench/route_parity.py  # edge routes and speed vs the Python router
uv run --all-extras python rust/bench/svg_png_parity.py  # SVG bytes per font mode, PNG vs Chromium
uv run --all-extras python rust/bench/css_parity.py    # CSS inspect() across modes, cascade speed
uv run --all-extras python rust/bench/wheel_smoke.py   # examples with and without the core, plus a PNG
bash rust/bench/render_all.sh OUT                   # every example to SVG, for byte-identity checks
```

## Wheels and source builds

CI builds one abi3 wheel per target (CPython 3.11+): manylinux and musllinux for x86_64 and aarch64, macOS arm64
and x86_64, Windows x64 and arm64. Linux aarch64, musllinux, macOS x86_64 and Windows arm64 are cross-compiled.
Each wheel that has a matching runner is installed there and checked with `rust/bench/wheel_smoke.py`, which
renders examples with and without the core and requires byte-identical SVGs plus a resvg PNG.

CI also builds the sdist. On a platform without a wheel, `pip install spinagram` builds it from that sdist with
maturin, which needs a Rust toolchain (`rustup`, stable); the `source-install` job checks this on Linux, macOS and
Windows. Releases publish every wheel and the sdist under the one `spinagram` name (`.github/workflows/release.yml`).
The package version comes from `pyproject.toml` only.

`src/spinagram/rust.py` decides: the core is used unless `SPINAGRAM_RUST=0` (or empty). If `spinagram._core`
cannot be imported, spinagram warns once and runs the pure-Python engine.

## WebAssembly build

`spinagram-wasm` is the Rust core in the browser (the rich editor: live edges while a node is dragged, edit
operations on release; zone and row/column operations for dragging, grouping and the icon palette). One-time setup, then a script builds it:

```bash
rustup target add wasm32-unknown-unknown
cargo install wasm-bindgen-cli --version "$(awk '/^name = "wasm-bindgen"$/{getline; gsub(/[^0-9.]/,""); print}' rust/Cargo.lock)" --locked
bash rust/spinagram-wasm/build.sh        # web/src/wasm (browser) and rust/spinagram-wasm/pkg-node (tests); both ignored by git
cd rust/spinagram-wasm && bun test       # exports against golden files; also prints reroute + renderSvg ms per call
cd ../../web && bun run build            # bundles the worker and the .wasm into src/spinagram/ui/static
```

The CLI must match the `wasm-bindgen` crate version in `Cargo.lock`. `spinagram-core` builds for wasm32 without
the `png` feature (`default-features = false`) and reads no files there: fonts and icons come in as bytes
(`font::register`, `svg::register_file`). The golden files in `rust/spinagram-wasm/tests/golden/` come from
`SPINAGRAM_RUST=0 uv run --all-extras python rust/spinagram-wasm/tests/gen_golden.py` (drawn bodies from the
pure-Python writer, patched YAML and source maps from the PyO3 binding); `rust/bench/reroute_fixtures.py` does the
same for the reroute tests. The wasm is about 1.9 MB (650 KB gzipped). In the browser `renderSvg` loads fonts by
URL and leaves out the sources metadata and content hash; the drawn layers are byte-identical to the server's.

### Edit operations

`edit::apply_ops(yaml, ops)` patches the YAML text by byte ranges taken from parser spans, so comments, key order
and flow/block style outside the edit are untouched, and a batch applies completely or not at all. The operations
(JSON shapes in `src/spinagram/edit.py`): `move`, `resize`, `rename`, `delete`, `add_node` (with an optional `icon`),
`connect`, `disconnect`; for zones `add_zone` (with an optional `style`, written as the zone's `color`), `set_zone_style`, `reparent` (a zone cannot go inside itself or a descendant) and
`move_zone` (children move by the same offset); for `rows`/`columns` containers (`row0`, `column1`: the ids the
scene uses) `group`, `ungroup`, `add_to_container` (also reorders a member), `remove_from_container` (a container
left with fewer than two members dissolves) and `set_container`. `srcmap` gives every node, zone, container and edge
its byte range. The scene JSON lists `zones` and `containers` so the canvas knows what holds what.

## Slices

| Slice | Core entry point | Python switch |
|---|---|---|
| Text | `measure`, `wrap_paragraphs`, `wrap_fit`, `fit_blocks` | `spinagram.text.measure`, `spinagram.engine.textfit.fit_blocks` |
| Edge routing | `route(src, dst, obstacles, margin, sides, busy_src, busy_dst, crossing, guides, fracs)` | `spinagram.autolayout.route.route` |
| Scene and SVG | `scene_roundtrip(json)`, `svg_draw(json)` | `spinagram.backends.svg.to_svg` |
| PNG | `render_png(svg, width, height, scale, font_files)` | `spinagram.backends.png.PngBackend` |
| CSS | `css_cascade(tree_json, rules_json)`, `css_select(tree_json, selectors)` | `spinagram.css.compute`, `select`, `inspect` |

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

With the core active, `to_svg` hands the scene to Rust as JSON; `svg.rs` draws the items and returns the
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

### CSS slice

Python keeps stylesheet tokenizing (tinycss2), `parse_selectors` validation, value typing (`PROPS`), warnings, the
trace and inheritance of typed values. With the core active, `compute()` sends the element tree and the rules as
JSON; Rust parses the accepted selector texts, matches them, orders the cascade by `(important, specificity, rule
order, declaration index)` (inline declarations at levels 1 and 3) and substitutes `var()` with the same custom
property scope as `resolve()`. It returns, per element and pseudo-element (`""`, `title`, `body`, `label`), the
matched declarations in cascade order as `(rule or inline, selector, declaration, resolved value)`, and Python
runs its typing loop over them. `select()` and the unused-selector scan of `inspect()` ask the core which
elements each selector matches.

Selector tokenizing, parsing, specificity and matching use the `cssparser` and Servo `selectors` crates (both
MPL-2.0); the glue is the element tree, the `::title`/`::body`/`::label` pseudo-elements and node kinds as type
names. The cascade sort and `var()` substitution are handwritten because no crate reproduces spinagram's rules.
`selectors` follows the CSS grammar, which is stricter than spinagram's regex parser for a leading or trailing
combinator (`> a`, `a >`) and an unquoted attribute value that is not an identifier (`[w=100px]`); the core
returns an error for those and `compute()`, `select()` and `inspect()` run the Python path instead, so results are
identical.

### Building on macOS 27

The macOS 27 linker writes a misaligned string table when the module has an odd number of indirect symbols, and
dyld then refuses to import it. If `from spinagram import _core` fails with "mis-aligned LINKEDIT string pool", check
`otool -l .../_core.abi3.so | grep nindirectsyms` and change the parity (the module init touches two Python data
symbols for this reason; add or remove one when it breaks again). Linux and CI are not affected.

### Harnesses

| Script | What it checks |
|---|---|
| `bench/route_parity.py` | Records every `route()` call made while building the examples (57 calls) plus 2,500 seeded random scenarios, requires identical point lists, prints `N of N identical` and a timing table. Exits 1 on any difference. |
| `bench/svg_png_parity.py` | SVG byte identity per font mode over every example scene (48), PNG similarity against Chromium per example (skipped without Chromium or with `--svg-only`), and timings. Exits 1 on any SVG difference or similarity breach. |
| `bench/css_parity.py` | `inspect()` and `styles()` across modes for every example (48) and 1,200 seeded random (diagram, stylesheet) pairs using every selector feature and `var()` form (errors must match too), then timings on a 561-element, 200-rule diagram. Exits 1 on any difference. |
| `bench/parity.py` | Text widths, fits and speed against Pillow (the text slice). |
| `bench/render_all.sh` | Renders every example to SVG; two runs, or `SPINAGRAM_RUST=0` versus the default, must give `diff -r` with no output. |

### Measured numbers

Developer machine, warm in-process, best of 3.

| Work | Before | After | Change |
|---|---|---|---|
| Build all examples, YAML cache (pure Python) | 1545 ms | 1273 ms | 18% faster |
| Build all examples with the core | 1262 ms | 394 ms | 3.2x |
| `route()` over the 57 recorded calls | 878 ms (Python) | 18.8 ms (Rust) | 46.6x |
| SVG writer, 48 scenes (subset) | 9 ms (Python) | 38 ms (Rust, includes building the scene JSON) | 0.2x |
| PNG at scale 1, 48 scenes | 4671 ms (Chromium, one browser start) | 4051 ms (resvg) | 1.2x |
| CSS matching + cascade, 561 elements, 200 rules | 97 ms (Python) | 14.2 ms (Rust, includes the JSON) | 6.8x |
| `compute()` end to end, same diagram | 190 ms (Python) | 82.8 ms (Rust) | 2.3x |

`compute()` gains less end to end because value typing, warnings and the trace stay in Python.

PNG similarity against Chromium over the 48 scenes: worst mean channel difference 1.00 (limit 8), worst share of
pixels differing by more than 64 is 0.39 % (limit 2 %). The Rust SVG writer is slower end to end than the Python
one because most of its time goes into serializing the scene to JSON; it exists for byte-identical drawing by
other front-ends, not for speed. PNG saves the 150 MB Chromium install and its start-up; per scene resvg takes
about 40 ms for a 1920x1080 diagram.

The YAML work is smaller than planned because routing dominates the build; the Rust router is where the time goes.
Spec files stay on PyYAML's `SafeLoader` (libyaml accepts input it rejects); themes and icon registries use libyaml
and a stat-keyed parse cache.

## Quality: clippy, cargo-deny, crates first and Verus

- **Clippy**: the workspace lint table denies `clippy::all` and warns on `pedantic`; CI runs
  `cargo clippy --workspace --all-targets -- -D warnings`. Every exception is an `#[expect(..., reason = "...")]`; no
  `#[allow(clippy::...)]` remains.
- **cargo-deny**: `rust/deny.toml` (advisories, permissive licences plus MPL-2.0, duplicate versions warn, crates.io
  only). Run `cargo deny check` in `rust/`; CI runs it too.
- **Crates first**: `DEPENDENCIES.md` lists every hand-written component with the crates tried and the evidence (a
  parity number or the first differing case). Replaced so far: HTML escaping (`html-escape`) and the compensated
  `sum()` (`compensated-summation`).
- **macOS link flags**: `spinagram-core-py/build.rs` calls `pyo3_build_config::add_extension_module_link_args()`,
  so `cargo build`, `cargo test` and maturin link the extension with `-undefined dynamic_lookup` from any directory.

### Verus proofs

The discrete kernels of the core are proved with [Verus](https://verus-lang.github.io/verus/guide/) and live in
`spinagram-core/src/verified/`. They are the production code: `text`, `css` and `route` call them, the ghost code is
erased by a normal `cargo build` and the maturin wheel, and the parity harnesses stay at 100 %.

Set up Verus once (release `0.2026.10.26.d17fbd0`, Rust toolchain `1.99.1`; the CI `verus` job does the same on x86
Linux):

```bash
# download verus-0.2026.10.26.d17fbd0-<platform>.zip from the verus-lang/verus releases into ~/.local/verus
rustup toolchain install 1.99.1
cd rust && PATH=$HOME/.local/verus:$PATH cargo verus verify -p spinagram-core   # "N verified, 0 errors"
```

| Module | Proved (`ensures`) | Used by |
|---|---|---|
| `segments` | `cuts` returns exactly the valid cut offsets of a token (strictly increasing, inside `0..len`, after a break character, outside every IPv4/CIDR range); `bounds` gives contiguous non-empty pieces from 0 to `len` that concatenate to the token | `text::segments` |
| `brackets` | `scan_close` stays in bounds, has positive depth before its result, and returns the length or an index where the depth is back to 0; the loop terminates | `css::substitute` (`var()`) |
| `bisect` | `bisect_left` on sorted integer keys: every key before the result is below `x`, every key from it on is at least `x` | router grid lookup (`order_key` maps `f64` to an order-preserving `u64`, tested not proved) |
| `cascade` | the key `(level, specificity, rule order, declaration index)` is a total order (reflexive, antisymmetric, transitive, total); `stable_order` returns a permutation sorted by key with equal keys in input order | `css::cascade` |
| `grid` | the A* neighbour step returns only cells inside the grid, and `None` exactly when the step leaves it | `route::search` |

No `assume`, `admit` or `#[verifier::external_body]` appears in `verified/`. Not proved, on purpose: floating-point
geometry (A* costs, text widths, PNG size), the Python-semantics number formatting in `pyfmt`, the SVG writer
(string and float heavy; Python-derived tests and the parity harnesses cover them) and `:not()` specificity, which
the `selectors` crate computes (see `DEPENDENCIES.md`).

## Parity rule

The Python implementation and its tests are the spec. Every ported slice must give identical results:
the same widths to the 1/64 px Pillow uses, the same lines, and byte-identical SVG for every example.

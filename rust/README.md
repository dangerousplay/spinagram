# spinagram Rust core

The engine is being ported to Rust one slice at a time. Python stays the main API and keeps working
without these crates.

| Crate | What it is |
|---|---|
| `spinagram-core` | Pure Rust library: font metrics, text measurement, wrapping and fitting (ported from `text.py` and `engine/textfit.py`), and orthogonal edge routing (ported from `autolayout/route.py`) |
| `spinagram-core-py` | PyO3 bindings, published as the `spinagram-core` wheel and imported as `spinagram_core` |

## Build and try it

```bash
cd rust && cargo test -p spinagram-core && cargo clippy --all-targets
cd spinagram-core-py && uvx maturin build --release -o ../target/wheels
cd ../.. && uv pip install --reinstall rust/target/wheels/spinagram_core-*.whl

SPINAGRAM_RUST=1 uv run --all-extras --no-sync pytest -q   # the Python suite against the Rust core
uv run --all-extras --no-sync python rust/bench/parity.py  # widths, fits and speed vs Pillow (a few minutes)
uv run --all-extras --no-sync python rust/bench/route_parity.py  # edge routes and speed vs the Python router
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

### Routing slice

`route.rs` is a line-by-line port of `autolayout/route.py`: the same A* order (the open set sorts like Python's
`heapq` on `(f, g, (i, j), dir, prev)`), the same float summation order, and `round(x, 2)` semantics in `simplify`
(ties such as 0.125 and 2.675 round like Python).

The crossing penalty crosses the boundary as data. `engine.route.Crossings(cost, drawn)` is callable from Python
and the core reads its `cost` and `drawn` fields. `route()` runs in Rust when the core is active and `penalty` is
None or a `Crossings`; any other callable penalty runs the Python router. `busy` is passed as the busy sides of
`src` and `dst` only.

### Harnesses

| Script | What it checks |
|---|---|
| `bench/route_parity.py` | Records every `route()` call made while building the examples (57 calls) plus 2,500 seeded random scenarios, requires identical point lists, prints `N of N identical` and a timing table. Exits 1 on any difference. |
| `bench/parity.py` | Text widths, fits and speed against Pillow (the text slice). |
| `bench/render_all.sh` | Renders every example to SVG; two runs, or Python versus `SPINAGRAM_RUST=1`, must give `diff -r` with no output. |

### Measured numbers

Developer machine, warm in-process, best of 3.

| Work | Before | After | Change |
|---|---|---|---|
| Build all examples, YAML cache (pure Python) | 1545 ms | 1273 ms | 18% faster |
| Build all examples with `SPINAGRAM_RUST=1` | 1262 ms | 394 ms | 3.2x |
| `route()` over the 57 recorded calls | 878 ms (Python) | 18.8 ms (Rust) | 46.6x |

The YAML work is smaller than planned because routing dominates the build; the Rust router is where the time goes.
Spec files stay on PyYAML's `SafeLoader` (libyaml accepts input it rejects); themes and icon registries use libyaml
and a stat-keyed parse cache.

## Parity rule

The Python implementation and its tests are the spec. Every ported slice must give identical results:
the same widths to the 1/64 px Pillow uses, the same lines, and byte-identical SVG for every example.

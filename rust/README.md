# spinagram Rust core

The engine is being ported to Rust one slice at a time. Python stays the main API and keeps working
without these crates.

| Crate | What it is |
|---|---|
| `spinagram-core` | Pure Rust library: font metrics, text measurement, wrapping and fitting (ported from `text.py` and `engine/textfit.py`) |
| `spinagram-core-py` | PyO3 bindings, published as the `spinagram-core` wheel and imported as `spinagram_core` |

## Build and try it

```bash
cd rust && cargo test -p spinagram-core && cargo clippy --all-targets
cd spinagram-core-py && uvx maturin build --release -o ../target/wheels
cd ../.. && uv pip install --reinstall rust/target/wheels/spinagram_core-*.whl

SPINAGRAM_RUST=1 uv run --all-extras --no-sync pytest -q   # the Python suite against the Rust core
uv run --all-extras --no-sync python rust/bench/parity.py  # widths, fits and speed vs Pillow
```

`SPINAGRAM_RUST=1` switches `spinagram.text.measure` and `spinagram.engine.textfit.fit_blocks` to the core
(see `src/spinagram/rust.py`). Without the flag or the wheel, everything is pure Python. Use `--no-sync`
so `uv run` does not remove the locally installed wheel.

## Parity rule

The Python implementation and its tests are the spec. Every ported slice must give identical results:
the same widths to the 1/64 px Pillow uses, the same lines, and byte-identical SVG for every example.

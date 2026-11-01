# Rust core routing + YAML loading: design

**Spec:** `spec.md` · **Decision:** STATE.md 2026-11-01 (Rust core port pattern)

## Components

```
src/spinagram/yamlload.py      NEW  parse(text) + load_file(path): libyaml loader, (path, mtime_ns, size) cache, deepcopy out, lock
src/spinagram/icons.py         EDIT _load_file → yamlload.load_file; registry() cached on (files' stat keys, cwd, $SPINAGRAM_ICON_PACKS)
src/spinagram/theme.py         EDIT _load_raw → yamlload.load_file
src/spinagram/yaml_io.py       EDIT safe_load calls → yamlload.parse (spec files are parsed once per load anyway)

rust/spinagram-core/src/route.rs   NEW  port of autolayout/route.py: _ports, _inside, _search (A*), _simplify, route
rust/spinagram-core-py/src/lib.rs  EDIT add route(...) binding
src/spinagram/engine/route.py      EDIT Crossings(cost, drawn) callable replaces the cost closure in route_ortho
src/spinagram/autolayout/route.py  EDIT route(): dispatch to the core when active and penalty is None/Crossings

rust/bench/render_all.sh        NEW  render every example folder to a directory (byte-identity checks)
rust/bench/route_parity.py      NEW  record route() calls from the examples + seeded random scenarios; compare; time
.github/workflows/ci.yml        EDIT new `rust` job: cargo test, clippy -D warnings, maturin wheel, pytest with SPINAGRAM_RUST=1
```

## Key decisions

- **Penalty as data.** `Crossings` holds `cost: float` and `drawn: list[((x1, y1), (x2, y2))]`. `__call__(p, q)` returns
  `cost * sum(crosses(p, q, *s) for s in drawn)`, identical to today's closure, so the Python router is unchanged.
  The binding takes `crossing: Option<(f64, Vec<((f64,f64),(f64,f64))>)>`.
- **Busy as two side lists.** `route()` only looks up `busy[src]` and `busy[dst]`, so the binding takes the two side
  sets, not the dict.
- **Exact A* order.** The open set is a min-heap over `(f, g, i, j, dx, dy, prev)` with `prev` ordered as Python
  tuples do (`None` only on the start state, which is pushed once). Floats compared with `total_cmp`; costs summed in
  the same order as Python (`g + step + bend + close*step`, then `+ penalty`).
- **Grid lines.** Collect, sort with `total_cmp`, dedup by `==` (Python set semantics). `bisect_left` = `partition_point(|v| v < x)`.
- **`round(x, 2)`.** Format with Rust's exact decimal formatting (`format!("{:.2}")`) only if it rounds ties to even
  like Python; otherwise implement Python's algorithm (correctly rounded decimal of the exact binary value). Tests with
  0.125, 0.375, 2.675, 1.005, -0.125 decide.
- **Flag check per call.** `rust.core()` is read at import like the text slice; `route()` checks `_CORE is not None`.

## Error handling

Rust never raises on engine input; any failure to import the core falls back to Python (`rust.core()` returns None).

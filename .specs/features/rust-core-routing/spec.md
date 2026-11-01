# Rust core: faster spec loading and edge routing in Rust

**Status:** In Tasks · **Size:** Large · **Branch:** `spike/rust-core`
**Builds on:** the text-core spike (`5f33d46`), `.specs/research/rust-spike-text-core.md`

## Problem Statement

Building the 46 example scenes takes about 1.95 s in-process. Two places dominate: orthogonal edge routing
(`autolayout/route.py`, A* search) is about 49 % of build time, and pure-Python YAML parsing is about 35 %,
mostly icon-pack registries and theme files re-read for every spec. The project has decided to port the
engine to Rust gradually while keeping Python fully supported. This feature removes the YAML waste in
Python and ports edge routing to the Rust core behind the existing `SPINAGRAM_RUST` switch.

## Goals

- [ ] Warm in-process build of all examples is at least 25 % faster with the YAML changes alone (pure Python).
- [ ] With `SPINAGRAM_RUST=1`, edge routing returns exactly the polylines the Python router returns, and the
      routing step is at least 10x faster on the recorded example corpus.
- [ ] Python stays the reference: the full test suite passes with and without the Rust core, and every
      example SVG is byte-identical in both modes.

## Out of Scope

| Feature | Reason |
|---|---|
| Porting `loop()`, `route_bundle`, `route_ortho` bookkeeping, `crossings()` | Cheap; only the A* `route()`/`_search()` is hot |
| Making Rust the default (flag on by default) | Needs wheels for every platform first |
| Publishing `spinagram-core` wheels to PyPI, adding it as a spinagram dependency | Separate release decision |
| Porting YAML parsing to Rust (saphyr) | YAML 1.1 vs 1.2 semantics; the libyaml switch gets most of the gain |
| Changing routing behaviour, costs or results | Pure port: Python output is the spec |
| WASM build of the core | Later milestone (web editor) |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
|---|---|---|---|
| How Rust gets the crossing penalty | A structured penalty object (`Crossings(cost, drawn_segments)`) that is still callable from Python; Rust reads its fields | The only caller (`engine/route.py`) always means "fixed cost per strict crossing with drawn segments"; a Python callback per A* step would erase the gain | y (only one caller, verified with `git grep penalty=`) |
| `route()` called with any other callable penalty | Runs the Python router | Keeps the public signature working for any caller | y |
| YAML loader | `yaml.CSafeLoader` when `yaml.__with_libyaml__`, else `yaml.SafeLoader` | Same YAML 1.1 semantics as `safe_load`, C speed | y |
| YAML error messages | User-facing errors that spinagram formats itself keep their text; the parser's own message text may differ between the C and Python loaders | libyaml words some parse errors differently; existing tests are the arbiter | y |
| File parse cache key | Absolute path + `st_mtime_ns` + `st_size`; callers get a deep copy | The live UI edits files while running; a copy keeps callers from mutating the cache | y |
| Icon registry cache | Cache `registry()` per process keyed by the registry files' (path, mtime_ns, size), the cwd and `$SPINAGRAM_ICON_PACKS` | Same invalidation rule as files | y |
| Float rounding in `_simplify` | Rust reproduces Python `round(x, 2)` exactly, including ties such as 0.125 and 2.675 | Polylines must be identical | y |
| A* tie-breaking | Rust orders the open set exactly like Python's `heapq` on `(f, g, (i, j), dir, prev)` tuples | Equal-cost paths must resolve the same way | y |
| Performance numbers | Measured on the developer machine with the bench scripts, best of 3, warm | Machine-dependent; recorded in validation.md | y |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Specs, themes and icon registries load fast in pure Python ⭐ MVP

**User Story**: As a spinagram user, I want rendering to skip re-parsing the same YAML files so that builds
and live preview are faster without installing anything new.

**Why P1**: Biggest gain for every user, no Rust required.

**Acceptance Criteria**:

1. WHERE libyaml is available (`yaml.__with_libyaml__` is True) the system SHALL parse YAML with `yaml.CSafeLoader`. <!-- optional-feature --> (YAML-01)
2. IF libyaml is not available THEN the system SHALL parse YAML with `yaml.SafeLoader` and return the same data. <!-- unwanted --> (YAML-02)
3. WHEN the same theme or icon registry file is loaded twice in one process without changing on disk THEN the system SHALL parse it once. <!-- event --> (YAML-03)
4. WHEN a cached file changes on disk (different `st_mtime_ns` or `st_size`) THEN the system SHALL parse it again on the next load. <!-- event --> (YAML-04)
5. WHEN a caller mutates data returned from the file cache THEN the system SHALL return unmutated data on the next load of that file. <!-- event --> (YAML-05)
6. WHEN `registry()` is called again with unchanged registry files, cwd and `$SPINAGRAM_ICON_PACKS` THEN the system SHALL return packs equal to a fresh build without re-reading the files. <!-- event --> (YAML-06)
7. WHEN `$SPINAGRAM_ICON_PACKS`, the cwd or any registry file changes THEN `registry()` SHALL rebuild the packs. <!-- event --> (YAML-07)
8. The system SHALL produce byte-identical SVG for every example before and after this change. <!-- ubiquitous --> (YAML-08)

**Independent Test**: Load a theme twice with the parser spied: one parse. Touch the file: two parses. Render examples before and after: identical.

---

### P1: Edge routing runs in Rust with identical results ⭐ MVP

**User Story**: As a spinagram user with the Rust core installed, I want edge routing to run in Rust so that
diagrams with many edges build fast, with exactly the same output.

**Why P1**: About half of build time.

**Acceptance Criteria**:

1. WHERE the Rust core is active (`SPINAGRAM_RUST=1` and `spinagram_core` importable) and `penalty` is None or a `Crossings` object, `autolayout.route.route()` SHALL compute the route in Rust. <!-- optional-feature --> (ROUTE-01)
2. WHERE the Rust core is active and `penalty` is any other callable, `route()` SHALL compute the route in Python. <!-- optional-feature --> (ROUTE-02)
3. WHILE the Rust core is not active `route()` SHALL behave exactly as before this feature. <!-- state --> (ROUTE-03)
4. The Rust router SHALL return the same list of points (same length, same coordinates, compared with `==`) as the Python router for the same arguments. <!-- ubiquitous --> (ROUTE-04)
5. WHEN no side pair yields a route THEN the Rust router SHALL return the same 4-point elbow fallback as Python (bottom of `src` to top of `dst`). <!-- event --> (ROUTE-05)
6. WHEN a port stub lies inside an obstacle THEN the Rust search SHALL reject that side pair, as Python does. <!-- event --> (ROUTE-06)
7. WHEN `busy` marks a side of `src` or `dst` THEN the Rust router SHALL add `BUSY` (400) per busy end to that side pair's cost. <!-- event --> (ROUTE-07)
8. WHEN `penalty` is a `Crossings(cost, drawn)` THEN the Rust search SHALL add `cost` × (number of drawn segments the grid segment strictly crosses) to each step, matching `engine.route.crosses`. <!-- event --> (ROUTE-08)
9. WHEN `fracs` gives a fraction for an end THEN the Rust router SHALL place that port at the fraction of its side, as Python's `_ports` does. <!-- event --> (ROUTE-09)
10. The Rust `_simplify` step SHALL round coordinates exactly like Python `round(x, 2)`, including binary ties such as 0.125, 0.375 and 2.675. <!-- ubiquitous --> (ROUTE-10)
11. `engine.route.route_ortho` SHALL pass its crossing penalty as a `Crossings` object, which stays callable with `(p, q)` and returns the same cost as the old closure. <!-- ubiquitous --> (ROUTE-11)

**Independent Test**: Replay every `route()` call recorded while building the examples, plus seeded random scenarios, through both routers: 100 % identical point lists.

---

### P2: Parity, speed and the Python suite are checked automatically

**User Story**: As a maintainer, I want CI to build the Rust core and run the Python suite against it so that
the two implementations cannot drift.

**Why P2**: Protects every future slice of the port.

**Acceptance Criteria**:

1. WHEN `rust/bench/route_parity.py` runs THEN it SHALL report the number of identical results out of the recorded example calls and at least 2,000 seeded random scenarios, and exit non-zero if any differ. <!-- event --> (PAR-01)
2. WHEN `rust/bench/route_parity.py` runs THEN it SHALL report Python and Rust routing time over the recorded corpus (best of 3). <!-- event --> (PAR-02)
3. WHEN CI runs on a push or pull request THEN it SHALL run `cargo test` and `cargo clippy -- -D warnings` for the Rust workspace. <!-- event --> (PAR-03)
4. WHEN CI runs on a push or pull request THEN it SHALL build the `spinagram-core` wheel, install it, and run the pytest suite with `SPINAGRAM_RUST=1`. <!-- event --> (PAR-04)
5. IF the `spinagram-core` wheel is not installed THEN the existing CI pytest job SHALL keep passing unchanged. <!-- unwanted --> (PAR-05)

**Independent Test**: Break one comparison in the Rust router locally: `route_parity.py` exits 1 and the CI job's pytest step fails.

---

## Edge Cases

- IF `obstacles` contains `src` or `dst` THEN both routers SHALL avoid them except at the ports (existing behaviour, ROUTE-04).
- WHEN `sides` fixes one or both ends THEN the Rust router SHALL try only those sides (ROUTE-04).
- WHEN `guides` is empty THEN the Rust router SHALL build the grid from obstacles and stubs only (ROUTE-04).
- WHEN two side pairs cost within 1e-9 of each other THEN the Rust router SHALL keep the first found, in the order top, bottom, left, right for both ends (ROUTE-04).
- IF a YAML file is empty THEN the cached loader SHALL return what `safe_load` returned for it (None) (YAML-02).
- IF a YAML file does not exist THEN loading SHALL raise the same exception type as before (YAML-03).

## Implicit-requirement dimensions

| Dimension | Coverage |
|---|---|
| Input validation & bounds | N/A because `route()` inputs come from the engine, already validated; Rust mirrors Python on any input |
| Failure / partial-failure states | ROUTE-05 (no route), ROUTE-06 (blocked stub), YAML-02 (no libyaml) |
| Idempotency / retry | YAML-03..07: repeated loads are cache hits, changes invalidate |
| Auth boundaries & rate limits | N/A because this is a local library with no access control |
| Concurrency / ordering | ROUTE-04 + A* tie-breaking assumption; the file cache must be safe for the live UI's single process (a lock around cache writes) |
| Data lifecycle / expiry | YAML-04, YAML-07: entries invalidate on file change; the cache lives for the process |
| Observability | PAR-01, PAR-02 report parity and timings |
| External-dependency failure | ROUTE-02/03: without the wheel or with another penalty, Python runs; YAML-02 without libyaml |
| State-transition integrity | N/A because there are no state machines in scope |

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
|---|---|---|---|
| YAML-01 | P1: fast YAML | In Tasks | Pending |
| YAML-02 | P1: fast YAML | In Tasks | Pending |
| YAML-03 | P1: fast YAML | In Tasks | Pending |
| YAML-04 | P1: fast YAML | In Tasks | Pending |
| YAML-05 | P1: fast YAML | In Tasks | Pending |
| YAML-06 | P1: fast YAML | In Tasks | Pending |
| YAML-07 | P1: fast YAML | In Tasks | Pending |
| YAML-08 | P1: fast YAML | In Tasks | Implementing |
| ROUTE-01 | P1: Rust routing | In Tasks | Pending |
| ROUTE-02 | P1: Rust routing | In Tasks | Pending |
| ROUTE-03 | P1: Rust routing | In Tasks | Pending |
| ROUTE-04 | P1: Rust routing | In Tasks | Pending |
| ROUTE-05 | P1: Rust routing | In Tasks | Pending |
| ROUTE-06 | P1: Rust routing | In Tasks | Pending |
| ROUTE-07 | P1: Rust routing | In Tasks | Pending |
| ROUTE-08 | P1: Rust routing | In Tasks | Pending |
| ROUTE-09 | P1: Rust routing | In Tasks | Pending |
| ROUTE-10 | P1: Rust routing | In Tasks | Pending |
| ROUTE-11 | P1: Rust routing | In Tasks | Pending |
| PAR-01 | P2: parity in CI | In Tasks | Pending |
| PAR-02 | P2: parity in CI | In Tasks | Pending |
| PAR-03 | P2: parity in CI | In Tasks | Pending |
| PAR-04 | P2: parity in CI | In Tasks | Pending |
| PAR-05 | P2: parity in CI | In Tasks | Pending |

**Coverage:** 24 total, 24 mapped to tasks, 0 unmapped.

---

## Success Criteria

- [ ] Warm in-process build of all examples (pure Python) is at least 25 % faster than before the YAML change.
- [ ] `route_parity.py`: 100 % identical results; Rust routing at least 10x faster than Python on the corpus.
- [ ] Full pytest suite passes with and without `SPINAGRAM_RUST=1`; all example SVGs byte-identical across modes.

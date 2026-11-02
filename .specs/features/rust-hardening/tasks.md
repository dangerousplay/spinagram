# Production hardening of the Rust engine — Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the per-task cycle.

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Spec**: `.specs/features/rust-hardening/spec.md`
**Status**: Ready

Every task is a refactor under a parity contract: outputs must not change unless the requirement says so. Run the
gate after each task, one Conventional Commit per task.

## Test Coverage Matrix

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Rust core | unit | New grammars, enums, errors, security rules; existing tests untouched | `#[cfg(test)] mod tests`, `rust/spinagram-core/tests/` | `cd rust && cargo test` |
| PyO3 bindings | integration | `EditError.index`, edge vectors against Python `parse_edge` | `tests/test_rust_edit.py`, `tests/test_edge_vectors.py` | `uv run --all-extras pytest -q` |
| WASM crate | integration | Error objects, goldens | `rust/spinagram-wasm/tests/*.test.ts` | `cd rust/spinagram-wasm && bunx bun@1.4.2 test` |
| Parity | script | 49/49 SVG, CSS, route, text | `rust/bench/*.py` | see Gate `full` |
| CI config | none | build gate only | `.github/workflows/ci.yml` | YAML parse + local wheel/sdist build |

## Gate Check Commands

**Gate `rust`**: `cd rust && cargo test && cargo clippy --workspace --all-targets -- -D warnings`
**Gate `full`**: gate `rust` + `uv sync --all-extras` + `uv run --all-extras pytest -q` + `SPINAGRAM_RUST=0 uv run --all-extras pytest -q` + `uv run --all-extras python rust/bench/svg_png_parity.py --svg-only` (all three modes it runs) + `css_parity.py` + `route_parity.py` + `parity.py` + `bash rust/spinagram-wasm/build.sh && (cd rust/spinagram-wasm && bunx bun@1.4.2 test)` + `(cd web && bunx bun@1.4.2 test)` + `cargo deny check` (when installed)

## Execution Plan

```
T1 ──→ T2 ──→ T3 ──→ T4 ──→ T5 ──→ T6 ──→ T7 ──→ T8 ──→ T9
```

## Task Breakdown

### T1: `yaml_span` module on saphyr-parser events

**What**: Move `parse`, `Frame`, `closer`, `Node`, `Val`, `parse_diagram` out of `edit.rs` into
`rust/spinagram-core/src/yaml_span.rs`. Detect flow/block after skipping anchor (`&x`) and tag (`!t`, `!!map`)
tokens; reject anchors and aliases ("anchors and aliases are not supported"); typed `YamlError` (thiserror) with
line, column and true byte offset (map saphyr's char index through the char→byte table).
**Depends on**: none
**Requirement**: PAR-01..04, ERR-01 (partial)
**Tests**: tagged flow map span; anchor/alias rejected; invalid YAML after `é` reports the byte offset; all existing edit tests unchanged.
**Gate**: rust
**Commit**: `refactor(core): yaml_span module with typed errors, anchors and tags`
**Status**: Done
**Notes**: Anchors are rejected only inside the edited top-level lists (nodes, zones, edges, rows, columns), as PAR-03 says; elsewhere they parse. Node gains an anchored flag.

### T2: `edge_syntax` grammar (winnow) with shared vectors

**What**: Add `winnow` and a `edge_syntax.rs` module: `EdgeText` (keeps spacing for rewrites), `EdgeOp` enum
(`<->`, `->`, `<-`, `--`, with `arrow()`), `Endpoint { target: EndpointTarget, id, side: Option<Side>, frac }`.
Grammar = Python `parse_edge` regex exactly (see spec LEX-01). Write `rust/schema/edge_vectors.json` (≥ 30 cases,
including every edge case in LEX-01 and endpoint suffixes) and run it from `cargo test` and from a new
`tests/test_edge_vectors.py` against `spinagram.model.parse_edge` (and `engine/endpoints._split` for endpoints).
Remove `EdgeText::parse`/`endpoint` from `edit.rs`.
**Depends on**: T1
**Requirement**: LEX-01..04, ENM-01 (EdgeOp, EndpointTarget)
**Tests**: the vector table on both sides; existing edge rewrite byte tests.
**Gate**: rust + pytest of the new file
**Commit**: `refactor(core): edge grammar on winnow with vectors shared with the Python loader`
**Status**: Done
**Notes**: Vectors: 319 edge strings and 23 edge ends from the Python loader; the Rust grammar also agreed on 12,059 random strings in a one-off run. Endpoint.frac is f64.

### T3: Typed edit operations and validated ends

**What**: `Axis`, container `Align`, prop key enums (`NodeProp`, `ZoneProp`, `EdgeProp` with `kind()`, `x-*` as an
extension), `Arrow`, `RouteKind` in `Op` and `set_props`; serde rejects unknown values with the accepted list.
`connect`/`reconnect` validate ends (LEX-05). Merge the reserved-word lists. Named consts (`SNAP`, `DEFAULT_GAP`,
`MAX_EXACT_INT`).
**Depends on**: T2
**Requirement**: ENM-01, ENM-03, ENM-04, LEX-05, API-02
**Tests**: `axis: "diagonal"` rejected naming index and values; `zone:x` with node `x` rejected; id containing `->` rejected.
**Gate**: rust
**Commit**: `refactor(core): enums for edit operation values and validated edge ends`
**Status**: Done
**Notes**: Op deserialises per operation, so a bad enum value reports its index and the accepted values; the group axis and container align errors keep the field name. Accepted values for container align are center, start, end. Axis lives in edit_values.rs (T5 reuses it for the scene).

### T4: Index per op and single re-parse

**What**: Build an `Index` (ids → entries, node → containers) once per op; reuse the parsed result of the
post-op check as the next op's input tree.
**Depends on**: T3
**Requirement**: PRF-01, PRF-02
**Tests**: existing edit tests; a 2,000-node `move_zone` test under a time bound generous enough for debug CI (e.g. < 2 s).
**Gate**: rust
**Commit**: `perf(core): one index and one parse per edit operation`
**Status**: Done
**Notes**: 2,000-node move_zone runs in 0.07 s in a debug build. Parses per batch: operations + 1.

### T5: Scene, SVG, route and fit enums and constants

**What**: `Side` shared by route and reroute; `ShapeKind` (replaces `MIDPOINT_KINDS`), `Role`, `ConnectorRoute`,
`MarkerKind`, `Paint`, `Align`, `VAlign`, `TextAnchor`, `LineCap`, `FitMode`, `FitStrategy`, `PseudoElement`
(drop `PSEUDOS` array), `MimeType`; named geometry consts in svg/route/fit/css. Serialised strings unchanged;
regenerate `rust/schema/` (only enum constraints may be added).
**Depends on**: T4
**Requirement**: ENM-01..03
**Tests**: round-trip every enum through serde; parity scripts.
**Gate**: full
**Commit**: `refactor(core): enums and named constants for scene, svg, routing and fitting`
**Status**: Done
**Notes**: Schema diff is only enum refs replacing string types. Role holds the eight roles Python writes (node, zone, pill, swatch, chrome, panel, node-part, callout); ShapeKind keeps unknown kinds as Other(String) because node kinds are an open set; scene enums reject unknown strings, as the scene writer only emits these. fit_blocks no longer returns Result (the mode is typed; FitMode::parse keeps the error text). The ::title/::body/::label order is unchanged.

### T6: Tokenizers for CSS var() and SVG paths

**What**: `css::substitute` on the cssparser tokenizer (nested fallbacks), `MAX_VAR_PASSES`; reroute `map_path` on
`svgtypes::PathParser` (direct dependency).
**Depends on**: T5
**Requirement**: LEX-06, LEX-07
**Tests**: nested fallback; path with relative commands and exponents; CSS parity; wasm goldens.
**Gate**: full
**Commit**: `refactor(core): cssparser tokenizer for var() and svgtypes for paths`
**Status**: Done
**Notes**: SPEC_DEVIATION (LEX-06, partial): cssparser splits the var() name from the fallback at the first top-level comma (nested fallbacks tested against Python), but the extent of a var( stays the proved parenthesis scanner. Python counts parentheses per character, strings and comments included, so a tokenizer would change var(--a, ")") and the unclosed var(--oops cases and break byte parity with the reference. Text with a string, comment or escape is cut at the first comma as Python does. Recorded in rust/DEPENDENCIES.md. LEX-07 as specified (svgtypes::PathParser; relative commands, exponents, H V S Q T A).

### T7: Errors, FFI and API surface

**What**: thiserror enums in remaining modules; no `unwrap`/`expect` on input data (pyfmt infallible split,
`LazyLock` regexes, poisoned locks recover). PyO3: `EditError` with `.index`. wasm: throw `Error` with `index`.
Internal modules `pub(crate)`, `#![warn(missing_docs)]`.
**Depends on**: T6
**Requirement**: ERR-01..04, API-01
**Tests**: pytest `EditError.index`; bun test reads `err.index` and `err.message`; message text unchanged.
**Gate**: full
**Commit**: `refactor(core): typed errors across the FFI and a smaller public API`
**Status**: Done
**Notes**: Per-module thiserror enums (YamlError, SceneError, FontError, DrawError, PngError, CssError, RerouteError, OpError, FitModeError, EditError); OpError keeps the free-form reason text of an operation as OpError::Invalid, with UnknownId and Yaml split out. apply_ops_json now returns EditError (index + reason), so bad JSON has index None and a bad operation its position. PyO3 sets .index on the ValueError and spinagram.edit.EditError reads it; wasm throws js_sys::Error with an index property, and the web worker sends error.message instead of String(error). Modules edge_syntax, edit_values, fit, css, route, ... stay public (documented grammar and types); pyfmt, verified and yaml_span are pub(crate). Op's variant fields are covered by one expect(missing_docs) since each variant doc names its fields. The scene schema gains field descriptions from the new doc comments (additions only).

### T8: SVG writer security

**What**: Escape colours in attributes and derive marker ids safely (both engines, byte-identical for normal
colours). Restrict file reads in `svg.rs` to registered files or the allowed roots the Python engine uses; match
Python's rule (investigate `src/spinagram/backends/svg.py` and the icon resolver first; fix Python too if it
reads arbitrary paths).
**Depends on**: T7
**Requirement**: SEC-01, SEC-02
**Tests**: colour `x" onload="y` escaped in both engines with identical output; `rgb(1,2,3)` marker id valid; scene icon path outside the roots not read.
**Gate**: full
**Commit**: `fix(svg): escape colours and restrict embedded file reads`

### T9: Stop committing the web bundle

**What**: `git rm -r --cached src/spinagram/ui/static`, add it to `.gitignore`. CI: `web` job uploads
`ui-static` artifact (drop the staleness check); `wheels` and `sdist` `needs: web` and download it into
`src/spinagram/ui/static`; `tool.maturin.include` for the bundle (format sdist and wheel). Skip
`test_the_committed_bundle_ships_the_wasm_the_canvas_loads` when the bundle is not built. Update
`docs/content/docs/reference/development.mdx` and `rust/README.md` if they say to commit it.
Verify locally: build the bundle, `uvx maturin build` and `uvx maturin sdist`, list both archives for `ui/static/index.html`.
**Depends on**: T8
**Requirement**: BLD-01..05
**Tests**: local wheel and sdist listing; ci.yml parses.
**Gate**: full
**Commit**: `build: build the UI bundle in CI instead of committing it`

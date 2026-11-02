# Feature: Production hardening of the Rust engine

**Status:** Specify · **Size:** Large · **Owner:** spinagram
**Source:** user request 2026-11-02 ("refactor the rust code, use a rust library for the diagram parsing, move all
the constants to enums, use robust tokenization/lexer, review as for production, remove the compiled static files").
**Review:** orchestrator-commissioned read-only review of `rust/` (2026-11-02), summarised under Findings.

## Problem Statement

The Rust engine is the default for rendering and editing, but parts of it read like a spike: string-typed values
(`axis: String`, `"<->"`, `"zone:"`, side and shape names, prop tables of string lists), hand-cut string parsing
(the edge DSL, endpoints, `var()` substitution, SVG path splitting), a hand-built YAML span tree that mis-handles
anchors and tags, `String` errors that lose the failing operation at the FFI boundary, two injection paths in the
SVG writer, and quadratic lookups in edit operations. The built web bundle (`src/spinagram/ui/static/`) is
committed and must be rebuilt by hand with a pinned bun; CI already has every tool to build it.

## Goals

- [ ] Every parser in the Rust core is a library parser (saphyr-parser events, winnow grammars, cssparser tokenizer,
      svgtypes path parser) with typed errors; no hand-cut `find`/`split` parsing of user text remains.
- [ ] Every closed set of string values in the Rust core is an enum; magic numbers are named constants.
- [ ] Output is unchanged: SVG parity 49/49 in every mode, wasm goldens, pytest in both engine modes.
- [ ] The repository holds no built web assets; CI builds them and every wheel and the sdist still ship them.

## Out of Scope

| Item | Reason |
|---|---|
| Replacing saphyr-parser events with the `saphyr` loader (`MarkedYaml`) | Verified by the review: it gives char (not byte) spans, flow ends before the bracket, block ends over trailing comments, no flow flag, no scalar style once resolved. It needs the same fix-ups as today and loses style; the event parser *is* the library. Decision recorded in STATE.md |
| Changing `src/verified/` (Verus) | Proof design is separate; only call sites may change |
| Changing the Python engine's behaviour | Python is the reference; Rust matches it. Python changes only where a security fix must stay byte-identical on both sides |
| Web UI features | None in this feature |

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
|---|---|---|---|
| YAML parsing library | Keep `saphyr-parser` (event API) in a dedicated `yaml_span` module; take flow/block from source after skipping anchor/tag tokens; reject anchors and aliases with a clear error | Review evidence above | orchestrator |
| Edge grammar library | `winnow` 1.x, one module `edge_syntax` for the edge text and the endpoint (`zone:` prefix, `.side@frac`) | Needs leftmost-operator-with-backtracking, which a DFA lexer (`logos`) cannot express | orchestrator |
| Enum derive | `strum` (`EnumString`, `AsRefStr`, `Display`, `IntoStaticStr`, `VariantArray`) + serde `rename_all`; scene enums also `JsonSchema` | Serialised strings must stay exactly as today | orchestrator |
| Errors | `thiserror` enums per module; the edit error keeps the op index across PyO3 (`EditError.index`) and wasm (JS `Error` with `index` property) | Callers lose the failing op index today | orchestrator |
| Bundle in CI | `web` job builds and uploads artifact `ui-static`; `wheels` and `sdist` download it into `src/spinagram/ui/static/` before maturin; maturin `include` keeps the ignored files | CI already builds the bundle; committing it forces a pinned local bun | orchestrator |

Open questions: none.

## User Stories

- As a maintainer, I want the Rust engine typed and parsed by libraries, so that edits and renders fail loudly instead of patching wrong bytes.
- As a user of `spinagram serve`, I want diagrams with odd colours or icon paths to render safely.
- As a contributor, I want CI to build the web bundle, so that I never commit generated files.

---

## Requirements

### PAR — YAML span parsing

- **PAR-01** WHEN an edit operation or `srcmap` reads YAML THEN the core SHALL build the span tree in a `yaml_span`
  module from saphyr-parser events, with UTF-8 byte spans.
- **PAR-02** WHEN a collection carries an anchor or tag (`&a {…}`, `!!map {…}`) THEN flow/block detection SHALL
  look past those tokens, and the span SHALL be the collection's own.
- **PAR-03** WHEN the YAML holds an anchor or alias inside an edited list THEN the operation SHALL fail with
  "anchors and aliases are not supported" rather than patch a wrong range.
- **PAR-04** WHEN the YAML is invalid THEN the error SHALL report line, column and *byte* offset (saphyr reports a
  char index as "byte"; non-ASCII text before the error must give the true byte offset).

### LEX — Grammars and tokenizers

- **LEX-01** WHEN an edge string is read THEN `edge_syntax` (winnow) SHALL accept exactly what Python's
  `parse_edge` (`src/spinagram/model.py`) accepts and return the same src, op, dst and label, including:
  leftmost operator with alternation order `<->`, `->`, `<-`, `--`; backtracking to a later operator; `zone:`
  prefix on dst; `a -> aws:s3` → dst `aws`, label `s3`; `a -> zone:` → dst `zone`, empty label → None; Unicode
  whitespace; newlines rejected; whitespace-only src kept.
- **LEX-02** WHEN a test vector table `rust/schema/edge_vectors.json` lists inputs and expected parses THEN both
  `cargo test` and pytest SHALL run it against their parser and agree with it.
- **LEX-03** WHEN an edit rewrites an edge (label, ends, reverse) THEN the untouched spacing SHALL be preserved
  as today (existing byte-preservation tests unchanged).
- **LEX-04** WHEN an endpoint is parsed THEN it SHALL be a typed `Endpoint { target: Node|Zone, id, side:
  Option<Side>, frac: Option<String|f64> }` matching Python `endpoints._split`.
- **LEX-05** WHEN `connect` or `reconnect` receives an end THEN it SHALL reject `zone:x` where `x` is not a zone,
  and any end whose rendered edge does not parse back to the same ends.
- **LEX-06** WHEN CSS `var()` is substituted THEN it SHALL use the cssparser tokenizer (nested fallbacks
  `var(--a, var(--b, red))` tested); CSS parity unchanged.
- **LEX-07** WHEN reroute maps an SVG path THEN it SHALL use `svgtypes::PathParser`; wasm goldens unchanged.

### ENM — Enums and constants

- **ENM-01** WHEN a value comes from a closed set THEN it SHALL be an enum in Rust: `Axis`, container `Align`,
  `EdgeOp`, `Arrow`, `RouteKind`, `Side` (single, shared by route and reroute), `EndpointTarget`, node/zone/edge
  prop keys with their value kind, `ShapeKind`, `Role`, `ConnectorRoute`, `MarkerKind`, `Paint`, text `Align`/
  `VAlign`/`TextAnchor`, `LineCap`, `FitMode`, `FitStrategy`, `PseudoElement`, `MimeType`.
- **ENM-02** WHEN an enum is serialised (serde, scene JSON schema, PyO3, wasm) THEN its strings SHALL be exactly the
  strings used today; `rust/schema/` regenerates with no diff other than added `enum` constraints.
- **ENM-03** WHEN a number has a meaning (snap 10, default gap 20, var passes 8, marker geometry, filter box,
  route padding, fit slack, max exact int) THEN it SHALL be a named `const` with a doc comment.
- **ENM-04** WHEN an op receives an unknown enum string (e.g. `axis: "diagonal"`) THEN it SHALL fail with the
  op index and the list of accepted values.

### ERR — Errors and FFI

- **ERR-01** The core SHALL use `thiserror` error enums per module instead of `Result<_, String>`.
- **ERR-02** WHEN `apply_ops` fails in Python THEN `spinagram.edit.EditError` (a `ValueError`) SHALL carry
  `.index` (or `None`) and the message format SHALL be unchanged (`operation 0: reparent: unknown id \`nowhere\``).
- **ERR-03** WHEN a wasm export fails THEN it SHALL throw a JS `Error` whose message is today's message and which
  carries `index` when an operation is to blame.
- **ERR-04** No `unwrap`/`expect`/panicking index on input-derived data in non-test code; poisoned mutexes recover.

### SEC — Security

- **SEC-01** WHEN a colour from the scene is written into SVG THEN it SHALL be attribute-escaped, and marker ids
  SHALL be derived so any colour yields a valid XML id. Normal colours (hex, rgb(), names) render byte-identically
  in both engines; the Python writer gets the same escaping.
- **SEC-02** WHEN the SVG writer embeds a file named in the scene THEN it SHALL only read files the host
  registered or that resolve inside an allowed root; any other path SHALL be skipped as a missing icon. Mirrors the
  Python engine's rule (verify which paths the Python engine reads, and match).

### PRF — Performance

- **PRF-01** An op SHALL parse the YAML once before and once after (today: twice before).
- **PRF-02** Id and container lookups inside one op SHALL use an index built once per op (no O(n²) rescans in
  `move_zone`, `descendants`, `group`, `in_container`).

### API — Surface

- **API-01** Internal modules SHALL be `pub(crate)`; the public facade is what the PyO3 and wasm crates and the
  benches use. `#![warn(missing_docs)]` passes.
- **API-02** Duplicated YAML reserved-word lists in `edit.rs` SHALL be one list.

### BLD — Built assets

- **BLD-01** `src/spinagram/ui/static/` SHALL not be tracked; `.gitignore` lists it.
- **BLD-02** WHEN CI runs THEN the `web` job SHALL build the bundle and upload it; `wheels` and `sdist` SHALL build
  with it in place, and wheel smoke SHALL keep asserting `ui/static/index.html` in the wheel.
- **BLD-03** WHEN the sdist is built THEN it SHALL contain the bundle, so `source-install` serves the UI.
- **BLD-04** WHEN pytest runs without a built bundle THEN tests that need the real bundle SHALL skip with a reason;
  the server keeps serving its placeholder page.
- **BLD-05** The development docs SHALL explain building the bundle locally and drop "commit the bundle".

## Success Criteria

- [ ] `cargo test`, `cargo clippy --workspace --all-targets -- -D warnings`, `cargo deny check` pass
- [ ] pytest passes in Rust and `SPINAGRAM_RUST=0` modes; SVG parity 49/49 (subset/embed/link); CSS, route, text parity scripts pass
- [ ] wasm bun tests and goldens pass; web bun tests and build pass
- [ ] A wheel and an sdist built locally with the bundle ignored by git still contain `spinagram/ui/static/index.html`

## Requirement Traceability

| ID | Task | Status |
|---|---|---|
| PAR-01 | T1 | Done |
| PAR-02 | T1 | Done |
| PAR-03 | T1 | Done |
| PAR-04 | T1 | Done |
| ERR-01 | T1 | Done |
| LEX-01 | T2 | Done |
| LEX-02 | T2 | Done |
| LEX-03 | T2 | Done |
| LEX-04 | T2 | Done |
| LEX-05 | T3 | Done |
| ENM-04 | T3 | Done |
| API-02 | T3 | Done |
| PRF-01 | T4 | Pending |
| PRF-02 | T4 | Pending |
| ENM-01 | T5 | Pending |
| ENM-02 | T5 | Pending |
| ENM-03 | T5 | Pending |
| LEX-06 | T6 | Pending |
| LEX-07 | T6 | Pending |
| ERR-02 | T7 | Pending |
| ERR-03 | T7 | Pending |
| ERR-04 | T7 | Pending |
| API-01 | T7 | Pending |
| SEC-01 | T8 | Pending |
| SEC-02 | T8 | Pending |
| BLD-01 | T9 | Pending |
| BLD-02 | T9 | Pending |
| BLD-03 | T9 | Pending |
| BLD-04 | T9 | Pending |
| BLD-05 | T9 | Pending |

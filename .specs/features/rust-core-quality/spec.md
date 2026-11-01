# Rust core quality: crates first, clippy, cargo-deny and Verus proofs

**Status:** In Tasks · **Size:** Large · **Branch:** `spike/rust-core`
**Builds on:** `rust-core-css`; user directives 2026-11-01 (crates over handwritten code; clippy; cargo-deny; Verus)

## Problem Statement

The Rust core now holds text, routing, the scene model, SVG/PNG and the CSS cascade, partly as hand-written ports. The
user wants established crates wherever they reproduce the required behaviour, enforced lint and supply-chain policy
(clippy, cargo-deny), and machine-checked proofs (Verus) for the core's logic. Parity with Python stays the contract:
any crate swap must keep every parity harness at 100 %.

## Goals

- [ ] Every hand-written component in `rust/` is either replaced by a crate or listed with the reason no crate fits.
- [ ] `cargo clippy` (pedantic) and `cargo deny check` pass locally and in CI.
- [ ] The core's discrete kernels are proved with Verus, and the proved functions are the ones production code calls.

## Out of Scope

| Feature | Reason |
|---|---|
| Proving floating-point geometry (A* costs, text widths, PNG size) | Verus support for `f64` is limited; parity harnesses cover these |
| Proving Python-semantics formatting (`pyfmt`) | String/float heavy; covered by Python-derived tests |
| Replacing a hand-written piece when no crate keeps parity | Parity is the contract; the reason is recorded instead |
| Publishing wheels | Separate release decision |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
|---|---|---|---|
| Verus version | Weekly release `0.2026.10.26.d17fbd0`, pinned toolchain `1.99.1`; installed locally at `~/.local/verus` (user-approved download); CI downloads the same release for x86 Linux | Reproducible proofs | y |
| Where proofs live | A `verified` module tree in `spinagram-core` inside `verus! {}` blocks, opted in with `[package.metadata.verus] verify = true`; plain `cargo build` and the maturin wheel keep compiling (ghost code erased) | Proved code is the production code: no drift | y |
| What is proved | (1) safe-break cut points of `text::segments`: strictly increasing, in bounds, never inside a protected IPv4/CIDR range, pieces concatenate to the input; (2) the `var()` bracket scanner: returns the matching close or the end, never out of bounds, terminates; (3) `bisect_left` over a sorted slice of totally ordered keys: first index with key ≥ x; (4) the cascade key order `(level, specificity, order, index)`: the comparator is a total order and the sort result is a sorted permutation; (5) `:not` specificity: adds the component-wise maximum of its arguments without overflow under stated bounds; (6) A* neighbour stepping never indexes outside the grid | Discrete logic Verus handles well; each is on a hot or correctness-critical path | y |
| Floats in kernels | Kernels take integer or totally ordered keys; callers convert `f64` with a key that preserves Python's ordering (tested, not proved) | Keeps proofs in Verus's strong fragment | y |
| Clippy level | `[workspace.lints.clippy]` `all` deny + `pedantic` warn, CI `-D warnings`; any exception is `#[expect(lint, reason = "...")]` at the item | Explicit, reviewable exceptions | y |
| cargo-deny policy | `rust/deny.toml`: advisories deny vulnerabilities and unsound, warn unmaintained; licenses allow MIT, Apache-2.0, Apache-2.0 WITH LLVM-exception, BSD-2/3-Clause, ISC, Zlib, Unicode-3.0, Unicode-DFS-2016, MPL-2.0, BSL-1.0, CC0-1.0; bans: multiple versions warn; sources: crates.io only | Permissive licences; reproducible sources | y |
| Crates-first audit output | `rust/DEPENDENCIES.md`: one row per hand-written component with candidates tried, result (replaced / kept) and evidence (parity numbers or the failing case) | Reviewable record of the directive | y |
| Wheel/CI toolchain | Production builds stay on stable Rust; only verification uses the pinned `1.99.1` | Verus pins its own toolchain | y |

**Open questions:** none.

---

## User Stories

### P1: Crates over hand-written code ⭐ MVP

**Acceptance Criteria**:

1. The repository SHALL contain `rust/DEPENDENCIES.md` with one row per hand-written component in `rust/spinagram-core/src` (at least: A* search, `_simplify`, Python float formatting, HTML escaping, compensated sum, text wrapping and token breaking, `var()` substitution, cascade sort, SVG writer, scene schema), each naming the crates evaluated and the outcome. <!-- ubiquitous --> (DEP-01)
2. WHEN a crate reproduces a component with every parity harness still at 100 % THEN the hand-written code SHALL be replaced by the crate. <!-- event --> (DEP-02)
3. IF a candidate crate changes any parity result THEN the component SHALL stay hand-written and its `DEPENDENCIES.md` row SHALL cite the first differing case. <!-- unwanted --> (DEP-03)

### P1: Lint and supply-chain policy ⭐ MVP

1. WHEN `cargo clippy --workspace --all-targets -- -D warnings` runs with the workspace lint table (`all` deny, `pedantic` warn) THEN it SHALL exit 0. <!-- event --> (LINT-01)
2. The Rust sources SHALL use `#[expect(..., reason = "...")]` for every lint exception, and SHALL contain no `#[allow(clippy::...)]`. <!-- ubiquitous --> (LINT-02)
3. WHEN `cargo deny check` runs in `rust/` THEN advisories, bans, licenses and sources SHALL all pass with `rust/deny.toml`. <!-- event --> (DENY-01)
4. WHEN CI's `rust` job runs THEN it SHALL run the clippy command of LINT-01 and `cargo deny check`. <!-- event --> (DENY-02)

### P1: Verus proofs of the core's kernels ⭐ MVP

1. WHEN `cargo verus verify -p spinagram-core` runs with the pinned Verus release THEN it SHALL report 0 errors. <!-- event --> (VER-01)
2. The verified `segments` cut function SHALL carry an `ensures` that the cuts are strictly increasing, within `0..=len`, outside every protected range, and that the pieces concatenate to the input. <!-- ubiquitous --> (VER-02)
3. The verified bracket scanner SHALL carry an `ensures` that its result is in bounds and is either the index after the matching `)` (depth back to 0) or the input length, with a `decreases` clause proving termination. <!-- ubiquitous --> (VER-03)
4. The verified `bisect_left` SHALL carry an `ensures` that every key before the result is `< x` and every key from it on is `≥ x`, given a sorted input. <!-- ubiquitous --> (VER-04)
5. The verified cascade comparator SHALL be proved reflexive, antisymmetric, transitive and total, and the verified sort SHALL be proved to return a sorted permutation of its input. <!-- ubiquitous --> (VER-05)
6. WHERE spinagram's own code computes selector specificity (not the `selectors` crate), the verified `:not` specificity SHALL carry an `ensures` that the result equals the base plus the component-wise maximum over its arguments, with no overflow for components below 2^16; WHERE the crate computes it, `DEPENDENCIES.md` SHALL say so and the row SHALL be N/A. <!-- optional-feature --> (VER-06)
7. The verified A* neighbour step SHALL carry an `ensures` that every produced index lies within the grid. <!-- ubiquitous --> (VER-07)
8. The production code paths (text breaking, `var()` substitution, routing grid lookup, cascade sort, specificity) SHALL call the verified functions, and every parity harness SHALL stay at 100 %. <!-- ubiquitous --> (VER-08)
9. WHEN `cargo build --workspace` and the maturin wheel build run on stable Rust THEN they SHALL succeed with the Verus annotations present. <!-- event --> (VER-09)
10. WHEN CI runs THEN a `verus` job SHALL download Verus `0.2026.10.26.d17fbd0` for x86 Linux, install its pinned toolchain, and run the command of VER-01. <!-- event --> (VER-10)
11. IF a proof obligation is weakened to make verification pass (`assume`, `admit`, `#[verifier::external_body]` on a kernel in scope) THEN the review SHALL reject it; the verified module SHALL contain none of these. <!-- unwanted --> (VER-11)

---

## Edge Cases

- WHEN a token has no break character THEN the cut list is empty and the piece is the whole token (VER-02).
- WHEN `var(` has no closing `)` THEN the scanner returns the input length (VER-03).
- WHEN the key slice is empty THEN `bisect_left` returns 0 (VER-04).
- WHEN two cascade keys are equal THEN the sort keeps their input order (stable, VER-05).

## Implicit-requirement dimensions

| Dimension | Coverage |
|---|---|
| Input validation & bounds | VER-02/03/04/07 bounds proofs; VER-06 overflow bound |
| Failure / partial-failure states | DEP-03 (crate rejected), VER-11 (no weakened proofs) |
| Idempotency / retry | N/A because tooling and proofs are deterministic |
| Auth boundaries & rate limits | N/A because this is a local library |
| Concurrency / ordering | VER-05 (cascade order total and stable) |
| Data lifecycle / expiry | N/A |
| Observability | CI jobs report clippy, deny and Verus results (DENY-02, VER-10) |
| External-dependency failure | DENY-01 (advisories, sources); VER-09 (production build independent of Verus) |
| State-transition integrity | N/A |

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
|---|---|---|---|
| DEP-01 | P1: crates | In Tasks | Implementing |
| DEP-02 | P1: crates | In Tasks | Implementing |
| DEP-03 | P1: crates | In Tasks | Implementing |
| LINT-01 | P1: policy | In Tasks | Implementing |
| LINT-02 | P1: policy | In Tasks | Implementing |
| DENY-01 | P1: policy | In Tasks | Implementing |
| DENY-02 | P1: policy | In Tasks | Implementing |
| VER-01 | P1: Verus | In Tasks | Implementing |
| VER-02 | P1: Verus | In Tasks | Implementing |
| VER-03 | P1: Verus | In Tasks | Implementing |
| VER-04 | P1: Verus | In Tasks | Implementing |
| VER-05 | P1: Verus | In Tasks | Implementing |
| VER-06 | P1: Verus | In Tasks | Implementing |
| VER-07 | P1: Verus | In Tasks | Implementing |
| VER-08 | P1: Verus | In Tasks | Implementing |
| VER-09 | P1: Verus | In Tasks | Implementing |
| VER-10 | P1: Verus | In Tasks | Implementing |
| VER-11 | P1: Verus | In Tasks | Implementing |

**Coverage:** 18 total, 18 mapped to tasks, 0 unmapped.

## Success Criteria

- [ ] `cargo clippy` (pedantic) and `cargo deny check` clean; Verus 0 errors; all parity harnesses 100 %; suite green in both modes.
- [ ] `DEPENDENCIES.md` lists every hand-written component with a decision and evidence.

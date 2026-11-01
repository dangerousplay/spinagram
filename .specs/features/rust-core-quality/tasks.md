# Rust core quality Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Spec**: `.specs/features/rust-core-quality/spec.md`
**Design**: spec Assumptions table. Verus: `~/.local/verus/{verus,cargo-verus}` (add to `PATH`), toolchain `1.99.1-aarch64-apple-darwin` installed. Guide: https://verus-lang.github.io/verus/guide/cargo_verus.html
**Status**: In Progress

---

## Test Coverage Matrix

> Guidelines: `.specs/LESSONS.md` (L-001, L-014, L-020, L-075). Verus proofs count as the test layer for kernels; parity harnesses are the regression net for every swap.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Verified kernels | proof (Verus) + unit (Rust) | each `ensures` of VER-02..07 proved; Rust unit tests for the edge cases listed in the spec | `rust/spinagram-core/src/verified/*.rs` | `PATH=$HOME/.local/verus:$PATH cargo verus verify -p spinagram-core` and `cargo test -p spinagram-core` |
| Crate swaps | integration (parity) | every parity harness 100 % | `rust/bench/*` | each harness |
| Config (lints, deny, CI) | none | build gate | `rust/Cargo.toml`, `rust/deny.toml`, `.github/workflows/ci.yml` | gate commands |

## Gate Check Commands

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Rust | Rust changes | `cd rust && cargo test && cargo clippy --workspace --all-targets -- -D warnings && cargo deny check` |
| Verus | Verified modules | `cd rust && PATH=$HOME/.local/verus:$PATH cargo verus verify -p spinagram-core` |
| Wheel | Before Python tests using the core | as in earlier features; confirm `import spinagram_core` works |
| Parity | Any swap or wiring | `route_parity.py`, `parity.py`, `svg_png_parity.py`, `css_parity.py` all exit 0 |
| Build | Phase ends | Rust + Verus (from Phase 3) + Wheel + ruff + pytest in both modes + Parity |

Baseline before T1: **2792 passed, 3 skipped, 1 deselected** in both modes; cargo test 139 passed. Always `--no-sync`; confirm `import spinagram_core` before trusting a Rust-mode run.

---

## Execution Plan

### Phase 1: Lint and supply-chain policy

```
T1 → T2 → T3
```

### Phase 2: Crates over hand-written code

```
T4 → T5
```

### Phase 3: Verus proofs

```
T6 → T7 → T8 → T9 → T10 → T11 → T12 → T13
```

---

## Task Breakdown

### T1: Workspace clippy policy

**What**: `[workspace.lints.clippy]` with `all = { level = "deny", priority = -1 }` and `pedantic = { level = "warn", priority = -1 }`, members inherit with `[lints] workspace = true`; fix findings or add item-level `#[expect(lint, reason = "...")]`; replace every `#[allow(clippy::...)]` with `#[expect]`.
**Where**: `rust/Cargo.toml` (+ fixes in `rust/*/src`)
**Depends on**: None
**Requirement**: LINT-01, LINT-02

**Done when**:

- [x] `cargo clippy --workspace --all-targets -- -D warnings` exits 0 (LINT-01)
- [x] `grep -rn "allow(clippy" rust/*/src` is empty (LINT-02)
- [x] Parity harnesses 100 %; Rust gate passes

**Tests**: none (config + mechanical fixes; parity is the net)
**Gate**: build
**Commit**: `build(rust): enforce clippy pedantic across the workspace`

---

### T2: cargo-deny policy

**What**: `rust/deny.toml` per the spec policy; fix or justify findings (a skip entry needs a comment with the reason).
**Where**: `rust/deny.toml`
**Depends on**: T1
**Requirement**: DENY-01

**Done when**:

- [x] `cargo deny check` exits 0 for advisories, bans, licenses, sources (DENY-01)
- [x] Rust gate passes

**Tests**: none
**Gate**: rust
**Commit**: `build(rust): add cargo-deny policy`

---

### T3: Policy in CI

**What**: CI `rust` job runs the LINT-01 clippy command and `cargo deny check` (EmbarkStudios/cargo-deny-action or the installed binary).
**Where**: `.github/workflows/ci.yml`
**Depends on**: T2
**Requirement**: DENY-02

**Done when**:

- [x] Workflow parses; both steps present; other jobs unchanged (DENY-02)
- [x] Build gate passes

**Tests**: none
**Gate**: build
**Commit**: `ci: run clippy pedantic and cargo-deny`

---

### T4: Crates-first audit

**What**: Evaluate crates for each hand-written component (spec DEP-01 list, plus anything else hand-written you find) by trying them against the parity harnesses; write `rust/DEPENDENCIES.md` with candidates, outcome and evidence. Candidates to try at least: `pathfinding` (A*), `html-escape` / `v_htmlescape` (escaping), `textwrap` first-fit with custom widths (wrapping), `itertools` / std sort (cascade sort), `fsum`-style crates (compensated sum).
**Where**: `rust/DEPENDENCIES.md`
**Depends on**: None (Phase 1 complete)
**Requirement**: DEP-01, DEP-03

**Done when**:

- [x] Every row names candidates and either "replace" (with parity evidence) or "keep" (with the first differing case) (DEP-01, DEP-03)
- [x] Rejected experiments are discarded (scratch only)

**Tests**: none (evaluation document)
**Gate**: rust
**Commit**: `docs(rust): record the crates-first audit`

---

### T5: Replace hand-written components with crates

**What**: Apply every "replace" decision from T4, one component at a time inside this task; new deps pass cargo-deny.
**Where**: `rust/spinagram-core/src` (files named in the T4 replace rows)
**Depends on**: T4
**Requirement**: DEP-02

**Done when**:

- [x] Each replaced component uses the crate; hand-written code removed (DEP-02)
- [x] All parity harnesses 100 %; Build gate passes

**Tests**: integration (parity)
**Gate**: build
**Commit**: `refactor(rust): use crates for <components>` (name them)

---

### T6: Set up Verus verification in the core

**What**: `vstd` dependency, `[package.metadata.verus] verify = true`, workspace `unexpected_cfgs` check-cfg for `verus_only`, `src/verified/mod.rs` with `use vstd::prelude::*;`; prove nothing yet beyond a trivial lemma.
**Where**: `rust/spinagram-core/Cargo.toml` (+ `src/verified/mod.rs`, workspace lints)
**Depends on**: None (Phase 2 complete)
**Requirement**: VER-01, VER-09

**Done when**:

- [x] `cargo verus verify -p spinagram-core` → 0 errors (VER-01)
- [x] `cargo build --workspace` on stable and the maturin wheel build succeed; `import spinagram_core` works (VER-09)
- [x] `cargo deny check` still passes with `vstd`

**Tests**: proof (Verus)
**Gate**: build
**Commit**: `build(rust): verify spinagram-core with verus`

---

### T7: Prove the safe-break cut points

**What**: Verified `cuts(token_bytes, break_mask, protected) -> Vec<usize>` with the VER-02 `ensures`; `text::segments` calls it.
**Where**: `rust/spinagram-core/src/verified/segments.rs`
**Depends on**: T6
**Requirement**: VER-02, VER-08

**Done when**:

- [x] Verus proves VER-02's postconditions; no `assume`/`admit`/`external_body` (VER-11)
- [x] Rust unit test: token without break chars → no cuts (edge case)
- [x] `parity.py` 40512/40512; Verus + Rust gates pass

**Tests**: proof + unit
**Gate**: verus
**Commit**: `feat(rust): prove text break points with verus`

---

### T8: Prove the var() bracket scanner

**What**: Verified scanner used by `var()` substitution with the VER-03 `ensures` and `decreases`.
**Where**: `rust/spinagram-core/src/verified/brackets.rs`
**Depends on**: T7
**Requirement**: VER-03, VER-08

**Done when**:

- [x] Verus proves VER-03; unclosed `var(` returns the length (edge case unit test)
- [x] `css_parity.py` 100 %; gates pass

**Tests**: proof + unit
**Gate**: verus
**Commit**: `feat(rust): prove the var() bracket scanner with verus`

---

### T9: Prove bisect_left and use it in the router grid

**What**: Verified `bisect_left` over a sorted slice of totally ordered integer keys (VER-04); the router converts grid coordinates to order-preserving keys (tested against `f64::total_cmp` and Python `bisect_left`) and calls it.
**Where**: `rust/spinagram-core/src/verified/bisect.rs`
**Depends on**: T8
**Requirement**: VER-04, VER-08

**Done when**:

- [ ] Verus proves VER-04; empty slice → 0 (edge case unit test)
- [ ] Unit test: the key conversion preserves order for negative, zero, positive and equal values
- [ ] `route_parity.py` 100 %; gates pass

**Tests**: proof + unit
**Gate**: verus
**Commit**: `feat(rust): prove bisect_left and use it in routing`

---

### T10: Prove the cascade order

**What**: Verified comparator over `(level, a, b, c, order, index)` integer keys (total order, VER-05) and a verified stable sort returning a sorted permutation; `css::cascade` uses them.
**Where**: `rust/spinagram-core/src/verified/cascade.rs`
**Depends on**: T9
**Requirement**: VER-05, VER-08

**Done when**:

- [ ] Verus proves comparator properties and sorted-permutation + stability (equal keys keep input order, edge case)
- [ ] `css_parity.py` 100 %; gates pass

**Tests**: proof + unit
**Gate**: verus
**Commit**: `feat(rust): prove the css cascade order with verus`

---

### T11: Prove :not specificity (or record N/A)

**What**: If spinagram code computes specificity, verified `not_specificity` (VER-06) used by `css`; if the `selectors` crate computes it, record N/A in `DEPENDENCIES.md` with where the crate does it.
**Where**: `rust/spinagram-core/src/verified/specificity.rs` (or `rust/DEPENDENCIES.md`)
**Depends on**: T10
**Requirement**: VER-06, VER-08

**Done when**:

- [ ] Proof of VER-06 with the overflow bound, wired, `css_parity.py` 100 %; or the N/A row with the crate's code location (VER-06)
- [ ] Gates pass

**Tests**: proof + unit (or none for N/A)
**Gate**: verus
**Commit**: `feat(rust): prove :not specificity with verus` or `docs(rust): note specificity comes from the selectors crate`

---

### T12: Prove A* neighbour bounds

**What**: Verified neighbour step returning only in-grid `(i, j)` (VER-07); the router's search loop uses it.
**Where**: `rust/spinagram-core/src/verified/grid.rs`
**Depends on**: T11
**Requirement**: VER-07, VER-08

**Done when**:

- [ ] Verus proves VER-07; `route_parity.py` 100 %; Build gate passes (all harnesses, both suite modes)

**Tests**: proof + unit
**Gate**: build
**Commit**: `feat(rust): prove router grid bounds with verus`

---

### T13: Verus in CI and docs

**What**: CI `verus` job (ubuntu): download `verus-0.2026.10.26.d17fbd0-x86-linux.zip`, install the pinned toolchain with rustup, add to PATH, run `cargo verus verify -p spinagram-core`; `rust/README.md` documents clippy, deny, Verus (local setup, what is proved, what is not and why).
**Where**: `.github/workflows/ci.yml` (+ `rust/README.md`)
**Depends on**: T12
**Requirement**: VER-10, VER-11

**Done when**:

- [ ] Workflow parses; `verus` job present; other jobs unchanged (VER-10)
- [ ] `grep -rnE "assume\(|admit\(|external_body" rust/spinagram-core/src/verified` is empty (VER-11)
- [ ] Build gate passes

**Tests**: none
**Gate**: build
**Commit**: `ci: verify the rust core with verus`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3

Phase 1:  T1 → T2 → T3
Phase 2:  T4 → T5
Phase 3:  T6 → T7 → T8 → T9 → T10 → T11 → T12 → T13
```

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | start of Phase 1 | ✅ |
| T2 | T1 | T1 → T2 | ✅ |
| T3 | T2 | T2 → T3 | ✅ |
| T4 | None (Phase 1 complete) | start of Phase 2 | ✅ |
| T5 | T4 | T4 → T5 | ✅ |
| T6 | None (Phase 2 complete) | start of Phase 3 | ✅ |
| T7 | T6 | T6 → T7 | ✅ |
| T8 | T7 | T7 → T8 | ✅ |
| T9 | T8 | T8 → T9 | ✅ |
| T10 | T9 | T9 → T10 | ✅ |
| T11 | T10 | T10 → T11 | ✅ |
| T12 | T11 | T11 → T12 | ✅ |
| T13 | T12 | T12 → T13 | ✅ |

## Test Co-location Validation

| Task | Code Layer | Matrix Requires | Task Says | Status |
| ---- | ---------- | --------------- | --------- | ------ |
| T1–T3 | config | none | none | ✅ |
| T4 | doc | none | none | ✅ |
| T5 | crate swaps | integration (parity) | integration | ✅ |
| T6 | verified setup | proof | proof | ✅ |
| T7–T12 | verified kernels | proof + unit | proof + unit | ✅ |
| T13 | CI + docs | none | none | ✅ |

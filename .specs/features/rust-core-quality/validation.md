**Verdict: PASS** (iteration 1: 18/18 ACs traced, Verus 22 verified / 0 errors re-run from a clean build, 6/6 mutants killed including 2 proof mutants Verus rejected, gates green; one item, the CI `verus` job, can only be confirmed on its first CI run)

# Validation: rust-core-quality - PASS (iteration 1)

**Date**: 2026-11-01
**Spec**: `.specs/features/rust-core-quality/spec.md`
**Diff range**: `a0eab07..667d214` (T1 `1750a7d` … T13 `667d214`)
**Verifier**: the orchestrator, fresh pass (author: the implementation sub-agent; one sub-agent cap).

## Spec-Anchored Acceptance Criteria

| ID | Spec-defined outcome | Evidence | Result |
|---|---|---|---|
| DEP-01 | one row per hand-written component | `rust/DEPENDENCIES.md`: 14 rows (A*, `_simplify`, pyfmt, escaping, sum, wrapping, token breaking, `var()`, cascade sort, SVG writer, scene schema, selectors/specificity, PNG, glyph advances) | ✅ |
| DEP-02 | replace when parity holds | `html-escape` (0/3007 differ) and `compensated-summation` (0/20,000 differ vs CPython 3.13) adopted in T5 `63a80fb`; parity harnesses 100 % | ✅ |
| DEP-03 | keep + first differing case | `pathfinding` A* (recorded call 14; 2270/2500 random), `sprintf` (1928/100,017 `.1f`), `ab_glyph` (1977/2000 widths); construction reasons for `textwrap`, `var()`, SVG writer, `geo` simplify | ✅ |
| LINT-01 | clippy pedantic `-D warnings` exit 0 | Verifier re-run: clean | ✅ |
| LINT-02 | only `#[expect(…, reason)]` | `grep -rn "allow(clippy" rust/*/src` → 0 | ✅ |
| DENY-01 | deny check passes | Verifier re-run: advisories, bans, licenses, sources ok (duplicate-version warnings only) | ✅ |
| DENY-02 | CI runs clippy + deny | `.github/workflows/ci.yml` `rust` job | ✅ |
| VER-01 | 0 errors | Verifier: `cargo clean -p spinagram-core` then `cargo verus verify -p spinagram-core` → **22 verified, 0 errors** | ✅ |
| VER-02 | cuts increasing, in bounds, unprotected, pieces cover input | `verified/segments.rs` `cuts` ensures: every output `is_cut` (0 < p < len, marked, not strictly inside a protected range), strictly increasing, and complete (every valid cut present); `bounds` ensures contiguous pieces from 0 to len, non-empty when len > 0 | ✅ |
| VER-03 | scanner in bounds, matching close or end, terminates | `verified/brackets.rs` `scan_close`: `from <= out <= len`, depth > 0 before `out`, `out == len` or depth back to 0; `decreases` in the loop. Precondition `len < usize::MAX - 1` (any `Vec`), not a weakened `ensures` | ✅ |
| VER-04 | bisect_left contract | `verified/bisect.rs`: sorted input ⇒ keys before `r` are `< x`, from `r` on `≥ x`. `order_key` (f64 → u64) tested against `partial_cmp`, `total_cmp` and Python `bisect_left`, incl. ±0 | ✅ |
| VER-05 | comparator total order; stable sorted permutation | `verified/cascade.rs`: `lemma_reflexive`, `lemma_antisymmetric`, `lemma_transitive`, `lemma_total`; `stable_order` ensures length, in-range, distinct indices, `stably_sorted` (ordered, equal keys keep input order) | ✅ |
| VER-06 | proof or N/A | N/A: `selectors` computes specificity (`builder.rs:380`, `:428-448`, `std::cmp::max` at `:444`; `parser.rs:882`), recorded in `DEPENDENCIES.md` | ✅ |
| VER-07 | neighbour in grid | `verified/grid.rs` `neighbour`: `Some` ⇒ in grid and equals `(i+di, j+dj)`; `None` exactly when the step leaves the grid | ✅ |
| VER-08 | production calls kernels; parity 100 % | `text.rs:177-178` (`cuts`, `bounds`), `css.rs:401` (`scan_close`), `css.rs:440-452` (`Key`, `stable_order`), `route.rs:10-11` (`lower_bound`, `neighbour`). Verifier parity: text 40512/40512, route 57/57 + 2500/2500, CSS 48/48 + 1200/1200, SVG 48/48 × 3 font modes | ✅ |
| VER-09 | stable build + wheel with annotations | maturin release wheel built and imported (Verifier); `cargo build --workspace` needs `rust/.cargo/config.toml` `dynamic_lookup` on macOS (a pre-existing PyO3 link issue, fixed in T6) | ✅ |
| VER-10 | CI verus job | `.github/workflows/ci.yml` `verus` job: downloads `verus-0.2026.10.26.d17fbd0-x86-linux.zip`, installs the pinned toolchain, locates `cargo-verus` with `find`, runs VER-01. YAML parses and the release URL answers 200; the job itself has not run (Linux zip layout unverified, not downloaded) | ⚠️ confirm on first CI run |
| VER-11 | no assume/admit/external_body | `grep -rnE "assume\|admit\|external\|trusted\|verifier::\|unsafe\|exec_allows\|nonlinear" rust/spinagram-core/src/verified/` (comments excluded) → nothing | ✅ |

## Discrimination Sensor

Scratch worktree at `667d214`; separate target dirs; real-tree porcelain unchanged.

| # | Mutation | Result |
|---|---|---|
| V1 | `cascade.rs` spec `kle`: `x.index <= y.index` → `<` (breaks reflexivity) | ✅ Verus rejects: 19 verified, 3 errors |
| V2 | `segments.rs` spec `is_cut`: `p < len` → `p <= len` | ✅ Verus rejects: 21 verified, 1 error |
| W1 | `text.rs`: call `cuts` with no protected ranges | ✅ cargo test 1 failure |
| W2 | `css.rs`: identity order instead of `stable_order` | ✅ cargo test 4 failures |
| — | Author's checks: `parity.py`, `route_parity.py`, `css_parity.py`, `svg_png_parity.py` exit 1 under their scratch faults (earlier features) | ✅ |

**Outcome**: 4/4 Verifier mutants killed (2 by Verus itself).

## Gate Check

- cargo test **159 passed** (was 139); clippy pedantic clean; `cargo deny check` ok; ruff clean.
- pytest **2792 passed, 3 skipped, 1 deselected** pure Python and with `SPINAGRAM_RUST=1` (`import spinagram_core` confirmed).
- Verus **22 verified, 0 errors** from a clean build.

## Notes

- Latent panic fixed in T8: `substitute` panicked when nothing followed `var(`; now returns an empty inner string as Python does (test with Python-derived values).
- `stable_order` is an insertion sort (quadratic); fine for per-element declaration lists, which are short.
- Trigger warnings from Verus (automatic trigger selection) are informational; `--triggers-mode silent` hides them.

## Requirement Traceability Update

| Requirement | Previous | New |
|---|---|---|
| DEP-01 … DEP-03, LINT-01, LINT-02, DENY-01, DENY-02, VER-01 … VER-09, VER-11 | Implementing | ✅ Verified |
| VER-10 | Implementing | ✅ Verified (configuration); runtime confirmation pending the first CI run |

## Summary

**Overall**: ✅ Ready. Crates-first applied with evidence, clippy pedantic and cargo-deny clean, five Verus-proved kernels on production paths, parity 100 % everywhere.

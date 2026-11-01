**Verdict: PASS** (iteration 1: 11/11 ACs traced to spec outcomes, 5/5 mutants killed, gates green; one recorded SPEC_DEVIATION on CSS-02 with identical output through the Python fallback)

# Validation: rust-core-css - PASS (iteration 1)

**Date**: 2026-11-01
**Spec**: `.specs/features/rust-core-css/spec.md`
**Diff range**: `af4d204..785faf7` (T1 `502bfb1`, T2 `dce4616`, crate replacement `eefd47c`, T3 `f52d7bb`, T4 `a8fbf33`, T5 `4e0a230`, T6 `a275b06`, T7 `9f35f36`, T8 `785faf7`)
**Verifier**: the orchestrator, fresh pass (author: the implementation sub-agent; one sub-agent cap).

## Task Completion

All 8 tasks done. `eefd47c` replaces the hand-written tokenizer/parser/matcher of T1–T2 with `cssparser` 0.38 + `selectors` 0.41 (MPL-2.0) and ~150 lines of glue, per the user's crates-first directive. Still hand-written, with recorded reasons: cascade sort and `var()` substitution.

## Spec-Anchored Acceptance Criteria

| ID | Spec-defined outcome | Evidence | Result |
|---|---|---|---|
| CSS-01 | compute values, warnings, trace equal | `tests/test_rust_css.py:125` `test_compute_equal_across_modes` (parametrized sheets, inline); `:132` dispatch; `:142` every example (`compute`/`inspect`); `css_parity.py` 48/48 + 1200/1200 | ✅ |
| CSS-02 | Rust parse structure + specificity = Python | `css.rs` tests `parse_*` (38 selectors incl. `parse_not_specificity_max`, `parse_pe_*`) with Python-derived canonical forms | ✅ with SPEC_DEVIATION: `> a`, `a >`, `[w=100px]` rejected by the crate → Python path (`css.rs:8-11`; `css.rs` `fallback_*` tests; `tests/test_rust_css.py:73`) |
| CSS-03 | match sets equal per feature | `css.rs` `match_*` (42 incl. kinds, attrs quoted/unquoted, `:root`, `:not` nested, lone root); `tests/test_rust_css.py:53` (binding vs Python), `:61` lone root | ✅ |
| CSS-04 | cascade order (important, specificity, order, index; inline 1/3) | `css.rs` `cascade_levels_normal_inline_important`, `cascade_specificity_then_order_then_index`, `cascade_important_beats_specificity`, `cascade_selector_list_duplicates_and_ties` | ✅ |
| CSS-05 | `var()` = `_substitute` | `css.rs` `cascade_var_nested_and_inherited`, `cascade_var_fallbacks`, `cascade_var_eight_levels`, `cascade_var_nine_levels`, `cascade_var_unclosed`, `cascade_var_pseudo_scope`, `cascade_var_inline_uses_css_scope` | ✅ |
| CSS-06 | select keys + order equal | `tests/test_rust_css.py:199`, dispatch `:207` | ✅ |
| CSS-07 | inspect equal incl. unused | `tests/test_rust_css.py:219`, `:142` (inspect over every example) | ✅ |
| CSS-08 | inactive unchanged | `tests/test_rust_css.py:151`, `:160` (unstyled), `:214` | ✅ |
| CSS-09 | same CssValueError | `tests/test_rust_css.py:171`; parity: 72 random pairs raise identically | ✅ |
| PAR-21 | harness, ≥1000 random, timing, exit codes | `css_parity.py`: 48/48, 1200/1200, exit 0 (re-run by Verifier); exit 1 under a scratch fault (author) | ✅ |
| PAR-22 | CI runs it | `.github/workflows/ci.yml` `rust` job | ✅ |

## Discrimination Sensor

Scratch worktree at `785faf7`; real tree porcelain unchanged.

| # | Mutation | Killed? |
|---|---|---|
| P1 | `css.py` `_rust_cascade`: re-raise instead of falling back | ✅ 2 failures |
| P2 | `css.py` `_rust_matches`: never ask the core | ✅ |
| R1 | `css.rs` `var()` passes 8 → 9 | ✅ `cascade_var_nine_levels` |
| R2 | `css.rs` next sibling off by one | ✅ |
| R3 | `css.rs` no previous sibling | ✅ 2 failures |

**Outcome**: 5/5 killed.

## Gate Check

- cargo test **139 passed**; clippy `-D warnings` clean; ruff clean; `import spinagram_core` confirmed with the core active.
- pytest **2792 passed, 3 skipped, 1 deselected** pure Python and with `SPINAGRAM_RUST=1` (was 2709; +83).
- `render_all.sh` byte-identical in all three font modes, both modes (author, every Build gate).

## Speed (Verifier re-run, 561 elements / 200 rules)

| Work | Python | Rust | Speed-up |
|---|---|---|---|
| matching + cascade (incl. JSON build) | 96 ms | 13.5 ms | 7.1x (goal 5x) |
| `compute()` end to end | 193 ms | 83.8 ms | 2.3x (typing, warnings, trace stay Python) |

## Requirement Traceability Update

| Requirement | Previous | New |
|---|---|---|
| CSS-01 … CSS-09, PAR-21, PAR-22 | Implementing | ✅ Verified |

## Summary

**Overall**: ✅ Ready. Crates-first applied (`cssparser`, `selectors`); output identical; 7.1x on matching + cascade.

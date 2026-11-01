**Verdict: FAIL** (iteration 1: 21/21 ACs traced and gates green on Python 3.13; one defect: Rust always uses Python 3.12+ compensated `sum()`, so SVG-01 byte identity is not guaranteed on Python 3.11, which the project supports)

# Validation: rust-core-svg-png (iteration 1)

**Date**: 2026-11-01
**Spec**: `.specs/features/rust-core-svg-png/spec.md`
**Diff range**: `2f49076..50168d5` (T1 `c5cb833` … T12 `50168d5`, plus `e82fe47` clippy follow-up for T2)
**Verifier**: the orchestrator, fresh pass over spec + diff (author: the implementation sub-agent). One sub-agent cap, so the Verifier role ran in the main session.

## Task Completion

All 12 tasks done (commits above). Follow-up `e82fe47` fixes a clippy lint left by T2's commit; acceptable, recorded here.

## Spec-Anchored Acceptance Criteria

| ID | Spec-defined outcome | Evidence (`file:line` / test) | Result |
|---|---|---|---|
| SCN-01 | version 1 + every field, 6 item tags | `tests/test_scene_json.py:45` `test_version_is_1`; `:50` `test_item_type_tags` (6 params); `:93-117` one test per scene field (L-014) | ✅ |
| SCN-02 | Rust round-trip equal | `tests/test_scene_json.py:137` (48 scenes); `scene.rs` `every_item_type_round_trips_to_an_equal_value` | ✅ |
| SCN-03 | committed schema fresh | `scene.rs` `committed_schema_is_fresh` | ✅ |
| SCN-04 | every example validates | `tests/test_scene_json.py:143`, `:153` | ✅ |
| SCN-05 | version error names found + supported | `scene.rs` `other_versions_are_rejected_naming_both`; `tests/test_scene_json.py:158` | ✅ |
| SVG-01 | byte identity, 3 font modes | `tests/test_rust_svg.py:70` (48 scenes × 3 modes), `:79` (scene with real font files × 3 modes); harness 48/48 per mode (re-run by Verifier) | ⚠️ holds on 3.13; see Fix 1 for 3.11 |
| SVG-02 | `.1f` / `g` = Python | `pyfmt.rs` `f1_matches_python`, `g_matches_python`, `g_more_python_values`; expected strings re-checked against Python 3 by the Verifier | ✅ |
| SVG-03 | `html.escape` both modes | `pyfmt.rs` `esc_matches_html_escape_without_quotes`, `attr_matches_html_escape_with_quotes` | ✅ |
| SVG-04 | same data URI | `svg.rs` `image_png_and_icon_svg`; missing file `tests/test_rust_svg.py:109`, `svg.rs` `missing_image_names_the_path` | ✅ |
| SVG-05 | marker/filter ids + order | `svg.rs` `connectors_markers` (all 6 marker kinds, exact defs string), `shape_shadows_dedupe` | ✅ |
| SVG-06 | same tooltips | `svg.rs` `shape_diamond_with_tip`; `tests/test_rust_svg.py:79` scene with facts | ✅ |
| SVG-07 | inactive unchanged | `tests/test_rust_svg.py:88`; `render_all.sh` pure Python == baseline | ✅ |
| SVG-08 | chars per face equal | `tests/test_rust_svg.py:100`; `svg.rs` `text_runs_fallback_and_empty` | ✅ |
| PNG-01 | resvg, no Playwright import | `tests/test_rust_png.py:29`, `:38` (`no_playwright` fixture) | ✅ |
| PNG-02 | `SPINAGRAM_PNG=chromium` → Playwright | `tests/test_rust_png.py:53`, `:62` | ✅ |
| PNG-03 | `round(W*s)` × `round(H*s)` | `tests/test_rust_png.py:46` (parametrized); `png.rs` `scale_gives_rounded_pixel_size`, `size_rounds_halves_to_even_like_python` | ✅ |
| PNG-04 | theme font file used | `png.rs` `text_is_drawn_with_the_given_font_file` (pixels differ by font file) | ✅ |
| PNG-05 | mean ≤ 8, >64 share ≤ 2 % | harness: worst mean 1.00, worst share 0.39 % over 48 scenes (re-run by Verifier) | ✅ |
| PNG-06 | old RuntimeError without core | `tests/test_rust_png.py:70` | ✅ |
| PAR-11 | harness reports + exit codes | `rust/bench/svg_png_parity.py` exit 0; exit 1 under a `pyfmt.rs` fault (author's check) | ✅ |
| PAR-12 | CI runs SVG parity + schema test | `.github/workflows/ci.yml` `rust` job (`--svg-only`; schema via `cargo test`) | ✅ |

## Discrimination Sensor

Scratch worktree at `50168d5`, separate `CARGO_TARGET_DIR`; real tree porcelain unchanged.

| # | Mutation | Killed? |
|---|---|---|
| P1 | `scene_json`: drop `meta_tooltips` | ✅ 4 failures |
| P2 | `png.py`: ignore `SPINAGRAM_PNG=chromium` | ✅ |
| P3 | `svg.py`: never dispatch to the core | ✅ |
| R1 | `scene.rs`: accept any version | ✅ |
| R2 | `pyfmt.rs`: `g` exponent window 6 → 7 | ✅ 2 failures |
| R3 | `svg.rs`: open-diamond fill `#FFFFFF` → `#FFF` | ✅ |
| R4 | `png.rs`: `round_ties_even` → `round` | ✅ |
| R5 | `svg.rs`: never reuse a shadow filter | ✅ |

**Result**: 8/8 killed.

## Gate Check

- cargo test 41 passed; clippy `-D warnings` clean; ruff clean.
- pytest **2707 passed, 3 skipped, 1 deselected** pure Python and with `SPINAGRAM_RUST=1` (was 2666; +41).
- Warnings 278 → 505: the new SVG/scene tests build every example scene and repeat the known "icon not found" warnings (existing hygiene item in HANDOFF). Not a defect.

## Code Quality / Deviations reviewed

| Item | Verdict |
|---|---|
| Two existing tests in `tests/test_cd_fonts.py` gained `monkeypatch.setenv("SPINAGRAM_PNG", "chromium")` | Accepted: they test the Chromium path; PNG-01 makes resvg the default with the core; no assertion changed. Surfaced to the user |
| macOS 27 linker workaround (`black_box(PyExc_KeyError)` in module init) | Accepted with risk: documented in `rust/README.md` and the T8 commit; fragile against future symbol changes; Linux unaffected |
| Rust SVG path slower end to end (40 ms vs 10 ms for 48 scenes) | Expected: JSON building dominates; value is the shared model (WASM, other languages). Documented |
| PNG 1.2x faster in total; resvg ~40 ms per 1920×1080 steady state | Meets the success criterion (faster than Chromium); no browser needed |
| `serde_json` `float_roundtrip`, `Run.base` flag for identity-based tspan logic | Correct and necessary |

## Fix Plans

### Fix 1 (Major): `sum()` semantics differ on Python 3.11

- **Root cause**: `pyfmt::py_sum` always applies Python 3.12+'s compensated summation. Python 3.11's `sum()` adds plainly. The Python writer's block/table totals (`Label.place`, table widths) then differ in the last bit on 3.11, so SVG-01 can fail for 3.11 users of the abi3 wheel. CI's `rust` job runs only 3.13.
- **Fix task F1**: pass the interpreter's behaviour into the core (e.g. `compensated = sys.version_info >= (3, 12)` in the scene JSON or as a `svg_draw` argument), and use plain left-to-right addition when false. Rust unit test for both modes (`[0.1]*10` → `1.0` compensated, `0.9999999999999999` plain), a Python test that the flag matches `sys.version_info`, and run `test_rust_svg.py` under Python 3.11 locally if available (else note it).
- **Priority**: Major

## Summary

**Overall**: ❌ Not ready (one fix)
**Spec-anchored check**: 21/21 traced; SVG-01 conditional on Python ≥ 3.12
**Sensor**: 8/8 killed
**Gate**: 2707 passed in both modes; Rust 41 passed

# Validation: Rust hardening (T1–T9)

**Result**: PASS. Two surviving mutants were closed with tests before this report. One small enum leftover was fixed.
**Verifier:** the orchestrator session. The author was a separate Sonnet sub-agent (author ≠ verifier).
**Diff range:** `610cf92..4b05246` on `refactor/rust-hardening` (9 commits, one per task), plus the verifier's own commit.
**Date:** 2026-11-02

## Gates (re-run independently)

| Gate | Result |
|---|---|
| `cargo test` (workspace) | 262 passed (261 from the author, plus 1 verifier test) |
| `cargo clippy --workspace --all-targets -- -D warnings` | clean |
| `cargo deny check` | advisories, bans, licenses and sources ok |
| `ruff check src tests examples` | clean |
| pytest, Rust core | 3220 passed, 3 skipped |
| pytest, `SPINAGRAM_RUST=0` | 3220 passed, 3 skipped |
| SVG parity (`svg_png_parity.py --svg-only`) | 49 of 49 identical in subset, embed and link |
| CSS, route and text parity scripts | pass |
| wasm `build.sh` + `bun test` (bun 1.4.2) | 24 pass |
| web `bun test` + `bun run build` (bun 1.4.2) | 246 pass, build ok |
| SVG writer speed | Rust 0.3x of Python, the same ratio as the base `610cf92` measured in a scratch worktree, so no regression |

## Per-requirement evidence

| Req | Evidence | Status |
|---|---|---|
| PAR-01 | `rust/spinagram-core/src/yaml_span.rs:57` spanned `Node`, built from saphyr-parser events | Covered |
| PAR-02 | `yaml_span.rs:193` `skip_properties`; tests `yaml_span.rs:262` and `yaml_span.rs:277` | Covered |
| PAR-03 | `yaml_span.rs:283`; edit-level test `edit.rs:1610` | Covered |
| PAR-04 | `yaml_span.rs:291` byte offset after `é` | Covered |
| LEX-01, LEX-02 | `edge_syntax.rs:345` runs `rust/schema/edge_vectors.json` (321 edges); `tests/test_edge_vectors.py` runs the same table against Python `parse_edge` (345 cases) | Covered |
| LEX-03 | `edge_syntax.rs` test `spacing_survives_a_rewrite`; the existing byte tests in `edit.rs` are unchanged | Covered |
| LEX-04 | `edge_syntax.rs` `edge_ends_split_as_the_loader_splits_them` (vector endpoints) | Covered |
| LEX-05 | `edit.rs:1593` `connect_and_reconnect_validate_their_ends` | Covered |
| LEX-06 | `css.rs:485` `split_var` on the cssparser tokenizer; nested fallbacks are checked against Python. See SPEC_DEVIATION T6 | Partial (accepted) |
| LEX-07 | `reroute.rs:196` `PathParser`; tests `reroute.rs:391`, `reroute.rs:398` and `reroute.rs:406`; the wasm goldens are unchanged | Covered |
| ENM-01, ENM-02 | `edit_values.rs:14`, `edit_values.rs:47`, `scene.rs:111`, `fit.rs:19`, `css.rs:67`, `route.rs:37`; round trips at `scene.rs:624`; schema diff adds only enum refs and descriptions | Covered |
| ENM-03 | `route.rs:23`, `fit.rs:10`, `css.rs:452`; `SNAP`/`DEFAULT_GAP` in `edit.rs` | Covered |
| ENM-04 | `edit.rs:1580` (`axis: "diagonal"` names the index and the accepted values) | Covered |
| ERR-01..04 | thiserror enums (`yaml_span.rs:38`, `css.rs:173`, `scene.rs:554`, `reroute.rs:25`, `svg.rs:57`); `tests/test_rust_edit.py:131` `.index`; wasm `rust/spinagram-wasm/tests/*.test.ts:72`; poisoned locks `font.rs:173`, `svg.rs:729` | Covered |
| SEC-01 | `svg.rs:241` `marker_key`; `src/spinagram/backends/svg.py` `_marker_key` and `_attr`; `tests/test_svg_security.py:37`, `tests/test_svg_security.py:49` and `tests/test_svg_security.py:56` (same bytes in both engines) | Covered |
| SEC-02 | `svg.rs:108` `FileAccess`; `svg.rs:937`; `tests/test_svg_security.py:62`. Python reads only paths of scenes it built; a user-given logo path is a feature of the local CLI | Covered |
| PRF-01, PRF-02 | `edit.rs:441` `Index`; the parse-count test `a_batch_parses_once_before_and_once_after_each_operation`; `edit.rs:1566` 2,000-node `move_zone` | Covered |
| API-01, API-02 | `lib.rs` (`pyfmt`, `verified` and `yaml_span` are `pub(crate)`; `missing_docs` warns, and clippy is clean) | Covered |
| BLD-01..05 | `.gitignore`; `ci.yml` `web` uploads `ui-static`, and `wheels`/`sdist` need it; `pyproject.toml` `include`; `tests/test_ui.py:641` skip; the local wheel lists `spinagram/ui/static/index.html` plus 5 assets, and the sdist lists `src/spinagram/ui/static/index.html` | Covered |

## Discrimination sensor

Mutants were run in a scratch `git worktree` at HEAD, with its own target dir. The worktrees were removed afterwards, and the real tree's porcelain matches the pre-sensor baseline.

| Mutant | Result |
|---|---|
| Edge operators tried in the order `<-` before `<->` | killed |
| `zone:` prefix branch without the fallback to a plain dst | killed |
| `$` accepts any trailing blank text after a label | **survived** → added vectors `"a -> b: x\n\n"` and `"a -> b: x\n "` (both rejected by Python) → killed |
| Anchor/tag skip removed | killed |
| Anchor flag dropped | killed |
| Marker key lets `( ) ,` through (Rust) | killed |
| FNV prime changed (Rust and Python, each) | killed |
| File roots permit everything | killed |
| One `var()` pass instead of 8 | killed |
| Duplicate id resolves to the last entry | **survived** → added `edit.rs` `a_duplicated_id_addresses_its_first_entry` (the behaviour before the refactor) → killed |
| Python marker colour not escaped | killed |
| Python text fill not escaped | killed |

The first operator-order mutant (`->` before `<->`) was equivalent: the two operators cannot start at the same character. It was replaced by the `<-` mutant above.

## Fixes made by the verifier

- `EdgeOp::arrow` and `EdgeText::arrow` returned `&'static str`, although `edit_values::Arrow` exists. They now return `Arrow`.
- Added 2 edge vectors and 1 edit test (above).

## Notes

- **`EdgeText::parse`:** it is a hand-driven backtracking search, with winnow used for the token pieces. It matches the regex exactly (vectors, plus a 12,059-string fuzz by the author). Its worst case is polynomial in the edge length, like the regex; edge strings are short.
- **Icon pack index files:** they name file paths inside the pack directory, and a hostile pack index could use `..`. That is outside this feature; it is a candidate for a pack-loader check.

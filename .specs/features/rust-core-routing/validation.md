**Verdict: FAIL** (iteration 1: 24/24 ACs traced, 1 surviving mutant (YAML-05), 1 spec-precision gap (ROUTE-07); gates green)

# Validation: rust-core-routing - FAIL (iteration 1)

**Date**: 2026-11-01
**Spec**: `.specs/features/rust-core-routing/spec.md`
**Diff range**: `fe9a98a..19f831b` (T1 `d7970d9` … T12 `19f831b`, spec amendment `6e6ccc1`)
**Verifier**: the orchestrator, fresh pass over spec + diff (author was the implementation sub-agent; author ≠ verifier).
The user capped the session at one sub-agent, so the Verifier role ran in the main session.

---

## Task Completion

| Task | Status | Notes |
|---|---|---|
| T1 `d7970d9` | ✅ Done | `rust/bench/render_all.sh`, 40 SVGs |
| T2 `a858e5d` | ✅ Done | `yamlload.parse` / `load_file` |
| T3 `df7869b` | ✅ Done | registry cache |
| T4 `011db11` | ✅ Done | theme through cache |
| T5 `9ee6323` | ✅ Done | redefined in `6e6ccc1`: spec files stay on SafeLoader (libyaml accepts `title: Why?` in a flow map) |
| T6 `4b1de12` | ✅ Done | `route.rs` |
| T7 `ba60e55` | ✅ Done | `Crossings` |
| T8 `c4dbd31` | ✅ Done | binding |
| T9 `c17bf54` | ✅ Done | dispatch |
| T10 `4806a51` | ✅ Done | `route_parity.py` |
| T11 `6ba1e73` | ✅ Done | CI `rust` job |
| T12 `19f831b` | ✅ Done | README |

---

## Spec-Anchored Acceptance Criteria

| ID | Spec-defined outcome | `file:line` + assertion | Result |
|---|---|---|---|
| YAML-01 (cl. 1) | theme/registry files parsed with `CSafeLoader` | `tests/test_yamlload.py:18` - `assert spy.call_args.kwargs["Loader"] is yaml.CSafeLoader` | ✅ |
| YAML-01 (cl. 2) | spec files keep `SafeLoader` | `tests/test_yamlload.py:105` - `all(ldr is yaml.SafeLoader for ldr in loaders)`; `:106` - `yaml.CSafeLoader not in loaders` | ✅ |
| YAML-02 | `SafeLoader` without libyaml, same data | `tests/test_yamlload.py:24` - `Loader is yaml.SafeLoader`; `:25` - `data == yaml.safe_load(SAMPLE)`; `:26` - `data["a"] is True ... data["c"] is None` | ✅ |
| YAML-03 | parsed once when unchanged | `tests/test_yamlload.py:35` - `spy.call_count == 1`; theme `:83` - `spy.call_count == 1`; icons `tests/test_icons_registry_cache.py:38` - `spy.call_count == 1` | ✅ |
| YAML-04 | re-parse on mtime or size change | `tests/test_yamlload.py:43` (size) - `== {"a": 1, "b": 22}`; `:53` (mtime only) - `== {"a": 2}` | ✅ |
| YAML-05 | next load unmutated after a caller mutates returned data | `tests/test_yamlload.py:62` - `load_file(f) == {"a": {"b": [1, 2]}}`; `:94` (theme) | ❌ only the miss-path copy is mutated; a hit returning the cache itself survives (M5) |
| YAML-06 | no file read, equal packs | `tests/test_icons_registry_cache.py:30-32` - `spy.call_count == 0`, `spy2.call_count == 0`, `second == first` | ✅ |
| YAML-07 | rebuild on env / cwd / file change | `tests/test_icons_registry_cache.py:46,48` (env), `:55,57` (cwd), `:63,66` (file) | ✅ |
| YAML-08 | byte-identical SVG | `rust/bench/render_all.sh` vs the `5f33d46` baseline: `diff -r` empty, 40 SVGs (re-run by the Verifier, pure Python) | ✅ |
| ROUTE-01 | core called for None / `Crossings` | `tests/test_rust_route.py:97-99` - result from core, `len(fake.calls) == 1`, crossing `is None`; `:105` - `fake.calls[0][-3] == (120.0, drawn)`; busy lookup `:111` | ✅ |
| ROUTE-02 | other callable → Python | `tests/test_rust_route.py:116` - `fake.calls == []`; `:117` - Python result | ✅ |
| ROUTE-03 | inactive core never called | `tests/test_rust_route.py:122` | ✅ |
| ROUTE-04 | identical point lists | `tests/test_rust_route.py:31` - `assert got == expected` (every binding test); `route_parity.py`: 57/57 recorded, 2500/2500 random (re-run by the Verifier) | ✅ |
| ROUTE-05 | 4-point elbow bottom→top | `tests/test_rust_route.py:36` - `== [(120, 140), (120, 170), (120, 170), (120, 200)]`; `route.rs` test `boxed_in_endpoints_give_the_elbow` | ✅ |
| ROUTE-06 | blocked stub rejects the side pair | `tests/test_rust_route.py:41`; `route.rs` `stub_inside_an_obstacle_rejects_the_side_pair` | ✅ |
| ROUTE-07 | + `BUSY` (400) per busy end | `tests/test_rust_route.py:47` - `free[0] == (40, 20) and busy[0] != (40, 20)` | ⚠️ spec-precision gap: the 400 value is enforced only by `route_parity.py`; pytest and cargo tests survive `BUSY = 200` (M6) |
| ROUTE-08 | `cost` × strict crossings per step | `tests/test_rust_route.py:31` via `check(... Crossings(1000.0, [wall]))`; `route.rs` `crossing_cost_makes_the_route_go_around` (`!pts.windows(2).any(crosses ...)`) | ✅ |
| ROUTE-09 | port at the fraction | `tests/test_rust_route.py:61` - `got[0] == (20, 40)`; `route.rs` `frac_places_the_port_on_its_side` | ✅ |
| ROUTE-10 | Python `round(x, 2)` incl. ties | `route.rs` `round2_matches_python_round`: 0.125→0.12, 0.375→0.38, 2.675→2.67, 1.005→1.0, -0.125→-0.12 | ✅ |
| ROUTE-11 | `Crossings` callable = old closure | `tests/test_engine_route.py` `test_crossings_equals_the_old_closure`, `test_crossings_values_for_known_cases` (120 / 0 / 0), `test_route_ortho_passes_a_crossings_object` (`isinstance`, `cost == CROSSING`, drawn) | ✅ |
| PAR-01 | N/N report, exit non-zero on difference | `route_parity.py` prints `57 of 57` / `2500 of 2500`; exits 1 under mutants M6, M7b, M8 (Verifier sensor) | ✅ |
| PAR-02 | timing table | `route_parity.py`: Python 914 ms vs Rust 19.8 ms (46.2x) | ✅ |
| PAR-03 | cargo test + clippy in CI | `.github/workflows/ci.yml` job `rust`: `cargo test`, `cargo clippy --all-targets -- -D warnings` | ✅ |
| PAR-04 | wheel + suite with the flag in CI | same job: maturin build, `uv pip install`, `SPINAGRAM_RUST=1 uv run --no-sync pytest -q` | ✅ |
| PAR-05 | `test` job unchanged | `git diff fe9a98a..HEAD -- .github/workflows/ci.yml`: additions only, under the new `rust` job | ✅ |

**Status**: ❌ 1 gap (YAML-05), ⚠️ 1 spec-precision gap (ROUTE-07)

---

## Discrimination Sensor

Scratch: `git worktree add --detach` under the session scratchpad; Python run with `PYTHONPATH=<wt>/src`; Rust built with
a separate `CARGO_TARGET_DIR`, the mutant wheel installed with `--target` into a scratch dir (the venv was not touched).
Real tree `git status --porcelain` identical before and after.

| # | File | Mutation | Killed? |
|---|---|---|---|
| M1 | `src/spinagram/yamlload.py` `stat_key` | key ignores `st_mtime_ns` | ✅ `test_changed_mtime_only_reparses` |
| M2 | `src/spinagram/icons.py` `registry` | key drops the files' stat keys | ✅ `test_editing_project_registry_rebuilds` |
| M3 | `src/spinagram/autolayout/route.py` `route` | any callable penalty goes to the core | ✅ `test_plain_callable_penalty_stays_in_python` |
| M4 | `src/spinagram/engine/route.py` `Crossings.__call__` | `cost * n` → `cost + n` | ✅ `test_crossings_values_for_known_cases` |
| M5 | `src/spinagram/yamlload.py` `load_file` | cache hit returns the cached object (no deepcopy) | ❌ **Survived** → Fix 1 |
| M6 | `rust/.../route.rs` | `BUSY` 400 → 200 | ✅ by `route_parity.py` (2424/2500, exit 1); ⚠️ pytest and cargo survive → Fix 2 |
| M7 | `rust/.../route.rs` | tie `<` → `<=` against `best - 1e-9` | equivalent in practice (no input yields cost exactly `best - 1e-9`); replaced by M7b |
| M7b | `rust/.../route.rs` | ties prefer the later side pair (`< best + 1e-9`) | ✅ 3 pytest failures + parity exit 1 |
| M8 | `rust/.../route.rs` `round2` | naive `(x*100).round()/100` | ✅ 3 cargo failures + parity 2131/2500 |

**Sensor depth**: expanded (8 effective mutations)
**Result**: 7/8 killed - FAIL

---

## Gate Check

- Rust: `cargo test` 9 passed; `cargo clippy --all-targets -- -D warnings` clean.
- Wheel rebuilt from HEAD and reinstalled.
- `ruff check src tests examples`: clean.
- pytest (pure Python): **2666 passed, 3 skipped, 1 deselected**. With `SPINAGRAM_RUST=1`: **2666 passed, 3 skipped, 1 deselected**.
- Test count before feature: 2630 → after: 2666 (+36). No skips added except `importorskip("spinagram_core")` in `TestBinding` (runs whenever the wheel is installed; CI `rust` job installs it).
- `render_all.sh` vs `5f33d46` baseline: identical in both modes (40 SVGs).

## Speed (measured)

| | Before | After |
|---|---|---|
| Warm build, all examples, pure Python (YAML caches) | 1545 ms | 1273 ms (−18 %, goal 25 %: missed, recorded in spec) |
| Same with `SPINAGRAM_RUST=1` | 1262 ms | 394 ms (3.2x) |
| `route()` over 57 recorded calls | 914 ms Python | 19.8 ms Rust (46.2x, goal ≥ 10x) |

---

## Code Quality

| Principle | Status |
|---|---|
| Minimum code / surgical | ✅ |
| No scope creep | ✅ |
| Matches patterns | ⚠️ minor: `icons.py` and `theme.py` use `from spinagram import yamlload`; the package elsewhere uses relative imports (`from .x import`). Not blocking |
| Shared cached objects | ⚠️ minor: `registry()` returns `dict(hit)`, so callers share cached `Pack` objects. No code mutates a `Pack` today (`git grep` checked). Not blocking |
| Every test maps to a spec requirement | ✅ (`test_register_and_unregister_are_seen` maps to the T3 Done-when) |
| Guidelines followed | ✅ `.specs/LESSONS.md` L-001 (PYTHONHASHSEED 0/1/2 byte identity run in T10), L-014 (clauses asserted separately) |

---

## Fix Plans

### Fix 1 (Major): YAML-05 is not tested on a cache hit

- **Root cause**: `test_mutating_result_does_not_touch_next_load` (`tests/test_yamlload.py:56`) and the theme test (`:86`) mutate the result of the first, cache-miss load. That result is always a copy, so removing the deepcopy on the hit path goes unnoticed.
- **Fix task F1**: load twice, mutate the second (cache-hit) result, assert the third load equals the original data. The same pattern applies to the theme test.
- **Priority**: Major (surviving mutant)

### Fix 2 (Minor): ROUTE-07's 400 is not pinned below the parity harness

- **Root cause**: the busy tests only check that the route changes side, which also holds for `BUSY = 200`.
- **Fix task F2**: a Rust unit test in `route.rs` where the cheapest free detour costs between 200 and 400 more than the busy side, so the route avoids the busy side (BUSY = 400 decides). Add a second case where the detour costs more than 400 extra, so the route keeps the busy side.
- **Priority**: Minor (killed by the CI parity harness, but the spec value deserves a direct test)

---

## Requirement Traceability Update

All IDs stay `Implementing` until the fixes land and iteration 2 passes.

## Summary

**Overall**: ❌ Not ready (2 small test fixes)
**Spec-anchored check**: 23/24 ACs matched, 1 gap (YAML-05), 1 spec-precision gap (ROUTE-07)
**Sensor**: 7/8 killed
**Gate**: 2666 passed in both modes; Rust 9 passed; clippy and ruff clean

**What works**: parity is exact (57/57 recorded, 2500/2500 random, 40 SVGs byte-identical in both modes and three hash seeds), Rust routing is 46x faster, and builds are 3.2x faster with the core. Python stays the reference and the default.

**Next steps**: F1 and F2 by the implementer, then iteration 2.

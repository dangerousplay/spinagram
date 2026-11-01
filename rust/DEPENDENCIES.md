# Crates first: what is hand-written in `spinagram-core` and why

The rule (user directive, 2026-11-01): use an established crate wherever it reproduces the required behaviour. Python
is the reference, so "reproduces" means every parity harness stays at 100 %. This table lists every component of
`rust/spinagram-core/src` that is not a thin use of a crate, the crates tried, and the outcome. Experiments ran in
scratch copies; none of the rejected code is in the tree.

Evidence is either **measured** (a corpus or a parity harness, numbers given) or **by construction** (the crate's
documented algorithm cannot give the required result; the case shows why).

| Component | Where | Crates evaluated | Outcome | Evidence |
|---|---|---|---|---|
| A* edge router (`search`) | `route.rs` | `pathfinding` 4 (`astar`) with `ordered-float` | **keep** | Measured: `astar` on the same grid with a virtual end node gave 55 of 57 recorded calls and 2,270 of 2,500 random scenarios identical. First difference, recorded call 14: Python `[(667.3, 442.4), (667.3, 456.4), (787.3, 456.4), (787.3, 543.6)]`, crate `[(667.3, 442.4), (667.3, 464.4), (787.3, 464.4), (787.3, 543.6)]`. Python orders the open set by `(f, g, cell, dir, prev)` tuples and adds the final bend after popping the goal; the crate breaks ties differently and optimises the bend too |
| Path simplification and `round(x, 2)` | `route.rs` (`simplify`, `round2`) | `geo` `Simplify` (Ramer-Douglas-Peucker), std formatting | **keep** (rounding is std `format!("{x:.2}")`) | By construction: spinagram merges exactly collinear points after rounding; RDP drops points within a tolerance, a different result for any near-collinear path |
| Python number formatting (`f1`, `g`, `repr_f64`) | `pyfmt.rs` | `sprintf` 0.4 (C-style `%.1f`, `%g`), `ryu` and `dtoa` (shortest digits) | **keep**, built on std `{:.N}` and `{:e}` | Measured with 100,017 floats against Python `format`: `sprintf` `%.1f` differs for 1,928 (first: `0.15` gives `0.2`, Python `0.1`); `%g` differs for 10,536 (first: `0.0` gives `NaN.`, Python `0`). `ryu` and `dtoa` give the same shortest digits as std `{:e}`, so they add nothing |
| HTML escaping (`esc`, `attr`) | `pyfmt.rs` | `html-escape` 0.2 (`encode_text`, `encode_quoted_attribute`) | **replace** | Measured: 0 of 3,007 strings differ from `html.escape(s, quote=False)` and `html.escape(s, quote=True)` (specials, non-ASCII, no-break space, already escaped text) |
| Compensated `sum()` (`py_sum`, 3.12+) | `pyfmt.rs` | `compensated-summation` 0.3 (`KahanBabuskaNeumaier`), `accurate` 0.4 (`Sum2`) | **replace** with `compensated-summation` (`accurate` also matched but pulls in rayon) | Measured: 0 of 20,000 random sums differ from CPython 3.13 `sum()` (bit-identical). The plain 3.11 branch stays a std `fold` |
| Text wrapping and token breaking (`wrap`, `break_token`, `wrap_fit`, `segments`) | `text.rs` | `textwrap` (`wrap_first_fit` over fragments), `unicode-linebreak` | **keep** | By construction: first-fit sums per-fragment widths, Python measures the joined candidate line. Pillow `getlength` of `AV` in Arial 14 is 18.584375 px, the sum of its letters 18.6, so line breaks move. Safe-break cuts are IPv4/CIDR-aware, which neither crate models (proved in `verified/segments.rs` from T7) |
| Glyph advances (`Face::length`, 26.6 fixed point) | `font.rs` | `skrifa` (used for the metrics), `ab_glyph` 0.2, `fontdue`, `freetype-rs` | **keep** the small `FT_DivFix`/`FT_MulFix` emulation on top of `skrifa` | Measured: `ab_glyph` summed advances (with kerning) differ from Pillow for 1,977 of 2,000 strings (first: `≔∻⃰⇢` at 18 px: 27.386 against 40.8). `freetype-rs` would add a C build to every wheel |
| `var()` substitution | `css.rs` (`substitute`) | `cssparser` tokenizer | **keep** | By construction: Python scans characters and counts parentheses, strings included. `var(--a, ")")` gives `"")` in Python; a CSS tokenizer reads the string as one token. Nested, unclosed (`var(--oops` gives `oop`) and eight-pass behaviour are Python's, pinned by tests |
| Cascade sort | `css.rs` (`cascade`) | std `slice::sort_by_key` (stable), `itertools` | **std**, no crate needed | Stable sort over the key `(level, specificity, rule order, declaration index)`; `css_parity.py` 100 % |
| SVG writer | `svg.rs` | `quick-xml` 0.40 writer and escaping, `svg`, `xmlwriter` | **keep** | By construction the bytes are Python's: attribute order, `&#160;`, hand-built `&apos;` in `font-family`. Measured: `quick-xml` escapes `'` as `&apos;`, Python `html.escape` as `&#x27;` |
| Scene model and JSON schema | `scene.rs` | `serde`, `serde_json`, `schemars` | **crates** (already) | The structs derive both; `float_roundtrip` is required for exact floats |
| Selector parsing, matching, specificity (including `:not()`) | `css.rs` | `cssparser`, `selectors` | **crates** (already) | Glue only: element tree, three pseudo-elements, node kinds as type names. `selectors` computes specificity (see the specificity note below) |
| PNG rendering | `png.rs` | `resvg`, `usvg`, `tiny-skia` | **crates** (already) | |
| Element tree for `selectors` | `css.rs` (`Tree`, `Node`, `El`) | none: the trait impl is the glue | **keep** | The crate defines `Element`; any user supplies the tree |

## Notes

- The two **replace** decisions (`html-escape`, `compensated-summation`) are applied in `pyfmt.rs`; all harnesses stay at 100 %.
- **Specificity (VER-06): N/A, the `selectors` crate computes it.** `selectors-0.41.0/builder.rs`: the `Negation` arm
  of the specificity walk (line 380) feeds `selector_list_specificity_and_flags` (lines 428-448), which takes
  `std::cmp::max` over the arguments of `:not()` (line 444); `parser.rs:882` exposes the packed value
  (`Selector::specificity`, ten bits per component, ids at bit 20). `spinagram-core` (`css.rs`,
  `Selector::specificity`) only unpacks the three components, so there is no hand-written `:not` specificity to prove
  and `verified/` has no specificity module. `css_parity.py` compares the unpacked tuples with Python's
  (`:not(.a, #b.c)`, nested `:not`, pseudo-element selectors) at 100 %.

# Feature: PNG → SVG icon vectorization

**Status:** Done (2026-10-08) · **Size:** Large · **Owner:** diagramkit

## Problem

Raster icons (PNG) degrade every editable output: they blur when a diagram is scaled, Figma/FigJam
needs one `upload_assets` per distinct PNG (they cannot be built inside `use_figma`), and they are not
editable vectors. Two built-in packs (`oci`, `openstack`) and most brand icon sets (e.g. a corporate
set, `{name}-{green,white}.png`) ship only PNG.

## Goal

Convert PNG icons to SVG **automatically**, only when the result is faithful to the source, so diagrams
get crisp, editable vector icons without any change to specs.

## Evidence (prototype, 2026-10-08)

vtracer (MIT, colour tracing) on real icons, compared after rasterising the SVG back with resvg-py
(MIT) over a neutral grey background:

| Icon | Size | SVG | mean Δ | px Δ>48 | px Δ>128 |
|---|---|---|---|---|---|
| oci compute-vm | 256² | 2 KB, 9 paths | 2.46 | 1.82% | 0.00% |
| openstack nova (multi-colour) | 256² | 21 KB, 36 paths | 5.16 | 5.66% | 0.46% |
| brand safe (line icon) | 434² | 16 KB, 3 paths | 1.06 | 0.76% | 0.00% |
| brand apps white | 435² | 17 KB, 4 paths | 1.57 | 1.56% | 0.00% |

Differences are anti-aliased edges (visual check in the contact sheet), ~0.03 s per icon.

## Requirements

| ID | Pri | Requirement | Acceptance |
|---|---|---|---|
| VEC-01 | P1 | `png_to_svg(path)` traces a PNG into a colour SVG with transparency kept, using parameters tuned for flat icons | returns SVG text with ≥1 `<path>`; transparent pixels stay transparent |
| VEC-02 | P1 | **Fidelity gate**: rasterise the SVG at the source size and compare over grey `#808080`; accept only when mean Δ ≤ 8 **and** pixels with Δ > 128 ≤ 1 % | nova and brand icons accepted; a photo-like noise PNG rejected; score stored |
| VEC-03 | P1 | **Icon packs**: when fetching, each PNG icon is vectorized; accepted ones become the icon's file (SVG), the PNG stays as `raster` | `oci:vm` resolves to `.svg`; index entry has `raster` + `vector.score` |
| VEC-04 | P1 | **Theme / spec icons**: a PNG resolved from a theme icon dir or a spec path is replaced by its cached vector twin when accepted | a brand `safe` icon resolves to an SVG in the vector cache |
| VEC-05 | P1 | **On by default, easy to turn off**: active when the `vector` extra is installed; `DIAGRAMKIT_VECTORIZE=0`, theme `icons.vectorize: false` or pack `vectorize: false` disable it; missing deps → PNG with a single warning | each switch verified by a test; no crash without deps |
| VEC-06 | P1 | **Cache & determinism**: results cached by sha256(PNG) + params version; rejected results cached too (no re-trace) | second resolve does no tracing; same bytes → same SVG |
| VEC-07 | P1 | **PPTX keeps raster**: python-pptx cannot embed SVG, so a vectorized icon keeps a sibling `.png` (the original) that the PPTX backend uses | PPTX of a vectorized icon still has a picture |
| VEC-08 | P2 | **CLI** `diagramkit vectorize <png|dir>... [-o DIR] [--force]` writes SVGs and prints a score table (accepted/rejected) | table printed; rejected files listed, exit 0 |
| VEC-09 | P2 | **Figma/FigJam**: vectorized icons reach the icon library as SVG (editable vectors, no PNG upload) | `-f figjam` bundle of a PNG-icon spec contains `.svg` |

## Out of scope

- Photos / gradients-heavy artwork (the gate rejects them — they stay PNG).
- Rasterising SVG for PPTX (deferred idea: resvg could also fill the PPTX SVG gap).

## Decisions (agent, from evidence)

- Engine **vtracer** (colour, stacked, spline) over potrace (monochrome only) and over wrapping the
  PNG in `<image>` (not a vector).
- Verification renderer **resvg-py** (no browser needed) instead of Playwright.
- Default **on** — the user asked for "automatically"; the fidelity gate makes it safe.

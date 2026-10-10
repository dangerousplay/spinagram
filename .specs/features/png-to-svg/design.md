# Design: PNG → SVG vectorization

## Components

```
icons.fetch ──┐                     ┌── cache: <cache>/vector/<sha>.json  (svg file, score, accepted)
Theme.icon ───┼─► vectorize.maybe() ─┤      <cache>/vector/<sha>.svg + <sha>.png (raster twin)
CLI vectorize ┘         │            └── deps: vtracer (trace) + resvg-py (verify), extra `vector`
                        └─► png_to_svg() ─► score() ─► gate
```

### `diagramkit/vectorize.py`
- `PARAMS` (tuned): colormode=color, hierarchical=stacked, mode=spline, filter_speckle=2,
  color_precision=8, layer_difference=8, corner_threshold=60, length_threshold=3.5,
  splice_threshold=45, path_precision=3. `PARAMS_VERSION = 1` (bump to invalidate cache).
- `available() -> bool` (imports vtracer + resvg_py lazily).
- `enabled(theme_flag=None) -> bool`: env `DIAGRAMKIT_VECTORIZE` ("0"/"false" → off), theme flag, deps.
- `png_to_svg(png: bytes) -> (svg: str, w, h)`; SVG gets `viewBox="0 0 w h"` so it scales.
- `score(png: bytes, svg: str) -> Score(mean, strong)` — resvg at source size, flatten both on grey.
- `accept(score)` — mean ≤ 8 and strong ≤ 0.01 (`MAX_MEAN`, `MAX_STRONG`).
- `vectorize_bytes(png) -> Result(svg|None, score, accepted)`.
- `maybe(path: Path) -> Path`: PNG → cached SVG path when accepted (writes `<sha>.svg` and copies the
  PNG to `<sha>.png` so `.with_suffix(".png")` finds the raster twin — VEC-07); otherwise the PNG.
  Cache record `<sha>.json` stores score/accepted so rejects are not re-traced.

### Integration
- `icons.fetch`: after the files are written, for each PNG icon when `enabled() and pack.vectorize`:
  `vectorize_bytes`; accepted → write `<file>.svg` next to it, index entry `{tone: svg, raster: {tone: png},
  vector: {tone: score}}`. Index records `vectorized: PARAMS_VERSION` (re-fetch upgrades old caches).
- `Theme.icon`: when the found file is `.png` and `enabled(icons.vectorize)` → `vectorize.maybe(found)`.
- PPTX `_raster(svg)` already looks for a sibling `.png` → satisfied by the twin (packs: `<stem>.png` is
  the original file next to `<stem>.svg`, same stem).
- CLI `vectorize`.
- `pyproject`: extra `vector = ["vtracer>=0.6", "resvg-py>=0.5"]`, included in `all`.

## Risks
- vtracer output size for complex icons (≤ 50 KB observed) — fine for SVG/Figma.
- resvg-py rendering differs slightly from browsers — thresholds have margin (nova at 5.2 vs 8).

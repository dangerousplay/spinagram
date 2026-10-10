# State

## Decisions
- 2026-10-08 · PNG→SVG uses vtracer (colour tracing) + resvg-py (verification), default on with a
  fidelity gate (mean Δ ≤ 8, strong ≤ 1 %). See `features/png-to-svg/spec.md`.
- 2026-10-08 · Icon packs: AWS via npm `aws-icons` (official asset-package URL rotates and 403s).

- 2026-10-08 · PPTX SVG: `asvg:svgBlip` + PNG fallback (sibling → resvg 4× → 1×1), deduped per deck.
  Opt-out by argument/env only (backend has no theme access — PSVG-06 deviation).
- 2026-10-08 · Auto layout: pluggable engines (flex built-in, dot, elk, d2) behind `LGraph → LResult`;
  user asked for all four. `build_scene` applies layout itself; laid-out copy has `layout=None`.

- 2026-10-09 · Live UI (`diagramkit serve`): Starlette + uvicorn + watchfiles (extra `ui`), SSE events,
  React + TS + Vite + Tailwind v4 SPA built with bun into `src/diagramkit/ui/static` (committed, ships in wheel).
  `icons.AUTO_FETCH=False` under serve: packs are fetched explicitly from the UI. See `features/live-ui/`.

## Deferred ideas
- UI: QA panel, export buttons, sample diagram per theme, re-theme current spec, extends diff, icon copy-ref /
  tone / vector badges, theme alias map, LAN sharing (from live-ui discussion).
- UI: fetch progress is status-only (fetching/done/failed); per-file progress needs a callback in `icons.fetch`.
- PPTX: honour a theme `pptx: {svg: raster}` key (needs theme access in backends).
- Layout: d2 spacing is looser than dot/elk (example overflows by ~90 px); ELK intra-group layer gap is tight.
- Layout: edge-label placement by engines; stable layout across edits.

## Lessons
- dot cluster margin is uniform: reserve the label band with a blank top label sized by fontsize.
- d2 blank labels reserve no space: use label "M" near top-center sized to the band.
- elkjs bundled worker under bun needs a stub `document`.
- FigJam connector `position` is in pixels; use `magnet` for side centres.
- `setPluginData` is unavailable in `use_figma`.
- `icons.fetch` must be serialised per pack: concurrent callers share one `.tmp` dir (fixed with a lock).
- A long-running process must drop `Theme` icon caches after a pack download (reload the theme).
- `.py` specs under a watcher: purge helper modules (by folder and by name) and skip `.pyc` writes,
  or a same-size edit within one second reuses stale bytecode.
- Starlette `TestClient` needs `base_url="http://127.0.0.1"` behind `TrustedHostMiddleware`.

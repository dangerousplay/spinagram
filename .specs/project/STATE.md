# State

## Decisions
- 2026-10-08 · PNG→SVG uses vtracer (colour tracing) + resvg-py (verification), default on with a
  fidelity gate (mean Δ ≤ 8, strong ≤ 1 %). See `features/png-to-svg/spec.md`.
- 2026-10-08 · Icon packs: AWS via npm `aws-icons` (official asset-package URL rotates and 403s).

- 2026-10-08 · PPTX SVG: `asvg:svgBlip` + PNG fallback (sibling → resvg 4× → 1×1), deduped per deck.
  Opt-out by argument/env only (backend has no theme access — PSVG-06 deviation).
- 2026-10-08 · Auto layout: pluggable engines (flex built-in, dot, elk, d2) behind `LGraph → LResult`;
  user asked for all four. `build_scene` applies layout itself; laid-out copy has `layout=None`.

- 2026-10-09 · Live UI (`spinagram serve`): Starlette + uvicorn + watchfiles (extra `ui`), SSE events,
  React + TS + Vite + Tailwind v4 SPA built with bun into `src/spinagram/ui/static` (committed, ships in wheel).
  `icons.AUTO_FETCH=False` under serve: packs are fetched explicitly from the UI. See `features/live-ui/`.
- 2026-10-12 · Diagram import (D2, PlantUML): toolchain-backed parsing — D2 via official D2.js (WASM) under
  bun/node installed into the cache like elkjs; PlantUML via own description-grammar parser over `--preproc`
  (Java optional). Imports re-layout with spinagram engines. Native shape kinds (cylinder, ellipse, hexagon,
  cloud, person, document) join the core model in the MVP. D2 ships first. See `features/diagram-import/`.
- 2026-10-12 · Focus shifts to behavior diagrams (flow, activity, state) and CSS-like styling. Specs:
  `features/layered-layout/` (built-in pure-Python Sugiyama engine, prerequisite), `features/behavior-diagrams/`
  (specialized builders, embeddable as typed regions in one diagram), `features/css-styling/` (real CSS subset).
  `features/diagram-import/` is parked (spec kept; native shapes and layered layout make it cheaper later).
- 2026-10-12 · Layered engine (`layered`, pure Python Sugiyama) is the default for Flowchart/StateMachine/Activity
  and typed regions; `flex` stays the default for plain diagrams. Right-flowing gaps are sized per label.
  Determinism is pinned by a golden hash across PYTHONHASHSEED 0-9.
- 2026-10-12 · Behavior symbols: geometry defined once in `spinagram.shapes` (absolute M/L/C/Z paths) and consumed
  by scene, SVG, PPTX (presets / group / freeform) and Figma (vector networks). Regions are groups with an
  `engine` hint laid out first and placed as blocks; crossing edges use the obstacle router.
- 2026-10-12 · CSS: tinycss2 + own selectors/cascade; inline CSS is `css=` (style= keeps naming theme styles and
  also matches as a class). Cascade: theme.css chain < _defaults stylesheets < diagram sheets/css < inline.
  Resolved once in `css.prepare` before layout; unstyled diagrams skip it (golden SVG unchanged).
- 2026-10-12 · CSS inspector: one trace (`css.compute(trace=)` → `css.inspect`) feeds `check --styles` and the
  live UI. The UI hit-tests with scene geometry from `api/diagrams/<key>.styles`, so the SVG stays untouched.
  `serve` maps saved `.css` files to diagrams through their cascade and watches external stylesheet folders.
  See `features/css-inspector/`.
- 2026-10-12 · Diagram catalog: diagrams carry `category` + `tags` (`group` is taken by layout zones). Effective
  metadata (declared + provider tags inferred from vendor icon packs; category = dominant provider) lives in
  `spinagram.metadata` and feeds both the CLI filters and `serve`. UI search/grouping/recents are pure TS in
  `web/src/catalog.ts`, tested with `bun test` (run by pytest when bun exists). See `features/diagram-catalog/`.
- 2026-10-12 · Catalog previews: Themes and Icon packs pages reuse the Diagrams card layout (`CatalogShell`).
  Theme cards render a built-in sample diagram per theme (`/api/themes/<ref>/thumbnail.svg`); pack cards show
  12 icons sampled from the name-sorted list (`packSample`). See `features/catalog-previews/`.
- 2026-10-12 · Annotations: legends, numbered steps, callouts and note variants are model data turned into plain
  scene primitives by `spinagram.annotate`, so every backend renders them natively with no backend code. Legend and
  steps live in a reserved right/bottom band subtracted from the layout area; callouts place greedily (sides top,
  right, bottom, left × centre/start/end alignment). CSS reaches them as `legend`, `step`, `callout`, `note.<variant>`.
  See `features/annotations/`.
- 2026-10-12 · Self-hosted and network packs: `selfhosted` (homarr-labs/dashboard-icons, Apache-2.0; `-light` files are
  the dark-fill variant) and `network` (ecceman/affinity, Unlicense; `name[-colour]`, `-circle`, `-plain`), both pinned
  GitHub sources fetched file by file. Their icons infer the `self-hosted` / `network` catalog tags. See
  `features/selfhosted-icons/`.
- 2026-10-12 · Legend from CSS: `legend { placement; width; columns; gap; padding; swatch-width; swatch-height;
  display }` and `legend::body { font-size }` drive the annotation band (right, left, top, bottom); an explicit
  `add_legend(position=...)` beats the stylesheet like inline style. See `features/legend-css/`.
- 2026-10-13 · Brand packs: `ai` (lobehub/lobe-icons, MIT), `cncf` (cncf/artwork) and `logos` (gilbarbara/logos,
  CC0), pinned GitHub sources. `current_color` paints `currentColor` SVGs per tone (an `<image>` draws them black)
  and adds the white dark-fill copy. `ai:`/`cncf:` infer catalog tags; `logos:` does not. See `features/brand-icons/`.

- 2026-10-17 · Live editor: `serve` shows and saves a diagram's spec and cascade stylesheet files (CodeMirror 6 in a
  lazy chunk) and can open another folder (recursive scan, skip list, 2,000-spec cap). Every source/write/folder
  endpoint requires `X-Spinagram: 1` (no CORS, so other origins cannot send it); writes go only to files listed by
  loaded diagrams, are version-checked (SHA-256) and atomic. See `features/live-editor/`.

- 2026-10-19 · Inspector declarations: the styles report lists unstyled diagrams' elements (`css.inspect(all_elements=True)`;
  the CLI keeps the old call) and gives each element a `declaration` found by a text search of its spec
  (`spinagram.ui.declare.locate`), which also drives the code panel's click-to-line. Hover chip in screen px; Recent
  sidebar and code panel both fold to rails. See `features/inspector-declarations/`.

## Deferred ideas
- UI: QA panel, export buttons, re-theme current spec, extends diff, icon copy-ref /
  tone / vector badges, theme alias map, LAN sharing (from live-ui discussion).
- UI: fetch progress is status-only (fetching/done/failed); per-file progress needs a callback in `icons.fetch`.
- PPTX: honour a theme `pptx: {svg: raster}` key (needs theme access in backends).
- Layout: d2 spacing is looser than dot/elk (example overflows by ~90 px); ELK intra-group layer gap is tight.
- Layout: edge-label placement by engines; stable layout across edits.
- Behavior: dashed dividers for orthogonal regions; YAML regions (BHV-27); connectors, interruptible regions.
- CSS: `font-family` switching between theme fonts, remaining CSS-08..11 properties (padding, text-align,
  icon-*), gradients, editing CSS from the inspector.
- Layout: obstacle router port spreading (two edges into one side share a point); tracks may collapse (F4).
- Icons: curated pack aliases are baked into the cached index at fetch time; apply them at resolve time so alias
  changes reach existing caches without a re-fetch.
- Annotations: callouts on groups/edges; animated step-through; free-corner panels; legend entries for group classes.
- Import (parked 2026-10-12): D2/PlantUML spec in `features/diagram-import/`; Mermaid / draw.io / Structurizr frontends; remote icon URLs; PlantUML sprites → icon packs.

## Lessons
- GitHub raw URLs must quote the path: one file name with a space fails the whole pack fetch.
- A CSS stylesheet that repaints a node does not change its icon tone: keep `style: dark` (CSS matches the style
  as a class) instead of a lookalike class, or the dark-tone artwork lands on a white fill.
- dot cluster margin is uniform: reserve the label band with a blank top label sized by fontsize.
- d2 blank labels reserve no space: use label "M" near top-center sized to the band.
- elkjs bundled worker under bun needs a stub `document`.
- FigJam connector `position` is in pixels; use `magnet` for side centres.
- `setPluginData` is unavailable in `use_figma`.
- `icons.fetch` must be serialised per pack: concurrent callers share one `.tmp` dir (fixed with a lock).
- A long-running process must drop `Theme` icon caches after a pack download (reload the theme).
- `.py` specs under a watcher: purge helper modules (by folder and by name) and skip `.pyc` writes,
  or a same-size edit within one second reuses stale bytecode.
- Static SPA under `serve`: a hash route change does not reload `index.html`; reload the page after a rebuild.
- Starlette `TestClient` needs `base_url="http://127.0.0.1"` behind `TrustedHostMiddleware`.

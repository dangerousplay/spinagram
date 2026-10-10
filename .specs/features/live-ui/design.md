# Live UI — Design

## Architecture

```
editor save ──► watchfiles.awatch(spec paths + theme chain + icon registries)
                     │ debounce 150 ms, classify change
                     ▼
              Workspace (ui/workspace.py)            Packs (ui/catalog.py)
              files → diagrams, theme, svg cache      registry, fetch jobs (thread)
                     │ publish(Event)                     │ publish(Event)
                     ▼                                    ▼
                         EventBus (asyncio queues per SSE client)
                                     │  GET /api/events (text/event-stream)
Browser (React SPA) ◄────────────────┘
   fetch /api/* JSON, <img>/inline SVG from /api/diagrams/{key}.svg, icons/fonts by URL
```

`spinagram serve` → `ui.server.run(paths, theme, layout, port, open)` → uvicorn on 127.0.0.1 with a
Starlette app built by `create_app(workspace, packs)`. The SPA is served from `ui/static/` (Vite build output,
committed). Everything imports lazily so the core install never needs starlette.

## Components

| Module | Responsibility |
|---|---|
| `ui/workspace.py` | `Workspace(paths, theme_ref, layout)`: scan spec files (`yaml_io` rules: `*.yaml|yml|py`, skip `_*`), load per file (errors kept per file), key = `<relpath>#<diagram id>`; render SVG = `apply_layout` → `build_scene` → `backends.svg.to_svg`, cached by (key, file mtime, theme gen, engine). `reload_theme()`, `invalidate(paths) → affected keys`. Purges `sys.modules` entries whose `__file__` lives in a spec dir before loading a `.py` spec (helper reload). `watch_roots()` = spec paths ∪ theme roots of the extends chain (built-in included — cheap). |
| `ui/themes.py` | `theme_sheet(ref) → dict`: name, extends, root, colours (token, value, resolved hex, via), fonts (role, family, weights, sample, font URLs), styles grouped by kind (node/zone/edge/legend/table raw values), defaults, chrome. `style_preview(theme, kind, style) → svg` via a synthetic `Diagram` (one box/zone/edge) rendered with `to_svg`, canvas cropped to content. `list_themes(active)`. |
| `ui/catalog.py` | `PackService`: list packs (registry + `index(auto_fetch=False)` for state/count), icons of a pack (name, aliases, tones, ext), resolve icon file inside `pack.dir` only; `start_fetch(name)` runs `icons.fetch` in a thread executor; one job per pack (409); status published as events; offline → disabled. |
| `ui/events.py` | `EventBus`: `subscribe()` → asyncio.Queue, `publish(dict)` thread-safe via `loop.call_soon_threadsafe`; SSE generator with 15 s keep-alive comments. |
| `ui/server.py` | `create_app()`: routes below, `HostGuard` middleware (Host ∈ {127.0.0.1:port, localhost:port}), static mount with SPA fallback, lifespan starts the watcher task. `run()` binds, prints URL, opens browser (`webbrowser.open` after startup). |
| `cli.py` | `serve` sub-command; import error → exit 2 with hint. |
| `web/` (repo root) | Vite + React + TS + Tailwind v4 (`@tailwindcss/vite`), `@tanstack/react-virtual`; `bun run build` → `../src/spinagram/ui/static`. Dev: `bun run dev` proxies `/api` to :8765. |

## API

| Method | Path | Returns |
|---|---|---|
| GET | `/api/workspace` | `{paths, theme, layout, offline, engines:[{name, hint|null}], files:[{path, error|null, diagrams:[{key, id, title, auto}]}]}` |
| GET | `/api/diagrams/{key}.svg?layout=E` | `image/svg+xml`; 422 JSON `{error, file}` on failure |
| GET | `/api/themes` | `[{name, ref, builtin, active, error}]` |
| GET | `/api/themes/{ref}` | token sheet JSON |
| GET | `/api/themes/{ref}/preview/{kind}/{style}.svg` | style preview |
| GET | `/api/themes/{ref}/font/{role}/{weight}` | font file (only files declared by the theme) |
| GET | `/api/packs` | `[{name, title, version, origin, license, homepage, fetched, count, fetching, error}]` |
| GET | `/api/packs/{name}/icons` | `[{name, aliases, tones, ext}]` |
| GET | `/api/packs/{name}/icons/{icon}` | icon file (`?tone=dark`) |
| POST | `/api/packs/{name}/fetch` | 202 / 409 running / 403 offline / 404 |
| GET | `/api/events` | SSE: `workspace`, `diagram {keys}`, `theme {ref}`, `pack {name, status, error}` |

Theme `ref` in URLs: built-in name, or `active` for the `--theme` path (avoids paths in URLs).

## Change classification (watcher)

- spec file / `_defaults.yaml` / other `.py` in a spec dir → reload that file (or all files in the dir for
  `_defaults`/helpers) → `diagram {keys}`; file set changed → `workspace`.
- theme root file → `reload_theme()`, clear svg cache → `theme {ref}` + `diagram {all keys}`.
- icon registry files (`~/.config/spinagram/icons.yaml`, `./spinagram-icons.yaml`) → `pack {*}` refresh.

## Frontend

- Shell: left nav (sections Diagrams / Themes / Icon packs) + header (layout dropdown, connection dot) + main.
- State: hash route `#/d/<key>`, `#/t/<ref>`, `#/p/<name>`; `useEvents()` single EventSource with
  reconnect → refetch workspace on open.
- Viewer: SVG fetched as text and injected (`dangerouslySetInnerHTML` of our own server output) inside a
  transformed div; `usePanZoom` (wheel around pointer, pointer drag, fit, 0/f keys). On `diagram` event for the
  current key → refetch, keep transform; previous SVG stays dimmed under an error overlay on 422.
- Theme sheet: sections with swatch grid, font cards (`@font-face` injected from font URLs), style previews as `<img>`.
- Packs: list cards with Fetch; grid with `useVirtualizer` rows, search filter client-side.
- Tailwind v4 with `@theme` tokens; dark via `prefers-color-scheme` (`dark:` variant default).

## Decisions / risks

- SSE over WebSocket: one-way, auto-reconnect, no extra dep.
- Built bundle committed (≈150–250 KB) — trade repo noise for zero-Node installs. `web/` excluded from wheel.
- Python helper reload via `sys.modules` purge scoped to spec dirs — avoids reloading spinagram itself.
- Rendering runs in a thread (`run_in_threadpool`) — dot/elk/d2 engines spawn processes.
- `httpx` added to dev group for Starlette `TestClient`.

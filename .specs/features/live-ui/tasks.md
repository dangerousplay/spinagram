# Tasks — live-ui

Gate for every Python task: `uv run pytest -q` green. Gate for web tasks: `bun run build` (tsc + vite) green.

| # | Task | Where | Depends | Reqs | Done when | Status |
|---|---|---|---|---|---|---|
| T1 | `ui` extra (starlette, uvicorn, watchfiles) + dev httpx; package skeleton; `serve` CLI w/ missing-extra hint | pyproject, ui/__init__, cli.py | – | UI-01, UI-02 | `diagramkit serve --help`; hint test | done |
| T2 | Workspace: scan/load/render/cache/invalidate, helper purge, watch roots | ui/workspace.py, tests | T1 | UI-03, UI-05, UI-06, UI-08 | unit tests: keys, svg, error kept, helper reload, layout override | done |
| T3 [P] | Theme sheet + style previews + theme list + font lookup | ui/themes.py, tests | T1 | UI-09, UI-10 | default theme sheet test; preview svg valid | done |
| T4 [P] | PackService: list/icons/file/fetch jobs/offline | ui/catalog.py, tests | T1 | UI-12..UI-14 | fake listing pack fetched via service; 409; offline 403 | done |
| T5 | EventBus + server routes + HostGuard + static/SPA fallback + watcher + run() | ui/events.py, ui/server.py, tests | T2–T4 | UI-01, UI-04, UI-11, UI-15 | TestClient tests for every route; bad Host 400; path escape 404 | done |
| T6 | Web scaffold: Vite+React+TS+Tailwind v4, proxy, build to static | web/ | – | UI-16 | `bun run build` writes static/index.html | done |
| T7 | Shell + nav + routing + events hook | web/src | T5, T6 | UI-03, UI-05 | nav lists examples; reconnect | done |
| T8 | Diagram viewer: pan/zoom/fit, live refetch, error overlay, layout dropdown | web/src | T7 | UI-06..UI-08 | manual: edit spec → updates, zoom kept | done |
| T9 [P] | Theme sheet view | web/src | T7 | UI-10, UI-11 | default theme sheet renders | done |
| T10 [P] | Packs view: list, fetch, virtual grid, search | web/src | T7 | UI-12..UI-14 | browse terrastruct, fetch a pack | done |
| T11 | E2E smoke (playwright if available) + README/SKILL docs + STATE | tests, README, skills | T8–T10 | all | smoke passes; docs updated | done |

Notes:
- T11 smoke ran with Playwright against `serve` (light + dark): edit → update 0.12 s with zoom kept, error overlay
  + recovery, layout switch, theme edit → sheet 0.8 s, pack fetch from UI (terrastruct 42 s) → icons appear.
  Script kept out of the suite (needs a browser and network); API behaviour is covered by `tests/test_ui.py`.

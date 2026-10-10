# Tasks: PNG → SVG vectorization

| # | Task | Reqs | Depends | Done when / Tests | Status |
|---|---|---|---|---|---|
| T1 | `vectorize.py`: params, availability/enabled switches, `png_to_svg`, `score`, `accept`, `vectorize_bytes`, cache-backed `maybe` (+ raster twin) | VEC-01,02,05,06,07 | — | unit tests: accepted line icon, rejected noise image, cache hit (no re-trace), env switch off | ✅ |
| T2 | `pyproject` extra `vector` (+ in `all`), lockfile | VEC-05 | — | `uv sync --extra vector` works | ✅ |
| T3 | `icons.fetch` vectorizes PNG icons; index `raster`/`vector`; pack `vectorize: false`; `resolve` prefers SVG | VEC-03,05 | T1 | test: zip pack with PNG → resolves `.svg`, `raster` kept; `vectorize:false` keeps PNG | ✅ |
| T4 | `Theme.icon` vectorizes PNG icons (theme dirs + spec paths); theme `icons.vectorize: false` | VEC-04,05 | T1 | test: theme PNG resolves to cached SVG; flag off → PNG | ✅ |
| T5 | PPTX keeps a picture for vectorized icons (twin PNG) | VEC-07 | T1,T4 | test: PPTX from PNG-icon spec contains a picture | ✅ |
| T6 | CLI `spinagram vectorize` | VEC-08 | T1 | test: writes SVG, prints table | ✅ |
| T7 | FigJam bundle contains SVG for PNG icons | VEC-09 | T3,T4 | test: `-f figjam` bundle file is `.svg` | ✅ |
| T8 | Real packs: re-fetch `oci`, `openstack`; report acceptance rate; visual check; docs (README, SKILL) | all | T1–T7 | acceptance table recorded below; render example | ✅ |

Gate per task: `uv run pytest -q` green.

## Verification (T8, 2026-10-08)

| Set | Icons | Accepted | Notes |
|---|---|---|---|
| Corporate brand set (green + white) | 102 | 102 | mean Δ 0.5–1.8 |
| oci pack (light + dark) | 140 | 140 | |
| openstack pack | 50 | 50 | multi-colour mascots, visually identical (contact sheet) |
| random-noise PNG (test) | 1 | 0 | gate rejects, PNG kept |

Study diagrams (Vault/Consul) re-rendered: o04 embeds 41 SVG icons, 0 PNG; QA 0 issues.
Tests: 26 passed (4 new for this feature).

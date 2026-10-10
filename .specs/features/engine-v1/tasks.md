# engine-v1 — tasks

| # | Task | Depends | Done when | Req | Status |
|---|---|---|---|---|---|
| T1 | pyproject (uv, extras), package skeleton, default theme | — | `uv sync` ok | ENG-05,14 | ✅ |
| T2 | model + yaml_io + edge shorthand | T1 | tests parse shorthand + legacy specs | ENG-01,02,04 | ✅ |
| T3 | theme loader (extends, tokens, icons, fonts) | T1 | tests | ENG-05 | ✅ |
| T4 | text metrics + wrap | T3 | tests | ENG-06 | ✅ |
| T5 | scene + layout | T2–T4 | tests | ENG-07 | ✅ |
| T6 | DSL (handles, row/column) | T2 | example renders | ENG-03 | ✅ |
| T7 | svg + png backends, registry | T5 | D01–D08 parity | ENG-08..10 | ✅ |
| T8 | pptx backend | T5 | LibreOffice render ok, connectors bound | ENG-11 | ✅ |
| T9 | figma backend | T5 | `node --check` ok | ENG-12 | ✅ |
| T10 | CLI + gallery + check | T7–T9 | commands work | ENG-13 | ✅ |
| T11 | External theme + migrate prototype specs + symlink | T10 | all outputs generated | — | ✅ |

Notes (2026-10-02):
- T9: validated by `node` dry-run on a mock Plugin API (8/8 scripts). A real `use_figma` run on a file is still pending (needs a fileKey).
- T8: LibreOffice render matches the SVG. Connectors are bound (`a:stCxn`/`a:endCxn`); theme `p:style` is stripped to remove shadows.
- `use_figma` forbids image bytes, so icons go through `upload_assets` with placeholders (README § Figma).

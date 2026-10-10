# engine-v1 — spec

## Requirements

| ID | Requirement |
|---|---|
| ENG-01 | Model: diagram with zones, nodes (box, note, pill, diamond, text), edges, tables, legend; absolute coordinates on a theme canvas |
| ENG-02 | YAML loader, backward compatible with the original prototype's spec schema |
| ENG-03 | Python DSL producing the same model; helpers `row()`/`column()`; nodes return handles with side anchors (`a.right`) |
| ENG-04 | Shorthand edges: `"a -> b"`, `"a.right -> b.left@0.3: label"`; bare ids auto-pick facing sides |
| ENG-05 | Theme directory (`theme.yaml` + assets): canvas, color tokens, fonts (files + Figma style names), node/edge/zone/table styles, icons (dir + pattern + variants), header/footer chrome, defaults; `extends:` inheritance; neutral built-in default |
| ENG-06 | Text fitting by real font metrics (Pillow) when font files exist, heuristic fallback; one wrap result shared by all backends |
| ENG-07 | Layout → backend-neutral Scene (shapes with labels/icons, connectors with bindings, tables, images, texts) |
| ENG-08 | Backend registry + protocol; backends: `svg`, `png`, `pptx`, `figma` |
| ENG-09 | SVG: fonts and images embedded (self-contained) |
| ENG-10 | PNG: 2x via Playwright from the SVG |
| ENG-11 | PPTX: one slide per diagram; native autoshapes with text inside; connectors bound to shapes when anchored at a side centre; arrowheads; native tables |
| ENG-12 | Figma: emit Plugin-API JavaScript (chunks ≤ 45 kB) for `use_figma`; frame named per diagram; re-run replaces content in place |
| ENG-13 | CLI `diagramkit render <files/dirs> --theme DIR -f svg,png,pptx,figma -o OUT` (+ gallery); `diagramkit check` reports text overflow |
| ENG-14 | No organisation-specific assets or names in the repo |

## Acceptance

- The existing prototype specs render through an external theme with parity to the stopgap renderer.
- The PPTX opens in LibreOffice and PowerPoint. Moving a box drags its connectors. Table cells are editable.
- The Figma JS passes `node --check` and runs through `use_figma` on a test file.

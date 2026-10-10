# spinagram

Diagrams as code, rendered once and delivered **editable** everywhere: SVG, PNG,
PowerPoint (native shapes, bound connectors, native tables) and Figma (native nodes
via the Plugin API / Figma MCP `use_figma`).

## Goals

- One source (YAML or Python) → many backends, same geometry.
- Theme-ready: palette, fonts, node styles, icons and page chrome live in a theme
  directory outside this repository. The repo ships only a neutral default theme.
- Backend-agnostic: layout resolves a backend-neutral *scene*; backends only draw it.
- Low verbosity: theme defaults, shorthand edges (`"a -> b: label"`), auto-picked
  sides, layout helpers in the Python DSL.
- Open-source ready: no organisation-specific code, names or assets.

## Non-goals (v1)

- Automatic graph layout (positions are explicit; helpers compute rows/columns).
- Data charts.

## Stack

Python ≥ 3.11, uv, hatchling. Core deps: PyYAML, Pillow (font metrics).
Extras: `pptx` (python-pptx), `png` (playwright).

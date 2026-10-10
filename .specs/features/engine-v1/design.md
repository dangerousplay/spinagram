# engine-v1 — design

```
YAML ─┐                                ┌─ svg ──► png
      ├─► model.Diagram ─► layout ─► Scene ─┼─ pptx
DSL ──┘        ▲            ▲             └─ figma (JS for use_figma)
               │          theme (dir outside repo) + text metrics
```

## Modules (`src/spinagram/`)

| Module | Responsibility |
|---|---|
| `model.py` | Dataclasses: `Diagram`, `Node`, `Edge`, `Zone`, `Table`, `Legend`. Pure data |
| `yaml_io.py` | `load(path) -> Diagram`; parses edge shorthand |
| `dsl.py` | `Diagram` builder methods, `NodeHandle` with anchors, `row/column` helpers |
| `theme.py` | `Theme.load(dir)`, `extends`, token resolution `color("primary")`, icon resolution, font lookup |
| `text.py` | `Metrics(theme)`: `measure(text, font)`, `wrap(text, font, width)` |
| `scene.py` | Neutral primitives: `Shape`, `Label/TextBlock`, `Icon`, `Connector`, `TableGrid`, `Text`, `Image`, `Scene` |
| `layout.py` | `build_scene(diagram, theme) -> Scene` (styles, wrapping, anchors, chrome) |
| `backends/` | `Backend` protocol + registry: `svg.py`, `png.py`, `pptx.py`, `figma.py` |
| `cli.py` | `render`, `check` |
| `qa.py` | Overflow checks on Scene |

## Key decisions

- **The Scene is the contract.** Everything is absolute and resolved: colours are hex, fonts are `FontRef(family, weight, style, size, file)`, text is pre-wrapped. Backends never read the theme or the model, so a new backend is one file.
- **Labels belong to shapes.** In PPTX and Figma the text lives inside, or is grouped with, its shape, so moving the box moves the text. Labels keep both the wrapped lines (SVG/Figma) and the raw paragraphs (PPTX reflow).
- **Connector binding.** A connector keeps `src=(shape_id, side, frac)`. PPTX binds to the connection points (0 top, 1 left, 2 bottom, 3 right) only when `frac == 0.5`; otherwise it draws an unbound line at the exact coordinates.
- **Theme lives outside the repo.** The only built-in theme is `default` (neutral grey/blue, system fonts, no icons). Organisation themes are directories passed with `--theme` or `SPINAGRAM_THEME`.
- **Chrome is in the theme.** Header bar, title, kicker template `{id} · {kicker}`, footer rule, logo and source text are optional per theme.

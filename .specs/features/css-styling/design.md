# CSS-like Styling Design

**Spec**: `.specs/features/css-styling/spec.md`
**Status**: Approved (2026-10-12, "proceed with an MVP"; `tinycss2` dependency accepted)

---

## Architecture Overview

```mermaid
graph LR
    T[theme.css] --> P[parse: tinycss2 → Rule list]
    DF[_defaults stylesheets] --> P
    D[d.stylesheet / css=] --> P
    I[inline css= on element] --> C
    P --> C[cascade: match selectors on element tree<br/>importance, specificity, order; inheritance; var()]
    C --> PRE[prepare: font sizes into nodes before sizing]
    C --> BS[build_scene: fill, stroke, dash, radius, opacity, shadow, fonts, markers]
    BS --> SVG & PPTX & FIG[backends]
```

The cascade runs once per diagram in `api.scenes` (`css.prepare(d, theme)`), before automatic layout,
and stores computed styles in `d.meta["css"]` keyed by element key (`node:<id>`, `edge:<index>`,
`group:<id>`). Diagrams without stylesheets, classes or inline css skip it entirely (byte-identical
output, CSS-27).

## Code Reuse Analysis

| Component | Location | How to Use |
| --------- | -------- | ---------- |
| Theme colours/tokens | `src/spinagram/theme.py:127` (`color`) | Resolve `var(--x)` and bare tokens |
| Named styles | `theme.py:151` (`node_style`) | Remain the base layer; `style="dark"` also adds class `dark` |
| Scene builder | `src/spinagram/layout.py:91` (`box`), `diamond`, connectors | Apply computed overrides when creating Shapes/Connectors/TextBlocks |
| `Shape.opacity`, `dashed` | `scene.py:67` | Extended with `dash: list[float]`, `shadow` |

## Components

### `css.py`
- `parse(text, origin) -> list[Rule]` (tinycss2 rules; errors collected with line/col).
- Selector compiler: compound selectors (type, `.class`, `#id`, `[attr]`, `[attr=v]`, `*`,
  `:first-child`, `:last-child`, `:not(...)`), combinators (descendant, `>`), lists, pseudo-elements
  `::title`, `::body`, `::label`; specificity `(ids, classes/attrs/pseudo-classes, types)`.
- Element tree: `El(type, kinds, id, classes, attrs, parent, children, inline)` built from diagram →
  groups (type `group`, `region`, `lane`) → nodes (`node` + kind) → edges (`edge`, attrs `from`, `to`,
  `label`); edges are children of the diagram root.
- `cascade(d, theme, sheets) -> dict[key, Computed]` with inheritance of `color`, `font-*`.
- Property table: name → parser (colour, length, dash list, shadow, marker, keyword) + scope.

### Model and front-ends
- `Node.cls`, `Node.css`, `Edge.cls`, `Edge.css`, `Group.cls`, `Group.css`; `class_=` keyword in
  builders; `Diagram.stylesheet(path_or_text)`, `Diagram(css=...)`; YAML keys `class`, `css`,
  `stylesheets`, and `_defaults.yaml` `stylesheets`; theme `theme.css` loaded when present.

### Scene + backends
- `Shape.dash`, `Shape.shadow`; `Connector.dash`, `Connector.marker_start/end` (`none`, `arrow`,
  `open-arrow`, `diamond`, `circle`); `Font.italic` already exists.
- SVG: `stroke-dasharray`, `<filter>` drop shadow, marker defs per type/colour.
- PPTX: `a:prstDash` mapped from the pattern (dot → `sysDot`, short dash → `dash`, long → `lgDash`,
  dash-dot → `dashDot`), `a:effectLst/a:outerShdw`, `headEnd/tailEnd` types.
- Figma: `dashPattern`, `effects: DROP_SHADOW`, stroke caps per marker.

## Risks & Concerns

| Concern | Location (file:line) | Impact | Mitigation |
| ------- | -------------------- | ------ | ---------- |
| Byte-identical regression | every backend | Silent visual drift | Style path only when CSS present; CSS-27 test renders all examples and compares SVG hashes against a no-CSS baseline computed in-test |
| Inline `style=` already means named style | `model.py` Node.style | Spec CSS-05 wording conflicts | Inline CSS is `css=` (Python) / `css:` (YAML); spec updated |
| Font changes after sizing | `autolayout/sizing.py` | Text overflow | `prepare` writes computed font sizes into nodes before layout |

## Tech Decisions

| Decision | Choice | Rationale |
| -------- | ------ | --------- |
| Tokenizer | `tinycss2` | Correct CSS tokenization, pure Python, accepted dependency |
| Inline styles | `css=` keyword | `style=` is the existing named-style field |
| MVP property subset | fill, stroke, stroke-width, stroke-dasharray, border-radius, opacity, box-shadow, color, font-size, font-weight, font-style, marker-start/end | Highest visual value; the rest of CSS-08..11 deferred |

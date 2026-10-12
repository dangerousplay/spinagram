# Diagram Import Context

**Gathered:** 2026-10-12
**Spec:** `.specs/features/diagram-import/spec.md`
**Status:** Ready for design approval

---

## Feature Boundary

Read D2 and PlantUML (component, deployment, use case, C4) diagrams, convert them to the spinagram model,
render them directly through every backend, and write editable Python (YAML in P2) specs, reporting every
construct that does not convert.

---

## Implementation Decisions

### Parsing

- Toolchain-backed: D2 through the official D2.js (WASM) run by bun or node, pinned and installed into the
  cache on first use like `elkjs`.
- PlantUML through spinagram's own description-grammar parser; Java and the PlantUML jar only for
  `--preproc` (needed for `!include`, `!define`, C4).

### Shapes

- Native shape kinds ship in the MVP: `cylinder`, `ellipse`, `hexagon`, `cloud`, `person`, `document`, in the
  model, Python/YAML front-ends, SVG, PowerPoint (preset geometry) and Figma/FigJam.
- Other foreign shapes fall back to a box with a warning.

### Layout

- Imported diagrams are re-laid out by spinagram's engines, carrying over the source direction.
  `--keep-layout` stays P2.

### Delivery order

- D2 first, together with the shared pipeline: native shapes, code generator, conversion report, `import`
  CLI, direct render/serve of `.d2`. PlantUML follows on the same pipeline.

### Agent's Discretion

- Generated code style, identifier sanitising, warning wording, cache layout for the toolchains.

### Declined / Undiscussed Gray Areas → Assumptions

- Colour overrides (P2), multi-board D2 files (one diagram per board), markdown/creole labels (plain text),
  remote non-Terrastruct icon URLs (dropped with a warning). Recorded in the spec's Assumptions table.

---

## Specific References

- D2.js `compile()` IR (`diagram.shapes`, `diagram.connections`) verified with `@terrastruct/d2` 0.1.33.
- PlantUML `--preproc` and SVG metadata verified with `plantuml-mit-1.2026.8.jar`.

---

## Deferred Ideas

- Mermaid, draw.io and Structurizr DSL frontends on the same pipeline.
- Remote icon URLs fetched and cached.
- PlantUML sprites / AWS-PlantUML stdlib icons mapped onto spinagram icon packs.

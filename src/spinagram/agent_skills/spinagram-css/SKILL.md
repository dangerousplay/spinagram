---
name: spinagram-css
description: Style spinagram diagrams with CSS (selectors, cascade, custom properties, shadows, dashes, markers) and lay out dense cloud architecture slides (AWS, Google Cloud, Azure, Kubernetes) that fit one 1920×1080 canvas. Use when asked to make spinagram diagrams look polished or on-brand, write or debug a stylesheet, build a dark or vendor-coloured architecture diagram, or explain why an element looks the way it does. Includes recipes, worked examples and layout hints. Requires the spinagram CLI.
---

# Style spinagram diagrams with CSS

A stylesheet restyles a diagram without touching its code. The same rules render in SVG, PNG,
PowerPoint and Figma. This skill covers the CSS subset, the recipes that look good, and the layout
habits that make dense architecture diagrams fit one slide. For general spinagram authoring, see
the `spinagram` skill.

Files next to this one:

- `references/recipes.css`: tested rules to copy (base cards, dark canvas, tiers, edge semantics,
  vendor accents).
- `examples/`: five complete diagrams with their stylesheets: AWS three-tier, AWS hub-and-spoke
  networking, Kubernetes workload, Kubernetes service networking and a Google Cloud global app.
  Render them with `spinagram render examples/ -f png -o out/`.

## Workflow

1. **Structure first, style second.** Write the diagram with groups and edges; give elements
   semantic classes (`class_="security"`, `class_="async"`), never colours.
2. **One base sheet plus one accent sheet.** The base sets cards, type and edges for every diagram
   in the set. The accent sheet adds the vendor or brand palette. Attach both in cascade order:
   `d.stylesheet("base.css")` then `d.stylesheet("aws.css")`.
3. **`spinagram check <spec>`** must report 0 issues. `info: unused selector` lines are hints,
   not failures.
4. **Render a PNG and look at it** if you can view images; otherwise ask the user to. Check that
   edges don't cross boxes, labels don't cover text and nothing is clipped.
5. **Explain a value** with `spinagram check --styles <spec> --select "#api"`, or press **Inspect**
   in `spinagram serve <specs>`, which reloads on every save of a spec or stylesheet.

## Attaching styles

| Where | Python | YAML |
|---|---|---|
| Diagram | `d.stylesheet("brand.css")`, `Diagram(..., css="...")` | `stylesheets: [brand.css]`, `css:` |
| Element | `class_="critical"`, `css="stroke-width: 6"` | `class:`, `css:` |
| Folder | — | `stylesheets:` in `_defaults.yaml` |
| Theme | `theme.css` next to `theme.yaml` | same |

Paths are relative to the spec. Later sheets win at equal specificity; inline `css=` beats every
sheet rule and `!important` beats inline. Classes work on nodes, edges and groups
(`d.group("VPC", style="aws-vpc", class_="private")` keeps the AWS outline and icon and adds the class).

## Selectors

| Selector | Matches |
|---|---|
| `node`, `edge`, `group`, `region`, `lane`, `diagram` | elements by type |
| `box`, `data`, `state`, `decision`, … | nodes of that kind |
| `.critical`, `#api`, `*` | class, id, anything |
| `[icon]`, `[kind=data]`, `edge[from=api]`, `edge[to=db]`, `[label="yes"]` | attributes |
| `group.vpc node`, `region > state` | descendant, child |
| `:first-child`, `:last-child`, `:not(.x)`, `:root` | pseudo-classes |
| `node::title`, `node::body`, `edge::label`, `group::label` | text parts |

Node ids come from titles (`"Orders DB"` → `#orders-db`) unless you pass `id=`.

## Properties

| Applies to | Properties |
|---|---|
| Nodes, groups | `fill`, `fill-opacity`, `stroke`, `stroke-width`, `stroke-dasharray`, `border-radius`, `opacity`, `box-shadow` (one: `x y blur colour`) |
| Text (`::title`, `::body`, `::label`) | `color`, `font-size`, `font-weight`, `font-style`; inherited from groups |
| Edges | `stroke`, `stroke-width`, `stroke-dasharray`, `opacity`, `marker-start`, `marker-end` (`none`, `arrow`, `open-arrow`, `diamond`, `open-diamond`, `circle`, `bar`) |

Colours: hex, `rgb()`/`rgba()`, CSS names, theme tokens (`fill: primary-soft`) and `var(--x)`, which
falls back to the theme token `x`. Lengths are canvas pixels (`4` or `4px`).

## Recipes

All are in `references/recipes.css`.

- **Layout-only group.** `fill: none` is rejected. A group that only arranges its children uses
  `group.bare { fill-opacity: 0; stroke-width: 0; box-shadow: none; }`.
- **Dark canvas.** Zones are translucent by default, so a dark group looks grey until it sets
  `opacity: 1; fill-opacity: 1`. Restyle what sits inside with descendant selectors:
  `group.night node::title { color: #F8FAFC }`.
- **Hero element.** One glow per diagram: `box-shadow: 0 0 22px rgba(140, 79, 255, 0.45)` with a
  thicker stroke. More than one and nothing stands out.
- **External actors.** Dashed outline and no shadow (`.external`), so they read as outside the system.
- **Edge semantics.** Solid for requests, dashed for async or control (`edge.async`, `edge.control`),
  a colour for one special path (`edge.hot`), `marker-start` for two-way flows (`edge.replication`).
- **Tiers.** Tint subnets or zones by tier (`group.public`, `group.private`, `group.data`) and colour
  their labels to match.
- **Vendor palettes.** AWS colours by service category (compute orange, network purple, database
  magenta, storage green); Google Cloud uses its four brand colours; Kubernetes uses `#326CE5`.

## Fitting dense diagrams on one slide

The canvas is fixed at 1920×1080 and content is not scaled down. `check` reports
`layout: overflow` with the excess in pixels.

- **Size cards yourself.** Automatic nodes are at least 220 px wide. Pass a size to every node,
  `N = {"w": 210, "h": 84}` then `d.box(..., **N)`, and widen only the few that need it.
- **Text room with an icon** is about `w − 102` px. A single word longer than that is reported as
  `overflow-x`: widen that node or pick a shorter word. Titles wrap onto two lines; bodies keep to one.
- **Smaller type shrinks boxes**: `node::title { font-size: 19px }` and `node::body { font-size: 14px }`.
- **Tighten spacing** with group hints (`gap=24`, `padding=0`) and the root `"gap"` in `layout`.
- **Use the margins** when needed: `layout={"area": [56, 176, 1808, 830]}` (x, y, w, h).
- **Turn a row into a column.** When the width overflows and there is room below, stack: AZs as rows
  of tier subnets, regions stacked, the control plane as a top row.

## Edges that don't cross boxes

- `flex` with `"route": "ortho"` draws elbowed edges but does **not** route around boxes. Connect
  neighbours only: arrange columns so every edge goes to the next column or the next box in a stack.
- An edge that would skip over a box: reorder (chain `users → dns → cdn` rather than fanning out),
  move one end to another column, or drop the edge and show the relationship with text or a class
  (a `.blocked` pod instead of a "deny" arrow).
- Anchored edges (`d.edge(a.left, b.left)`) are drawn straight, not routed. Use them only between
  boxes that face each other.
- `elk` routes around boxes but lays out wider and ignores group `direction`. Compare with
  `spinagram render spec.py --layout elk` before switching.

## Backends

SVG and PNG draw everything exactly. In PowerPoint and Figma, `open-diamond` becomes a filled
diamond and `bar` is dropped, each with a warning; `opacity` blends the fill only. `font-family` is
checked but not applied: text keeps the theme font. PowerPoint may warn that a PNG fallback for some
Kubernetes SVG icons could not be made; recent PowerPoint versions show the SVG anyway.

## Done when

- `spinagram check` reports 0 issues.
- The PNG shows no overlaps, clipped text or edges crossing boxes.
- Classes describe meaning (`security`, `async`), and colours live only in stylesheets.

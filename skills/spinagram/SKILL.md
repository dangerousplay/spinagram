---
name: spinagram
description: Author professional diagrams as code with spinagram (YAML or Python) and deliver them as SVG, PNG, editable PowerPoint and editable Figma. Use when asked to create, update or export flowcharts, decision trees, process/approval flows, swimlanes, today-vs-target comparisons, org/structure charts, matrices or tables-as-diagrams, especially for slide decks, studies or Figma. Covers layout grid, text fitting, edge routing, themes, icons, QA, and the Figma MCP (use_figma + upload_assets) hand-off. Not for data charts (bar/line) or auto-laid-out graphs of hundreds of nodes.
---

# spinagram: diagrams as code with editable outputs

You write a **spec** (YAML or Python). A **theme** directory supplies the brand. spinagram resolves both into one scene and renders it through backends: `svg`, `png`, `pptx`, `figma`.

```
spec (YAML/.py) + theme dir ──► layout (fonts, wrap, anchors) ──► svg · png · pptx · figma
```

## Workflow

1. **Message first.** State the single question the diagram answers. That becomes the `subtitle`, a full sentence with the conclusion. The `title` names the topic in 2–6 words.
2. **Pick a pattern** (table below) and sketch the grid on paper: columns, rows, gaps.
3. **Write the spec.** Use YAML for one-off diagrams. Use Python when you repeat geometry (`row`, `column`, `chain`) or generate diagrams from data.
4. **`spinagram check`** must report 0 issues (text overflow).
5. **Render PNG and look at it.** Check overlaps, arrows crossing text, label pills on borders, and empty zones. Fix the spec, never the output.
6. **Deliver.** Use `-f svg,png,pptx` for decks. Add `figma` and follow the Figma hand-off below.

```bash
spinagram render specs/ -t <theme-dir> -f svg,png,pptx,figma -o out/
spinagram check  specs/ -t <theme-dir>
spinagram render specs/ --only D04 -f png      # iterate on one
```

## Patterns

| Need | Pattern | Building blocks |
|---|---|---|
| Linear process | Row of 4–6 boxes and `chain` | `row()`, `chain()` |
| Decision | Diamonds with `yes`/`no` labels; branches leave from different sides | `kind: diamond`, side anchors |
| Today vs target | Two zones, paired cards, one arrow per pair | `zones`, mirrored `x` |
| Process + per-context detail | Row on top, table below | `tables` with an `icons` column |
| Lifecycle / loop | Clockwise ring; the dashed return arrow carries the loop condition | `dashed: true`, `via` |
| Org / governance | Tree top-down: global body on top, one row per level | `column()` per branch, `"a.bottom -> b.top"` |
| Approval scenario | Request → engine → policy box → parallel approvers → outcomes | `style` = semantic state |

## Diagram or UI mockup?

spinagram draws **diagrams**. For **product UI** such as an e-mail, a chat, a card or a screen, a diagram looks fake. Use an HTML page instead:

1. Build it with Tailwind at the slide size (1920×1080). Use the same header and footer as the diagram slides, and the theme's tokens, fonts and icons.
2. Screenshot it at 2x with Playwright.
3. Add the screenshot to the deck as a full-bleed picture slide.

Keep the real, implementable template (an e-mail HTML with inline CSS, or an Adaptive Card) next to it, so the mockup is never the only artifact.

## Layout rules

- **Canvas** is 1920×1080 with an 80 px side margin. Content goes in `y` 170–1000, between the header and the footer rule.
- **Use a grid.** Gaps between boxes are 28–40 in dense rows, 60–100 between steps and 40 between rows. Equal sizes inside a row.
- **Size boxes for text.** Allow at most 3 body lines. If `check` reports `overflow-y`, enlarge the box or cut text. Do not shrink the font below the theme default.
- **Icons** scale with box height (theme `icon_scale`, `icon_max`). Use `icon_size` only to make one emphasis node larger. Every box in a row has an icon, or none does.
- **One reading direction:** left→right for flows, top→bottom for hierarchies. Return arrows go dashed.
- **Layered landscape:** put the layer name in a left column (free `label`) and shift the boxes right. A zone label at the top collides with vertical arrows between layers.
- **Short vertical gaps:** put the edge label beside the line (`label_at` offset in x), not on it. Otherwise the pill hides the arrowhead.
- **Don't let tall boxes float text:** a 590 px box holding 8 lines reads as empty. Split the content into several boxes (one per source or route), or shrink the box to fit its text.
- **Leave white space.** If a zone is half empty, shrink it. Do not stretch cards to fill it.

## Text rules

- **One idea per box.** Titles have 1–4 words. The body is a short phrase, not a sentence list.
- **Numbers** in a diagram must come from the study/report sources. Put the source in `source:` (footer).
- **Same vocabulary across all diagrams in a set:** one term per concept.
- Edge labels are 1–2 words (`sim`, `não`, `afeta`, `reprovou`).

## Edges

- Prefer `"a -> b"` (sides auto-picked) or `"a.right -> b.left"`. Use `@0.3` to spread several edges leaving one side.
- Side-centre anchors become **bound connectors in PowerPoint**: moving a box drags the arrow. Off-centre (`@frac`), `via` and `curve` edges are drawn exactly but stay unbound.
- Route around boxes with `via: [[x, y], ...]`. Do not cross text. Place labels with `label_at` when the midpoint lands on a box.
- Colours are semantic: default = normal flow, alert/orange = risk path, gray = alternative or neutral.

## Styles (semantic, theme-mapped)

| Style | Use |
|---|---|
| `default` | Normal step |
| `dark` | Engine / central decision maker (one or two per diagram) |
| `soft` | Background grouping, decision diamonds |
| `warning` | Needs review / attention |
| `alert` | Risk, problem, blocking body (CAB, incident) |
| `neutral` | Outcome or side note |

## Numbers are facts

Never type a number from data into a spec. Write `{{fact_id}}` and declare `facts:` (plus `locale:`) in `_defaults.yaml`. Each fact must carry its `query` or `formula` and its `computed_at`.

- Forecasts are derived facts whose formula states the assumption, e.g. `0.3*crit_mudanca`.
- `spinagram facts` lists every fact used; `fontes.md` is the reviewer's document.
- Use `|raw` to get a plain number for CSS widths in HTML bar charts.

## Story decks

**HTML deck** (`spinagram deck deck.yaml -t <theme> [-o out.html]`): one self-contained page — cover
(title, subtitle, date, authors with photo and role), a full-colour divider per section, then one slide
per diagram (title band + one-line message + the diagram at full width). Fonts, logos, photos and
diagrams are embedded; printing gives one slide per page. `deck.yaml` lists `specs:` (dirs, relative to
the file), `authors:` and `sections: [{title, subtitle, slides: [{diagram: <id>, title, message}]}]`;
`image: svg` (vector, default) or `png` (smaller with many fonts). Colours and logos come from the
theme's `deck:` block (`accent`, `strong`, `deep`, `page`, `logo`, `logo_negative`).

For PowerPoint decks:

When the diagrams form a presentation:

- Keep a `deck.yaml` with sections, slide order and a `talk` line per slide; it becomes the speaker notes.
- Open with a cover and a roadmap. Close with a case exercise, the benefits and the asks.
- Slides not listed go to an appendix.

## YAML pitfalls

- **Quote values in flow mappings** (`{...}`) that contain `,`, `:`, `?` or `#`. For example, `text: "a, b, c"` or `title: ["Algum", "gatilho?"]`. Unquoted commas silently split the value; the loader now rejects the resulting unknown keys.
- `yes`, `no`, `on` and `off` are booleans in YAML; never use them unquoted as ids (the loader rejects them).
- `at: [x, y, w, h]` is shorthand for the four keys.
- A `_defaults.yaml` in the specs folder supplies keys every diagram shares (`kicker`, `source`).

## Live preview

While iterating, run `spinagram serve <specs> --theme <theme>` (extra `ui`): the browser re-renders on every
save, shows load/render errors inline, the theme token sheet (colour token names, styles) and the icon packs
(search names, fetch missing packs). Use it to pick tokens and icon names instead of guessing.

## Icon packs

Use `icon: "<pack>:<name>"` for vendor icons: `aws`, `gcp`, `azure`, `k8s`, `oci`, `openstack`, `terrastruct` are built in
and download on first use (`spinagram icons fetch`). Find names with `spinagram icons search <words>`;
short aliases exist for common services (`aws:s3`, `aws:alb`, `aws:kms`, `gcp:gke`, `azure:aks`, `k8s:pod`).
For general software architecture (languages, databases, caches, queues) use `terrastruct`:
`terrastruct:java|python|go|nodejs|react`, `terrastruct:postgres|mysql|mongo|redis|oracle`,
`terrastruct:kafka|sqs|sns|service-bus|pubsub`, `terrastruct:tech-server`, `terrastruct:db`. It has no
native Kafka/RabbitMQ logo: `kafka` maps to the AWS MSK icon.
Register a brand or extra set with `spinagram icons add <name> --dir|--zip|--npm|--github …`
(`--project` writes `./spinagram-icons.yaml`, shareable with the repo). Prefer SVG packs; PNG packs
(oci, openstack) carry a dark variant used automatically on dark fills.

**PNG → SVG:** with the `vector` extra, PNG icons (theme, spec paths, packs) become traced SVG when a
fidelity gate passes — crisper output and editable vectors in Figma (no PNG uploads). Check a set with
`spinagram vectorize <dir>`; disable with `SPINAGRAM_VECTORIZE=0` or `icons: {vectorize: false}`.

## Automatic layout (no coordinates)

For architecture views (Region › VPC › AZ) and flows, prefer `layout:` and `groups:` over hand-placed
coordinates. spinagram sizes and places everything, and each group is drawn as a zone.

- **Engine:**
  - `dot` for ranked flows and AWS views; it gives clean orthogonal routes.
  - `elk` for many edges crossing group borders.
  - `flex` (no dependencies) for grids of cards; add `route: ortho` for elbowed edges.
  - `d2` when you need D2's layouts.
- **Compare engines** before choosing: `spinagram render spec.yaml --layout dot|elk|flex|d2`.
- **Group hints for flex:** `direction` (row|column), `columns`, `gap`, `padding`, `align`. Sibling groups stretch to equal size.
- **Leave edges unanchored** (`a -> b`) so the engine routes them. An anchor (`a.right`) or `via` opts that edge out.
- **Mixed slides:** a legend or note with explicit `at:` stays where you put it; the auto content fills `layout.area`.
- **Hand-tuning:** `spinagram layout spec.yaml -o frozen.yaml` freezes the result; edit the frozen spec.
- `check` reports `layout: overflow` when the content does not fit. Change the direction, split the diagram or shorten titles.

## Groups with outlines (AWS-style)

Zone styles may declare `stroke`, `dashed`, `icon`, `radius`, `upper` and `fill: none`, which draws
cloud-provider groups the way AWS Architecture Icons do: an outline, no fill, the group icon flush in
the top-left corner and the label beside it (`d.zone("AZ 1a", ..., color="aws-az")`). Nest them
Account › Region › VPC › AZ; regional services (S3, KMS) sit inside the Region but outside the VPC.
Keep AZ labels short (`AZ 1a`) so arrows entering the boxes below do not cross them.

## Python DSL

```python
from spinagram import Diagram
d = Diagram("D01", "Release flow", subtitle="Evidence decides the path")
a, b, c = d.row(["Build", "Stress & chaos", "Risk gate"], x=80, y=220, w=440, h=220, gap=100,
                styles=[None, None, "dark"])
d.chain(a, b, c)
d.edge(c.bottom, d.box("Deploy", x=700, y=560, w=500, h=150).top, label="green")
diagram = d          # the CLI picks up `diagram`, `diagrams` or `build()`
```

Helpers next to the spec are importable (`from _layout import spread`); files starting with `_`
are not loaded as specs.

## Outputs

- **PowerPoint:** one slide per diagram, with native shapes and the text inside each shape. Tables are native, and the diagram `source` goes into the speaker notes. Viewers need the theme fonts installed.
- **Figma:**
  - **Scripts:** `out/figma/<slug>-NN.js` (run in order) and `<slug>.assets.json`.
    1. Load the `figma-use` skill.
    2. Run each script with `use_figma` (`fileKey` from the URL).
  - **Container:** the diagram becomes a frame (Design file), a slide (Slides file) or a section (FigJam board, `figma.com/board/...`) named `spinagram:<id>`. Re-running it rebuilds the content in place.
  - **FigJam:** edges whose both ends sit on box sides become native connectors attached to the boxes (they follow when a box moves); free edges stay vectors. Load the `figma-use-figjam` skill too.
  - **SVG icons** are rebuilt as editable vectors inside the script (`createNodeFromSvg`) — no upload. Only raster icons (PNG) need `upload_assets`.
  - **FigJam in one step:** `-f figjam` writes library-mode scripts, `figma/icons/` (every icon used),
    `icon-library.js` (finds the uploaded layers by file name) and a `README.md` with the order of calls.
  - **Icon library (recommended for many diagrams):** upload every distinct icon once with `upload_assets` (multipart, the file name becomes the layer name), run `icon_library_js({file: nodeId})` to rename them `dk-icon:<file>` inside a section `spinagram:icons`, then generate scripts with `FigmaBackend(library=True)` / `to_figma_js(scene, library=True)`: icons are cloned from the library — exact bytes, much smaller scripts (≈30 KB instead of 45 KB+ with inline SVG).
  - **FigJam gotchas:** connector endpoints use `magnet` (TOP/BOTTOM/LEFT/RIGHT) for side centres; `position` is in **pixels** from the node's top-left, not 0–1. Elbow routes are auto-computed — if one crosses a box, re-anchor that end to another side. `setPluginData` is not available in `use_figma` (placeholders carry ` · asset:<file>` in the layer name instead).
  - **Images:**
    - The script returns `imageTargets`.
    - Call `upload_assets(fileKey, count=n, nodeIds=[...])`.
    - POST each file listed in `assets.json` to its URL.
  - **Edges (Design/Slides):** drawn as vectors, because the connector node is FigJam-only.
- **SVG** is self-contained (fonts and images embedded). **PNG** is rendered at 2x (3840×2160) for slides.

## Themes

Use `extends: default` and override `colors` (tokens may alias tokens), `fonts` (with files, for metrics and embedding), `icons` (`dir` + `pattern` `{name}-{variant}.png`, variants per background tone), `styles.*` and `chrome` (bar, title, kicker template, footer logo). Keep brand themes **outside** the engine repository.

## Done when

- `check` reports 0 issues.
- The PNG has been reviewed: no overlap, no clipped text, and arrows do not cross labels.
- Requested formats are written. PPTX opens.
- The Figma scripts ran, or the hand-off steps were given to the user.

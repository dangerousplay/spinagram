# spinagram

Diagrams as code, delivered **editable** everywhere:

| Backend | Output |
|---|---|
| `svg` | Self-contained SVG with fonts and images embedded |
| `png` | 2x PNG rendered from the SVG (Playwright) |
| `pptx` | One slide per diagram. Native shapes with the text inside, connectors bound to their shapes (move a box and the arrows follow), native tables. SVG icons stay vectors (PowerPoint 365 `svgBlip`) with a PNG fallback for other readers (`SPINAGRAM_PPTX_SVG=raster` turns this off) |
| `figma` | Figma Plugin-API JavaScript, run through the Figma MCP `use_figma` tool to build native, editable nodes |
| `figjam` | FigJam board hand-off: one section per diagram, edges as native connectors bound to the boxes, icons cloned from an uploaded icon library (`figma/icons/`, `icon-library.js`, `README.md`) |

Diagrams are written in **YAML** or **Python**. A **theme** directory supplies colours, fonts, node styles, icons and page chrome, so the same diagram source renders in any brand.

## Install

```bash
uv tool install "spinagram[all] @ /path/to/spinagram"     # or: uv add --editable /path/to/spinagram[all]
# extras: pptx, png (Playwright), vector (vtracer + resvg-py: PNG icons → SVG)
uv run playwright install chromium                          # only for PNG
```

## YAML

```yaml
id: D01
title: How a change is routed
subtitle: Facts decide the path
nodes:
  - {id: req, x: 80, y: 220, w: 420, h: 300, title: Change request, text: Created by the source tool, icon: document}
  - {id: eng, x: 600, y: 220, w: 420, h: 300, style: dark, title: Risk engine}
  - {id: cab, kind: diamond, x: 1120, y: 260, w: 260, h: 220, title: [Business, impact?]}
edges:
  - req -> eng
  - "eng -> cab: classify"
  - {from: cab.bottom, to: [1250, 700], color: alert, dashed: true}
```

Edge shorthand is `"<from> -> <to>[: label]"`. An endpoint is either a node id, in which case the facing side is picked automatically, or `node.side[@frac]`, where side is one of `top|bottom|left|right|center` and `frac` is a position from 0 to 1 along that side.

## Python

```python
from spinagram import Diagram

d = Diagram("D01", "How a change is routed", subtitle="Facts decide the path")
req, eng, out = d.row(["Change request", "Risk engine", "Route"], x=80, y=220, w=420, h=300, gap=80,
                      styles=["default", "dark", "default"])
d.edge(req, eng)
d.edge(eng.right, out.left, label="classify")
d.save("out/", theme="path/to/theme", formats=["svg", "pptx"])
```

## CLI

```bash
spinagram render specs/ --theme ../my-theme -f svg,png,pptx,figma -o out/
spinagram check specs/ --theme ../my-theme        # text overflow report
spinagram render specs/ --layout elk -o out/     # override the layout engine of `layout:` specs
spinagram layout spec.yaml -o frozen.yaml         # freeze automatic positions
```

`render` writes `<id>-<slug>.{svg,png}`, one `diagrams.pptx` containing all slides, `figma/<id>.js` chunks and an `index.html` gallery.

## Facts: traceable numbers

Point a diagram, or a folder via `_defaults.yaml`, at a facts JSON file with `facts: path/to/facts.json` and `locale: pt-BR`. Then write numbers as `{{fact_id}}`, or `{{fact_id|pct1}}` to override the format, in any text.

A fact has `id`, `label`, `format`, and either a `value` or `source.formula` + `source.inputs`. Reviewers see these optional `source` keys: `system`, `query`, `review_url`, `computed_at`, `computation`, `classification`, `data`.

Every render records which element shows which fact:

| Output | Where the provenance appears |
|---|---|
| SVG | `<title>` tooltips, plus an embedded `<metadata>` block |
| PowerPoint | Speaker notes |
| Review files | `fontes.md` and `sources.json` |

CLI:

- `spinagram facts <specs>` lists every fact used, per diagram.
- An unknown fact id fails `check` and `render`.

HTML slides can use the same placeholders through `spinagram.facts.render_html`.

## Automatic layout

Add `layout:` to a diagram and leave out the coordinates. Nest nodes in `groups:`, such as an AWS Region,
a VPC and its availability zones, and spinagram sizes every node from its text and icon, places
everything and draws each group as a zone with its label and corner icon.

```yaml
layout: {engine: dot, direction: right}      # flex (default) | dot | elk | d2
groups:
  - id: region
    label: us-east-1
    style: aws-region                         # any zone style: aws-region, aws-vpc, aws-az, soft…
    children:
      - {id: az-a, label: us-east-1a, style: aws-az, children: [vault-1, consul-1]}
      - {id: az-b, label: us-east-1b, style: aws-az, children: [vault-2, consul-2]}
nodes:
  - {id: alb, title: ALB, icon: "aws:elastic-load-balancing-application-load-balancer"}
  - {id: vault-1, title: Vault 1, icon: vault}        # `in: az-a` on a node works too
edges: ["alb -> vault-1", "vault-1 -> consul-1"]
```

The full example is [`examples/aws_layout.yaml`](examples/aws_layout.yaml). In Python, use
`with d.group("us-east-1", style="aws-region"): ...`.

| Engine | Needs | Strengths |
|---|---|---|
| `flex` | nothing (pure Python) | Nested rows, columns and grids (`direction`, `columns`, `gap`, `padding`, `align` on a group). Deterministic. Edges are straight, or elbowed with `route: ortho`. |
| `dot` | Graphviz (`dot` on PATH) | Ranked flows. Clusters for groups. Orthogonal routes (`splines=ortho`). |
| `elk` | `bun` or `node`; `elkjs` is installed into the cache on first use | Layered layout with edges routed across group borders. Orthogonal routes. |
| `d2` | `d2` on PATH | D2's own layouts (`options: {layout: elk\|dagre\|tala}`). |

- **Engine options:** `layout.options` is passed to the engine unchanged, as ELK properties or dot graph attributes.
- **Comparing engines:** `--layout ENGINE` on `render`, `check` and `facts` overrides the spec's engine.
- **Mixed slides:** nodes with explicit `x`/`y` outside any group keep their position. Laid-out content goes into `layout.area: [x, y, w, h]`, which defaults to the canvas minus the margins and chrome. Anything that does not fit is reported by `check`.
- **Edge routes:** a route from the engine becomes the edge's `via`, bound to node sides. An edge you anchored (`a.right`) or routed (`via`) is left alone.
- **Hand-tuning:** `spinagram layout spec.yaml -o frozen.yaml` writes the computed positions as an explicit spec, which you can then tune by hand.
- **Your own engine:** an engine is a class with `name`, `available()` and `run(LGraph) -> LResult` (see `spinagram.autolayout.graph`), registered through the `spinagram.layouts` entry point.

## Themes

A theme is a directory containing `theme.yaml` plus its assets. Start with `extends: default` and override only what differs. See [`src/spinagram/themes/default/theme.yaml`](src/spinagram/themes/default/theme.yaml) for every key. Select a theme with `--theme DIR` or the `SPINAGRAM_THEME` environment variable.

## Backends

A backend is a class with `name`, `render(scenes, out_dir) -> list[Path]`, registered through the `spinagram.backends` entry point. Backends only read the resolved `Scene`, in which every colour is hex, fonts are resolved, text is pre-wrapped and coordinates are absolute. Adding an output format never touches layout or themes.

## Figma

`figma` writes `out/figma/<slug>-NN.js` plus `<slug>.assets.json`. Through the Figma MCP:

1. Run each `-NN.js` in order with `use_figma` against a Design or Slides file. The diagram becomes a frame (Design) or a slide (Slides) named `spinagram:<id>`. Re-running rebuilds its content in place and keeps the canvas position.
2. Images: `use_figma` cannot add image bytes, so the script draws placeholders and returns `imageTargets: [{nodeId, asset}]`. Call `upload_assets(fileKey, count=n, nodeIds=[...])`, then POST each file listed in `assets.json` to its returned URL.

Edges are vectors with arrow caps. Figma's Connector node exists only in FigJam.

## Development

```bash
uv sync --all-extras && uv run pytest
node tests/js/figma_mock.mjs out/figma/<slug>-01.js     # dry-run a Figma script on a mock Plugin API
```

Specs: `.specs/` (spec-driven: PROJECT, feature spec/design/tasks).

## Live UI

`spinagram serve` opens a local, read-only web UI with live reload (needs the `ui` extra:
`pip install 'spinagram[ui]'`; the web bundle ships in the wheel, no Node needed):

```bash
spinagram serve specs/ --theme ../my-theme          # http://127.0.0.1:8765, opens the browser
spinagram serve specs/ --layout elk --port 0 --no-open
```

- **Diagrams** — every spec under the paths; saving a spec, its `_defaults.yaml`, a `.py` helper or any file
  of the theme (including the themes it `extends`) re-renders in place, keeping zoom/pan. Errors show over
  the last good render. Wheel zooms, drag pans, `f` fits, `0` is 100 %; the header switches the layout
  engine for diagrams with `layout:`. Overflow, icon warnings and not-downloaded icon packs are flagged.
- **Themes** — token sheet of the built-in and active theme: colours (with the token they point to), font
  roles rendered in the embedded fonts, node/zone styles with previews, defaults and chrome.
- **Icon packs** — registry state, a searchable grid per downloaded pack and **Fetch** for missing ones.
  `serve` never downloads during a render (a missing pack is flagged with a link to fetch it).

Binds 127.0.0.1 only and rejects other `Host` headers. Frontend source: `web/` (React + TypeScript + Vite +
Tailwind CSS v4, built with bun): `bun install && bun run dev` (proxies `/api` to `serve --port 8765`),
`bun run build` rewrites `src/spinagram/ui/static/`.

## Icon packs

Vendor icon sets are downloaded on first use into `~/.cache/spinagram/icons` (override with
`SPINAGRAM_CACHE`; set `SPINAGRAM_OFFLINE=1` to never download) and referenced as `pack:name`:

```yaml
nodes:
  - {id: db, title: Orders DB, icon: "aws:rds"}
  - {id: gke, title: Cluster, icon: "gcp:gke"}
```

| Pack | Source | Format |
|---|---|---|
| `aws` | AWS Architecture Icons via the npm package `aws-icons` | SVG |
| `gcp` | Google Cloud official icons | SVG |
| `azure` | Azure public service icons V21 | SVG |
| `k8s` | kubernetes/community icons (`-labeled` variants too) | SVG |
| `oci` | Oracle Cloud icons from mingrammer/diagrams (dark variant on dark fills) | PNG |
| `openstack` | OpenStack project icons from mingrammer/diagrams | PNG |
| `terrastruct` | Terrastruct/D2 icon sheet: languages, databases, frameworks, dev tools, generic infra + cloud subset | SVG |

Names are kebab-case file names (`aws:amazon-ec2`), with short aliases (`aws:ec2`, `aws:s3`, `aws:alb`,
`gcp:gke`, `azure:aks`, …). For general software architecture use `terrastruct`: technologies by plain
name (`terrastruct:python`, `terrastruct:postgres`, `terrastruct:redis`, `terrastruct:kafka`, `terrastruct:sqs`),
generic glyphs by category (`terrastruct:tech-server`, `terrastruct:infra-firewall`, `terrastruct:db`).
See `examples/software_architecture.yaml`. Find names with `spinagram icons search <words>`.

```bash
spinagram icons list                       # packs, version, download state
spinagram icons fetch aws k8s              # pre-download (default: all)
spinagram icons search load balancer
spinagram icons add brand --dir ~/brand/icons                     # local folder
spinagram icons add tabler --npm @tabler/icons@3.19.0 --include 'package/icons/outline/*'
spinagram icons add mine --github org/repo@v1.2 --include 'svg/*' --project   # ./spinagram-icons.yaml
spinagram icons add corp --npm @team/icons@1.0.0 --registry https://artifactory.example/api/npm/npm-virtual/
spinagram icons import node_modules/@team/icons/spinagram-icons.yaml   # a package can ship its own descriptor
spinagram icons remove brand
```

A pack is YAML (built-ins in `src/spinagram/icon_packs/`): `source` (`zip` URL, `npm` package, `github`
repo/ref, `listing` (an index page: `url` + `pattern` regex naming each file), or local `dir`, plus `include` globs), `rules` (regex → name template, optional `tone: dark`
and `aliases`), `strip` (regexes that derive short aliases) and a curated `alias` map. Registries merge
built-in < `~/.config/spinagram/icons.yaml` < `./spinagram-icons.yaml` < `$SPINAGRAM_ICON_PACKS`.
A theme can map its own names onto packs: `icons: {alias: {ec2: "aws:ec2"}}`.

Vendor artwork keeps its owner's terms (each pack lists `license` and `homepage`).

## FigJam

`spinagram render specs/ -f figjam -o out/` writes, under `out/figma/`, library-mode scripts plus the
icon bundle. With the Figma MCP: `upload_assets` for every file in `icons/` (multipart, so each layer is
named after its file), run `icon-library.js` once, then each `<slug>-NN.js`. Details in the generated
`README.md`. FigJam reads connector positions in pixels, so edges anchored on a side centre become
`magnet` endpoints and everything else a pixel position.

## PNG → SVG icons

With the `vector` extra installed, PNG icons are traced into SVG automatically — theme icons, icons
referenced by path and PNG icon packs (`oci`, `openstack`). A traced icon is only used when it is
faithful: it is rendered back with resvg at the source size and compared over grey (mean Δ ≤ 8 and
≤ 1 % of pixels off by more than 128); photos and heavy gradients stay PNG. Results are cached by
content hash. PowerPoint gets the SVG with the original PNG as its fallback.

```bash
spinagram vectorize icons/ -o vector/      # batch, with a score table (--force writes rejects too)
SPINAGRAM_VECTORIZE=0 spinagram render …   # turn it off; or icons: {vectorize: false} in a theme / pack
```

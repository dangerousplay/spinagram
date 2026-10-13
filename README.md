<p align="center">
  <img src="https://dangerousplay.github.io/spinagram/assets/logo.svg" width="96" alt="spinagram logo">
</p>

<h1 align="center">spinagram</h1>

<p align="center">
  <b>Diagrams as code, delivered editable everywhere.</b><br>
  Write a few lines of Python. Get SVG, PNG, PowerPoint with native shapes, and Figma or FigJam nodes you can keep editing.
</p>

<p align="center">
  <a href="https://dangerousplay.github.io/spinagram/docs/"><b>Documentation</b></a> ·
  <a href="https://dangerousplay.github.io/spinagram/docs/getting-started/">Getting started</a> ·
  <a href="https://dangerousplay.github.io/spinagram/docs/python/">Python guide</a> ·
  <a href="examples/">Examples</a>
</p>

<p align="center">
  <a href="https://github.com/dangerousplay/spinagram/actions/workflows/ci.yml"><img src="https://github.com/dangerousplay/spinagram/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://dangerousplay.github.io/spinagram/"><img src="https://github.com/dangerousplay/spinagram/actions/workflows/docs.yml/badge.svg" alt="Docs"></a>
  <a href="https://pypi.org/project/spinagram/"><img src="https://img.shields.io/pypi/v/spinagram" alt="PyPI"></a>
</p>

![One source: Python or YAML, rendered by spinagram to SVG, PNG, PowerPoint and Figma](https://dangerousplay.github.io/spinagram/assets/overview.svg)

## Why spinagram

- **Editable output, not screenshots.** PowerPoint slides get native shapes with the text inside and
  connectors bound to the boxes, so moving a box drags its arrows along. Figma gets real frames and nodes.
- **Python that reads like the picture.** `users >> lb >> api`, groups as `with` blocks, loops and
  functions for the repetitive parts. YAML works too, for generated diagrams.
- **No coordinates needed.** spinagram sizes every box from its text and icon, nests groups such as an
  AWS Region, a VPC and its zones, and places everything with one of four layout engines.
- **Brand once, render anywhere.** A theme directory holds colours, fonts, styles, icons and page chrome.
- **Thousands of icons.** AWS, GCP, Azure, Kubernetes, OCI, OpenStack and Terrastruct packs download on
  first use. Add your own from a folder, npm or GitHub.
- **Built for reviews.** `spinagram check` catches text overflow, `spinagram serve` previews live, and
  numbers can come from a facts file with their provenance in every render.

## Quick start

```bash
pip install "spinagram[all]"            # or: uv add "spinagram[all]"
```

Say what is connected to what. spinagram sizes, places and styles everything:

```python
from spinagram import Diagram

d = Diagram("Q01", "Web app on AWS", subtitle="No coordinates, laid out automatically")

users = d.box("Users", icon="aws:users")
with d.group("us-east-1", style="aws-region", direction="right"):
    with d.group("VPC", style="aws-vpc", direction="right"):
        lb = d.box("Load balancer", icon="aws:alb")
        api = d.box("API", text="FastAPI on ECS", icon="terrastruct:python")
        with d.group():  # no style: a light "soft" zone
            db = d.box("Orders DB", text="PostgreSQL", icon="terrastruct:postgres")
            cache = d.box("Cache", text="Redis", icon="terrastruct:redis")
    s3 = d.box("Uploads", text="S3 bucket", icon="aws:s3")

users.to(lb, "HTTPS") >> api
api.to(db, "SQL")
api >> [cache, s3]

d.save("out/", formats=["svg", "png", "pptx"])
```

![Web app on AWS, laid out automatically](https://dangerousplay.github.io/spinagram/assets/quickstart.svg)

- `d.box(...)` adds a node; its size comes from its text and icon. No coordinates needed.
- `a >> b` draws an arrow, `a.to(b, "label")` a labelled one, `a >> [b, c]` fans out.
- `with d.group(...)` nests nodes in a zone (an AWS Region, a VPC, or any style from your theme).
- `d.save()` writes the files; in Jupyter the diagram shows inline. `spinagram serve file.py` previews it live.

<details>
<summary>The same diagram in YAML</summary>

```yaml
id: Q01
title: Web app on AWS
subtitle: No coordinates, laid out automatically
groups:
  - id: region
    label: us-east-1
    style: aws-region
    direction: right
    children:
      - id: vpc
        label: VPC
        style: aws-vpc
        direction: right
        children: [lb, api, data]
      - s3
  - {id: data, children: [db, cache]}
nodes:
  - {id: users, title: Users, icon: "aws:users"}
  - {id: lb, title: Load balancer, icon: "aws:alb"}
  - {id: api, title: API, text: FastAPI on ECS, icon: "terrastruct:python"}
  - {id: db, title: Orders DB, text: PostgreSQL, icon: "terrastruct:postgres"}
  - {id: cache, title: Cache, text: Redis, icon: "terrastruct:redis"}
  - {id: s3, title: Uploads, text: S3 bucket, icon: "aws:s3"}
edges:
  - "users -> lb: HTTPS"
  - lb -> api
  - "api -> db: SQL"
  - api -> cache
  - api -> s3
```

```bash
spinagram render examples/quickstart.yaml -f svg,png,pptx -o out/
```

</details>

Need pixel-exact slides instead? Give nodes coordinates
([manual layout](https://dangerousplay.github.io/spinagram/docs/manual-layout/)), or freeze an automatic layout with
`spinagram layout spec.py -o frozen.yaml` and tune it by hand.

## Flowcharts, state machines, activities and CSS

`Flowchart`, `StateMachine` and `Activity` builders add the symbols and verbs of behavior diagrams
(decisions, forks and joins, swimlanes, composite states) laid out by a built-in layered engine, and
`with d.state_machine(...)` puts one inside any diagram. A CSS subset styles everything:
`d.stylesheet("brand.css")`, `class_="critical"`, `edge.async { stroke-dasharray: 6 4 }`.
`spinagram check --styles` explains which rule set each value, `spinagram serve` has a click-to-inspect
styles panel and re-renders when a stylesheet is saved.
See [behavior diagrams](https://dangerousplay.github.io/spinagram/docs/behavior/),
[CSS styling](https://dangerousplay.github.io/spinagram/docs/styling/) and
[CSS by backend](https://dangerousplay.github.io/spinagram/docs/css-reference/) (what SVG, PowerPoint
and Figma do with each property). [`examples/showcase`](examples/showcase) has AWS, Kubernetes and Google Cloud
reference architectures styled only with CSS.

![Order fulfilment activity with swimlanes](https://dangerousplay.github.io/spinagram/assets/demo/b03.svg)

## Outputs

| Format | What you get |
|---|---|
| `svg` | Self-contained SVG with fonts and images embedded |
| `png` | 2x PNG rendered from the SVG |
| `pptx` | One slide per diagram with native shapes, bound connectors and native tables |
| `figma` | Figma Plugin-API scripts that build native, editable nodes |
| `figjam` | A FigJam board with connectors bound to the boxes |

## Learn more

The [documentation](https://dangerousplay.github.io/spinagram/docs/) (searchable) covers:

- [Automatic layout](https://dangerousplay.github.io/spinagram/docs/auto-layout/): groups and the `flex`, `dot`, `elk` and `d2` engines
- [Icon packs](https://dangerousplay.github.io/spinagram/docs/icons/) (AWS, Google Cloud, Azure, Kubernetes, CNCF projects, AI, about 2,000 technology logos, self-hosted and network gear) and [themes](https://dangerousplay.github.io/spinagram/docs/themes/)
- [Annotations](https://dangerousplay.github.io/spinagram/docs/annotations/): legends, numbered steps, callouts and designed notes
- [Facts](https://dangerousplay.github.io/spinagram/docs/facts/): numbers with traceable sources
- [Figma and FigJam](https://dangerousplay.github.io/spinagram/docs/figma/) hand-off
- [CLI](https://dangerousplay.github.io/spinagram/docs/cli/) and the [live UI](https://dangerousplay.github.io/spinagram/docs/live-ui/)
- [AI agent skills](https://dangerousplay.github.io/spinagram/docs/ai-skills/): `spinagram skills install --agent claude|codex|cursor|gemini|copilot|…` teaches your coding agent to write and style diagrams
- [Extending](https://dangerousplay.github.io/spinagram/docs/extending/) with your own backends and layout engines

## Development

```bash
uv sync --all-extras && uv run pytest
cd docs && bun install && bun run dev  # docs at http://localhost:3000
```

See [Development](https://dangerousplay.github.io/spinagram/docs/development/) for the UI frontend, docs and releases.

## Changelog and license

See [CHANGELOG.md](CHANGELOG.md) for what changed in each release. spinagram is released under the
[MIT License](LICENSE). Icon packs are downloaded from their upstream projects on first use and keep
their own licenses (listed by `spinagram icons list`).

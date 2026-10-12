<p align="center">
  <img src="https://dangerousplay.github.io/spinagram/assets/logo.svg" width="96" alt="spinagram logo">
</p>

<h1 align="center">spinagram</h1>

<p align="center">
  <b>Diagrams as code, delivered editable everywhere.</b><br>
  Write YAML or Python. Get SVG, PNG, PowerPoint with native shapes, and Figma or FigJam nodes you can keep editing.
</p>

<p align="center">
  <a href="https://dangerousplay.github.io/spinagram/"><b>Documentation</b></a> ·
  <a href="https://dangerousplay.github.io/spinagram/getting-started/">Getting started</a> ·
  <a href="examples/">Examples</a>
</p>

<p align="center">
  <a href="https://github.com/dangerousplay/spinagram/actions/workflows/ci.yml"><img src="https://github.com/dangerousplay/spinagram/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://dangerousplay.github.io/spinagram/"><img src="https://github.com/dangerousplay/spinagram/actions/workflows/docs.yml/badge.svg" alt="Docs"></a>
  <a href="https://pypi.org/project/spinagram/"><img src="https://img.shields.io/pypi/v/spinagram" alt="PyPI"></a>
</p>

![One source: YAML or Python, rendered by spinagram to SVG, PNG, PowerPoint and Figma](https://dangerousplay.github.io/spinagram/assets/overview.svg)

## Why spinagram

- **Editable output, not screenshots.** PowerPoint slides get native shapes with the text inside and
  connectors bound to the boxes, so moving a box drags its arrows along. Figma gets real frames and nodes.
- **No coordinates needed.** Add `layout:` and spinagram sizes every box from its text and icon, nests
  groups such as an AWS Region, a VPC and its zones, and places everything.
- **Brand once, render anywhere.** A theme directory holds colours, fonts, styles, icons and page chrome.
- **Thousands of icons.** AWS, GCP, Azure, Kubernetes, OCI, OpenStack and Terrastruct packs download on
  first use. Add your own from a folder, npm or GitHub.
- **Built for reviews.** `spinagram check` catches text overflow, `spinagram serve` previews live, and
  numbers can come from a facts file with their provenance in every render.

## Quick start

```bash
uv tool install "spinagram[all]"        # or: pip install "spinagram[all]"
```

Describe what is connected to what. spinagram does the layout. Pick YAML or Python, they produce the same diagram.

**YAML** ([`examples/quickstart.yaml`](examples/quickstart.yaml))

```yaml
id: Q01
title: Web app on AWS
subtitle: No coordinates, laid out automatically
layout: {engine: flex, direction: right, gap: 60}
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
        children: [alb, api, data]
      - s3
  - {id: data, direction: down, children: [db, cache]}
nodes:
  - {id: users, title: Users, icon: "aws:users"}
  - {id: alb, title: Load balancer, icon: "aws:alb"}
  - {id: api, title: API, text: FastAPI on ECS, icon: "terrastruct:python"}
  - {id: db, title: Orders DB, text: PostgreSQL, icon: "terrastruct:postgres"}
  - {id: cache, title: Cache, text: Redis, icon: "terrastruct:redis"}
  - {id: s3, title: Uploads, text: S3 bucket, icon: "aws:s3"}
edges:
  - "users -> alb: HTTPS"
  - "alb -> api"
  - "api -> db: SQL"
  - "api -> cache"
  - "api -> s3"
```

```bash
spinagram render examples/quickstart.yaml -f svg,png,pptx -o out/
```

**Python** ([`examples/quickstart.py`](examples/quickstart.py))

```python
from spinagram import Diagram

d = Diagram("Q01", "Web app on AWS", subtitle="No coordinates, laid out automatically",
            layout={"engine": "flex", "direction": "right", "gap": 60})
users = d.box("Users", icon="aws:users")
with d.group("us-east-1", style="aws-region", direction="right"):
    with d.group("VPC", style="aws-vpc", direction="right"):
        alb = d.box("Load balancer", icon="aws:alb")
        api = d.box("API", text="FastAPI on ECS", icon="terrastruct:python")
        with d.group(direction="down"):
            db = d.box("Orders DB", text="PostgreSQL", icon="terrastruct:postgres")
            cache = d.box("Cache", text="Redis", icon="terrastruct:redis")
    s3 = d.box("Uploads", text="S3 bucket", icon="aws:s3")

d.edge(users, alb, label="HTTPS")
d.chain(alb, api)
d.edge(api, db, label="SQL")
d.edge(api, cache)
d.edge(api, s3)

d.save("out/", formats=["svg", "png", "pptx"])
```

Result:

![Web app on AWS, laid out automatically](https://dangerousplay.github.io/spinagram/assets/quickstart.svg)

Need pixel-exact slides instead? Drop `layout:` and give nodes coordinates
([manual layout](https://dangerousplay.github.io/spinagram/manual-layout/)), or freeze an automatic layout
with `spinagram layout spec.yaml -o frozen.yaml` and tune it by hand.

## Outputs

| Format | What you get |
|---|---|
| `svg` | Self-contained SVG with fonts and images embedded |
| `png` | 2x PNG rendered from the SVG |
| `pptx` | One slide per diagram with native shapes, bound connectors and native tables |
| `figma` | Figma Plugin-API scripts that build native, editable nodes |
| `figjam` | A FigJam board with connectors bound to the boxes |

## Learn more

The [documentation](https://dangerousplay.github.io/spinagram/) covers:

- [Automatic layout](https://dangerousplay.github.io/spinagram/auto-layout/): groups and the `flex`, `dot`, `elk` and `d2` engines
- [Icon packs](https://dangerousplay.github.io/spinagram/icons/) and [themes](https://dangerousplay.github.io/spinagram/themes/)
- [Facts](https://dangerousplay.github.io/spinagram/facts/): numbers with traceable sources
- [Figma and FigJam](https://dangerousplay.github.io/spinagram/figma/) hand-off
- [CLI](https://dangerousplay.github.io/spinagram/cli/) and the [live UI](https://dangerousplay.github.io/spinagram/live-ui/)
- [Extending](https://dangerousplay.github.io/spinagram/extending/) with your own backends and layout engines

## Development

```bash
uv sync --all-extras && uv run pytest
uv run --group docs mkdocs serve        # docs at http://127.0.0.1:8000
```

See [Development](https://dangerousplay.github.io/spinagram/development/) for the UI frontend, docs and releases.

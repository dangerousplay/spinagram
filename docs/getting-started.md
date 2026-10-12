# Getting started

## Install

spinagram needs Python 3.11 or newer.

```bash
uv tool install "spinagram[all]"     # CLI on your PATH
uv add "spinagram[all]"              # or as a project dependency
pip install "spinagram[all]"         # or with pip
```

The base package renders SVG. Extras add the other outputs:

| Extra | Adds |
|---|---|
| `pptx` | PowerPoint backend (`python-pptx`) |
| `png` | PNG backend (Playwright); also run `playwright install chromium` |
| `vector` | Traces PNG icons into SVG (`vtracer`, `resvg-py`) |
| `ui` | `spinagram serve`, the live-reload web UI |
| `all` | Everything above |

The [automatic layout](auto-layout.md) engine `flex` is pure Python. The optional `dot`, `elk` and
`d2` engines need Graphviz, `bun`/`node` or `d2` on your `PATH`.

## Render a diagram

Save this as `web.yaml`:

```yaml
--8<-- "examples/quickstart.yaml"
```

Then render it:

```bash
spinagram render web.yaml -f svg,png,pptx -o out/
```

`out/` now holds `Q01-web-app-on-aws.svg`, its PNG, a `diagrams.pptx` with one slide per diagram and
an `index.html` gallery. Icon packs used by the diagram (`aws`, `terrastruct`) are downloaded into
`~/.cache/spinagram/icons` on first use.

## The same diagram in Python

```python
--8<-- "examples/quickstart.py"
```

Python specs render with the CLI too: `spinagram render` picks up any `*.py` that defines a
module-level `diagram`, a list in `diagrams`, or a `build()` function that returns either.

## Iterate

```bash
spinagram check web.yaml           # report text overflow and layout issues
spinagram serve .                  # live preview that re-renders on save
```

## Where next

- [Automatic layout](auto-layout.md): groups, engines and hand-tuning.
- [Manual layout](manual-layout.md): exact coordinates, anchors, tables and legends.
- [Icon packs](icons.md) and [themes](themes.md).

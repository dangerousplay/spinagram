# CLI

```bash
spinagram render specs/ --theme ../my-theme -f svg,png,pptx,figma -o out/
spinagram check specs/ --theme ../my-theme        # text overflow and layout report
spinagram facts specs/                             # facts used, per diagram
spinagram layout spec.yaml -o frozen.yaml          # freeze automatic positions
spinagram serve specs/                             # live-reload UI
spinagram icons search load balancer               # icon pack management
spinagram vectorize icons/ -o vector/              # trace PNG icons into SVG
spinagram deck deck.yaml -o slides.html            # HTML presentation
```

`paths` are spec files or directories (`*.yaml`, `*.py`). A `_defaults.yaml` in a directory sets
defaults for every spec in it.

| Option | Commands | Meaning |
|---|---|---|
| `-t, --theme` | render, check, facts, layout, deck, serve | Theme directory or built-in name (env `SPINAGRAM_THEME`) |
| `--only ID...` | render, check, facts, layout | Diagram ids to include |
| `--layout ENGINE` | render, check, facts, layout, serve | Engine for specs with `layout:` (`flex`, `dot`, `elk`, `d2`; env `SPINAGRAM_LAYOUT`) |
| `-f, --formats` | render | Comma list from `svg`, `png`, `pptx`, `figma`, `figjam` |
| `-o, --out` | render, layout, vectorize, deck | Output directory or file |
| `--no-gallery` | render | Skip `index.html` |

## Environment variables

| Variable | Effect |
|---|---|
| `SPINAGRAM_THEME` | Default theme |
| `SPINAGRAM_LAYOUT` | Default layout engine override |
| `SPINAGRAM_CACHE` | Cache directory for icon packs (default `~/.cache/spinagram`) |
| `SPINAGRAM_OFFLINE=1` | Never download icon packs |
| `SPINAGRAM_ICON_PACKS` | Extra icon pack registry file |
| `SPINAGRAM_VECTORIZE=0` | Do not trace PNG icons into SVG |
| `SPINAGRAM_PPTX_SVG=raster` | PowerPoint gets PNG icons only |

# Development

```bash
git clone https://github.com/dangerousplay/spinagram && cd spinagram
uv sync --all-extras && uv run pytest
uv run ruff check src tests examples
node tests/js/figma_mock.mjs out/figma/<slug>-01.js     # dry-run a Figma script on a mock Plugin API
```

Feature specs live in `.specs/` (spec-driven: project, then spec, design and tasks per feature).

## Live UI frontend

Source is in `web/` (React + TypeScript + Vite + Tailwind CSS v4, built with bun):

```bash
cd web
bun install && bun run dev      # proxies /api to `spinagram serve --port 8765`
bun run build                   # rewrites src/spinagram/ui/static/
```

CI fails if the committed bundle is stale.

## Docs

This site is built with MkDocs Material from `docs/` and deployed to GitHub Pages on every push to
`main`:

```bash
uv run --group docs mkdocs serve
```

The diagrams on these pages are rendered by spinagram itself:

```bash
spinagram render docs/diagrams/ examples/quickstart.yaml -f svg -o out/
cp out/S00-spinagram.svg docs/assets/overview.svg
cp out/Q01-web-app-on-aws.svg docs/assets/quickstart.svg
```

## Releasing

```bash
uv version --bump minor && git commit -am "Release v$(uv version --short)"
git tag "v$(uv version --short)" && git push --follow-tags
```

The tag triggers CI, publishes to PyPI with trusted publishing and creates a GitHub release.

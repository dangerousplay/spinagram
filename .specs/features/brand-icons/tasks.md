# AI, CNCF and Technology Logo Packs Tasks

**Design**: inline (pack YAML + two indexer changes; see spec assumptions)
**Status**: Done

## Gate Check Commands

| Gate Level | Command |
| ---------- | ------- |
| Quick | `uv run pytest tests/test_brand_icon_packs.py tests/test_icon_packs.py -q` |
| Build | `uv run ruff check src tests && uv run pytest -q && uv run spinagram check examples/showcase` |

## Task Breakdown

### T1: `current_color` and alias-through-alias in the indexer
**Where**: `src/spinagram/icons.py` · **Requirement**: BRAND-04, BRAND-05, BRAND-06
- [x] `currentColor` SVGs painted per tone, dark copy added when missing; curated alias may target a derived alias

### T2: GitHub source quotes paths and skips unnamed files
**Where**: `src/spinagram/icons.py` · **Requirement**: BRAND-17, BRAND-18
- [x] `cncf/artwork` has a file name with a space (it failed the first fetch with `InvalidURL`); half its files are
      PNG copies no rule names (the fetch fell from ~2 to ~1.3 minutes)

### T3: `ai`, `cncf` and `logos` packs
**Where**: `src/spinagram/icon_packs/{ai,cncf,logos}.yaml` · **Requirement**: BRAND-01..03, BRAND-07..16
- [x] Naming dry-run over the real upstream trees: ai 948 icons, cncf 1,344 (665 with a dark tone), logos 1,990
- [x] Real fetch of all three packs; every requested brand resolves

### T4: Catalog inference
**Where**: `src/spinagram/metadata.py` · **Requirement**: BRAND-19
- [x] `ai` and `cncf` providers

### T5: Showcase, docs, skill, README
**Where**: `examples/showcase/delivery_ai.{py,css}`, `docs/content/docs/{icons,python}.mdx`,
`src/spinagram/agent_skills/spinagram/SKILL.md`, `README.md` · **Requirement**: BRAND-20, BRAND-21
- [x] PNG reviewed: dark tiles draw white artwork; `spinagram check` 0 issues

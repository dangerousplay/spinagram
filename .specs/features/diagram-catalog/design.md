# Diagram Catalog Design

**Spec**: `.specs/features/diagram-catalog/spec.md`
**Status**: Approved

---

## Architecture Overview

Metadata lives on the core `Diagram` model; one pure module derives the *effective* tags and category
(declared + inferred from icons). The CLI and the live UI server both read that module, so a diagram
groups the same way everywhere. The web UI receives effective metadata from `/api/workspace` and does
searching, grouping and recents client-side in pure, unit-tested functions.

```mermaid
graph TD
    PY[Python spec: Diagram category=, tags=] --> M[model.Diagram category, tags]
    YAML[YAML spec + _defaults.yaml] --> L[yaml_io loaders] --> M
    M --> MD[metadata.py effective_tags / effective_category / matches]
    MD --> CLI[cli _collect --tag --category]
    MD --> WS[ui/workspace summary: category, tags, subtitle]
    WS --> API[/api/workspace]
    API --> CAT[web catalog.ts filter / group / recents]
    CAT --> DP[DiagramsPage cards + search + chips]
    CAT --> SB[Recents sidebar]
    NAV[Navbar: Diagrams, Themes, Icon packs, Docs] --> ROUTES[hooks.ts routes]
```

Approach chosen: compute effective metadata in Python (shared by CLI and server). The alternative,
inferring in the browser, would leave the CLI filter without inference and duplicate icon parsing in TS.

---

## Code Reuse Analysis

### Existing Components to Leverage

| Component | Location | How to Use |
| --------- | -------- | ---------- |
| `Diagram` dataclass | `src/spinagram/model.py:229` | Add `category`, `tags` fields |
| `from_dict`, `load_yaml.merged`, `load_python` folder defaults | `src/spinagram/yaml_io.py:46,118,138` | Read keys; merge folder `category`/`tags` like `stylesheets` |
| `_collect` | `src/spinagram/cli.py:16` | Add tag/category filtering beside `--only` |
| `Workspace.summary` | `src/spinagram/ui/workspace.py:317` | Emit `category`, `tags`, `subtitle` per diagram |
| `api.diagram` SVG endpoint | `src/spinagram/ui/server.py:148` | Card thumbnails via `<img src>` (cached per workspace) |
| Route hash parsing | `web/src/hooks.ts` | Extend with section index routes |
| `NavLink`, `Section`, `Empty` | `web/src/App.tsx` | Reuse styling for navbar, sidebar, pages |
| Theme/pack views | `web/src/ThemeView.tsx`, `web/src/PackView.tsx` | Unchanged; index pages link to them |

### Integration Points

| System | Integration Method |
| ------ | ------------------ |
| `/api/workspace` | Additive fields per diagram entry; old clients ignore them |
| SSE `workspace` / `diagram` events | Existing reload path refreshes cards (thumbnail URL carries a rev) |
| Static bundle | `cd web && bun run build` writes `src/spinagram/ui/static` (committed, ships in wheel) |

---

## Components

### Diagram metadata fields

- **Purpose**: Hold declared category and normalised tags.
- **Location**: `src/spinagram/model.py`
- **Interfaces**: `Diagram(..., category: str | None = None, tags: list[str] | str = [])`; normalised in `__post_init__` through `normalize_tags(value, where) -> list[str]` (raises `ValueError` naming the diagram and key).
- **Reuses**: dataclass defaults.

### Loader support

- **Purpose**: YAML keys `category`, `tags`; folder defaults for YAML and Python specs.
- **Location**: `src/spinagram/yaml_io.py`
- **Interfaces**: unchanged public API; `_dir_defaults` keys `category` (fill if unset) and `tags` (union).

### metadata module

- **Purpose**: Effective metadata and filters.
- **Location**: `src/spinagram/metadata.py`
- **Interfaces**:
  - `PROVIDERS: dict[str, tuple[str, str]]` pack prefix → (tag, display name)
  - `provider_counts(d) -> Counter[str]` icon references per provider tag (nodes, groups, zones; `aws-*` styles)
  - `effective_tags(d) -> list[str]` sorted union of declared and provider tags
  - `effective_category(d) -> str` declared, else dominant provider display name, else `""`
  - `matches(d, tags, category) -> bool` AND over tags, case-insensitive category
- **Dependencies**: model only (no theme, no icon download).

### CLI filters

- **Location**: `src/spinagram/cli.py`
- **Interfaces**: `--tag T` (repeatable) and `--category C` on render, check, facts, layout; `_collect(paths, only, tags, category)`.

### Workspace summary

- **Location**: `src/spinagram/ui/workspace.py`
- **Interfaces**: each diagram entry gains `subtitle`, `category`, `tags`.

### catalog.ts (pure UI logic)

- **Location**: `web/src/catalog.ts`
- **Interfaces**:
  - `matchesQuery(d, query) -> boolean`, `filterDiagrams(list, query, tags) -> DiagramRef[]`
  - `groupByCategory(list) -> {category: string, label: string, diagrams}[]` sorted, "Uncategorised" last
  - `allTags(list) -> {tag, count}[]`
  - `pushRecent(keys, key, max = 10) -> string[]`, `visibleRecents(keys, known) -> string[]`
  - `recentStore(storage?)` with `load()/save()` that never throws (in-memory fallback)

### Routes

- **Location**: `web/src/hooks.ts`
- **Interfaces**: `Route` adds `{kind: "diagrams"}`, `{kind: "themes"}`, `{kind: "packs"}`; `#/` → diagrams, `#/t` → themes index, `#/p` → packs index; `parse`/`href` exported for tests.

### App shell

- **Location**: `web/src/App.tsx`
- **Purpose**: Top navbar (Diagrams, Themes, Icon packs, Docs ↗), left recents sidebar, themes and packs index pages, records recents on diagram open.

### DiagramsPage

- **Location**: `web/src/DiagramsPage.tsx`
- **Purpose**: Search box, tag chips, category sections of cards (lazy `<img>` thumbnail, id, title, tags), empty state with "Clear filters", spec-file errors.

---

## Data Models

```typescript
type DiagramRef = {
  key: string; id: string; title: string; auto: boolean;
  subtitle: string | null; category: string; tags: string[];   // new
};
```

```python
PROVIDERS = {"aws": ("aws", "AWS"), "gcp": ("gcp", "Google Cloud"), "k8s": ("kubernetes", "Kubernetes"),
             "azure": ("azure", "Azure"), "oci": ("oci", "OCI"), "openstack": ("openstack", "OpenStack")}
```

---

## Error Handling Strategy

| Error Scenario | Handling | User Impact |
| -------------- | -------- | ----------- |
| `tags: 5`, `category: [x]` | `ValueError("<id>: tags must be a list of strings")` | Spec load error (CLI exit 2; UI shows file error) |
| localStorage throws / unavailable | `recentStore` falls back to memory | Recents last for the session |
| Recent key no longer in workspace | `visibleRecents` drops it | Not shown |
| Thumbnail render fails | `<img onError>` shows "preview unavailable" | Card still opens diagram |
| No match | Empty state + "Clear filters" | User resets in one click |

---

## Risks & Concerns

| Concern | Location (file:line) | Impact | Mitigation |
| ------- | -------------------- | ------ | ---------- |
| Thumbnails render every diagram on first visit | `src/spinagram/ui/workspace.py:262` | CPU burst on large workspaces | `loading="lazy"` images; workspace render cache already keys by diagram |
| `App.tsx` mixes routing, events and nav | `web/src/App.tsx:11` | Growing component | Move pages into own files (DiagramsPage); keep App as shell |
| No JS unit test runner | `web/package.json` | UI logic untested | `bun test` (built in) for `catalog.ts`/`hooks.ts`; a pytest wrapper runs it when bun exists |
| Python `Diagram` is constructed positionally in places | `src/spinagram/model.py:229` | New fields could shift args | Add fields after existing ones with defaults |

---

## Tech Decisions

| Decision | Choice | Rationale |
| -------- | ------ | --------- |
| Grouping field name | `category` | Avoids collision with layout `group`/`groups` (user confirmed) |
| JS tests | `bun test` | Already the UI toolchain; zero new dependencies |
| Search location | Client-side over `/api/workspace` | Workspace is small and already loaded; instant filtering |

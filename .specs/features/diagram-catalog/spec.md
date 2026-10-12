# Diagram Catalog Specification

## Problem Statement

A workspace with dozens of diagrams is a flat file list in `spinagram serve`: finding "the GKE one" means
scanning paths. Diagrams carry no metadata to group or filter by, so neither the UI nor the CLI can answer
"show me the AWS diagrams". Authors want to tag diagrams, see them grouped (AWS, Google Cloud, Kubernetes…)
and search them, and the UI navigation should match: recent diagrams on the left, sections in a top navbar.

## Goals

- [ ] Every diagram exposes a category and tags, declared by the author or inferred from its icons, so
      existing diagrams group by cloud provider with zero edits.
- [ ] In the live UI, a user finds a diagram by typing part of its id, title, tag or category, browsing
      thumbnail cards grouped by category.
- [ ] The CLI renders or checks a subset with `--tag` / `--category`.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Editing metadata from the UI | The UI is read-only by design (live-ui spec) |
| Full-text search inside node text | Metadata search answers "which diagram"; node search is a later idea |
| Bundling the docs site in the wheel | User chose the online docs link |
| Metadata in the static `render` gallery (`index.html`) | Separate surface; can reuse the same fields later |
| Server-side persistence of recent diagrams | Recents are a per-viewer convenience |
| Tags inferred from `terrastruct:` icons | Generic pack; its vendor subset is ambiguous |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Name of the grouping field | `category` (YAML key, Python argument, API field) | `group`/`groups` already mean layout zones (`d.group()`, YAML `groups:`); reusing it would collide | y |
| Groupings without metadata | Inferred provider tags from icon packs; category = dominant provider | User chose "declared + inferred" | y |
| Provider tags | Icon pack prefix → tag: `aws`→`aws`, `gcp`→`gcp`, `k8s`→`kubernetes`, `azure`→`azure`, `oci`→`oci`, `openstack`→`openstack`; AWS group styles (`aws-*`) count as `aws` | The six vendor packs that ship with spinagram | n |
| Provider display names | `aws` "AWS", `gcp` "Google Cloud", `kubernetes` "Kubernetes", `azure` "Azure", `oci` "OCI", `openstack` "OpenStack" | Vendor names as the docs use them | n |
| Dominant provider | Most icon references; a tie goes to the alphabetically first tag | Deterministic; GCP01 uses one `k8s:` icon among ten `gcp:` ones and must land in Google Cloud | n |
| Tag normalisation | Trimmed, lower-cased, de-duplicated, sorted | Case-insensitive matching without surprises | n |
| Folder defaults | `_defaults.yaml` `category` fills an unset category; `tags` are merged (folder + spec) | Same rule as `stylesheets` | n |
| Results view | Thumbnail cards (live SVG) per category section | User choice | y |
| Docs navbar item | Opens `https://dangerousplay.github.io/spinagram/docs/` in a new tab | User choice | y |
| CLI filter | `--tag` (repeatable, all must match) and `--category` on render, check, facts, layout | User choice; AND matches "narrow down" | y |
| Recent diagrams | Last 10 opened, per browser (localStorage), newest first | Per-viewer convenience; no server state | n |
| Search matching | Case-insensitive; every whitespace-separated term must match id, title, subtitle, category or a tag | Predictable narrowing as you type | n |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Diagram metadata ⭐ MVP

**User Story**: As a diagram author, I want to give a diagram a category and tags in Python or YAML so that
tools can group and filter it.

**Why P1**: Everything else reads these fields.

**Acceptance Criteria**:

1. WHEN a Python spec builds `Diagram(id, title, category="Networking", tags=["aws", "Hub"])` THEN the diagram SHALL report category `Networking` and declared tags `["aws", "hub"]`.
2. WHEN a YAML spec sets `category: Networking` and `tags: [aws, Hub]` THEN the loaded diagram SHALL report the same category and tags as META-01.
3. IF `tags` is not a list of strings or a single string, or `category` is not a string, THEN loading SHALL fail with an error naming the diagram id and the key.
4. WHEN `tags` is a single string THEN it SHALL be treated as a one-element list.
5. WHEN `_defaults.yaml` sets `category` and the spec does not THEN the diagram SHALL take the folder category, for YAML and Python specs.
6. WHEN `_defaults.yaml` and the spec both set `tags` THEN the diagram's declared tags SHALL be the normalised union of both.
7. The system SHALL normalise tags by trimming, lower-casing, de-duplicating and sorting them.

**Independent Test**: load a YAML and a Python spec with metadata and a `_defaults.yaml`; assert the fields.

---

### P1: Inferred provider tags and category ⭐ MVP

**User Story**: As a user with existing diagrams, I want AWS, Google Cloud and Kubernetes diagrams grouped
without editing them.

**Why P1**: The user asked for these groupings; inference makes them work on day one.

**Acceptance Criteria**:

1. WHEN a diagram's nodes, groups or zones use icons from the `aws`, `gcp`, `k8s`, `azure`, `oci` or `openstack` packs THEN its effective tags SHALL include the matching provider tags (`aws`, `gcp`, `kubernetes`, `azure`, `oci`, `openstack`) in addition to its declared tags.
2. WHEN a group or zone uses an `aws-*` style THEN the diagram's effective tags SHALL include `aws`.
3. WHEN a diagram declares no category and uses provider icons THEN its effective category SHALL be the display name of the dominant provider (most icon references; ties to the alphabetically first tag).
4. WHEN a diagram declares a category THEN its effective category SHALL be the declared one, regardless of icons.
5. WHEN a diagram declares no category and uses no provider icons THEN its effective category SHALL be empty (shown as "Uncategorised").

**Independent Test**: the five `examples/showcase` diagrams report categories AWS, AWS, Kubernetes, Kubernetes, Google Cloud with no metadata in their source.

---

### P1: Search and grouped browsing in the live UI ⭐ MVP

**User Story**: As a user of `spinagram serve`, I want a Diagrams page where I type to filter and see cards
grouped by category, so that I find a diagram in seconds.

**Why P1**: The user-facing goal of the feature.

**Acceptance Criteria**:

1. WHEN the UI requests `/api/workspace` THEN each diagram entry SHALL include `category` (effective, possibly empty), `tags` (effective, sorted) and `subtitle`.
2. WHEN the user opens the Diagrams page THEN the UI SHALL show one section per effective category, sorted by name with "Uncategorised" last, each holding a card per diagram with a thumbnail, id, title and tags.
3. WHEN the user types in the search box THEN the UI SHALL show only diagrams where every whitespace-separated term matches (case-insensitive substring) the id, title, subtitle, category or a tag.
4. WHEN the user selects one or more tag chips THEN the UI SHALL show only diagrams carrying every selected tag.
5. IF no diagram matches THEN the UI SHALL show "No diagrams match" with a control that clears the search and chips.
6. WHEN the user clicks a card THEN the UI SHALL open that diagram's view.
7. IF a spec file fails to load THEN the Diagrams page SHALL list it with its error instead of cards.

**Independent Test**: serve `examples/showcase`, type "kube", see the two Kubernetes cards under "Kubernetes".

---

### P1: Navbar and recent diagrams ⭐ MVP

**User Story**: As a UI user, I want sections in a top navbar and my recent diagrams on the left.

**Why P1**: The requested navigation; the old sidebar mixed three lists.

**Acceptance Criteria**:

1. The UI SHALL show a top navbar with Diagrams, Themes, Icon packs and Docs, highlighting the active section.
2. WHEN the user clicks Docs THEN the UI SHALL open `https://dangerousplay.github.io/spinagram/docs/` in a new tab.
3. WHEN the user opens Themes or Icon packs THEN the UI SHALL list every theme or pack on that page, linking to the existing theme sheet or pack view.
4. WHEN the user opens a diagram THEN the UI SHALL record it as the most recent entry, keeping at most 10 entries without duplicates.
5. The UI SHALL show the recent diagrams in a left sidebar, newest first, on every section.
6. IF a recent entry's diagram is no longer in the workspace THEN the sidebar SHALL omit it.
7. IF browser storage is unavailable THEN the UI SHALL keep recents for the session only and SHALL NOT fail.
8. WHEN the UI starts with no route THEN it SHALL show the Diagrams page.

**Independent Test**: open three diagrams, reload: they appear newest first on the left; Docs opens the site.

---

### P2: CLI filtering by metadata

**User Story**: As a CLI user, I want `spinagram render specs/ --tag aws` to process only matching diagrams.

**Why P2**: Useful for builds; the UI goal stands without it.

**Acceptance Criteria**:

1. WHEN `--tag T` is given (repeatable) to render, check, facts or layout THEN only diagrams whose effective tags include every given tag (case-insensitive) SHALL be processed.
2. WHEN `--category C` is given THEN only diagrams whose effective category equals C (case-insensitive) SHALL be processed.
3. WHEN `--only`, `--tag` and `--category` are combined THEN a diagram SHALL be processed only if it satisfies all of them.
4. IF no diagram matches THEN the command SHALL exit with "no diagrams found" (the existing behaviour).

**Independent Test**: `spinagram check examples/showcase --category kubernetes` reports 2 diagrams; `--tag kubernetes` reports 3 (GCP01 also uses a `k8s:` icon, META-08).

---

## Edge Cases

- IF a tag is empty after trimming THEN it SHALL be dropped.
- WHEN the same diagram is opened twice in a row THEN recents SHALL hold it once.
- WHEN the workspace changes on disk THEN the Diagrams page SHALL refresh through the existing `workspace` event.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| META-01 | P1: Metadata - Python fields | Tasks | Implementing |
| META-02 | P1: Metadata - YAML keys | Tasks | Implementing |
| META-03 | P1: Metadata - type validation | Tasks | Implementing |
| META-04 | P1: Metadata - single-string tags | Tasks | Implementing |
| META-05 | P1: Metadata - folder category | Tasks | Implementing |
| META-06 | P1: Metadata - folder tags merge | Tasks | Implementing |
| META-07 | P1: Metadata - normalisation | Tasks | Implementing |
| META-08 | P1: Inference - provider tags from icons | Tasks | Implementing |
| META-09 | P1: Inference - aws-* styles | Tasks | Implementing |
| META-10 | P1: Inference - dominant category | Tasks | Implementing |
| META-11 | P1: Inference - declared category wins | Tasks | Implementing |
| META-12 | P1: Inference - uncategorised | Tasks | Implementing |
| META-13 | P1: UI - workspace API fields | Tasks | Implementing |
| META-14 | P1: UI - grouped cards | Tasks | Implementing |
| META-15 | P1: UI - text search | Tasks | Implementing |
| META-16 | P1: UI - tag chips | Tasks | Implementing |
| META-17 | P1: UI - empty result | Tasks | Implementing |
| META-18 | P1: UI - card opens diagram | Tasks | Implementing |
| META-19 | P1: UI - file errors listed | Tasks | Implementing |
| META-20 | P1: Nav - navbar sections | Tasks | Pending |
| META-21 | P1: Nav - docs link | Tasks | Pending |
| META-22 | P1: Nav - themes and packs pages | Tasks | Pending |
| META-23 | P1: Nav - record recents | Tasks | Implementing |
| META-24 | P1: Nav - recents sidebar | Tasks | Pending |
| META-25 | P1: Nav - stale recents omitted | Tasks | Implementing |
| META-26 | P1: Nav - storage unavailable | Tasks | Implementing |
| META-27 | P1: Nav - default route | Tasks | Implementing |
| META-28 | P2: CLI - --tag | Tasks | Implementing |
| META-29 | P2: CLI - --category | Tasks | Implementing |
| META-30 | P2: CLI - combined filters | Tasks | Implementing |
| META-31 | P2: CLI - no match | Tasks | Implementing |

**Coverage:** 31 total, 31 mapped to tasks, 0 unmapped

---

## Success Criteria

- [ ] `spinagram serve examples/showcase` groups the five diagrams under AWS, Google Cloud and Kubernetes with no source edits.
- [ ] Typing a term in the search box narrows the cards within one keystroke render.
- [ ] `spinagram check examples/showcase --category kubernetes` processes exactly 2 diagrams.

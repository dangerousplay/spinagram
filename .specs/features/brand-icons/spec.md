# AI, CNCF and Technology Logo Packs Specification

## Problem Statement

Platform and delivery diagrams name GitLab, JFrog, Oracle, Harbor, Argo CD and, more and more, the AI stack
(OpenAI, Claude, Ollama, MCP). spinagram covers some of them through `selfhosted`, a homelab set, but has no
CNCF project artwork, thin AI coverage and no general technology set. Authors fall back to files they manage by
hand. Three built-in packs should cover them.

## Goals

- [x] `ai:openai`, `ai:claude`, `ai:claude-code`, `ai:ollama`, `ai:mcp` and about 950 more AI logos resolve, and
      monochrome marks stay visible on dark fills.
- [x] `cncf:harbor`, `cncf:argo`, `cncf:prometheus`, `cncf:otel` and every other CNCF project resolve, with the
      project's white artwork on dark fills.
- [x] `logos:gitlab`, `logos:jfrog`, `logos:oracle`, `logos:jenkins` and about 2,000 more technology logos resolve.
- [x] Diagrams using `ai:` and `cncf:` group in the catalog, and the showcase draws a delivery platform with them.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Simple Icons | 3,000+ marks, but one colour each and no artwork for dark fills beyond recolouring; `logos` covers the brands in colour |
| devicon | Overlaps `logos` and `terrastruct` for languages and tools |
| CNCF certification badges, events and illustrations (`cka`, `kubecon-*`, `phippy-*`) | Not architecture icons; their folders have no `icon/` form |
| CNCF projects with irregular folders and no colour file (`openeverest` light/dark, the two kubeflow subprojects) | Their tone naming is ambiguous; add when a diagram needs them |
| Bundling icons in the wheel | Packs download on first use like every built-in pack |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| AI source | `lobehub/lobe-icons` (MIT), `packages/static-svg/icons/*` at a pinned commit | Largest maintained AI logo set, SVG, permissive | y |
| CNCF source | `cncf/artwork`, `projects/*` and `other/*` at a pinned commit | The projects' own artwork; Linux Foundation trademark guidelines, like vendor packs | y |
| Technology source | `gilbarbara/logos` (CC0), `logos/*` at a pinned commit | About 2,000 colour logos, public domain | y |
| AI naming | bare name = `-color` file, else the monochrome one; `-mono`, `-text`, `-text-cn`, `-brand`, `-brand-mono` | Colour reads best; every file stays addressable | y |
| Monochrome artwork | painted black on light fills and white on dark fills (`current_color`) | `currentColor` inside an `<image>` is always black | y |
| CNCF naming | bare name = `icon/color`; `-horizontal`, `-stacked`, `-black`; `white` folders are the dark tone; `-wtext` copies skipped | Mirrors the artwork repo; folder case varies | y |
| Technology naming | bare name = `-icon` file, else the full logo; `-logo` = full logo; `-icon-<variant>` = `<name>-<variant>` | Diagram icons are square; the full logo is often a wordmark | y |
| Catalog inference | `ai:` adds tag `ai` (category "AI"), `cncf:` adds `cncf` ("CNCF"); `logos:` adds none | `logos` is not a provider | y |

**Open questions:** none.

---

## User Stories

### P1: AI pack ⭐ MVP

**Acceptance Criteria**:

1. The registry SHALL list a built-in `ai` pack whose source is `lobehub/lobe-icons` at a pinned commit, including only `packages/static-svg/icons/*`, with license `MIT`. (BRAND-01)
2. WHEN `<name>-color.svg` exists THEN `ai:<name>` SHALL be it. (BRAND-02)
3. WHEN the pack indexes `<name>.svg` THEN it SHALL be `ai:<name>-mono`, and `ai:<name>` WHEN no colour file exists. (BRAND-03)
4. WHEN an SVG is drawn in `currentColor` THEN its light tone SHALL be painted `#000000`. (BRAND-04)
5. WHEN such an SVG has no dark variant THEN a dark-tone copy painted `#ffffff` SHALL be added. (BRAND-05)
6. WHEN a curated alias targets a derived alias (`lm-studio` → `lmstudio` → `lmstudio-mono`) THEN it SHALL resolve. (BRAND-06)

### P1: CNCF pack ⭐ MVP

1. The registry SHALL list a built-in `cncf` pack whose source is `cncf/artwork` at a pinned commit, including `projects/*` and `other/*`. (BRAND-07)
2. WHEN the pack indexes `projects/<p>/icon/color/*.svg` (any folder case) THEN it SHALL be `cncf:<p>`. (BRAND-08)
3. WHEN it indexes `projects/<p>/<form>/white/*.svg` THEN it SHALL be the dark tone of that form. (BRAND-09)
4. `-horizontal`, `-stacked` and `-black` SHALL name the other forms. (BRAND-10)
5. Files ending `-wtext` SHALL be skipped. (BRAND-11)
6. SVG SHALL be preferred over PNG; `k8s`, `otel`, `argocd`, `fluxcd` SHALL be aliases; a project with only a horizontal or stacked logo SHALL resolve by its bare name. (BRAND-12)

### P1: Technology logos pack ⭐ MVP

1. The registry SHALL list a built-in `logos` pack whose source is `gilbarbara/logos` at a pinned commit, including `logos/*`, with license `CC0-1.0`. (BRAND-13)
2. WHEN `<name>-icon.svg` exists THEN it SHALL be `logos:<name>`. (BRAND-14)
3. `<name>.svg` SHALL be `logos:<name>-logo`. (BRAND-15)
4. WHEN no `-icon` file exists THEN `logos:<name>` SHALL resolve to the full logo. (BRAND-16)

### P1: GitHub source

1. WHEN a file path holds characters that are not URL-safe (a space) THEN the download URL SHALL quote it. (BRAND-17)
2. Files no rule names SHALL NOT be downloaded. (BRAND-18)

### P1: Catalog inference

1. `ai:` icons SHALL add tag `ai` (category "AI") and `cncf:` icons tag `cncf` (category "CNCF"); `logos:` none. (BRAND-19)

### P2: Showcase and docs

1. The showcase SHALL include a delivery platform diagram using `logos:`, `cncf:` and `ai:` icons on light and dark fills, and `spinagram check` SHALL report 0 issues for it. (BRAND-20)
2. The icon docs, the `spinagram` agent skill and the README SHALL list the three packs with source, license and naming, and every pack name they cite SHALL resolve. (BRAND-21)

---

## Requirement Traceability

| Requirement ID | Story | Status |
| -------------- | ----- | ------ |
| BRAND-01..06 | P1: AI pack | Verified |
| BRAND-07..12 | P1: CNCF pack | Verified |
| BRAND-13..16 | P1: Technology logos | Verified |
| BRAND-17..18 | P1: GitHub source | Verified |
| BRAND-19 | P1: Catalog | Verified |
| BRAND-20 | P2: Showcase | Verified (PNG reviewed) |
| BRAND-21 | P2: Docs | Verified (46 cited names resolve) |

**Coverage:** 21 total, 21 mapped to tasks, 0 unmapped

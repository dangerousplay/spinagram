# Self-hosted and Network Icon Packs Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `inline (pack YAML only; see spec assumptions)`
**Status**: Approved

---

## Test Coverage Matrix

> Guidelines: `pyproject.toml` (pytest, ruff); no coverage thresholds - strong defaults.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Pack rules / metadata | unit | 1:1 to spec ACs and edge cases | `tests/test_icon_packs.py` | `uv run pytest tests/test_icon_packs.py -q` |
| Pack fetch + resolve (fixture tree) | integration | Every spec name form | `tests/test_icon_packs.py` | `uv run pytest -q` |
| Theme config, showcase, docs | none | build gate; PNG review | - | build gate |

## Gate Check Commands

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | Unit tasks | `uv run pytest tests/test_icon_packs.py -q` |
| Full | Integration tasks | `uv run pytest -q` |
| Build | Config, showcase, docs, phase ends | `uv run ruff check src tests && uv run pytest -q && uv run spinagram check examples/showcase` |

---

## Execution Plan

### Phase 1: Packs and inference

```
T1 → T2 → T3
```

### Phase 2: Showcase and docs

```
T4 → T5 → T6
```

---

## Task Breakdown

### T1: Network icon pack

**What**: Built-in `network` pack: ecceman/affinity at a pinned commit, naming rules for square/circle/plain and colours, aliases.
**Where**: `src/spinagram/icon_packs/network.yaml`
**Depends on**: None
**Reuses**: pack YAML format, `classify`
**Requirement**: ICON-07, ICON-08, ICON-09, ICON-10, ICON-11, ICON-12

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] classify maps each source layout to the spec name; a fixture tree indexes and resolves every name form and alias
- [ ] Gate check passes: `uv run pytest tests/test_icon_packs.py -q`

**Tests**: unit
**Gate**: quick

---

### T2: Self-hosted icon pack

**What**: Built-in `selfhosted` pack: homarr-labs/dashboard-icons at a pinned commit, `-light` files as dark tone, aliases.
**Where**: `src/spinagram/icon_packs/selfhosted.yaml`
**Depends on**: T1
**Reuses**: pack YAML format
**Requirement**: ICON-01, ICON-02, ICON-03, ICON-04, ICON-05, ICON-06

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] fixture tree: `proxmox` light and dark tones, `portainer-dark` own name, aliases; a dark-fill node draws the dark variant
- [ ] Gate check passes: `uv run pytest tests/test_icon_packs.py -q`

**Tests**: unit
**Gate**: quick

---

### T3: Catalog inference for the new packs

**What**: `selfhosted:` → tag self-hosted / Self-hosted, `network:` → tag network / Network.
**Where**: `src/spinagram/metadata.py`
**Depends on**: T2
**Reuses**: PROVIDERS
**Requirement**: ICON-13, ICON-14, ICON-15

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] tags and dominant categories asserted for both packs
- [ ] Gate check passes: `uv run pytest tests/test_icon_packs.py -q`

**Tests**: unit
**Gate**: quick

---

### T4: Showcase: homelab private cloud

**What**: Annotated homelab diagram with self-hosted logos and network symbols.
**Where**: `examples/showcase/homelab.py`
**Depends on**: None (previous phase completes first)
**Reuses**: showcase css, annotations
**Requirement**: ICON-16

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `check` 0 issues; PNG reviewed
- [ ] Gate check passes: `build gate`

**Tests**: none
**Gate**: build

---

### T5: Showcase: campus network

**What**: Campus network diagram with network symbols; skill examples synced.
**Where**: `examples/showcase/campus_network.py`
**Depends on**: T4
**Reuses**: network pack
**Requirement**: ICON-17, ICON-18

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `check examples/showcase` 0 issues; skill examples identical
- [ ] Gate check passes: `build gate`

**Tests**: none
**Gate**: build

---

### T6: Documentation

**What**: Icon pack docs list both packs with source, license and naming; README and skill mention them.
**Where**: `docs/content/docs/icons.mdx`
**Depends on**: T5
**Reuses**: docs
**Requirement**: ICON-19

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] docs build
- [ ] Gate check passes: `build gate`

**Tests**: none
**Gate**: build

---

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | start of phase | ✅ |
| T2 | T1 | T1 → T2 | ✅ |
| T3 | T2 | T2 → T3 | ✅ |
| T4 | None | start of phase | ✅ |
| T5 | T4 | T4 → T5 | ✅ |
| T6 | T5 | T5 → T6 | ✅ |

## Test Co-location Validation

| Task | Code Layer | Matrix Requires | Task Says | Status |
| ---- | ---------- | --------------- | --------- | ------ |
| T1 | Model/annotate/qa | unit | unit | ✅ |
| T2 | Model/annotate/qa | unit | unit | ✅ |
| T3 | Model/annotate/qa | unit | unit | ✅ |
| T4 | Config/showcase/docs | none | none | ✅ |
| T5 | Config/showcase/docs | none | none | ✅ |
| T6 | Config/showcase/docs | none | none | ✅ |

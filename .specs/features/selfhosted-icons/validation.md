# Self-hosted and Network Icon Packs Validation

## Validation: selfhosted-icons - PASS

**Date**: 2026-10-12
**Spec**: `.specs/features/selfhosted-icons/spec.md`
**Diff range**: `main..HEAD` (main = `7eea970`; `3068275`..`c1397cd`, 12 commits; iteration 3 adds `57f8317`, `c1397cd`)
**Verifier**: independent sub-agent (author ≠ verifier)
**Iteration**: 3 (user-driven additions T9/T10 re-verified after the iteration-2 verdict; see the Iteration 3 section). Iteration 2: Iteration 1 (at `b322cf2`) found 1 surviving mutant (M02: the gray-square fixture used a file
name that does not exist upstream), a dead curated alias `npm`, and "public domain" in place of the licence name.
`072acf8` (tests) and `ffd77a0` (alias + docs) closed all three.

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1-T6 | ✅ Done | `3068275`..`b322cf2` |
| T7 gray network fixture | ✅ Done | `072acf8` |
| T8 npm alias, licence wording | ✅ Done | `ffd77a0` |

---

## Spec-Anchored Acceptance Criteria

| AC | Spec-defined outcome | `file:line` + assertion | Result |
| -- | -------------------- | ----------------------- | ------ |
| ICON-01 | `selfhosted` from `homarr-labs/dashboard-icons`, pinned commit, only `svg/*`, `Apache-2.0` | `tests/test_icon_packs.py:95` - `(type, repo, include) == ("github", "homarr-labs/dashboard-icons", ["svg/*"])`; `:97` - `len(ref) == 40`; `:98` - `"Apache-2.0" in p.license` | ✅ |
| ICON-02 | `svg/proxmox.svg` → `proxmox`, light | `tests/test_icon_packs.py:102,109` - `(got[0], got[1]) == ("proxmox", "light")` | ✅ |
| ICON-03 | `svg/proxmox-light.svg` → dark variant of `proxmox` | `tests/test_icon_packs.py:103,109` - `== ("proxmox", "dark")`; `:122` dark resolve reads the `-light` file | ✅ |
| ICON-04 | `svg/portainer-dark.svg` → `portainer-dark`, light | `tests/test_icon_packs.py:104,109` - `== ("portainer-dark", "light")`; `:123-124` resolves to that file | ✅ |
| ICON-05 | `pve`/`esxi`/`pihole` → `proxmox`/`vmware-esxi`/`pi-hole` | `tests/test_icon_packs.py:125-127` - `resolve("selfhosted:<alias>") == resolve("selfhosted:<target>")` for pve, esxi, pihole (+ pbs, nsx), distinct fixture files; `nginx-pm` replaces the shadowed `npm` at `src/spinagram/icon_packs/selfhosted.yaml:23` | ✅ |
| ICON-06 | dark-fill node draws the dark variant | `tests/test_icon_packs.py:145` - `shapes["pve"].icon.path.read_text() == proxmox-light.svg`; `:146` light fill gets `proxmox.svg` | ✅ |
| ICON-07 | `network` from `ecceman/affinity`, pinned, only `svg/*`, `Unlicense` | `tests/test_icon_packs.py:43` - `== ("github", "ecceman/affinity", ["svg/*"])`; `:44` - `len(ref) == 40`; `:45` - `"Unlicense" in p.license` | ✅ |
| ICON-08 | `svg/square/blue/sq_router_blue.svg` → `router` | `tests/test_icon_packs.py:49,61` - `got[0] == "router"`; `:76` resolve `router == router-blue` | ✅ |
| ICON-09 | square colour → `router-green` | `tests/test_icon_packs.py:50,61` - `got[0] == "router-green"`; `:51,61` real upstream form `sq_switch_multilayer.svg` (gray, no suffix) → `switch-multilayer-gray`; `:83-84` `network:router-gray` reads `svg/square/gray/sq_router.svg` | ✅ |
| ICON-10 | `c_router_red.svg` → `router-circle-red`; blue circle → `router-circle` | `tests/test_icon_packs.py:53,61` and `:52,61` - one assertion per clause | ✅ |
| ICON-11 | `svg/naked/router.svg` → `router-plain` | `tests/test_icon_packs.py:54,61` - `got[0] == "router-plain"` | ✅ |
| ICON-12 | `fw`/`lb`/`l3-switch`/`ap` → `firewall`/`loadbalancer`/`switch-multilayer`/`wifi` | `tests/test_icon_packs.py:79-82` - `got["network:fw"] == resolve("network:firewall")` etc., with `:75` all non-None | ✅ |
| ICON-13 | `selfhosted:` icons → tag `self-hosted` | `tests/test_icon_packs.py:158` - `effective_tags(lab) == ["network", "self-hosted"]` | ✅ |
| ICON-14 | `network:` icons → tag `network` | `tests/test_icon_packs.py:164` - `effective_tags(net) == ["network"]` | ✅ |
| ICON-15 | dominant `selfhosted:` → `Self-hosted`; dominant `network:` → `Network` | `tests/test_icon_packs.py:159` - `== "Self-hosted"`; `:164` - `== "Network"`; `tests/test_metadata.py:206-207` HOME01/NET01 | ✅ |
| ICON-16 | homelab showcase with `selfhosted:` + `network:` icons, legend, numbered steps | `examples/showcase/homelab.py:16,17,21` icons from both packs; `:35,37,40-42` `step=`; `:47` `d.add_legend()`; `tests/test_metadata.py:207` HOME01 loads | ✅ (matrix: build gate + review) |
| ICON-17 | campus showcase with `network:` icons | `examples/showcase/campus_network.py:15-29` all `network:` icons; `:43` legend; `tests/test_metadata.py:207` NET01 | ✅ |
| ICON-18 | `spinagram check examples/showcase` → 0 issues | gate run: `8 diagram(s), 0 issue(s)` | ✅ |
| ICON-19 | docs list both packs with source, license and naming | `docs/content/docs/icons.mdx:24` Dashboard Icons link + Apache-2.0; `:25` Affinity link + "Unlicense, public domain"; `:38-59` naming (tones, shape/colour table, aliases incl. `nginx-pm` at `:43`); `docs/content/docs/python.mdx:57-58` provider table | ✅ |

**Status**: ✅ All 19 ACs covered with spec-exact assertions; 0 spec-precision gaps

---

## Real-source cross-check

The pinned upstream trees (GitHub API) were classified path by path with `registry()[pack].classify`:

| Pack | Included files | Unmatched | Name collisions |
| ---- | -------------- | --------- | --------------- |
| network | 557 | 1 (`svg/square/green/.DS_Store`, skipped) | 1 harmless: `shield-circle` from `c_shield.svg` and `c_shield_blue.svg` (fetch keeps the first by path) |
| selfhosted | 3,637 → 3,260 icons, 514 dark variants | 1 (`svg/assetgrid.png`, skipped) | 0 |

On the real cache, every icon reference in the showcases, docs, README and skill resolves, and so does every curated alias. `selfhosted:nginx-pm` gives `nginx-proxy-manager`, `network:router-gray` and `network:switch-multilayer-gray` resolve, and `selfhosted:npm` correctly draws the upstream npm logo.

---

## Discrimination Sensor

The sensor ran in an isolated `git worktree` at `ffd77a0` in the scratchpad, with these settings:

- `PYTHONDONTWRITEBYTECODE=1`, and `__pycache__` cleared before each mutant
- `SPINAGRAM_CACHE` and `XDG_CONFIG_HOME` set to fresh scratch dirs
- the worktree's `src/spinagram` confirmed as the imported package

Tests run: `tests/test_icon_packs.py tests/test_metadata.py`.

| Mutation | File:line | Description | Killed? |
| -------- | --------- | ----------- | ------- |
| M01 | `src/spinagram/icon_packs/network.yaml:12` | square blue named `{stem}-blue` | ✅ Killed |
| M02 | `src/spinagram/icon_packs/network.yaml:13` | square colour suffix required | ✅ Killed (iteration 1: survived); fails both `tests/test_icon_packs.py:51` and `:84` |
| M03 | `network.yaml:14` | blue circle suffix required | ✅ Killed |
| M04 | `network.yaml:15` | coloured circle suffix required | ✅ Killed |
| M05 | `network.yaml:15` | `{stem}-{color}-circle` | ✅ Killed |
| M06 | `network.yaml:14` | blue circle named `-circle-blue` | ✅ Killed |
| M07 | `network.yaml:16` | plain named `-naked` | ✅ Killed |
| M08 | `network.yaml:12-13` | colour-square rule before blue-square rule | ✅ Killed |
| M09 | `network.yaml:18` | `fw` → `loadbalancer` | ✅ Killed |
| M10 | `network.yaml:19` | `lb` removed | ✅ Killed |
| M11 | `network.yaml:21` | `l3-switch` → `switch` | ✅ Killed |
| M12 | `network.yaml:23` | `ap` → `wlc` | ✅ Killed |
| M13 | `network.yaml:9` | ref → `master` | ✅ Killed |
| M14 | `network.yaml:7` | license → MIT | ✅ Killed |
| M15 | `network.yaml:9` | include → `["*"]` | ✅ Killed |
| M16 | `network.yaml:9` | repo changed | ✅ Killed |
| M17 | `src/spinagram/icon_packs/selfhosted.yaml:11` | `-light` rule loses `tone: dark` | ✅ Killed |
| M18 | `selfhosted.yaml:11-12` | rule order swapped | ✅ Killed |
| M19 | `selfhosted.yaml:11` | `-dark` also treated as dark tone | ✅ Killed |
| M20 | `selfhosted.yaml:14` | `pve` → `proxmox-backup-server` | ✅ Killed |
| M21 | `selfhosted.yaml:17` | `esxi` removed | ✅ Killed |
| M22 | `selfhosted.yaml:21` | `pihole` removed | ✅ Killed |
| M23 | `selfhosted.yaml:16` | `pbs` → `proxmox` | ✅ Killed |
| M24 | `selfhosted.yaml:20` | `nsx` → `vmware-esxi` | ✅ Killed |
| M25 | `selfhosted.yaml:8` | ref → `main` | ✅ Killed |
| M26 | `selfhosted.yaml:6` | license → MIT | ✅ Killed |
| M27 | `selfhosted.yaml:8` | repo → walkxcode fork | ✅ Killed |
| M28 | `selfhosted.yaml:9` | include → `["*"]` | ✅ Killed |
| M29 | `src/spinagram/metadata.py:22` | tag `self-hosted` → `selfhosted` | ✅ Killed |
| M30 | `metadata.py:22` | name `Self-hosted` → `Selfhosted` | ✅ Killed |
| M31 | `metadata.py:23` | tag `network` → `networking` | ✅ Killed |
| M32 | `metadata.py:23` | name `Network` → `Networking` | ✅ Killed |
| M33 | `metadata.py:23` | `network` provider removed | ✅ Killed |

**Sensor depth**: expanded (33 manual mutants)
**Sensor outcome**: 33/33 killed, 0 survived

Isolation: worktree removed and pruned. The real tree's `git status --porcelain` shows only this report, `.specs/LESSONS.md` and `.specs/lessons.json`, and the real cache was not touched.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code | ✅ (two pack YAML files and two PROVIDERS entries) |
| Surgical changes | ✅ |
| No scope creep | ✅ |
| Matches patterns | ✅ (same pack YAML and PROVIDERS shape as the cloud packs) |
| Spec-anchored outcome check | ✅ |
| Per-layer Coverage Expectation met | ✅ (fixtures now mirror upstream names, including unsuffixed gray squares) |
| Every test maps to a spec requirement | ✅ |
| Documented guidelines followed: `pyproject.toml` (pytest, ruff) | ✅ |

---

## Edge Cases

- [x] Artwork only as `<name>-light.svg` still resolves on any fill - `tests/test_icon_packs.py:129-130` (`nightowl`)
- [x] File no rule matches is skipped - `tests/test_icon_packs.py:65` (network png), `:113` (selfhosted png); fixture trees also carry `README.md`, `png/`, `meta/` files

---

## Gate Check

- **Gate command**: `set -o pipefail; uv run ruff check src tests && uv run pytest -q && uv run spinagram check examples/showcase`
- **Outcome**: ruff clean; 485 passed, 0 failed, 3 skipped; showcase `8 diagram(s), 0 issue(s)`; exit 0
- **Test count before feature**: 437 collected (clean worktree of `main`)
- **Test count after feature**: 458 collected (clean worktree of HEAD). The real tree collects 488 because it also holds ignored local test files that are not in git.
- **Delta**: +21 (`tests/test_icon_packs.py`); `tests/test_metadata.py:206-207` extended, not weakened
- **Skipped tests**: 3 environment-only skips that predate this feature (dot / soffice not installed)
- **Failures**: none

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| ICON-01 .. ICON-19 | Implementing / Needs Fix (ICON-09) | ✅ Verified |

---

## Summary

**Overall**: ✅ Ready

**Spec-anchored check**: 19/19 ACs matched their spec outcomes; 0 spec-precision gaps
**Sensor**: 33/33 mutations killed
**Gate**: 485 passed, 0 failed, 3 skipped (environment-only)

**Fixes since iteration 1**:
- The gray network fixtures now use real upstream file names, and resolve is asserted for `network:router-gray`.
- `npm` was replaced with `nginx-pm`.
- The docs now name the Affinity licence as Unlicense.

**Lessons**: L-016 was recorded from the iteration-1 signal (M02). This iteration adds no new signal.

---

## Iteration 3 - T9 theme pack refresh, T10 EVPN fabric showcase

### T9: `Theme.icon` refreshes its pack list for an unknown pack prefix (`57f8317`)

| Check | Evidence | Result |
| ----- | -------- | ------ |
| A pack registered after the theme loaded resolves | `tests/test_icon_packs.py:173` - `"late" not in theme.icon_packs()` (the list is cached first); `:179` - `got.read_text() == (root / "gear.svg").read_text()` | ✅ |
| The test fails without the fix | T-M1: pre-fix `src/spinagram/theme.py` (`git show 57f8317^:src/spinagram/theme.py`, refresh at `:236-237` removed) - `1 failed` | ✅ Killed |
| The condition matters | T-M2: `not in` → `in` at `src/spinagram/theme.py:236` - `1 failed` | ✅ Killed |
| Resolve uses the refreshed list | T-M3: refresh kept but `resolve` given the stale dict (`src/spinagram/theme.py:238`) - `1 failed` | ✅ Killed |
| No loop, and an unknown prefix is not masked | probe: `theme.icon("nosuchpack:gear")` returns `None` twice and `nosuchpack:other` returns `None`; `registry()` reloads once per distinct unknown ref (2 for 2 refs, because the `None` is cached in `_icon_cache` at `src/spinagram/theme.py:239`); a known prefix reloads 0 times | ✅ |

**Residual (informational, not a gap):**
- A `None` cached for a `pack:name` that was asked for *before* its pack was registered stays cached for that theme instance.
- The fix covers the reported case, where the first lookup happens after registration, so this does not block the verdict.

### T10: NET02 EVPN-VXLAN fabric showcase (`c1397cd`)

| Check | Evidence | Result |
| ----- | -------- | ------ |
| Uses `network:` icons | `examples/showcase/evpn_fabric.py:17,21-23,33,38` - `switch-multilayer-green`, `switch-multilayer`, `switch`, `router-cloud-red`, `server-circle`; all 5 resolve on the real cache | ✅ |
| Steps, callouts and an explicit legend | `examples/showcase/evpn_fabric.py:55-59` 5 `d.step`; `:60-63` 2 callouts; `:64-66` `d.add_legend({...})` | ✅ |
| Catalog groups it as Network | `tests/test_metadata.py:207` - `"NET02": "Network"` | ✅ |
| Check is clean | `spinagram check examples/showcase` - `9 diagram(s), 0 issue(s)` | ✅ |
| Skill copies synced | `cmp` identical: `evpn_fabric.py`, `fabric.css` | ✅ |
| Render reviewed | PNG rendered to scratch: spine-leaf mesh drawn straight from anchors, ESI links, eBGP to ISPs, steps 1-5, legend | ✅ |

**Cosmetic notes (non-blocking):**
- `examples/showcase/fabric.css:26`: `edge.vxlan-path` is unused, and `check` reports it at info level.
- In the render, the underlay lines cross the "Border leaves · AS 65100" and "Rack B · AS 65102" group titles.

### Iteration 3 gate

- `set -o pipefail; uv run ruff check src tests && uv run pytest -q && uv run spinagram check examples/showcase`
- Outcome: ruff clean; 486 passed, 0 failed, 3 skipped (environment-only); `9 diagram(s), 0 issue(s)`; exit 0.
- Delta: +1 test (`tests/test_icon_packs.py:168`).

### Iteration 3 sensor

- 3/3 T9 mutants killed (T-M1..T-M3).
- They ran in an isolated worktree at `c1397cd`, with `PYTHONDONTWRITEBYTECODE=1`, `__pycache__` cleared per mutant, and scratch `SPINAGRAM_CACHE` and `XDG_CONFIG_HOME`. The worktree's `src` was confirmed as the imported package.
- The worktree was removed and pruned.
- Combined with M01-M33: 36/36 killed.

### Iteration 3 verdict

Iteration 3 is clean: T9 and T10 add no gap, no surviving mutant and no spec-precision gap, so no new lesson.


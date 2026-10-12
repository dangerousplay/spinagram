# Self-hosted and Network Icon Packs Specification

## Problem Statement

spinagram ships vendor icons for public clouds (AWS, Google Cloud, Azure, OCI) and Kubernetes, but homelabs and
private clouds are drawn with Proxmox, OPNsense, VMware, TrueNAS and plain network gear (routers, switches,
firewalls). Authors fall back to generic glyphs or hand-managed files. Two built-in packs should cover them.

## Goals

- [ ] `selfhosted:proxmox`, `selfhosted:opnsense`, `selfhosted:vmware-esxi` and about 3,600 more self-hosted and
      private-cloud logos resolve like any built-in icon.
- [ ] `network:router`, `network:switch`, `network:firewall` and the rest of a consistent network-symbol set resolve
      in four colours and three shapes.
- [ ] Diagrams using them group in the catalog, and the showcase demonstrates a homelab private cloud.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Simple Icons (monochrome brand marks) | Overlaps the self-hosted set; single-colour marks need recolouring support |
| selfh.st icons | CC BY 4.0 needs per-use attribution; dashboard-icons covers the same apps |
| Vendor stencils (Cisco, VMware Validated Designs) | Redistribution terms unclear |
| Bundling icons in the wheel | Packs download on first use like every built-in pack |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Self-hosted source | `homarr-labs/dashboard-icons` (Apache-2.0), `svg/*` at a pinned commit | Largest maintained set of self-hosted and private-cloud logos, SVG, permissive | n |
| Network source | `ecceman/affinity` (Unlicense), `svg/*` at a pinned commit | Consistent network-diagram symbols, public domain | n |
| Pack names | `selfhosted` and `network` | Read as what they hold; no clash with existing packs | n |
| Self-hosted tones | `<name>-light.svg` is the dark-fill variant of `<name>`; `<name>-dark.svg` stays its own name | dashboard-icons names variants by artwork colour; the `-light` artwork suits dark fills | n |
| Network naming | `network:<symbol>` = square blue; `<symbol>-<colour>` square in that colour; `<symbol>-circle[-<colour>]` circle; `<symbol>-plain` unframed | Square blue is the set's canonical look; every variant stays addressable | n |
| Short aliases | network: `lb`, `fw`, `l3-switch`, `ap`, `vm-host`; selfhosted: `pve`, `pbs`, `esxi`, `nsx`, `pihole`, `truenas` | Names people type in homelab diagrams | n |
| Catalog inference | `selfhosted:` icons add tag `self-hosted` (category "Self-hosted"); `network:` icons add tag `network` (category "Network") | Same rule as the cloud packs | n |
| Showcase | Two diagrams: a homelab private cloud (self-hosted + network icons, annotated) and a campus network (network icons) | Shows both packs at their best | n |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Self-hosted pack ⭐ MVP

**User Story**: As a homelab or private-cloud author, I want vendor logos by name so that my diagrams look like my stack.

**Acceptance Criteria**:

1. The registry SHALL list a built-in `selfhosted` pack whose source is `homarr-labs/dashboard-icons` at a pinned commit, including only `svg/*` files, with license `Apache-2.0`.
2. WHEN the pack indexes `svg/proxmox.svg` THEN the icon SHALL be named `proxmox` with the light tone.
3. WHEN the pack indexes `svg/proxmox-light.svg` THEN it SHALL be the dark-tone variant of `proxmox`.
4. WHEN the pack indexes `svg/portainer-dark.svg` THEN the icon SHALL be named `portainer-dark` with the light tone.
5. WHEN a diagram uses `selfhosted:pve`, `selfhosted:esxi` or `selfhosted:pihole` THEN they SHALL resolve to `proxmox`, `vmware-esxi` and `pi-hole`.
6. WHEN a node with a dark fill uses `selfhosted:proxmox` THEN the dark-tone variant SHALL be drawn.

**Independent Test**: index a fixture tree laid out like the source and resolve `selfhosted:pve` in both tones.

### P1: Network pack ⭐ MVP

**User Story**: As a network author, I want a consistent symbol set for routers, switches and firewalls.

**Acceptance Criteria**:

1. The registry SHALL list a built-in `network` pack whose source is `ecceman/affinity` at a pinned commit, including only `svg/*` files, with license `Unlicense`.
2. WHEN the pack indexes `svg/square/blue/sq_router_blue.svg` THEN the icon SHALL be named `router`.
3. WHEN the pack indexes `svg/square/green/sq_router_green.svg` THEN the icon SHALL be named `router-green`.
4. WHEN the pack indexes `svg/circle/red/c_router_red.svg` THEN the icon SHALL be named `router-circle-red`, and the blue circle `router-circle`.
5. WHEN the pack indexes `svg/naked/router.svg` THEN the icon SHALL be named `router-plain`.
6. WHEN a diagram uses `network:fw`, `network:lb`, `network:l3-switch` or `network:ap` THEN they SHALL resolve to `firewall`, `loadbalancer`, `switch-multilayer` and `wifi`.

**Independent Test**: index a fixture tree laid out like the source and resolve each name form.

### P1: Catalog inference

**User Story**: As a catalog user, I want homelab diagrams grouped without metadata.

**Acceptance Criteria**:

1. WHEN a diagram uses `selfhosted:` icons THEN its effective tags SHALL include `self-hosted`.
2. WHEN a diagram uses `network:` icons THEN its effective tags SHALL include `network`.
3. WHEN `selfhosted:` icons dominate and no category is declared THEN the effective category SHALL be `Self-hosted`; WHEN `network:` icons dominate, `Network`.

**Independent Test**: diagrams using each pack report the tag and category.

### P2: Showcase and docs

**User Story**: As a visitor, I want to see what homelab and network diagrams look like.

**Acceptance Criteria**:

1. The showcase SHALL include a homelab private-cloud diagram using `selfhosted:` and `network:` icons, a legend and numbered steps.
2. The showcase SHALL include a campus network diagram using `network:` icons.
3. `spinagram check examples/showcase` SHALL report 0 issues.
4. The icon pack docs SHALL list both packs with source, license and naming.

**Independent Test**: render `examples/showcase` and review the PNGs.

---

## Edge Cases

- WHEN an artwork exists only as `<name>-light.svg` THEN `<name>` SHALL still resolve (to the dark-tone file) on any fill.
- IF the source has a file no rule matches THEN it SHALL be skipped.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| ICON-01 | P1: Self-hosted - registry entry | Tasks | Implementing |
| ICON-02 | P1: Self-hosted - plain name | Tasks | Implementing |
| ICON-03 | P1: Self-hosted - light file is dark tone | Tasks | Implementing |
| ICON-04 | P1: Self-hosted - dark file keeps its name | Tasks | Implementing |
| ICON-05 | P1: Self-hosted - aliases | Tasks | Implementing |
| ICON-06 | P1: Self-hosted - dark fill uses dark tone | Tasks | Implementing |
| ICON-07 | P1: Network - registry entry | Tasks | Implementing |
| ICON-08 | P1: Network - square blue default | Tasks | Implementing |
| ICON-09 | P1: Network - square colours | Tasks | Implementing |
| ICON-10 | P1: Network - circles | Tasks | Implementing |
| ICON-11 | P1: Network - plain | Tasks | Implementing |
| ICON-12 | P1: Network - aliases | Tasks | Implementing |
| ICON-13 | P1: Catalog - self-hosted tag | Tasks | Implementing |
| ICON-14 | P1: Catalog - network tag | Tasks | Implementing |
| ICON-15 | P1: Catalog - categories | Tasks | Implementing |
| ICON-16 | P2: Showcase - homelab | Tasks | Implementing |
| ICON-17 | P2: Showcase - campus network | Tasks | Pending |
| ICON-18 | P2: Showcase - check clean | Tasks | Pending |
| ICON-19 | P2: Docs | Tasks | Pending |

**Coverage:** 19 total, 19 mapped to tasks, 0 unmapped

---

## Success Criteria

- [ ] `spinagram icons fetch selfhosted network` downloads both packs, and `spinagram icons search proxmox` finds `selfhosted:proxmox`.
- [ ] The homelab showcase renders with real Proxmox, OPNsense and TrueNAS logos and network symbols, 0 check issues.

# Feature: Live UI (`spinagram serve`)

**Status:** Done (2026-10-09) · **Size:** Large · **Owner:** spinagram

## Problem Statement

Authoring a diagram today is a loop of *edit spec → `spinagram render` → open the SVG/PNG*. Themes and
icon packs are only visible by reading YAML and `spinagram icons search` output, so picking a colour token
or an icon name means guessing and re-rendering. A local live-reload UI closes the loop: save in the editor,
see the diagram; look up tokens and icons visually.

## Goals

- [ ] Saving a spec or theme file updates the browser in ≤ 1 s (typical spec) with no manual refresh.
- [ ] Every built-in and active theme is readable as a token sheet; every registered pack is browsable,
      and a not-yet-downloaded pack can be fetched from the UI.
- [ ] `pip install spinagram[ui]` users need no Node/bun: the web bundle ships inside the wheel.

## Out of Scope

| Feature | Reason |
|---|---|
| Editing specs/themes in the browser | Editor stays the source of truth; UI is read-only |
| QA warnings panel, export buttons (SVG/PNG/PPTX) | Not chosen for v1 (CLI covers them) |
| Sample diagram per theme, re-theming the current spec, `extends` diff view | Not chosen for v1 |
| Icon click-to-copy, light/dark + vector badges, theme alias map | Not chosen for v1 |
| Binding to non-loopback hosts / LAN sharing | Security: fetch endpoint would be exposed |
| PPTX / Figma previews | Backends produce files, not views |

---

## User Stories

### P1: Live diagram preview ⭐ MVP

**User Story**: As a diagram author, I want `spinagram serve specs/` to show my diagrams and re-render them
when I save, so I can iterate without running render commands.

**Acceptance Criteria**:

1. WHEN I run `spinagram serve <paths…> [--theme T] [--layout E] [--port N] [--no-open]` THEN the server SHALL
   bind 127.0.0.1 only, print the URL and open the default browser unless `--no-open`.
2. WHEN the `ui` extra is not installed THEN `serve` SHALL exit 2 with `pip install 'spinagram[ui]'` as hint.
3. WHEN the UI loads THEN the left nav SHALL list every spec file under the paths and the diagrams (id + title)
   each one defines; selecting one SHALL render it as SVG in the main pane.
4. WHEN a spec file, a `_defaults.yaml`, a `.py` helper next to a spec, or any file of the active theme
   (extends chain included) is saved THEN the affected diagram(s) SHALL re-render and the open view SHALL update
   without a page reload, keeping zoom/pan.
5. WHEN a spec is added or removed THEN the nav SHALL update.
6. WHEN loading or rendering fails THEN the main pane SHALL show the error message (file, message, hint)
   over the last good render (dimmed); the next successful save SHALL clear it.

**Independent Test**: serve `examples/`, edit a node title in `decision.yaml`, see it change in < 1 s.

### P1: Zoom / pan / fit

1. WHEN I scroll the wheel over the diagram THEN it SHALL zoom around the pointer (10 %–800 %).
2. WHEN I drag THEN it SHALL pan; WHEN I press Fit (or `f`) THEN it SHALL fit the canvas to the pane; `0` = 100 %.
3. WHEN the diagram re-renders THEN zoom/pan SHALL be kept; WHEN I select another diagram THEN it SHALL fit.

### P1: Layout engine switch

1. WHEN the UI loads THEN a dropdown SHALL list layout engines (spec default, flex, dot, elk, d2, plugins);
   unavailable engines SHALL be disabled with their install hint as tooltip.
2. WHEN I pick an engine THEN diagrams that use `layout:` SHALL re-render with it (same as `--layout`);
   diagrams with explicit coordinates SHALL show "fixed layout" and ignore the switch.
3. WHEN `--layout E` is given THEN it SHALL be the initial selection.

### P1: Theme token sheet

1. WHEN I open Themes THEN the nav SHALL list the built-in themes plus the active theme (`--theme`), the active
   one marked.
2. WHEN I select a theme THEN the main pane SHALL show: name and `extends`; colour tokens as swatches (token
   name, resolved hex, the token it points to when indirect); font roles (family, weights, sample text in the
   theme's embedded font); node/zone/edge styles each with a rendered preview; defaults and chrome values.
3. WHEN a file of a displayed theme changes THEN the sheet SHALL reload live.
4. WHEN a theme fails to load THEN the sheet SHALL show the error instead.

### P1: Icon pack browser with fetch

1. WHEN I open Icon packs THEN each registered pack SHALL show title, version, origin, license, homepage,
   downloaded state and icon count.
2. WHEN I select a downloaded pack THEN a virtualised grid SHALL show every icon with its `pack:name` and a
   search box SHALL filter by name and alias (all words must match).
3. WHEN I press Fetch on a pack that is not downloaded THEN the server SHALL download it in the background, the
   UI SHALL show "fetching…" and, on completion, the count and grid; on failure the error message.
4. WHEN a fetch for the same pack is already running THEN the request SHALL be rejected (409) and the UI SHALL
   keep showing progress.
5. WHEN `SPINAGRAM_OFFLINE=1` THEN Fetch SHALL be disabled with that reason.

## Edge Cases

- WHEN a path has no specs THEN the nav SHALL say so (with the paths searched).
- WHEN a `.py` spec imports a helper that changed THEN the reload SHALL use the new helper code.
- WHEN many files change at once (git checkout) THEN events SHALL be debounced into one re-render per diagram.
- WHEN the browser loses the event stream THEN it SHALL reconnect and refetch state.
- WHEN a request carries a `Host` other than localhost/127.0.0.1:port THEN it SHALL be refused (DNS rebinding).
- WHEN an icon/font request names a file outside the pack cache/theme THEN it SHALL be 404.
- WHEN the port is taken THEN `serve` SHALL fail with a clear message (`--port 0` picks a free one).

## Requirement Traceability

| ID | Story | Requirement | Status |
|---|---|---|---|
| UI-01 | Preview | `serve` command, loopback bind, auto-open, `--no-open`/`--port` | Verified |
| UI-02 | Preview | missing `ui` extra → exit 2 with hint | Verified |
| UI-03 | Preview | nav: spec files + diagrams; select → SVG | Verified |
| UI-04 | Preview | watch specs/_defaults/helpers/theme chain → live re-render (SSE), debounced | Verified |
| UI-05 | Preview | add/remove spec updates nav | Verified |
| UI-06 | Preview | inline error over last good render | Verified |
| UI-07 | Zoom | wheel zoom, drag pan, fit/100 %, state kept on reload | Verified |
| UI-08 | Layout | engine dropdown with availability; override for `layout:` diagrams | Verified |
| UI-09 | Themes | theme list (built-in + active) | Verified |
| UI-10 | Themes | token sheet: colours, fonts w/ sample, styles w/ preview, defaults, chrome | Verified |
| UI-11 | Themes | live reload of sheet + load error display | Verified |
| UI-12 | Packs | pack list with metadata and state | Verified |
| UI-13 | Packs | virtualised icon grid + search | Verified |
| UI-14 | Packs | background fetch, 409 on duplicate, offline disabled, error shown | Verified |
| UI-15 | Security | Host check, no path escapes, loopback only | Verified |
| UI-16 | Packaging | built bundle ships in wheel; no Node at runtime | Verified |
| UI-17 | Packs | `serve` never downloads inside a render; missing packs and icon warnings are flagged with a link to fetch; a finished fetch re-renders open diagrams | Verified |

**Coverage:** 17 total, 17 verified (pytest `tests/test_ui.py` + Playwright smoke).

UI-17 was added during execution: the first end-to-end run showed a render silently blocking on a
1.2k-file pack download and racing a second download of the same pack.

## Success Criteria

- [ ] Edit → visible update ≤ 1 s for `examples/*.yaml` (flex layout).
- [ ] `uv build` wheel contains `spinagram/ui/static/index.html`; `serve` works from it without bun.
- [ ] All tests pass; new API tests cover UI-03..UI-06, UI-08..UI-10, UI-12..UI-15.

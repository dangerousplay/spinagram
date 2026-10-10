# Live UI Context

**Gathered:** 2026-10-09
**Spec:** `.specs/features/live-ui/spec.md`
**Status:** Ready for design

## Feature Boundary

Local, read-only web UI started by `spinagram serve`: live preview of specs, theme token sheets, icon pack
browser with fetch.

## Implementation Decisions

### Stack
- Backend: Starlette + uvicorn + watchfiles as optional extra `ui`; live events over SSE.
- Frontend: React + TypeScript + Vite + Tailwind CSS v4, built with bun; built bundle committed into
  `src/spinagram/ui/static/` so wheel users need no Node.

### What live reload covers
- Spec paths + active theme directory (and its `extends` chain). Errors inline.

### Themes
- Token sheet only (colours, fonts, styles, defaults, chrome). No sample diagram, no re-theming, no inheritance view.

### Icon packs
- Fetch from UI. Browsing (grid + search) is implied by "showing icon packs"; no copy-ref / tone toggle / alias map.

### Preview
- Zoom/pan + fit, layout engine switch. No QA panel, no exports.

### Shell and launch
- Left nav (Diagrams / Themes / Icon packs) + main pane; UI follows system light/dark.
- `spinagram serve`, 127.0.0.1 only, auto-open browser, `--port`, `--no-open`.

### Agent's Discretion
- Visual design details, component library choice (none — Tailwind utilities), virtualisation lib.

## Specific References
- Icon sheet feel of icons.terrastruct.com (grid of icons with names).

## Deferred Ideas
- QA panel, export buttons, sample diagram per theme, re-theme current spec, extends diff,
  icon copy-ref/tone/vector badges, theme alias map, LAN sharing.

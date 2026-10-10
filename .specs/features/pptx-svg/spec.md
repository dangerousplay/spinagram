# Feature: SVG icons and images in PowerPoint

**Status:** Done (2026-10-08) · **Size:** Medium · **Owner:** diagramkit

## Problem

python-pptx embeds raster images only, so `backends/pptx.py::_raster` uses a sibling `.png` of an SVG
icon and **silently drops** the icon when there is none. Every SVG-only icon disappears from the deck:
all built-in packs (aws, gcp, azure, k8s), an npm brand-assets pack (SVG-first since 1.0.0)
and SVG logos in the chrome. A real-world PPTX lost every brand icon after the theme moved to
the package.

## Goal

SVG icons and images appear in PowerPoint **as vectors** (PowerPoint 365/2019+: crisp, recolourable,
"Convert to Shape" makes them editable) with a raster fallback for older clients and other readers
(LibreOffice, Keynote, Google Slides) — the same markup PowerPoint itself writes when you insert an SVG.

## Requirements

| ID | Pri | Requirement | Acceptance |
|---|---|---|---|
| PSVG-01 | P1 | An SVG icon or image is embedded as a picture whose `a:blip` points to a PNG fallback and carries the `asvg:svgBlip` extension (`{96DAC541-7B7A-43D3-8B79-37D633B846F1}`) pointing to the SVG part | zip contains `ppt/media/*.svg` and `*.png`; slide XML has `asvg:svgBlip r:embed` resolving to the SVG |
| PSVG-02 | P1 | PNG fallback is rendered with resvg-py at 4× the drawn size (min 256 px) when no sibling PNG exists; a sibling PNG (vectorized icon's original) is preferred | pack SVG icon with no sibling gets a fallback; vectorized brand icon reuses its PNG |
| PSVG-03 | P1 | Applies to every picture the backend writes: node icons, zone corner icons, table cell icons, chrome `Image` (logo) | one test per path |
| PSVG-04 | P1 | Identical SVGs are stored once per deck (dedupe by sha256, like python-pptx does for PNG) | 6 uses of one icon → 1 svg part |
| PSVG-05 | P1 | Without `resvg-py` and without a sibling PNG: still embed the SVG, with a 1×1 transparent PNG fallback, and warn once | icon visible in PowerPoint 365; no crash |
| PSVG-06 | P2 | Opt-out `PptxBackend(svg="raster")` / theme `pptx: {svg: raster}` writes only the PNG (for readers that choke on extensions) | no `svgBlip` in XML |
| PSVG-07 | P1 | The PPTX re-opens in python-pptx and LibreOffice headless converts it without error | `soffice --convert-to pdf` exit 0 in the test when available (skip otherwise) |

## Out of scope

- Converting SVG icons into native PowerPoint freeform shapes (that is PowerPoint's own "Convert to Shape").
- SVG for whole-slide images (mockups) — they are PNG already.

## Design (inline)

`backends/pptx.py`: replace `_raster()` with `_Slide.picture(container, path, x, y, w, h, name)`:
1. raster path → `add_picture` (unchanged);
2. SVG → fallback PNG (sibling → resvg cache `vector/pptx-<sha>-<px>.png` → 1×1) → `add_picture(fallback)`;
   then create/reuse an `image/svg+xml` `Part` (`/ppt/media/imageN.svg`), `slide.part.relate_to(part, RT.IMAGE)`
   and append `a:extLst/a:ext/asvg:svgBlip` under the picture's `a:blip`.
Dedupe via a per-`Presentation` dict `sha256 → Part`. Content type `svg` default is registered by
python-pptx's package on save through the part's `content_type`.

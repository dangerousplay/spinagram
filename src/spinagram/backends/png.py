"""PNG from the SVG backend: resvg in the Rust core (no browser), or headless Chromium (Playwright).

With the Rust core active (the default; ``SPINAGRAM_RUST=0`` turns it off) PNG uses resvg unless ``SPINAGRAM_PNG=chromium``. Without
the core, or with ``SPINAGRAM_PNG=chromium``, it uses Playwright."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Sequence

from ..rust import core
from ..scene import Scene
from ..text import BUNDLED
from .svg import check_fonts, to_svg

_CORE = core()


class PngBackend:
    name = "png"

    def __init__(self, scale: float = 2.0, fonts: str = "subset"):
        self.scale = scale
        self.fonts = check_fonts(fonts)  # the SVG it renders embeds fonts the same way (FNT-07)

    def render(self, scenes: Sequence[Scene], out_dir: Path) -> list[Path]:
        if _CORE is not None and os.environ.get("SPINAGRAM_PNG", "").lower() != "chromium":
            return self._render_resvg(scenes, out_dir)
        return self._render_chromium(scenes, out_dir)

    def _render_resvg(self, scenes: Sequence[Scene], out_dir: Path) -> list[Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        bundled = [str(p) for _, p in BUNDLED if p.exists()]
        paths = []
        for sc in scenes:
            files = list(dict.fromkeys([str(f.file) for f in sc.fonts() if f.file] + bundled))
            # resvg reads the font files itself and ignores the SVG's @font-face data; the SVG is still the one of
            # this font mode (FNT-07)
            png = _CORE.render_png(to_svg(sc, fonts=self.fonts), sc.width, sc.height, self.scale, files)
            dst = out_dir / f"{sc.slug}.png"
            dst.write_bytes(png)
            paths.append(dst)
        return paths

    def _render_chromium(self, scenes: Sequence[Scene], out_dir: Path) -> list[Path]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("PNG needs the 'png' extra: uv add 'spinagram[png]' && "
                               "uv run playwright install chromium") from exc
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
            browser = pw.chromium.launch()
            for sc in scenes:
                src = Path(tmp) / f"{sc.slug}.svg"
                src.write_text(to_svg(sc, fonts=self.fonts), encoding="utf-8")
                page = browser.new_page(viewport={"width": int(sc.width), "height": int(sc.height)},
                                        device_scale_factor=self.scale)
                page.goto(src.as_uri())
                page.evaluate("document.fonts.ready")
                dst = out_dir / f"{sc.slug}.png"
                page.screenshot(path=str(dst), clip={"x": 0, "y": 0, "width": sc.width, "height": sc.height})
                page.close()
                paths.append(dst)
            browser.close()
        return paths

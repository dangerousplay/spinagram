"""PNG rendered from the SVG backend with headless Chromium (Playwright)."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Sequence

from ..scene import Scene
from .svg import check_fonts, to_svg


class PngBackend:
    name = "png"

    def __init__(self, scale: float = 2.0, fonts: str = "subset"):
        self.scale = scale
        self.fonts = check_fonts(fonts)  # the SVG it renders embeds fonts the same way (FNT-07)

    def render(self, scenes: Sequence[Scene], out_dir: Path) -> list[Path]:
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

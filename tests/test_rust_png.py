"""PNG with resvg and the Chromium path (PNG-01, PNG-02, PNG-03, PNG-06)."""
import sys
from unittest import mock

import pytest
from PIL import Image

from spinagram.backends import png
from spinagram.backends.png import PngBackend
from spinagram.scene import Line, Scene, Shape


@pytest.fixture
def core():
    return pytest.importorskip("spinagram._core")


@pytest.fixture
def no_playwright(monkeypatch):
    monkeypatch.setitem(sys.modules, "playwright", None)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)


def scene(w=301.0, h=203.0) -> Scene:
    return Scene("S", "T", "s", w, h, "#ffffff", [Shape("a", "rect", 10, 10, 100, 60, "#cc0000"),
                                                  Line("l", 0, 0, w, h, "#000000", 2)])


def test_resvg_renders_without_playwright(core, no_playwright, monkeypatch, tmp_path):  # PNG-01
    monkeypatch.setattr(png, "_CORE", core)
    monkeypatch.delenv("SPINAGRAM_PNG", raising=False)
    with mock.patch.object(PngBackend, "_render_chromium") as chromium:
        [path] = PngBackend(scale=1).render([scene()], tmp_path)
    assert path == tmp_path / "s.png" and path.stat().st_size > 0
    assert chromium.call_count == 0


def test_explicit_resvg_value_uses_resvg(core, no_playwright, monkeypatch, tmp_path):  # PNG-01 (SPINAGRAM_PNG=resvg)
    monkeypatch.setattr(png, "_CORE", core)
    monkeypatch.setenv("SPINAGRAM_PNG", "resvg")
    [path] = PngBackend(scale=1).render([scene()], tmp_path)
    assert path.exists()


@pytest.mark.parametrize("scale,size", [(1, (301, 203)), (1.5, (452, 304)), (2, (602, 406))])
def test_png_size_is_round_w_scale_by_round_h_scale(core, monkeypatch, tmp_path, scale, size):  # PNG-03
    # 301 * 1.5 = 451.5 and 203 * 1.5 = 304.5: Python round gives 452 and 304 (halves to even)
    monkeypatch.setattr(png, "_CORE", core)
    [path] = PngBackend(scale=scale).render([scene()], tmp_path)
    assert Image.open(path).size == size


def test_chromium_value_calls_the_playwright_path(core, monkeypatch, tmp_path):  # PNG-02
    monkeypatch.setattr(png, "_CORE", core)
    monkeypatch.setenv("SPINAGRAM_PNG", "chromium")
    with mock.patch.object(PngBackend, "_render_chromium", return_value=["chromium.png"]) as chromium, \
            mock.patch.object(PngBackend, "_render_resvg") as resvg:
        assert PngBackend().render([scene()], tmp_path) == ["chromium.png"]
    assert chromium.call_count == 1 and resvg.call_count == 0


def test_without_the_core_chromium_is_used(monkeypatch, tmp_path):  # PNG-02 (no core)
    monkeypatch.setattr(png, "_CORE", None)
    monkeypatch.delenv("SPINAGRAM_PNG", raising=False)
    with mock.patch.object(PngBackend, "_render_chromium", return_value=[]) as chromium:
        PngBackend().render([scene()], tmp_path)
    assert chromium.call_count == 1


def test_missing_playwright_without_core_keeps_the_error(no_playwright, monkeypatch, tmp_path):  # PNG-06
    monkeypatch.setattr(png, "_CORE", None)
    with pytest.raises(RuntimeError) as err:
        PngBackend().render([scene()], tmp_path)
    assert str(err.value) == ("PNG needs the 'png' extra: uv add 'spinagram[png]' && "
                              "uv run playwright install chromium")

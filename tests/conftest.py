"""Shared test setup: no test reads the developer's icon cache (``~/.cache/spinagram/icons``)."""
from __future__ import annotations

import pytest

from spinagram import icons
from spinagram.engine import vendor


def pytest_configure(config):
    config.addinivalue_line("markers", "real_icon_cache: use $SPINAGRAM_CACHE as set outside the test run")


def _clear_icon_caches() -> None:
    icons._INDEX_CACHE.clear()  # resolve(): pack indexes by pack@version
    vendor.clear_cache()        # vendor.match(): icon names by pack dir


@pytest.fixture(autouse=True)
def _isolated_icon_cache(request, tmp_path_factory, monkeypatch):
    """Point ``SPINAGRAM_CACHE`` at an empty directory, stay offline (no pack download into it) and drop the
    in-memory pack indexes, so vendor hints and pack icons never depend on the packs this machine has cached.
    Tests that need packs set their own cache (and lift ``SPINAGRAM_OFFLINE`` for local packs);
    ``@pytest.mark.real_icon_cache`` opts out."""
    if request.node.get_closest_marker("real_icon_cache"):
        yield
        return
    monkeypatch.setenv("SPINAGRAM_CACHE", str(tmp_path_factory.mktemp("icon-cache")))
    monkeypatch.setenv("SPINAGRAM_OFFLINE", "1")  # an empty cache must not download packs
    _clear_icon_caches()
    yield
    _clear_icon_caches()

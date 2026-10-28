"""The suite never reads the developer's icon cache (tests/conftest.py)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from spinagram import icons
from spinagram.engine import vendor

HOME_CACHE = Path.home() / ".cache" / "spinagram" / "icons"


def test_icon_cache_is_an_empty_temporary_directory():
    root = icons.cache_root()
    assert root != HOME_CACHE and root.is_dir() and list(root.iterdir()) == []
    assert icons._INDEX_CACHE == {} and vendor._NAMES == {}
    assert os.environ["SPINAGRAM_OFFLINE"] == "1"                            # an empty cache downloads nothing


def test_each_test_gets_its_own_cache(tmp_path_factory):
    assert icons.cache_root().parent == tmp_path_factory.getbasetemp()      # mktemp: one fresh dir per test


@pytest.mark.real_icon_cache
def test_real_icon_cache_marker_opts_out(tmp_path_factory):
    assert icons.cache_root().parent != tmp_path_factory.getbasetemp()

"""The Rust core is the default engine and SPINAGRAM_RUST=0 restores pure Python."""
import sys

import pytest

from spinagram import rust


@pytest.fixture
def fresh_load():
    rust._load.cache_clear()
    yield
    rust._load.cache_clear()


def test_core_is_on_by_default(monkeypatch, fresh_load):
    monkeypatch.delenv("SPINAGRAM_RUST", raising=False)
    from spinagram import _core

    assert rust.core() is _core


@pytest.mark.parametrize("value", ["0", ""])
def test_switch_off_gives_pure_python(monkeypatch, fresh_load, value):
    monkeypatch.setenv("SPINAGRAM_RUST", value)
    assert rust.core() is None


def test_missing_core_warns_and_falls_back(monkeypatch, fresh_load):
    monkeypatch.delenv("SPINAGRAM_RUST", raising=False)
    monkeypatch.setitem(sys.modules, "spinagram._core", None)  # makes the import raise ImportError
    with pytest.warns(UserWarning, match="spinagram._core is not importable"):
        assert rust.core() is None

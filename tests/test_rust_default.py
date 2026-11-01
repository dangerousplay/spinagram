"""The Rust core is the default engine; SPINAGRAM_RUST=0 restores pure Python; versions move in lockstep."""
import re
import sys
import tomllib
from importlib.metadata import version
from pathlib import Path

import pytest

from spinagram import rust

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def fresh_load():
    rust._load.cache_clear()
    yield
    rust._load.cache_clear()


def test_core_is_on_by_default(monkeypatch, fresh_load):
    monkeypatch.delenv("SPINAGRAM_RUST", raising=False)
    import spinagram_core

    assert rust.core() is spinagram_core


@pytest.mark.parametrize("value", ["0", ""])
def test_switch_off_gives_pure_python(monkeypatch, fresh_load, value):
    monkeypatch.setenv("SPINAGRAM_RUST", value)
    assert rust.core() is None


def test_missing_core_warns_and_falls_back(monkeypatch, fresh_load):
    monkeypatch.delenv("SPINAGRAM_RUST", raising=False)
    monkeypatch.setitem(sys.modules, "spinagram_core", None)  # makes the import raise ImportError
    with pytest.warns(UserWarning, match="spinagram-core is not importable"):
        assert rust.core() is None


def test_core_version_matches_spinagram():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    cargo = tomllib.loads((ROOT / "rust" / "Cargo.toml").read_text())["workspace"]["package"]["version"]
    pinned = [re.fullmatch(r"spinagram-core==(\S+)", d) for d in project["dependencies"]]
    assert [m.group(1) for m in pinned if m] == [project["version"]]
    assert cargo == project["version"]
    import spinagram_core

    assert spinagram_core.__version__ == version("spinagram-core") == project["version"]

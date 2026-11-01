"""icons.registry() is cached until a registry file, the cwd or $SPINAGRAM_ICON_PACKS changes (YAML-06, YAML-07)."""
from unittest import mock

import pytest

from spinagram import icons, yamlload

PACK = "packs:\n  {name}:\n    title: {name}\n    source: {{type: dir, path: /tmp}}\n"


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.delenv("SPINAGRAM_ICON_PACKS", raising=False)
    proj = tmp_path / "proj"
    proj.mkdir()
    monkeypatch.chdir(proj)
    return proj


def _write(path, name):
    path.write_text(PACK.format(name=name))


def test_second_call_reads_no_file_and_equals_first():  # YAML-06
    first = icons.registry()
    with mock.patch.object(icons, "_load_file", wraps=icons._load_file) as spy, \
            mock.patch.object(yamlload, "load_file", wraps=yamlload.load_file) as spy2:
        second = icons.registry()
    assert spy.call_count == 0
    assert spy2.call_count == 0
    assert second == first


def test_files_are_read_through_the_yaml_cache():  # YAML-03 (icons side)
    with mock.patch.object(yamlload, "load_file", wraps=yamlload.load_file) as spy:
        icons._load_file(next(icons.BUILTIN_DIR.glob("*.yaml")), "builtin")
    assert spy.call_count == 1


def test_env_change_rebuilds(tmp_path, monkeypatch):  # YAML-07 clause 1
    icons.registry()
    extra = tmp_path / "extra.yaml"
    _write(extra, "envpack")
    monkeypatch.setenv("SPINAGRAM_ICON_PACKS", str(extra))
    assert "envpack" in icons.registry()
    monkeypatch.delenv("SPINAGRAM_ICON_PACKS")
    assert "envpack" not in icons.registry()


def test_cwd_change_rebuilds(tmp_path, monkeypatch):  # YAML-07 clause 2
    other = tmp_path / "other"
    other.mkdir()
    _write(other / icons.PROJECT_REGISTRY, "otherpack")
    assert "otherpack" not in icons.registry()
    monkeypatch.chdir(other)
    assert "otherpack" in icons.registry()


def test_editing_project_registry_rebuilds(env):  # YAML-07 clause 3
    f = env / icons.PROJECT_REGISTRY
    _write(f, "first")
    assert "first" in icons.registry() and "second" not in icons.registry()
    _write(f, "second")
    reg = icons.registry()
    assert "second" in reg and "first" not in reg


def test_register_and_unregister_are_seen():
    icons.registry()
    icons.register("fresh", {"type": "dir", "path": "/tmp"})
    assert "fresh" in icons.registry()
    assert icons.unregister("fresh") is True
    assert "fresh" not in icons.registry()

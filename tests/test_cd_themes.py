"""Themes resolved by name: built-in, path, SPINAGRAM_THEME_PATH, entry points (THM-01..04)."""
from __future__ import annotations

import importlib
import importlib.metadata
import os
from pathlib import Path

import pytest

from spinagram import Theme
from spinagram.theme import BUILTIN, _resolve_dir

GROUP = "spinagram.themes"


def _theme(d: Path, name: str | None = None, extends: str = "default") -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "theme.yaml").write_text(f"extends: {extends}\nname: {name or d.name}\n")
    return d


@pytest.fixture
def world(tmp_path, monkeypatch):
    """cwd, HOME, two theme path dirs, a missing one, and installable entry points (none by default)."""
    for sub in ("cwd", "home", "envA", "envB", "site"):
        (tmp_path / sub).mkdir()
    monkeypatch.chdir(tmp_path / "cwd")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("SPINAGRAM_THEME_PATH", raising=False)
    monkeypatch.syspath_prepend(str(tmp_path / "site"))
    eps: list = []
    real = importlib.metadata.entry_points

    def fake(**kw):
        if kw.get("group") == GROUP:
            return [e for e in eps]
        return real(**kw)

    monkeypatch.setattr(importlib.metadata, "entry_points", fake)
    w = {"root": tmp_path, "eps": eps}

    def env(*dirs):
        monkeypatch.setenv("SPINAGRAM_THEME_PATH", os.pathsep.join(str(tmp_path / d) for d in dirs))

    def ep(name, value):
        eps.append(importlib.metadata.EntryPoint(name=name, value=value, group=GROUP))

    def package(pkg, theme_dir_attr=None):
        """A package ``pkg`` with theme.yaml in its directory, or a module ``pkg.paths`` whose THEME names a
        theme directory elsewhere."""
        root = tmp_path / "site" / pkg
        root.mkdir(parents=True)
        (root / "__init__.py").write_text("")
        importlib.invalidate_caches()
        if theme_dir_attr is None:
            _theme(root, pkg)
        else:
            (root / "paths.py").write_text(f"THEME = {str(theme_dir_attr)!r}\n")
        return root

    w.update(env=env, ep=ep, package=package)
    return w


def _setup_builtin(w):
    _theme(w["root"] / "envA" / "default", "shadow")
    w["env"]("envA")
    return BUILTIN / "default"


def _setup_abs(w):
    return _theme(w["root"] / "elsewhere" / "brand")


def _setup_home(w):
    return _theme(w["root"] / "home" / "brand")


def _setup_cwd(w):
    return _theme(w["root"] / "cwd" / "brand")


def _setup_env(w):
    w["env"]("envA")
    return _theme(w["root"] / "envA" / "brand")


def _setup_env_order(w):
    w["env"]("envA", "envB")
    _theme(w["root"] / "envB" / "brand")
    return _theme(w["root"] / "envA" / "brand")


def _setup_env_missing_first(w):
    w["env"]("missing", "envB")
    return _theme(w["root"] / "envB" / "brand")


def _setup_env_without_yaml(w):
    w["env"]("envA", "envB")
    (w["root"] / "envA" / "brand").mkdir()                   # a directory without theme.yaml is skipped
    return _theme(w["root"] / "envB" / "brand")


def _setup_cwd_beats_env(w):
    w["env"]("envA")
    _theme(w["root"] / "envA" / "brand")
    return _theme(w["root"] / "cwd" / "brand")


def _setup_env_beats_ep(w):
    w["env"]("envA")
    w["package"]("brand_pkg_a")
    w["ep"]("brand", "brand_pkg_a")
    return _theme(w["root"] / "envA" / "brand")


def _setup_ep_package(w):
    w["ep"]("brand", "brand_pkg_b")
    return w["package"]("brand_pkg_b")


def _setup_ep_attr(w):
    target = _theme(w["root"] / "shipped" / "brand-theme")
    w["package"]("brand_pkg_c", target)
    w["ep"]("other", "brand_pkg_c")                          # other names are ignored
    w["ep"]("brand", "brand_pkg_c.paths:THEME")
    return target


RESOLVES = [  # (id, setup → expected dir, ref)
    ("builtin-first", _setup_builtin, "default"),
    ("absolute-path", _setup_abs, None),
    ("home-path", _setup_home, "~/brand"),
    ("cwd-relative", _setup_cwd, "brand"),
    ("env-dir", _setup_env, "brand"),
    ("env-order", _setup_env_order, "brand"),
    ("env-missing-dir-skipped", _setup_env_missing_first, "brand"),
    ("env-dir-without-yaml-skipped", _setup_env_without_yaml, "brand"),
    ("path-before-env", _setup_cwd_beats_env, "brand"),
    ("env-before-entry-point", _setup_env_beats_ep, "brand"),
    ("entry-point-package", _setup_ep_package, "brand"),
    ("entry-point-attr", _setup_ep_attr, "brand"),
]


@pytest.mark.parametrize("setup,ref", [r[1:] for r in RESOLVES], ids=[r[0] for r in RESOLVES])
def test_resolve(world, setup, ref):
    want = setup(world)
    ref = ref or str(want)
    assert _resolve_dir(ref) == want.resolve()
    assert Theme.load(ref).root == want.resolve()                # Theme.load / -t name


@pytest.mark.parametrize("setup", [_setup_env, _setup_ep_package, _setup_ep_attr], ids=["env", "ep-pkg", "ep-attr"])
def test_extends_resolves_by_name(world, setup):
    want = setup(world)
    child = _theme(world["root"] / "child", extends="brand")
    t = Theme.load(child)
    assert t.root == child.resolve() and t.data["name"] == "child" and want.is_dir()


def test_extends_relative_to_the_extending_theme(world):
    _theme(world["root"] / "themes" / "base", "base")
    child = _theme(world["root"] / "themes" / "child", extends="../base")
    assert _resolve_dir("../base", child.resolve()) == (world["root"] / "themes" / "base").resolve()
    assert Theme.load(child).root == child.resolve()


def _names():
    return ", ".join(sorted(x.name for x in BUILTIN.iterdir() if (x / "theme.yaml").is_file()))


def test_not_found_lists_every_place_in_order(world):
    world["env"]("envA", "missing")
    (world["root"] / "envA" / "nope").mkdir()
    world["ep"]("other", "x")
    r = world["root"]
    with pytest.raises(FileNotFoundError) as err:
        _resolve_dir("nope")
    assert str(err.value) == "\n".join([
        "theme 'nope' not found; searched, in order:",
        f"  1. built-in themes ({_names()})",
        f"  2. {r / 'cwd' / 'nope'}",
        f"  3. {r / 'envA' / 'nope'} (SPINAGRAM_THEME_PATH)",
        f"  4. {r / 'missing'} (SPINAGRAM_THEME_PATH; directory missing, skipped)",
        "  5. entry point 'nope' in group 'spinagram.themes' (none installed)",
    ])


def test_not_found_from_extends_lists_the_relative_place(world):
    child = _theme(world["root"] / "child", extends="nope")
    r = world["root"]
    with pytest.raises(FileNotFoundError) as err:
        Theme.load(child)
    assert str(err.value) == "\n".join([
        "theme 'nope' not found; searched, in order:",
        f"  1. built-in themes ({_names()})",
        f"  2. {(r / 'child').resolve() / 'nope'} (relative to the extending theme)",
        f"  3. {r / 'cwd' / 'nope'}",
        "  4. entry point 'nope' in group 'spinagram.themes' (none installed)",
    ])


def test_not_found_path_lists_the_path_only(world):
    r = world["root"]
    with pytest.raises(FileNotFoundError) as err:
        _resolve_dir(str(r / "no" / "theme"))
    assert str(err.value) == f"theme {str(r / 'no' / 'theme')!r} not found; searched, in order:\n  1. {r / 'no' / 'theme'}"


def test_entry_point_without_theme_yaml_is_listed(world):
    pkg = world["root"] / "site" / "empty_pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    importlib.invalidate_caches()
    world["ep"]("nope", "empty_pkg")
    with pytest.raises(FileNotFoundError) as err:
        _resolve_dir("nope")
    assert str(err.value).splitlines()[-1] == \
        f"  3. entry point 'nope' in group 'spinagram.themes' → {pkg} (no theme.yaml)"

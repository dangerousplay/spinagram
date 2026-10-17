"""AI, CNCF and technology logo packs (spec: .specs/features/brand-icons/spec.md)."""
from __future__ import annotations

import dataclasses
import json

import pytest

from spinagram import icons

MONO = '<svg fill="currentColor" viewBox="0 0 24 24"><path d="M{}"/></svg>'
FIXED = '<svg viewBox="0 0 24 24"><path fill="#D97757" d="M{}"/></svg>'


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setenv("SPINAGRAM_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    icons._INDEX_CACHE.clear()
    yield tmp_path
    icons._INDEX_CACHE.clear()


def _offline(name: str, root, files: dict[str, str]):
    """The built-in pack ``name`` reading ``files`` (path → template, laid out like its source) from a folder."""
    for i, (f, template) in enumerate(files.items()):
        p = root / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(template.format(i))
    pack = dataclasses.replace(icons.registry()[name], source={"type": "dir", "path": str(root)})
    icons.fetch(pack)
    return {name: pack}


@pytest.mark.parametrize("name, repo, include, license", [
    ("ai", "lobehub/lobe-icons", ["packages/static-svg/icons/*"], "MIT"),          # BRAND-01
    ("cncf", "cncf/artwork", ["projects/*", "other/*"], "Linux Foundation"),        # BRAND-07
    ("logos", "gilbarbara/logos", ["logos/*"], "CC0-1.0"),                          # BRAND-13
])
def test_packs_are_registered(name, repo, include, license):
    p = icons.registry()[name]
    assert (p.source["type"], p.source["repo"], p.source["include"]) == ("github", repo, include)
    assert len(p.source["ref"]) == 40
    assert license in p.license


# T1 · ai --------------------------------------------------------------------------------------------------
AI = "packages/static-svg/icons/"


@pytest.mark.parametrize("path, name", [
    (AI + "claude-color.svg", "claude"),             # BRAND-02
    (AI + "claude.svg", "claude-mono"),              # BRAND-03
    (AI + "claude-text.svg", "claude-text"),
    (AI + "google-brand-color.svg", "google-brand"),
    (AI + "doubao-text-cn.svg", "doubao-text-cn"),
])
def test_ai_names(path, name):
    got = icons.registry()["ai"].classify(path)
    assert got is not None and got[0] == name


def test_ai_colour_wins_and_mono_gets_both_tones(cache):  # BRAND-02..05
    packs = _offline("ai", cache / "lobe", {AI + "claude-color.svg": FIXED, AI + "claude.svg": MONO,
                                             AI + "openai.svg": MONO, AI + "lmstudio.svg": MONO})
    claude = icons.resolve("ai:claude", packs=packs)
    assert "#D97757" in claude.read_text()
    assert icons.resolve("ai:claude", "dark", packs=packs) == claude  # colour artwork: no dark copy
    light, dark = icons.resolve("ai:openai", packs=packs), icons.resolve("ai:openai", "dark", packs=packs)
    assert light.name == "ai__openai-mono.svg"  # no colour file: the bare name is the monochrome mark
    assert "currentColor" not in light.read_text() and 'fill="#000000"' in light.read_text()
    assert "currentColor" not in dark.read_text() and 'fill="#ffffff"' in dark.read_text()
    assert icons.resolve("ai:chatgpt", packs=packs) == light
    assert icons.resolve("ai:lm-studio", packs=packs) == icons.resolve("ai:lmstudio-mono", packs=packs)  # BRAND-06


# T2 · cncf ------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("path, name, tone", [
    ("projects/harbor/icon/color/harbor-icon-color.svg", "harbor", "light"),                   # BRAND-08
    ("projects/harbor/icon/white/harbor-icon-white.svg", "harbor", "dark"),                    # BRAND-09
    ("projects/harbor/icon/black/harbor-icon-black.svg", "harbor-black", "light"),
    ("projects/harbor/horizontal/color/harbor-horizontal-color.svg", "harbor-horizontal", "light"),  # BRAND-10
    ("projects/harbor/stacked/white/harbor-stacked-white.svg", "harbor-stacked", "dark"),
    ("projects/copa/Icon/Color/copa-icon-color.svg", "copa", "light"),                         # any folder case
    ("other/cncf/icon/color/cncf-icon-color.svg", "cncf", "light"),
])
def test_cncf_names_and_tones(path, name, tone):
    got = icons.registry()["cncf"].classify(path)
    assert got is not None and (got[0], got[1]) == (name, tone)


def test_cncf_skips_wtext_copies():  # BRAND-11
    assert icons.registry()["cncf"].classify("projects/copa/Horizontal/Color/copa-horizontal-color-wtext.svg") is None


def test_cncf_resolves_forms_aliases_and_prefers_svg(cache):  # BRAND-08..12
    root = cache / "artwork"
    packs = _offline("cncf", root, {
        "projects/harbor/icon/color/harbor-icon-color.svg": FIXED,
        "projects/harbor/icon/white/harbor-icon-white.svg": FIXED,
        "projects/kubernetes/icon/color/kubernetes-icon-color.svg": FIXED,
        "projects/kanister/stacked/color/kanister-stacked-color.svg": FIXED,
        "projects/argo/icon/color/argo-icon-color.png": FIXED,
        "projects/argo/icon/color/argo-icon-color.svg": FIXED})
    light, dark = icons.resolve("cncf:harbor", packs=packs), icons.resolve("cncf:harbor", "dark", packs=packs)
    assert dark.read_text() == (root / "projects/harbor/icon/white/harbor-icon-white.svg").read_text() != light.read_text()
    assert icons.resolve("cncf:k8s", packs=packs) == icons.resolve("cncf:kubernetes", packs=packs)
    assert icons.resolve("cncf:argocd", packs=packs).suffix == ".svg"
    assert icons.resolve("cncf:kanister", packs=packs) == icons.resolve("cncf:kanister-stacked", packs=packs)


# T3 · logos -----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("path, name", [
    ("logos/gitlab-icon.svg", "gitlab"),         # BRAND-14
    ("logos/gitlab.svg", "gitlab-logo"),         # BRAND-15
    ("logos/github-icon-dark.svg", "github-dark"),
])
def test_logos_names(path, name):
    got = icons.registry()["logos"].classify(path)
    assert got is not None and got[0] == name


def test_logos_bare_name_falls_back_to_the_full_logo(cache):  # BRAND-14..16
    packs = _offline("logos", cache / "logos", {"logos/gitlab-icon.svg": FIXED, "logos/gitlab.svg": FIXED,
                                                 "logos/oracle.svg": FIXED})
    assert icons.resolve("logos:gitlab", packs=packs).name == "logos__gitlab.svg"
    assert icons.resolve("logos:gitlab-logo", packs=packs).name == "logos__gitlab-logo.svg"
    assert icons.resolve("logos:oracle", packs=packs).name == "logos__oracle-logo.svg"


# T4 · github source ---------------------------------------------------------------------------------------
def test_github_source_quotes_paths_and_skips_unnamed_files(cache, monkeypatch):  # BRAND-17, BRAND-18
    tree = {"tree": [{"type": "blob", "path": "projects/x/icon/color/x icon-color.svg"},
                     {"type": "blob", "path": "projects/x/icon/color/x-icon-color-wtext.svg"},
                     {"type": "blob", "path": "projects/x/horizontal/color/x-horizontal-color.png"}]}
    asked: list[str] = []

    def get(url: str, timeout: int = 300) -> bytes:
        asked.append(url)
        return json.dumps(tree).encode() if "api.github.com" in url else FIXED.format(1).encode()

    monkeypatch.setattr(icons, "_get", get)
    got = list(icons._iter_source(icons.registry()["cncf"]))
    assert [p for p, _ in got] == ["projects/x/icon/color/x icon-color.svg"]
    assert [u for u in asked if "raw.githubusercontent" in u][0].endswith("/projects/x/icon/color/x%20icon-color.svg")
    assert len(asked) == 2  # the tree, then one file: the -wtext copy and the unnamed PNG are never downloaded


# T5 · catalog ---------------------------------------------------------------------------------------------
def test_ai_and_cncf_icons_add_tags_and_categories():  # BRAND-19
    from spinagram import Diagram
    from spinagram.metadata import effective_category, effective_tags

    d = Diagram("B1", "Models")
    d.box("Claude", icon="ai:claude")
    d.box("Ollama", icon="ai:ollama")
    d.box("Harbor", icon="cncf:harbor")
    d.box("GitLab", icon="logos:gitlab")
    assert effective_tags(d) == ["ai", "cncf"]
    assert effective_category(d) == "AI"

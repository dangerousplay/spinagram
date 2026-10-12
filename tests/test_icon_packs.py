"""Self-hosted and network icon packs (spec: .specs/features/selfhosted-icons/spec.md)."""
from __future__ import annotations

import dataclasses

import pytest

from spinagram import icons

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8"><rect width="8" height="8" fill="{}"/></svg>'


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setenv("SPINAGRAM_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    icons._INDEX_CACHE.clear()
    yield tmp_path
    icons._INDEX_CACHE.clear()


def _offline(name: str, root, files: list[str]):
    """The built-in pack ``name`` reading ``files`` (laid out like its real source) from a local folder."""
    for i, f in enumerate(files):
        p = root / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(SVG.format(f"#{i:06x}"))
    pack = dataclasses.replace(icons.registry()[name], source={"type": "dir", "path": str(root)})
    icons.fetch(pack)
    return pack


# T1 · network ---------------------------------------------------------------------------------------
NETWORK_FILES = ["svg/square/blue/sq_router_blue.svg", "svg/square/green/sq_router_green.svg",
                 "svg/circle/blue/c_router_blue.svg", "svg/circle/red/c_router_red.svg", "svg/naked/router.svg",
                 "svg/square/blue/sq_firewall_blue.svg", "svg/square/blue/sq_loadbalancer_blue.svg",
                 "svg/square/blue/sq_switch_multilayer_blue.svg", "svg/square/blue/sq_wifi_blue.svg",
                 "svg/square/blue/sq_server_blue.svg", "README.md"]


def test_network_pack_is_registered():  # ICON-07
    p = icons.registry()["network"]
    assert (p.source["type"], p.source["repo"], p.source["include"]) == ("github", "ecceman/affinity", ["svg/*"])
    assert len(p.source["ref"]) == 40  # a pinned commit
    assert "Unlicense" in p.license


@pytest.mark.parametrize("path, name", [
    ("svg/square/blue/sq_router_blue.svg", "router"),                  # ICON-08
    ("svg/square/green/sq_router_green.svg", "router-green"),          # ICON-09
    ("svg/square/gray/sq_switch_multilayer_gray.svg", "switch-multilayer-gray"),
    ("svg/circle/blue/c_router_blue.svg", "router-circle"),            # ICON-10
    ("svg/circle/red/c_router_red.svg", "router-circle-red"),
    ("svg/naked/router.svg", "router-plain"),                          # ICON-11
    ("svg/circle/gray/c_camera_dome.svg", "camera-dome-circle-gray"),  # colour from the folder
    ("svg/circle/blue/c_bug.svg", "bug-circle"),
    ("svg/square/red/sq_router_cloud_red.svg", "router-cloud-red"),
])
def test_network_names(path, name):
    got = icons.registry()["network"].classify(path)
    assert got is not None and got[0] == name and got[1] == "light"


def test_network_skips_files_no_rule_matches():
    assert icons.registry()["network"].classify("png/square/blue/sq_router_blue.png") is None


def test_network_pack_resolves_every_name_form_and_alias(cache):  # ICON-08..12
    pack = _offline("network", cache / "affinity", NETWORK_FILES)
    packs = {"network": pack}
    got = {ref: icons.resolve(ref, packs=packs) for ref in (
        "network:router", "network:router-blue", "network:router-green", "network:router-circle",
        "network:router-circle-red", "network:router-plain", "network:fw", "network:lb", "network:l3-switch",
        "network:ap")}
    assert all(p is not None and p.exists() for p in got.values()), got
    assert got["network:router"] == got["network:router-blue"]
    assert len({got[r] for r in ("network:router", "network:router-green", "network:router-circle",
                                 "network:router-circle-red", "network:router-plain")}) == 5
    assert got["network:fw"] == icons.resolve("network:firewall", packs=packs)
    assert got["network:lb"] == icons.resolve("network:loadbalancer", packs=packs)
    assert got["network:l3-switch"] == icons.resolve("network:switch-multilayer", packs=packs)
    assert got["network:ap"] == icons.resolve("network:wifi", packs=packs)

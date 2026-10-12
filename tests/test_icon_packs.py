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
                 "svg/square/blue/sq_server_blue.svg", "svg/square/gray/sq_router.svg", "README.md"]


def test_network_pack_is_registered():  # ICON-07
    p = icons.registry()["network"]
    assert (p.source["type"], p.source["repo"], p.source["include"]) == ("github", "ecceman/affinity", ["svg/*"])
    assert len(p.source["ref"]) == 40  # a pinned commit
    assert "Unlicense" in p.license


@pytest.mark.parametrize("path, name", [
    ("svg/square/blue/sq_router_blue.svg", "router"),                  # ICON-08
    ("svg/square/green/sq_router_green.svg", "router-green"),          # ICON-09
    ("svg/square/gray/sq_switch_multilayer.svg", "switch-multilayer-gray"),  # upstream gray files lack the suffix
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
    gray = icons.resolve("network:router-gray", packs=packs)  # from svg/square/gray/sq_router.svg (no suffix)
    assert gray is not None and gray.read_text() == (cache / "affinity" / "svg/square/gray/sq_router.svg").read_text()


# T2 · self-hosted -------------------------------------------------------------------------------------
SELFHOSTED_FILES = ["svg/proxmox.svg", "svg/proxmox-light.svg", "svg/portainer.svg", "svg/portainer-dark.svg",
                    "svg/vmware-esxi.svg", "svg/vmware-nsx.svg", "svg/pi-hole.svg", "svg/proxmox-backup-server.svg",
                    "svg/opnsense.svg", "svg/nightowl-light.svg", "png/proxmox.png", "meta/x.json"]


def test_selfhosted_pack_is_registered():  # ICON-01
    p = icons.registry()["selfhosted"]
    assert (p.source["type"], p.source["repo"], p.source["include"]) == (
        "github", "homarr-labs/dashboard-icons", ["svg/*"])
    assert len(p.source["ref"]) == 40
    assert "Apache-2.0" in p.license


@pytest.mark.parametrize("path, name, tone", [
    ("svg/proxmox.svg", "proxmox", "light"),                 # ICON-02
    ("svg/proxmox-light.svg", "proxmox", "dark"),            # ICON-03
    ("svg/portainer-dark.svg", "portainer-dark", "light"),   # ICON-04
    ("svg/plex-alt-light.svg", "plex-alt", "dark"),
])
def test_selfhosted_names_and_tones(path, name, tone):
    got = icons.registry()["selfhosted"].classify(path)
    assert got is not None and (got[0], got[1]) == (name, tone)


def test_selfhosted_skips_other_formats():
    assert icons.registry()["selfhosted"].classify("png/proxmox.png") is None


def test_selfhosted_aliases_and_tones_resolve(cache):  # ICON-02..05, edge case
    pack = _offline("selfhosted", cache / "dashboard-icons", SELFHOSTED_FILES)
    packs = {"selfhosted": pack}
    light, dark = icons.resolve("selfhosted:proxmox", packs=packs), icons.resolve("selfhosted:proxmox", "dark",
                                                                                     packs=packs)
    assert light.read_text() != dark.read_text()
    assert dark.read_text() == (cache / "dashboard-icons" / "svg/proxmox-light.svg").read_text()
    assert icons.resolve("selfhosted:portainer-dark", packs=packs).read_text() == (
        cache / "dashboard-icons" / "svg/portainer-dark.svg").read_text()
    for alias, target in (("pve", "proxmox"), ("esxi", "vmware-esxi"), ("pihole", "pi-hole"),
                          ("pbs", "proxmox-backup-server"), ("nsx", "vmware-nsx")):
        assert icons.resolve(f"selfhosted:{alias}", packs=packs) == icons.resolve(f"selfhosted:{target}",
                                                                                   packs=packs), alias
    only = icons.resolve("selfhosted:nightowl", packs=packs)  # only a -light file exists
    assert only is not None and only.read_text() == (cache / "dashboard-icons" / "svg/nightowl-light.svg").read_text()


def test_dark_fill_draws_the_dark_variant(cache, monkeypatch):  # ICON-06
    from spinagram import Diagram
    from spinagram.layout import build_scene
    from spinagram.theme import Theme

    pack = _offline("selfhosted", cache / "dashboard-icons", SELFHOSTED_FILES)
    real = icons.registry
    monkeypatch.setattr(icons, "registry", lambda cwd=None: {**real(cwd), "selfhosted": pack})
    d = Diagram("H1", "Tones")
    d.box("PVE", icon="selfhosted:proxmox", style="dark", x=100, y=300, w=300, h=120)
    d.box("PVE 2", icon="selfhosted:proxmox", x=500, y=300, w=300, h=120)
    shapes = build_scene(d, Theme.load("default")).shapes()
    assert shapes["pve"].icon.path.read_text() == (cache / "dashboard-icons" / "svg/proxmox-light.svg").read_text()
    assert shapes["pve-2"].icon.path.read_text() == (cache / "dashboard-icons" / "svg/proxmox.svg").read_text()


# T3 · catalog inference --------------------------------------------------------------------------------
def test_new_packs_add_tags_and_categories():  # ICON-13, ICON-14, ICON-15
    from spinagram import Diagram
    from spinagram.metadata import effective_category, effective_tags

    lab = Diagram("L1", "Lab")
    for n in ("proxmox", "opnsense", "truenas"):
        lab.box(n, icon=f"selfhosted:{n}")
    lab.box("Switch", icon="network:switch")
    assert effective_tags(lab) == ["network", "self-hosted"]
    assert effective_category(lab) == "Self-hosted"

    net = Diagram("N1", "Net")
    for n in ("router", "switch", "firewall"):
        net.box(n, icon=f"network:{n}")
    assert (effective_tags(net), effective_category(net)) == (["network"], "Network")


# fix · a pack registered after the theme loaded -----------------------------------------------------------
def test_theme_sees_a_pack_registered_after_it_loaded(cache, monkeypatch):
    """A long-running `spinagram serve` keeps its theme: packs added later must still resolve."""
    from spinagram.theme import Theme

    theme = Theme.load("default")
    assert "late" not in theme.icon_packs()  # the theme has cached its pack list
    root = cache / "late-src"
    root.mkdir()
    (root / "gear.svg").write_text(SVG.format("#123456"))
    icons.register("late", {"type": "dir", "path": str(root)})  # user registry, after the theme loaded
    got = theme.icon("late:gear")
    assert got is not None and got.read_text() == (root / "gear.svg").read_text()

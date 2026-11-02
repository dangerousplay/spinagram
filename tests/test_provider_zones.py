"""Provider zone styles of the default theme (wasm-editor T30): AWS, Azure, Google Cloud and Kubernetes groups carry
their provider's header icon, following each provider's diagram convention."""
import pytest

from spinagram import Diagram, Theme, build_scene, icons
from spinagram.qa import check
from spinagram.scene import Shape, Text

# style -> header icon ("pack:name"), or None where the provider's convention draws no icon
EXPECTED = {
    "aws-cloud": "aws:group-aws-cloud",
    "aws-account": "aws:group-aws-account",
    "aws-region": "aws:group-region",
    "aws-vpc": "aws:group-virtualprivatecloud-vpc",
    "aws-az": None,  # an Availability Zone is a dashed box without an icon
    "aws-public-subnet": "aws:group-publicsubnet",
    "aws-private-subnet": "aws:group-privatesubnet",
    "aws-auto-scaling-group": "aws:group-auto-scalinggroup",
    "aws-corporate-dc": "aws:group-corporatedatacenter",
    "aws-spot-fleet": "aws:group-spot-fleet",
    "aws-server-contents": "aws:group-servercontents",
    "aws-ec2-contents": "aws:group-ec2instancecontents",
    "azure-management-group": "azure:management-groups",
    "azure-subscription": "azure:subscriptions",
    "azure-resource-group": "azure:resource-groups",
    "azure-vnet": "azure:virtual-networks",
    "azure-subnet": "azure:subnet",
    "gcp-cloud": "gcp:cloud-generic",
    "gcp-project": "gcp:project",
    "gcp-region": None,  # Google draws regions, zones and subnets as coloured areas
    "gcp-zone": None,
    "gcp-vpc": "gcp:virtual-private-cloud",
    "gcp-subnet": None,
    "k8s-cluster": None,  # the Kubernetes icon set has no cluster icon
    "k8s-namespace": "k8s:ns",
}
WITH_ICON = [s for s, i in EXPECTED.items() if i]


def test_every_provider_style_exists_with_its_icon():
    t = Theme.load("default")
    for style, icon in EXPECTED.items():
        assert t.zone_style(style)["icon"] == icon, style
        assert t.style_key("zone", style) == style, f"{style} is not a zone style of the theme"


def test_aws_subnet_is_the_private_subnet():
    t = Theme.load("default")
    assert t.zone_style("aws-subnet") == t.zone_style("aws-private-subnet")


def test_styles_differ_where_conventions_differ():
    t = Theme.load("default")
    pub, priv = t.zone_style("aws-public-subnet"), t.zone_style("aws-private-subnet")
    assert pub["stroke"] != priv["stroke"] and pub["fill"] != priv["fill"]  # green vs teal
    assert t.zone_style("aws-region")["dashed"] and not t.zone_style("aws-vpc")["dashed"]
    assert t.zone_style("azure-vnet")["dashed"] and not t.zone_style("azure-subscription")["dashed"]
    assert t.zone_style("aws-vpc")["header"] == {"inset": False}  # the corner icon is flush, as in AWS's groups


def test_every_icon_names_a_registered_pack():
    packs = icons.registry()
    for ref in filter(None, EXPECTED.values()):
        assert ref.split(":", 1)[0] in packs, ref


@pytest.mark.real_icon_cache
def test_every_icon_resolves_in_its_pack_index():
    """Against the packs cached on this machine (skipped where a pack is not downloaded)."""
    packs = icons.registry()
    for ref in filter(None, EXPECTED.values()):
        pack = packs[ref.split(":", 1)[0]]
        if icons.index(pack, auto_fetch=False) is None:
            pytest.skip(f"icon pack {pack.name!r} is not cached")
        assert icons.resolve(ref, packs=packs) is not None, ref


@pytest.fixture
def fake_icons(tmp_path, monkeypatch):
    svg = tmp_path / "i.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>')
    monkeypatch.setattr(icons, "resolve", lambda ref, tone="light", *, packs=None: svg)
    return svg


def _scene(fake=True):
    d = Diagram("Z", "Provider zones")
    ids = {}
    for n, style in enumerate(EXPECTED):
        z = d.zone(style, x=40 + (n % 5) * 360, y=180 + (n // 5) * 260, w=330, h=220, color=style, id=f"z-{style}")
        ids[style] = z.id
    return build_scene(d, Theme.load("default")), ids


def test_a_zone_of_each_style_renders_its_header_icon(fake_icons):
    sc, ids = _scene()
    by = {i.id: i for i in sc.items if isinstance(i, (Shape, Text))}
    shapes = [i for i in sc.items if isinstance(i, (Shape, Text))]
    icon_owners = {i.id for i in shapes if getattr(i, "icon", None) is not None}
    for style, icon in EXPECTED.items():
        # the header icon is a shape named after the zone's shape id (`z0-icon` for the first zone, and so on)
        zid = next(s for s, z in sc.zone_ids.items() if z == ids[style])
        assert (f"{zid}-icon" in by) == bool(icon), style
        if icon:
            assert by[f"{zid}-icon"].icon is not None
    assert icon_owners


def test_provider_styles_pass_spinagram_check(fake_icons):
    sc, _ = _scene()
    assert check(sc) == []


@pytest.mark.real_icon_cache
def test_the_aws_showcase_follows_the_group_conventions_and_checks_clean():
    """examples/showcase/editable_platform.yaml: Cloud > account > Region > VPC > subnets, each with its icon."""
    from pathlib import Path

    from spinagram.yaml_io import load

    packs = icons.registry()
    if icons.index(packs["aws"], auto_fetch=False) is None:
        pytest.skip("icon pack 'aws' is not cached")
    root = Path(__file__).resolve().parents[1] / "examples" / "showcase"
    d = load(root / "editable_platform.yaml")[0]
    sc = build_scene(d, Theme.load("default"))
    owners = {i.id: i for i in sc.items if isinstance(i, (Shape, Text)) and i.id.endswith("-icon")}
    assert len(owners) == 7 and all(o.icon is not None for o in owners.values())  # one header icon per group
    assert check(sc) == []

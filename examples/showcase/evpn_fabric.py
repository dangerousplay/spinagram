"""An EVPN-VXLAN data center fabric: an eBGP underlay (one AS per spine layer and per leaf pair), an EVPN overlay
with VNI subnets (VNI 10010 = 10.10.0.0/24, VNI 10020 = 10.20.0.0/24), hosts multihomed to leaf pairs with
ESI-LAG, and border leaves peering eBGP with two ISPs. Spine-leaf links are anchored, so they are drawn straight."""
from spinagram import Diagram

N = {"w": 196, "h": 84}

d = Diagram("NET02", "EVPN-VXLAN data center fabric",
            subtitle="eBGP underlay · EVPN overlay · all-active ESI multihoming · eBGP to two ISPs",
            layout={"engine": "flex", "direction": "down", "rank_gap": 96,
                    "area": [56, 176, 1808, 830]})
d.stylesheet("showcase.css")
d.stylesheet("fabric.css")

with d.group("Spines · AS 65000 · EVPN route servers", id="spines", class_="as spine-as", direction="right",
             gap=260, align="center"):
    spines = [d.box(f"spine-{i}", text=f"lo 10.0.0.{i}/32", icon="network:switch-multilayer-green",
                    class_="spine", id=f"spine-{i}", **N) for i in (1, 2)]
with d.group(id="pods", class_="bare", direction="right", gap=24, align="start", padding=0):
    pairs, below = {}, {}
    for key, label, cls, icon, n0 in (("border", "Border leaves · AS 65100", "as border-as", "network:switch-multilayer",
                                       11),
                                      ("a", "Rack A · AS 65101", "as", "network:switch", 21),
                                      ("b", "Rack B · AS 65102", "as", "network:switch", 31)):
        with d.group(id=f"pod-{key}", class_="bare", direction="down", gap=56, align="center", padding=0):
            with d.group(label, id=f"pair-{key}", class_=cls, direction="right", gap=16):
                pairs[key] = [d.box(f"leaf-{key}{i}" if key != "border" else f"border-{i}",
                                    text=f"VTEP 10.0.1.{n0 + i}", icon=icon,
                                    class_="border-leaf" if key == "border" else "leaf",
                                    id=f"leaf-{key}{i}" if key != "border" else f"border-{i}", **N) for i in (1, 2)]
            if key == "border":
                with d.group("Internet transit", id="wan", class_="wan", direction="right", gap=16):
                    below[key] = [d.box(f"ISP {x}", text=f"AS {asn}", icon="network:router-cloud-red", class_="isp",
                                        id=f"isp-{x}", **N) for x, asn in (("A", 64512), ("B", 64513))]
            else:
                vni, net, role = ("10010", "10.10.0.10", "web") if key == "a" else ("10020", "10.20.0.10", "db")
                with d.group(f"VNI {vni} · {role}", id=f"vni-{role}", class_="vni", direction="right", gap=16):
                    below[key] = [d.box(f"{role}-01", text=f"{net}, ESI-LAG", icon="network:server-circle",
                                        class_="host", **N)]
web, db, isps = below["a"][0], below["b"][0], below["border"]

# eBGP underlay: every leaf peers with both spines (straight lines, the usual spine-leaf drawing)
leaves = (*pairs["border"], *pairs["a"], *pairs["b"])
for s, spine in enumerate(spines):
    for j, leaf in enumerate(leaves):
        d.edge(spine.at("bottom", 0.15 + 0.7 * j / (len(leaves) - 1)), leaf.at("top", 0.35 + 0.3 * s),
               class_="underlay-ebgp")
# multihoming: each host to both leaves of its pair, one Ethernet segment
for host, pair in ((web, pairs["a"]), (db, pairs["b"])):
    for leaf in pair:
        d.edge(leaf.bottom, host.top, class_="esi-multihoming")
for border, isp in zip(pairs["border"], isps):
    d.edge(border.bottom, isp.top, "eBGP", class_="wan-ebgp")

d.step("web-01 sends to db-01 over its ESI-LAG", on=web)
d.step("leaf-a1 encapsulates in VXLAN, VNI 10010 → L3 VNI", on="leaf-a1")
d.step("Spines route on the outer IP only", on="spine-1")
d.step("leaf-b1 decapsulates and delivers on VNI 10020", on="leaf-b1")
d.step("Border leaves export EVPN type-5 routes to the ISPs", on="border-1")
d.callout(db, "One Ethernet segment on two leaves: both forward, a DF election handles BUM traffic.",
          title="ESI multihoming", kind="info")
d.callout("spine-2", "Spines carry the EVPN address family but hold no VNIs: they only route between VTEPs.",
          title="Lean spines", kind="tip")
d.add_legend({".spine": "Spine (EVPN route server)", ".border-leaf": "Border leaf", ".leaf": "Leaf (VTEP)",
              ".host": "Multihomed host", ".isp": "ISP router", "edge.underlay-ebgp": "eBGP underlay",
              "edge.esi-multihoming": "ESI multihoming", "edge.wan-ebgp": "eBGP to transit"})

diagram = d

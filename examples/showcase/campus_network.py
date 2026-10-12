"""A campus network in three tiers: WAN edge, a redundant core and access switches serving Wi-Fi, phones and
desks, drawn with the Affinity symbols of the `network` pack in their colour and circle variants."""
from spinagram import Diagram

N = {"w": 220, "h": 92}
E = {"w": 210, "h": 80}

d = Diagram("NET01", "Campus network", subtitle="Redundant core, access layer and endpoints, left to right",
            layout={"engine": "flex", "direction": "right", "rank_gap": 64, "route": "ortho",
                    "area": [56, 176, 1808, 830]})
d.stylesheet("showcase.css")
d.stylesheet("campus.css")

with d.group("WAN edge", id="edge", class_="tier", direction="down", gap=40, align="center"):
    isp = d.box("ISP", text="2 × 10 Gb/s", icon="network:internet", class_="internet", **N)
    router = d.box("Edge router", text="BGP, NAT", icon="network:router-red", class_="edge-gear", **N)
    fw = d.box("Firewall", text="HA pair", icon="network:firewall-red", class_="edge-gear", **N)
with d.group("Core", id="core", class_="tier", direction="down", gap=72, align="center"):
    core_a = d.box("Core A", text="L3, 100 Gb/s", icon="network:switch-multilayer-green", class_="core", **N)
    core_b = d.box("Core B", text="L3, 100 Gb/s", icon="network:switch-multilayer-green", class_="core", **N)
with d.group("Access", id="access", class_="tier", direction="down", gap=24, align="center"):
    floors = [d.box(f"Floor {i}", text="48 × 2.5 Gb/s", icon="network:switch", class_="access", id=f"floor-{i}",
                    **N) for i in (1, 2, 3)]
    wlc = d.box("Wireless LAN", text="controller", icon="network:wlc", class_="access", **N)
with d.group("Endpoints", id="endpoints", class_="tier", direction="down", gap=24, align="center"):
    ap = d.box("Access points", text="Wi-Fi 7", icon="network:wifi-plain", class_="endpoint", **E)
    phone = d.box("IP phones", text="PoE", icon="network:ip-phone-circle", class_="endpoint", **E)
    desk = d.box("Desks", text="1 Gb/s", icon="network:client-circle", class_="endpoint", **E)
    printer = d.box("Printers", text="VLAN 40", icon="network:printer-circle", class_="endpoint", **E)

isp >> router >> fw
fw.to(core_a, class_="uplink")
fw.to(core_b, class_="uplink")
d.edge(core_a, core_b, "VSS", class_="redundant-link")
core_a.to([floors[0], floors[1]], class_="uplink")
core_b.to([floors[2], wlc], class_="uplink")
floors[0] >> ap
floors[1] >> phone
floors[2] >> desk
wlc.to(printer, "Wi-Fi")
d.callout(core_b, "Either core carries the whole campus: links and supervisors are redundant.",
          title="No single point of failure", kind="info")
d.add_legend()

diagram = d

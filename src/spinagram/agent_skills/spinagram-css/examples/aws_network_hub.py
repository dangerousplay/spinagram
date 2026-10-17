"""AWS hub-and-spoke network: Transit Gateway with centralized inspection and egress, after the AWS
reference architecture for multi-VPC networking, with an automatic legend and numbered traffic steps."""
from spinagram import Diagram

N = {"w": 200, "h": 80}  # compact cards: the whole network fits one slide

d = Diagram("AWS02", "Hub-and-spoke networking on AWS",
            subtitle="Transit Gateway hub · centralized inspection and egress · hybrid connectivity",
            layout={"engine": "flex", "direction": "right", "gap": 32, "route": "ortho",
                    "area": [56, 176, 1808, 830]})
d.stylesheet("showcase.css")
d.stylesheet("aws.css")

with d.group(id="hybrid", class_="bare", direction="right", gap=32, align="center"):
    with d.group("Corporate data center", id="dc", class_="onprem", direction="down", gap=24,
                 icon="aws:group-corporatedatacenter"):
        office = d.box("Branch offices", text="SD-WAN", icon="aws:officebuilding", class_="external", **N)
        cgw = d.box("Customer gateway", text="BGP ASN 65010", icon="aws:vpc-customer-gateway",
                    class_="on-premises", **N)
    with d.group(id="links", class_="bare", direction="down", gap=24):
        dx = d.box("Direct Connect", text="2 × 10 Gbps", icon="aws:direct-connect", class_="hybrid-link", **N)
        vpn = d.box("VPN", text="IPsec backup", icon="aws:aws-siteto-site-vpn", class_="hybrid-link", **N)
with d.group("us-east-1 · network account", style="aws-region", direction="down", gap=28, padding=16):
    with d.group(id="services", class_="bare", direction="right", gap=24):
        with d.group("Inspection VPC", style="aws-vpc"):
            nfw = d.box("Network Firewall", text="stateful IPS", icon="aws:network-firewall", class_="security", **N)
        with d.group("Egress VPC", style="aws-vpc", direction="down", gap=20):
            nat = d.box("NAT gateway", text="per AZ", icon="aws:vpcnat-gateway", class_="egress", **N)
            igw = d.box("Internet gateway", text="to 0.0.0.0/0", icon="aws:vpc-internet-gateway", class_="egress", **N)
    with d.group(id="core", class_="bare", direction="right", gap=60, align="center"):
        tgw = d.box("Transit Gateway", text="routing hub", icon="aws:aws-transit-gateway",
                    class_="transit-hub", **N)
        with d.group(id="spokes", class_="bare", direction="down", gap=14):
            spokes = [d.box(name, text=cidr, icon="aws:group-virtualprivatecloud-vpc", class_="workload", **N)
                      for name, cidr, env in (("Prod VPC", "10.1.0.0/16", "prod"),
                                              ("Staging VPC", "10.2.0.0/16", "staging"),
                                              ("Shared services", "10.3.0.0/16", "shared"))]

office >> cgw
cgw.to(dx, "primary", class_="private-circuit")
cgw.to(vpn, "backup", class_="backup-path")
dx.to(tgw, "DX gateway", class_="private-circuit", step="Branch traffic reaches AWS over DX")
vpn.to(tgw, class_="backup-path")
for s in spokes:
    tgw.to(s, arrow="both")
tgw.to(nfw, "inspect", class_="inspection", step="TGW sends traffic to inspection")
nfw.to(nat, step="Allowed flows leave via NAT")
nat.to(igw, step="The internet gateway egresses")
d.add_legend()

"""AWS hub-and-spoke network: Transit Gateway with centralized inspection and egress,
after the AWS reference architecture for multi-VPC networking."""
from spinagram import Diagram

N = {"w": 212, "h": 84}  # compact cards: the whole network fits one slide

d = Diagram("AWS02", "Hub-and-spoke networking on AWS",
            subtitle="Transit Gateway hub · centralized inspection and egress · hybrid connectivity",
            layout={"engine": "flex", "direction": "right", "gap": 34, "route": "ortho",
                    "area": [56, 176, 1808, 830]})
d.stylesheet("showcase.css")
d.stylesheet("aws.css")

with d.group(id="hybrid", class_="bare", direction="right", gap=40, align="center"):
    with d.group("Corporate data center", id="dc", class_="onprem", direction="down", gap=24,
                 icon="aws:group-corporatedatacenter"):
        office = d.box("Branch offices", text="SD-WAN", icon="aws:officebuilding", class_="client", **N)
        cgw = d.box("Customer gateway", text="BGP ASN 65010", icon="aws:vpc-customer-gateway",
                    class_="onprem-gear", **N)
    with d.group(id="links", class_="bare", direction="down", gap=40):
        dx = d.box("Direct Connect", text="2 × 10 Gbps", icon="aws:direct-connect", class_="hybrid", **N)
        vpn = d.box("VPN", text="IPsec backup", icon="aws:aws-siteto-site-vpn", class_="hybrid", **N)
with d.group("us-east-1 · network account", style="aws-region", direction="down", gap=28):
    with d.group(id="services", class_="bare", direction="right", gap=40):
        with d.group("Inspection VPC", style="aws-vpc"):
            nfw = d.box("Network Firewall", text="stateful IPS", icon="aws:network-firewall", class_="security", **N)
        with d.group("Egress VPC", style="aws-vpc", direction="down", gap=20):
            nat = d.box("NAT gateway", text="per AZ", icon="aws:vpcnat-gateway", class_="egress", **N)
            igw = d.box("Internet gateway", text="0.0.0.0/0", icon="aws:vpc-internet-gateway", class_="egress", **N)
    with d.group(id="core", class_="bare", direction="right", gap=60, align="center"):
        tgw = d.box("Transit Gateway", text="2 route tables", icon="aws:aws-transit-gateway",
                    class_="hub", **N)
        with d.group(id="spokes", class_="bare", direction="down", gap=14):
            spokes = [d.box(name, text=cidr, icon="aws:group-virtualprivatecloud-vpc", class_=f"spoke {env}", **N)
                      for name, cidr, env in (("Prod VPC", "10.1.0.0/16", "prod"),
                                              ("Staging VPC", "10.2.0.0/16", "staging"),
                                              ("Shared services", "10.3.0.0/16", "shared"))]
internet = d.box("Internet", icon="aws:internet", class_="client", **N)

office >> cgw
cgw.to(dx, "primary", class_="hybrid")
cgw.to(vpn, "backup", class_="hybrid backup")
dx.to(tgw, "DX gateway", class_="hybrid")
vpn.to(tgw, class_="hybrid backup")
for s in spokes:
    tgw.to(s, arrow="both")
tgw.to(nfw, "inspect", class_="inspect")
nfw >> nat >> igw
igw.to(internet, "egress")

diagram = d

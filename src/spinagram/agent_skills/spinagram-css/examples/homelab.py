"""A homelab private cloud: OPNsense at the edge, a core switch with Wi-Fi and DNS, a three-node Proxmox VE
cluster running K3s and services, TrueNAS storage and Proxmox Backup Server, split into VLANs. Self-hosted logos
from the `selfhosted` pack, network symbols from the `network` pack."""
from spinagram import Diagram

N = {"w": 196, "h": 96}

d = Diagram("HOME01", "Homelab private cloud",
            subtitle="Proxmox VE cluster behind OPNsense, with TrueNAS storage and off-host backups",
            layout={"engine": "flex", "direction": "right", "rank_gap": 28, "route": "ortho",
                    "area": [56, 176, 1808, 830]})
d.stylesheet("showcase.css")
d.stylesheet("homelab.css")

with d.group("VLAN 10 · edge", id="edge", class_="vlan dmz", direction="down", gap=22, padding=16):
    internet = d.box("Internet", text="ISP fibre", icon="network:internet", class_="external", **N)
    fw = d.box("Firewall", text="OPNsense", icon="selfhosted:opnsense", class_="security", **N)
    vpn = d.box("VPN", text="WireGuard", icon="selfhosted:wireguard", class_="security", **N)
with d.group("VLAN 1 · core", id="core", class_="vlan", direction="down", gap=22, padding=16):
    wifi = d.box("Wi-Fi", text="UniFi APs", icon="selfhosted:unifi", class_="networking", **N)
    switch = d.box("Core switch", text="10 GbE, L3", icon="network:l3-switch", class_="networking", **N)
    dns = d.box("DNS", text="Pi-hole", icon="selfhosted:pihole", class_="networking", **N)
with d.group("VLAN 20 · servers", id="servers", class_="vlan servers", direction="down", gap=24, padding=16):
    with d.group(id="nodes", class_="bare", direction="right", gap=12, padding=0):
        pves = [d.box(f"pve-{i}", text="Proxmox VE", icon="selfhosted:proxmox", class_="hypervisor",
                      id=f"pve-{i}", **N) for i in (1, 2, 3)]
    with d.group("Workloads", id="workloads", class_="bare", direction="right", gap=12, padding=0):
        d.box("K3s", text="3 VMs", icon="selfhosted:k3s", class_="workload", **N)
        d.box("Traefik", text="ingress, TLS", icon="selfhosted:traefik", class_="workload", **N)
        d.box("Smart home", text="HA OS", icon="selfhosted:home-assistant", class_="workload", **N)
with d.group("VLAN 30 · storage", id="storage", class_="vlan storage-vlan", direction="down", gap=36, padding=16):
    nas = d.box("TrueNAS", text="ZFS, NFS", icon="selfhosted:truenas-scale", class_="storage", **N)
    pbs = d.box("Backups", text="Proxmox BS", icon="selfhosted:pbs", class_="storage", **N)

internet.to(fw, step="Traffic enters through OPNsense")
vpn.to(fw, class_="remote-access")
fw.to(switch, step="VLANs trunk to the core switch")
switch - wifi
switch - dns
switch.to(pves[0], step="Workloads run on the cluster")
pves[2].to(nas, class_="storage-traffic", step="VMs mount storage on TrueNAS")
nas.to(pbs, class_="backup-job", step="Nightly backups to PBS")
d.callout(vpn, "The only way in from outside: WireGuard on 51820/udp, no other port open.",
          title="Remote access", kind="warning")
d.callout("traefik", "Let's Encrypt certificates and single sign-on for every service.", title="One front door",
          kind="tip")
d.add_legend()

diagram = d

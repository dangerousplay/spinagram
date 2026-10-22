"""A load-balanced Git service across two sites, written with the layout engine helpers.

Every hand fix from the 0.3 version is gone: zone headers inset their icons, zones fit their children,
rows share one size, labels place themselves, edges reach zones and share a trunk, and the legend lists the
line and outline styles the diagram uses.
"""
from spinagram import Diagram

ICONS = "icons/"

d = Diagram("LE01", "Git service across two sites", subtitle="Layout engine showcase", output="git-two-sites")
g = d.grid(cols=[80, 400, 1480], rows=[190, 760], gutter=40)

users = d.box("Developers", id="users", text="git over HTTPS and SSH", icon=ICONS + "users.svg", cell=g[0, 0], h=110)
pool = d.box("lb-pool-https-8081", id="pool", text="8 members · nginx :8081", icon=ICONS + "balancer.svg",
             x=80, y=420, w=280, h=110)

with d.zone("Network 10.10.0.0/16", id="net", fit="children", dash="dashed", stroke="primary", padding=20,
            meaning="network"):
    with d.zone("AZ site-a", id="az-a", fit="children", dash="dotted", stroke="primary", padding=18,
                icon=[ICONS + "site.svg", ICONS + "vendor-wordmark.svg"], equalize="siblings",
                meaning="availability zone"):
        with d.row(x=480, y=330, gap=24, same_size=True):
            for k in "ab":
                d.box(f"node-{k}", id=f"node-{k}", text="gitlab 17 · gitaly", icon=ICONS + "server.svg",
                      badges=[ICONS + "os.svg"])
    with d.zone("AZ site-b", id="az-b", fit="children", dash="dotted", stroke="primary", padding=18,
                icon=[ICONS + "site.svg", ICONS + "vendor-wordmark.svg"], equalize="siblings"):
        with d.row(x=1180, y=330, gap=24, same_size=True):
            d.box("node-c", id="node-c", text="gitlab 17 · gitaly", icon=ICONS + "server.svg",
                  badges=[ICONS + "os.svg"])

nas = d.box("nas-01", id="nas", text="NFS v4 · replicated", icon=ICONS + "storage.svg", x=480, y=800, w=300, h=100)
nas_b = d.box("nas-02", id="nas-b", text="NFS v4 · standby", icon=ICONS + "storage.svg", x=1180, y=800, w=300, h=100)
obs = d.box("observability", id="obs", text="logs and metrics SaaS", icon=ICONS + "cloud.svg", x=1540, y=640, w=300,
            h=110)

d.edge(users, pool, "HTTPS", straight=True)
d.edge(pool, "zone:net", "HTTPS", fan="bus")
d.edge(nas, nas_b, "replication", dashed=True, color="gray", meaning="replication")
logs = [d.edge(f"node-{k}", obs, meaning="log shipping", color="primary") for k in "abc"]
d.bundle(logs, trunk="bottom")
d.add_legend(items="auto", place=(80, 640, 320, 260))

diagram = d

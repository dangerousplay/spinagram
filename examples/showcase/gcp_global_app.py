"""A global web application on Google Cloud: one anycast load balancer in front of GKE in two
regions, Spanner for multi-region consistency and a streaming analytics path to BigQuery."""
from spinagram import Diagram

N = {"w": 230, "h": 84}

d = Diagram("GCP01", "Global web application on Google Cloud",
            subtitle="Anycast load balancing · GKE in two regions · Spanner · streaming analytics",
            layout={"engine": "flex", "direction": "right", "gap": 48, "route": "ortho",
                    "area": [56, 176, 1808, 830]})
d.stylesheet("showcase.css")
d.stylesheet("gcp.css")

users = d.box("Users", text="worldwide", icon="k8s:user", class_="client", **N)
with d.group("Global edge", id="edge", class_="edge", direction="down", gap=28):
    dns = d.box("Cloud DNS", text="anycast, DNSSEC", icon="gcp:cloud-dns", class_="net", **N)
    lb = d.box("Load Balancing", text="global L7 + CDN", icon="gcp:cloud-load-balancing", class_="net lb", **N)
    armor = d.box("Cloud Armor", text="WAF, DDoS", icon="gcp:cloud-armor", class_="security", **N)
with d.group("Project · shop-prod", id="project", class_="project", direction="right", gap=56, align="center"):
    with d.group("VPC · shared", id="vpc", class_="vpc", direction="down", gap=28):
        regions = []
        for rid, name in (("us", "us-central1"), ("eu", "europe-west1")):
            with d.group(name, id=f"r-{rid}", class_="region", direction="down", gap=24):
                gke = d.box("GKE Autopilot", text="web + api pods", icon="gcp:gke", class_="compute",
                            id=f"gke-{rid}", **N)
                cache = d.box("Memorystore", text="Redis, sessions", icon="gcp:memorystore", class_="data",
                              id=f"cache-{rid}", **N)
            regions.append((gke, cache))
    with d.group("Managed data", id="data", class_="services", direction="down", gap=28):
        spanner = d.box("Cloud Spanner", text="nam-eur-asia1", icon="gcp:cloud-spanner", class_="data db", **N)
        pubsub = d.box("Pub/Sub", text="order events", icon="gcp:pubsub", class_="analytics", **N)
        flow = d.box("Dataflow", text="streaming ETL", icon="gcp:dataflow", class_="analytics", **N)
        bq = d.box("BigQuery", text="warehouse", icon="gcp:bigquery", class_="analytics", **N)

users.to(dns, "resolve")
dns >> lb
armor.to(lb, class_="policy")
for gke, cache in regions:
    lb.to(gke, "HTTPS")
    gke.to(cache, class_="soft")
for gke, _ in regions:
    gke.to(spanner, "SQL", class_="db-edge")
regions[1][0].to(pubsub, "events", class_="async")
pubsub >> flow >> bq

diagram = d

"""A global web application on Google Cloud: one anycast load balancer in front of GKE in two
regions, Spanner for multi-region consistency and a streaming analytics path to BigQuery."""
from spinagram import Diagram


d = Diagram("GCP01", "Global web application on Google Cloud", node_size=(230, 84),
            subtitle="Anycast load balancing · GKE in two regions · Spanner · streaming analytics",
            layout={"engine": "flex", "direction": "right", "gap": 48, "route": "ortho",
                    "area": [56, 176, 1808, 830]})
d.stylesheet("showcase.css")
d.stylesheet("gcp.css")

with d.group("Global edge", id="edge", class_="edge", direction="down", gap=22, padding=16):
    users = d.box("Users", text="worldwide", icon="k8s:user", class_="external")
    dns = d.box("Cloud DNS", text="anycast, DNSSEC", icon="gcp:cloud-dns", class_="networking")
    lb = d.box("Load Balancing", text="global L7 + CDN", icon="gcp:cloud-load-balancing",
               class_="networking global-entry")
    armor = d.box("Cloud Armor", text="WAF, DDoS", icon="gcp:cloud-armor", class_="security")
with d.group("Project · shop-prod", id="project", class_="project", direction="right", gap=56, align="center"):
    with d.group("VPC · shared", id="vpc", class_="vpc", direction="down", gap=28):
        regions = []
        for rid, name in (("us", "us-central1"), ("eu", "europe-west1")):
            with d.group(name, id=f"r-{rid}", class_="region", direction="down", gap=24):
                gke = d.box("GKE Autopilot", text="web + api pods", icon="gcp:gke", class_="compute",
                            id=f"gke-{rid}")
                cache = d.box("Memorystore", text="Redis, sessions", icon="gcp:memorystore", class_="data-store",
                              id=f"cache-{rid}")
            regions.append((gke, cache))
    with d.group("Managed data", id="data", class_="services", direction="down", gap=28):
        spanner = d.box("Cloud Spanner", text="nam-eur-asia1", icon="gcp:cloud-spanner",
                        class_="data-store primary-database")
        pubsub = d.box("Pub/Sub", text="order events", icon="gcp:pubsub", class_="analytics")
        flow = d.box("Dataflow", text="streaming ETL", icon="gcp:dataflow", class_="analytics")
        bq = d.box("BigQuery", text="warehouse", icon="gcp:bigquery", class_="analytics")

users.to(dns, "resolve", step="Users resolve the anycast IP")
dns.to(lb, step="One global L7 load balancer")
armor.to(lb, class_="security-policy")
for gke, cache in regions:
    lb.to(gke, "HTTPS", step="Nearest healthy region serves" if gke.id == "gke-us" else None)
    gke.to(cache, class_="session-cache")
for gke, _ in regions:
    gke.to(spanner, "SQL", class_="database-traffic")
regions[1][0].to(pubsub, "events", class_="event-stream", step="Orders stream to analytics")
pubsub >> flow >> bq
d.callout(bq, "Streaming inserts are queryable in seconds; dashboards read live data.", title="Real-time",
          kind="tip")
d.add_legend()

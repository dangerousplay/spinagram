"""Icons from twelve packs and a local file. An icon is just `icon="pack:name"` or a path next to the spec;
packs download on first use. Find names with `spinagram icons search <word>`."""
from spinagram import Diagram

d = Diagram("I01", "One argument, thousands of icons", subtitle='icon="pack:name" or icon="file.svg"',
            layout={"engine": "flex", "direction": "down", "gap": 24})
d.stylesheet("icons.css")

GROUPS = {
    "Cloud": [("EKS", "aws:eks"), ("BigQuery", "gcp:bigquery"), ("AKS", "azure:aks"), ("Compute", "oci:vm")],
    "Cloud native": [("Pod", "k8s:pod"), ("Cilium", "cncf:cilium"), ("Argo", "cncf:argo"),
                     ("OpenTelemetry", "cncf:otel")],
    "Languages and data": [("Rust", "devicon:rust"), ("Python", "terrastruct:python"),
                           ("PostgreSQL", "devicon:postgresql"), ("Kafka", "devicon:kafka")],
    "Products": [("Terraform", "logos:terraform"), ("GitHub Actions", "logos:github-actions"),
                 ("Datadog", "logos:datadog"), ("Anthropic", "logos:anthropic")],
    "Self-hosted": [("Proxmox", "selfhosted:proxmox"), ("Grafana", "selfhosted:grafana"),
                    ("Home Assistant", "selfhosted:hass"), ("OpenStack", "openstack:nova")],
    "Network and yours": [("Firewall", "network:firewall"), ("L3 switch", "network:l3-switch"),
                          ("Access point", "network:ap"), ("Your logo", "acme.svg")],
}
with d.group(id="grid", class_="bare", columns=3, gap=20, padding=0):
    for name, items in GROUPS.items():
        with d.group(name, class_=name.lower().replace(" ", "-"), columns=2, gap=12, padding=14):
            for title, icon in items:
                d.box(title, text=icon, icon=icon, w=262, h=78)

diagram = d

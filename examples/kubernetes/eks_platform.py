"""A Kubernetes platform on Amazon EKS: Cilium as the eBPF CNI and Gateway API implementation, Karpenter for
nodes, Argo CD for GitOps, cert-manager and ExternalDNS for TLS and DNS, Hubble and Prometheus for visibility."""
from spinagram import Diagram

N = {"w": 230, "h": 84}

d = Diagram("EKS01", "Kubernetes platform on Amazon EKS",
            subtitle="Cilium · Gateway API · Karpenter · Argo CD · cert-manager · ExternalDNS",
            layout={"engine": "flex", "direction": "right", "gap": 28, "route": "ortho",
                    "area": [56, 176, 1808, 840]})
d.stylesheet("../showcase/showcase.css")
d.stylesheet("eks.css")

with d.group(id="outside", class_="bare", direction="down", gap=220):
    users = d.box("Users", text="browsers, apps", icon="aws:users", class_="external", w=200, h=84)
    git = d.box("GitHub", text="platform repo", icon="logos:github", class_="external", w=200, h=84)

with d.group("AWS · eu-west-1", id="region", style="aws-region", direction="right", gap=24, padding=16):
    with d.group("EKS cluster · shop-prod", id="cluster", class_="cluster", direction="down", gap=12, padding=14):
        with d.group("Networking", id="net", class_="lane", direction="right", gap=10):
            gw = d.box("Gateway", text="Gateway API on Envoy", icon="cncf:envoy", class_="gateway", **N)
            certs = d.box("cert-manager", text="Let's Encrypt TLS", icon="cncf:cert-manager",
                          class_="addon", **N)
            cilium = d.box("Cilium", text="eBPF, no kube-proxy", icon="cncf:cilium", class_="cilium", **N)
            xdns = d.box("ExternalDNS", text="writes records", icon="k8s:crd", class_="addon", **N)
        with d.group("namespace: shop", id="ns-shop", class_="lane ns", direction="right", gap=10):
            route = d.box("HTTPRoute", text="/api and /web", icon="k8s:crd", class_="gateway", **N)
            svc = d.box("Service", text="ClusterIP", icon="k8s:svc", class_="workload", **N)
            pods = d.box("Shop", text="6 pods", icon="k8s:pod", class_="workload", **N)
        with d.group("Platform", id="platform", class_="lane", direction="right", gap=10):
            argo = d.box("Argo CD", text="GitOps sync", icon="cncf:argo", class_="addon", **N)
            karp = d.box("Karpenter", text="right-sized nodes", icon="aws:amazon-ec2-auto-scaling",
                         class_="addon", **N)
            hubble = d.box("Hubble", text="flows, service map", icon="cncf:cilium", class_="cilium", **N)
            prom = d.box("Prometheus", text="and Grafana", icon="cncf:prometheus", class_="addon", **N)
    with d.group("Managed services", id="aws", class_="services", direction="down", gap=40):
        dns = d.box("Route 53", text="public zone", icon="aws:route53", class_="aws-svc", **N)
        db = d.box("Aurora", text="PostgreSQL", icon="aws:amazon-aurora", class_="aws-svc", **N)
        ecr = d.box("ECR", text="signed images", icon="aws:elastic-container-registry", class_="aws-svc", **N)

users.to(gw, "HTTPS via NLB")
gw.to(route, "routes")
route >> svc >> pods
pods.to(db, "SQL")
certs.to(gw, class_="control")
xdns.to(dns, "records", class_="control")
git.to(argo, "sync", class_="control")

d.add_legend({".gateway": "Gateway API", ".cilium": "Cilium", ".addon": "Platform add-on",
              ".workload": "Workload", ".aws-svc": "AWS service", "edge.control": "Control or sync"},
             position="bottom")

diagram = d

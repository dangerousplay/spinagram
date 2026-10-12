"""Kubernetes service networking: how a request reaches a pod on another node, with the per-node
agents that program the data path and the policy that guards it."""
from spinagram import Diagram

N = {"w": 226, "h": 84}
WIDE = {"w": 252, "h": 84}
POD = {"w": 186, "h": 64}

d = Diagram("K8S02", "Kubernetes service networking",
            subtitle="Ingress → Service → EndpointSlice → pods on any node, guarded by NetworkPolicy",
            layout={"engine": "flex", "direction": "right", "gap": 44, "route": "ortho",
                    "area": [56, 176, 1808, 830]})
d.stylesheet("showcase.css")
d.stylesheet("k8s.css")

client = d.box("Client", text="api.example.com", icon="k8s:user", class_="client", **N)
with d.group("Cluster · pod CIDR 10.244.0.0/16", id="cluster", class_="cluster", direction="right", gap=48,
             align="center"):
    with d.group(id="front", class_="bare", direction="down", gap=36):
        ing = d.box("Ingress", text="NGINX controller", icon="k8s:ing", class_="net", **WIDE)
        svc = d.box("Service api", text="VIP 10.96.0.12", icon="k8s:svc", class_="net vip", **WIDE)
        ep = d.box("EndpointSlice", text="3 ready endpoints", icon="k8s:ep", class_="net", **WIDE)
        pol = d.box("NetworkPolicy", text="only ingress → api", icon="k8s:netpol", class_="policy", **WIDE)
    with d.group(id="nodes", class_="bare", direction="down", gap=28):
        nodes = []
        for name, cidr, pods in (("node-a", "10.244.1.0/24", ("api-5c-x", "api-5c-y")),
                                 ("node-b", "10.244.2.0/24", ("api-5c-z", "web-9f-k"))):
            with d.group(f"{name} · {cidr}", id=name, class_="worker", direction="right", gap=24):
                with d.group(id=f"{name}-agents", class_="bare", direction="down", gap=14):
                    kubelet = d.box("kubelet", text="CRI, probes", icon="k8s:kubelet-labeled",
                                    class_="cp-part", id=f"{name}-kubelet", **N)
                    proxy = d.box("kube-proxy", text="IPVS rules", icon="k8s:k-proxy-labeled",
                                  class_="cp-part", id=f"{name}-proxy", **N)
                with d.group("pods", id=f"{name}-pods", class_="pods", direction="down", gap=12):
                    ps = [d.box(p, text="denied" if p.startswith("web") else "10.244." + cidr.split(".")[2] + f".{i + 10}", icon="k8s:pod",
                                class_="pod" + (" blocked" if p.startswith("web") else ""), id=p, **POD)
                          for i, p in enumerate(pods)]
            nodes.append((proxy, ps))

client.to(ing, "HTTPS")
ing >> svc
svc.to(ep, "selects app=api")
for proxy, ps in nodes:
    ep.to(proxy, "watch", class_="control")
    for p in ps:
        if not p.id.startswith("web"):
            proxy.to(p, "DNAT")

diagram = d

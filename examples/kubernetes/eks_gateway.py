"""Gateway API on EKS with Cilium: the AWS NLB hands traffic to Cilium's Gateway, an HTTPRoute decides the
backend (shown as a flowchart region), and a Cilium network policy lets only the Gateway reach the pods."""
from spinagram import Diagram

N = {"w": 230, "h": 84}

d = Diagram("EKS02", "Gateway API routing with Cilium",
            subtitle="Architecture and the HTTPRoute's rules as a flowchart, on one slide",
            layout={"engine": "flex", "direction": "down", "gap": 30, "route": "ortho",
                    "area": [56, 176, 1808, 840]})
d.stylesheet("../showcase/showcase.css")
d.stylesheet("eks.css")

with d.group(id="edge", class_="bare", direction="right", gap=60):
    nlb = d.box("NLB", text="AWS LB Controller", icon="aws:nlb", class_="aws-svc", **N)
    dns = d.box("Route 53", text="shop.example.com", icon="aws:route53", class_="aws-svc", **N)

with d.group("EKS cluster · shop-prod", id="cluster", class_="cluster", direction="right", gap=26, padding=16):
    with d.group("Gateway API", id="gwapi", class_="lane", direction="down", gap=18):
        gwc = d.box("GatewayClass", text="io.cilium/gateway", icon="cncf:cilium", class_="cilium", **N)
        gw = d.box("Gateway", text=":443, TLS by cert-manager", icon="cncf:envoy", class_="gateway", id="gateway", **N)
        route = d.box("HTTPRoute", text="shop-route", icon="k8s:crd", class_="gateway", **N)

    with d.flowchart("HTTPRoute rules", id="rules", class_="flow", direction="right") as fc:
        req = fc.start("Request")
        api = fc.decision("/api/*?")
        canary = fc.decision("x-canary?")
        v2 = fc.process("api v2")
        v1 = fc.process("api v1")
        web = fc.process("web")
        req >> api
        api.yes(canary)
        api.no(web)
        canary.yes(v2)
        canary.no(v1)

    with d.group("namespace: shop", id="ns-shop", class_="lane ns", direction="down", gap=18):
        svc2 = d.box("api-v2", text="Service · 10 %", icon="k8s:svc", class_="workload", **N)
        svc1 = d.box("api-v1", text="Service · 90 %", icon="k8s:svc", class_="workload", **N)
        svcw = d.box("web", text="Service", icon="k8s:svc", class_="workload", **N)
        pol = d.box("Policy", text="Gateway only; Hubble logs drops", icon="k8s:netpol", class_="cilium", **N)

dns.to(nlb, "alias", class_="control")
nlb.to(gw, "TCP :443")
gwc >> gw >> route
route.to(req, "evaluates", class_="link")
v2.to(svc2, class_="link")
v1.to(svc1, class_="link")
web.to(svcw, class_="link")

diagram = d
